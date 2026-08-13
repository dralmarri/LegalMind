#!/bin/bash
# إرجاع مدخل app بلا كلمة سر (إن عجز التطبيق عن التعامل معها)
set -e
sed -i '/auth_basic "LegalMind";/d;/auth_basic_user_file \/etc\/nginx\/.htpasswd-legalmind;/d' /etc/nginx/sites-available/legalmind-app
nginx -t && systemctl restart nginx
sleep 2
curl -sk -o /dev/null -w "app → %{http_code} (200 = عاد كما كان)\n" https://app.soutaladalah.com/
echo "أغلق التطبيق تماماً وافتحه — سيعود للعمل"
