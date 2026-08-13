#!/bin/bash
# فحص للقراءة فقط: إعدادات nginx والشهادات قبل تحويل soutaladalah.com للنظام الحالي
set -e
echo "===== ملفات المواقع المفعلة ====="
ls -la /etc/nginx/sites-enabled/

echo ""
echo "===== محتوى كل ملف (بلا تعليقات) ====="
for f in /etc/nginx/sites-enabled/*; do
  echo ""
  echo "########## $f ##########"
  grep -vE '^\s*#' "$f" | grep -vE '^\s*$'
done

echo ""
echo "===== الشهادات ====="
certbot certificates 2>/dev/null || ls -la /etc/letsencrypt/live/ 2>/dev/null || echo "لا يوجد certbot/letsencrypt ظاهر"

echo ""
echo "===== الحالة الحية ====="
curl -sk -o /dev/null -w "https://soutaladalah.com → %{http_code} (إعادة توجيه إلى: %{redirect_url})\n" https://soutaladalah.com/ || true
curl -sk -o /dev/null -w "https://www.soutaladalah.com → %{http_code} (إعادة توجيه إلى: %{redirect_url})\n" https://www.soutaladalah.com/ || true
curl -sk -o /dev/null -w "https://admin.soutaladalah.com → %{http_code}\n" https://admin.soutaladalah.com/ || true

echo ""
echo "===== واجهة النظام الحالي ====="
ls -d /var/www/legalmind-v3 && du -sh /var/www/legalmind-v3
echo "===== انتهى الفحص ====="
