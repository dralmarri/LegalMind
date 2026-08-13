#!/bin/bash
# تفعيل كلمة السر على app.soutaladalah.com (اختبار قدرة التطبيق على التعامل معها)
set -e
sed -i 's|root /var/www/legalmind-v3;|auth_basic "LegalMind";\n    auth_basic_user_file /etc/nginx/.htpasswd-legalmind;\n    root /var/www/legalmind-v3;|' /etc/nginx/sites-available/legalmind-app
nginx -t && systemctl restart nginx
sleep 2
curl -sk -o /dev/null -w "app → %{http_code} (401 = الحماية مفعلة)\n" https://app.soutaladalah.com/
echo "الآن أغلق التطبيق تماماً وافتحه — إن ظهرت نافذة كلمة السر أدخل بياناتك المعتادة وانتهينا"
echo "وإن ظهرت شاشة بيضاء، شغّل سطر الإرجاع"
