#!/bin/bash
# قناة التشغيل الآلي: سحب أوامر الصيانة من مستودع الإدارة كل 5 دقائق ونشر النتائج
set -e
QDIR=/opt/legalmind-autopilot
mkdir -p "$QDIR"

TOKEN=$(tr -dc a-z0-9 < /dev/urandom | head -c 20)
echo "$TOKEN" > "$QDIR/token"
chmod 600 "$QDIR/token"

cat > "$QDIR/pull.sh" <<'EOF'
#!/bin/bash
# ينفذ أمر الصيانة الجديد (إن تغير) وينشر مخرجاته
QDIR=/opt/legalmind-autopilot
TOKEN=$(cat "$QDIR/token")
URL="https://raw.githubusercontent.com/dralmarri/LegalMind/main/ops/autorun/queue.sh"
NEW=$(curl -fsSL "$URL" 2>/dev/null) || exit 0
[ -n "$NEW" ] || exit 0
SUM=$(printf '%s' "$NEW" | sha256sum | cut -d' ' -f1)
LAST=$(cat "$QDIR/last-sha" 2>/dev/null || true)
[ "$SUM" = "$LAST" ] && exit 0
echo "$SUM" > "$QDIR/last-sha"
OUT="/var/www/legalmind-v3/status-$TOKEN.txt"
{
  echo "== تنفيذ آلي: $(date -u +%FT%TZ) | sha: ${SUM:0:12} =="
  printf '%s' "$NEW" | timeout 3300 bash 2>&1 | tail -n 500
  echo "== انتهى التنفيذ =="
} > "$OUT.tmp" 2>&1 && mv "$OUT.tmp" "$OUT"
EOF
chmod 700 "$QDIR/pull.sh"

cat > "$QDIR/pushlog.sh" <<'EOF'
#!/bin/bash
# ينشر سجل المراجعة الجارية ليُتابع عن بعد
QDIR=/opt/legalmind-autopilot
TOKEN=$(cat "$QDIR/token")
for f in auto-review-all auto-review; do
  [ -f "/root/$f.log" ] && cp -f "/root/$f.log" "/var/www/legalmind-v3/review-$TOKEN.txt"
done
exit 0
EOF
chmod 700 "$QDIR/pushlog.sh"

cat > /etc/cron.d/legalmind-autopilot <<EOF
*/5 * * * * root /opt/legalmind-autopilot/pull.sh >/dev/null 2>&1
*/5 * * * * root /opt/legalmind-autopilot/pushlog.sh >/dev/null 2>&1
EOF
chmod 644 /etc/cron.d/legalmind-autopilot

"$QDIR/pushlog.sh"
echo "قناة التشغيل الآلي جاهزة ✓"
echo ""
echo "STATUS_URL=https://app.soutaladalah.com/status-$TOKEN.txt"
echo "REVIEW_URL=https://app.soutaladalah.com/review-$TOKEN.txt"
echo ""
echo "لإيقاف القناة نهائياً في أي وقت: rm -f /etc/cron.d/legalmind-autopilot"
