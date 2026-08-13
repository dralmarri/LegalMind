#!/bin/bash
# استئناف الحذف النهائي بعد انقطاع الاتصال — يعمل في الخلفية فلا يتأثر بانقطاع المحطة
set -e
BK=/root/old-system-final-backup-20260813

echo "===== التحقق من النسخ الاحتياطية أولاً ====="
[ -s "$BK/legalmind.dump" ] || { echo "نسخة legalmind غير موجودة — لن أكمل الحذف!"; exit 1; }
ls -lh "$BK/"
echo "النسخ سليمة ✓"

cat > /root/delete_resume.sh <<'EOF'
#!/bin/bash
echo "== إصلاح حالة مدير الحزم بعد الانقطاع =="
for i in $(seq 1 30); do
  if fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; then
    echo "قفل الحزم مشغول — انتظار ($i)"; sleep 10
  else
    break
  fi
done
dpkg --configure -a 2>&1 | tail -3

echo "== إكمال إزالة بوستغرس المضيف =="
systemctl stop postgresql 2>/dev/null
systemctl disable postgresql 2>/dev/null
apt-get purge -y 'postgresql*' 2>&1 | tail -3
apt-get autoremove -y 2>&1 | tail -2
rm -rf /var/lib/postgresql /etc/postgresql /var/log/postgresql
echo "أُزيل بوستغرس المضيف ✓"

echo "== حذف ملفات النظام القديم =="
for d in /opt/legalmind-api /var/www/legalmind; do
  if [ -d "$d" ]; then
    du -sh "$d"; rm -rf "$d"; echo "حُذف: $d ✓"
  else
    echo "$d غير موجود (حُذف مسبقاً) ✓"
  fi
done
for u in $(systemctl list-unit-files --no-legend 2>/dev/null | awk '{print $1}' | grep -E '^legalmind-api' ); do
  systemctl stop "$u" 2>/dev/null; systemctl disable "$u" 2>/dev/null
  rm -f "/etc/systemd/system/$u"; echo "أُزيلت الخدمة: $u"
done
systemctl daemon-reload

echo "== سلامة النظام الحالي =="
systemctl is-active legalmind-admin legalmind-ingest docker
docker ps --format '{{.Names}} | {{.Status}}' | grep -Ei 'legalmind|qdrant'
curl -s -o /dev/null -w "لوحة الإدارة محلياً: %{http_code}\n" http://127.0.0.1:8088/

echo "== المساحة بعد =="
df -h / | tail -1
echo "===== اكتمل الحذف النهائي ====="
EOF
chmod +x /root/delete_resume.sh
nohup /root/delete_resume.sh > /root/delete-resume.log 2>&1 &
echo "انطلق الاستئناف في الخلفية — لن يتأثر بانقطاع المحطة"
echo "تابع بعد ~3 دقائق: tail -30 /root/delete-resume.log"
