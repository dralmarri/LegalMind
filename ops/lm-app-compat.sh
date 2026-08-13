#!/bin/bash
# إعادة admin.soutaladalah.com للخدمة الكاملة (بدل التحويلة) حتى يعمل تطبيق iOS دون تعديل
set -e
cp -a /etc/nginx/sites-available/legalmind-admin /root/nginx-backup-switch-20260813/legalmind-admin.redirect 2>/dev/null || true

cat > /etc/nginx/sites-available/legalmind-admin <<'EOF'
server {
    server_name admin.soutaladalah.com;
    client_max_body_size 512m;
    auth_basic "LegalMind";
    auth_basic_user_file /etc/nginx/.htpasswd-legalmind;
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
    ssl_certificate /etc/letsencrypt/live/admin.soutaladalah.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/admin.soutaladalah.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}
server {
    listen 80;
    listen [::]:80;
    server_name admin.soutaladalah.com;
    return 301 https://admin.soutaladalah.com$request_uri;
}
EOF

nginx -t && systemctl restart nginx
sleep 2
echo "===== الفحوص ====="
curl -sk -o /dev/null -w "الرئيسي soutaladalah.com → %{http_code} (401 = سليم)\n" https://soutaladalah.com/
curl -sk -o /dev/null -w "admin.soutaladalah.com → %{http_code} (401 = سليم، يخدم النظام مجدداً)\n" https://admin.soutaladalah.com/
echo "===== تم — جرّب التطبيق الآن ====="
