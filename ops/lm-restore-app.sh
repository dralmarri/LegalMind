#!/bin/bash
# استعادة app.soutaladalah.com (مدخل تطبيق iOS) بعد إعادة سجل DNS في GoDaddy
set -e
echo "== انتظار انتشار سجل DNS =="
OK=""
for i in $(seq 1 20); do
  IP=$(dig +short app.soutaladalah.com @8.8.8.8 2>/dev/null | tail -1)
  if [ "$IP" = "72.61.237.80" ]; then OK=1; echo "DNS جاهز ✓"; break; fi
  echo "  لم ينتشر بعد (محاولة $i/20) — انتظار 20 ثانية"
  sleep 20
done
[ -n "$OK" ] || { echo "سجل DNS لم يظهر بعد — تأكد من إضافته في GoDaddy (A | app | 72.61.237.80) ثم أعد تشغيل هذا السطر"; exit 1; }

echo ""
echo "== إعداد مؤقت لإصدار الشهادة =="
cat > /etc/nginx/sites-available/legalmind-app <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name app.soutaladalah.com;
    root /var/www/legalmind-v3;
}
EOF
ln -sf /etc/nginx/sites-available/legalmind-app /etc/nginx/sites-enabled/legalmind-app
nginx -t && systemctl reload nginx
certbot certonly --nginx -d app.soutaladalah.com --non-interactive --agree-tos -m dralmarri@gmail.com
echo "الشهادة صدرت ✓"

echo ""
echo "== الإعداد الكامل كما كان =="
cat > /etc/nginx/sites-available/legalmind-app <<'EOF'
server {
    server_name app.soutaladalah.com;
    client_max_body_size 512m;
    root /var/www/legalmind-v3;
    index index.html;
    location /api/ {
        proxy_pass http://127.0.0.1:8088;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 1200;
    }
    location = /health {
        proxy_pass http://127.0.0.1:8088/health;
    }
    location / {
        try_files $uri $uri/ /index.html;
    }
    listen 443 ssl;
    listen [::]:443 ssl;
    ssl_certificate /etc/letsencrypt/live/app.soutaladalah.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.soutaladalah.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}
server {
    listen 80;
    listen [::]:80;
    server_name app.soutaladalah.com;
    return 301 https://app.soutaladalah.com$request_uri;
}
EOF
nginx -t && systemctl reload nginx

echo ""
echo "===== الفحوص ====="
curl -sk -o /dev/null -w "https://app.soutaladalah.com → %{http_code} (200 = التطبيق سيعمل)\n" https://app.soutaladalah.com/
curl -sk -o /dev/null -w "https://soutaladalah.com → %{http_code} (401 = الرئيسي محمي كما هو)\n" https://soutaladalah.com/
echo "===== تم — أغلق التطبيق تماماً وافتحه من جديد ====="
