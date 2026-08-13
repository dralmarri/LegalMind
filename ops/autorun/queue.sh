#!/bin/bash
# أمر آلي 1: مشرف يرافق المراجعة الشاملة حتى تمامها ثم ينشر التقرير الختامي
if [ -f /root/.autorun-supervisor-lock ]; then
  echo "المشرف يعمل مسبقاً — لا حاجة لإطلاق آخر"
  exit 0
fi
touch /root/.autorun-supervisor-lock

# تحسين ناشر السجل: يفضّل التقرير الختامي إن وُجد
cat > /opt/legalmind-autopilot/pushlog.sh <<'EOF'
#!/bin/bash
QDIR=/opt/legalmind-autopilot
TOKEN=$(cat "$QDIR/token")
if [ -f /root/review-final.txt ]; then
  cp -f /root/review-final.txt "/var/www/legalmind-v3/review-$TOKEN.txt"
elif [ -f /root/auto-review-all.log ]; then
  cp -f /root/auto-review-all.log "/var/www/legalmind-v3/review-$TOKEN.txt"
fi
exit 0
EOF
chmod 700 /opt/legalmind-autopilot/pushlog.sh

cat > /root/supervisor.sh <<'EOS'
#!/bin/bash
exec > /root/supervisor.log 2>&1
echo "== مشرف المراجعة انطلق: $(date -u +%F' '%T) UTC =="
for i in $(seq 1 480); do
  pgrep -f "python /root/auto_review_all.py" > /dev/null || break
  sleep 30
done
echo "الجولة الأولى انتهت: $(date -u +%F' '%T) UTC"
set -a; source /opt/LegalMind/deploy/.env; set +a
PEND=$(docker exec legalmind-postgres psql -U legalmind -d legalmind -Atc \
  "SELECT count(*) FROM knowledge_objects WHERE verification_status='machine_pending_human' AND coalesce(metadata->>'human_edited','')<>'true';")
echo "معلق بعد الجولة الأولى: $PEND"
if [ "${PEND:-0}" -gt 0 ] 2>/dev/null; then
  echo "جولة ثانية للمتبقي..."
  /opt/LegalMind/.venv/bin/python /root/auto_review_all.py >> /root/auto-review-all.log 2>&1
fi
{
  echo "==== التقرير الختامي للمراجعة الشاملة — $(date -u +%F' '%T) UTC ===="
  echo ""
  echo "-- توزيع حالات التوثيق في كامل القاعدة --"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
    "SELECT verification_status, count(*) FROM knowledge_objects GROUP BY 1 ORDER BY 2 DESC;"
  echo "-- الدفعات التي بقي فيها معلق (فارغ = اكتمل كل شيء) --"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
    "SELECT metadata->>'batch_id' AS batch,
            count(*) FILTER (WHERE verification_status='machine_pending_human') AS pending,
            count(*) AS total
     FROM knowledge_objects GROUP BY 1
     HAVING count(*) FILTER (WHERE verification_status='machine_pending_human') > 0
     ORDER BY 2 DESC LIMIT 15;"
  echo ""
  echo "-- آخر سطور سجل المراجعة --"
  tail -35 /root/auto-review-all.log
} > /root/review-final.txt
cp -f /root/review-final.txt "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
rm -f /root/.autorun-supervisor-lock
echo "== انتهى المشرف ونُشر التقرير: $(date -u +%F' '%T) UTC =="
EOS
chmod +x /root/supervisor.sh
nohup /root/supervisor.sh > /dev/null 2>&1 &
echo "انطلق مشرف المراجعة في الخلفية ✓"
