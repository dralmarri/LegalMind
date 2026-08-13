#!/bin/bash
# إنهاء عملية apt المعلقة على سؤال debconf ميت، ثم إصلاح dpkg وإكمال إزالة حزم بوستغرس
set -e
echo "== إنهاء عملية الإزالة المعلقة =="
pkill -f "apt-get purge -y postgresql" 2>/dev/null || true
sleep 5
pkill -9 -f "apt-get purge -y postgresql" 2>/dev/null || true
pkill -9 -f "dpkg --status-fd" 2>/dev/null || true
pkill -9 -f "postgresql-16.postrm" 2>/dev/null || true
sleep 3
if ps aux | grep -E 'apt-get purge|dpkg --status-fd' | grep -v grep; then
  echo "ما زالت عمليات حية — أعد تشغيل السطر بعد دقيقة"; exit 1
fi
echo "لا عمليات حزم معلقة ✓"

echo ""
echo "== إصلاح حالة الحزم وإكمال الإزالة (بلا أسئلة) =="
export DEBIAN_FRONTEND=noninteractive
dpkg --configure -a 2>&1 | tail -5
apt-get purge -y 'postgresql*' 2>&1 | tail -5
apt-get autoremove -y 2>&1 | tail -2
rm -rf /var/lib/postgresql /etc/postgresql /var/log/postgresql

echo ""
echo "== ما تبقى من حزم بوستغرس =="
dpkg -l 2>/dev/null | grep -i postgres || echo "لا شيء — أُزيلت كلها ✓"

echo ""
echo "== سلامة النظام الحالي =="
systemctl is-active legalmind-admin legalmind-ingest docker nginx
docker ps --format '{{.Names}} | {{.Status}}' | grep -Ei 'legalmind|qdrant'
curl -s -o /dev/null -w "لوحة الإدارة محلياً: %{http_code}\n" http://127.0.0.1:8088/ || true

echo ""
echo "== المساحة النهائية =="
df -h / | tail -1
echo "===== اكتمل التنظيف النهائي ====="
