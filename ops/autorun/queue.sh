#!/bin/bash
# أمر آلي 70: كشف خط الفهرسة الآلي وإيقافه مؤقتاً قبل رفع الملفات عبر النظام
set -a; source /opt/LegalMind/deploy/.env; set +a

echo "== خدمات systemd ذات الصلة =="
systemctl list-units --all --no-pager 2>/dev/null | grep -iE 'legal|ingest|watch|inbox' || echo "(لا شيء)"
echo ""
echo "== كرون =="
ls -la /etc/cron.d/ 2>/dev/null
crontab -l 2>/dev/null | head -20
echo ""
echo "== عمليات تعمل الآن =="
ps aux | grep -iE 'watch|ingest|legalmind' | grep -v grep | head -10
echo ""
echo "== مسار صندوق الوارد في التطبيق =="
grep -nE 'inbox|INBOX|upload_dir|UPLOAD|save.*file|/data/' /opt/LegalMind/admin/app.py 2>/dev/null | head -12
grep -rnE 'inbox' /opt/LegalMind/deploy/ 2>/dev/null | head -8
echo ""
echo "== محتوى مجلدات البيانات =="
for d in /opt/LegalMind/data /opt/LegalMind/inbox /opt/LegalMind/data/inbox; do
  [ -d "$d" ] && echo "[$d]" && ls -la "$d" | head -10
done
echo ""
echo "== الإيقاف المؤقت =="
STOPPED=""
for u in $(systemctl list-units --all --no-pager --plain 2>/dev/null | grep -iE 'legal' | awk '{print $1}' | grep -iE 'watch|ingest|inbox|reader'); do
  systemctl stop "$u" && systemctl disable "$u" 2>/dev/null && STOPPED="$STOPPED $u" && echo "أُوقف: $u"
done
[ -z "$STOPPED" ] && echo "(لم توقف خدمة systemd — إن كان الخط يعمل بالكرون سأوقفه في الأمر التالي بعد رؤية النتائج)"
echo "===== اكتمل الأمر 70 ====="
