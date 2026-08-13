#!/bin/bash
# تحويل الدومين الرئيسي soutaladalah.com لخدمة النظام مباشرة + admin يتحول إليه + إزالة إعداد app
set -e
BK=/root/nginx-backup-switch-20260813
mkdir -p "$BK"
cp -a /etc/nginx/sites-available/legalmind /etc/nginx/sites-available/legalmind-admin "$BK/" 2>/dev/null || true
cp -a /etc/nginx/sites-available/legalmind-app "$BK/" 2>/dev/null || true
echo "نسخة احتياطية من الإعدادات في: $BK"

cat > /etc/nginx/sites-available/legalmind <<'EOF'
server {
    server_name soutaladalah.com www.soutaladalah.com;
    client_max_body_size 512m;
    auth_basic "LegalMind";
    auth_basic_user_file /etc/nginx/.htpasswd-legalmind;
    root /var/www/legalmind-v3;
    index index.html;
    location = /ingest-center { proxy_pass http://127.0.0.1:8088; proxy_set_header Host $host; }
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
    ssl_certificate /etc/letsencrypt/live/soutaladalah.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/soutaladalah.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}
server {
    listen 80;
    listen [::]:80;
    server_name soutaladalah.com www.soutaladalah.com;
    return 301 https://soutaladalah.com$request_uri;
}
EOF

cat > /etc/nginx/sites-available/legalmind-admin <<'EOF'
server {
    server_name admin.soutaladalah.com;
    listen 443 ssl;
    listen [::]:443 ssl;
    ssl_certificate /etc/letsencrypt/live/admin.soutaladalah.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/admin.soutaladalah.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    return 301 https://soutaladalah.com$request_uri;
}
server {
    listen 80;
    listen [::]:80;
    server_name admin.soutaladalah.com;
    return 301 https://soutaladalah.com$request_uri;
}
EOF

rm -f /etc/nginx/sites-enabled/legalmind-app /etc/nginx/sites-available/legalmind-app

if nginx -t; then
    systemctl reload nginx
    echo "أُعيد تحميل nginx ✓"
    certbot delete --cert-name app.soutaladalah.com --non-interactive 2>/dev/null && \
        echo "أُزيلت شهادة app المنسية ✓" || echo "شهادة app لم تُزل (غير مؤثر)"
    echo ""
    echo "===== الفحوص الحية ====="
    curl -sk -o /dev/null -w "https://soutaladalah.com → %{http_code} (المطلوب 401 لوجود كلمة السر)\n" https://soutaladalah.com/
    curl -sk -o /dev/null -w "https://www.soutaladalah.com → %{http_code}\n" https://www.soutaladalah.com/
    curl -sk -o /dev/null -w "https://admin.soutaladalah.com → %{http_code} إلى %{redirect_url} (المطلوب 301 إلى الرئيسي)\n" https://admin.soutaladalah.com/
    curl -sk -o /dev/null -w "http://soutaladalah.com → %{http_code} إلى %{redirect_url}\n" http://soutaladalah.com/
    echo ""
    echo "===== اكتمل التحويل: النظام يعمل الآن على soutaladalah.com مباشرة ====="
else
    echo "فشل اختبار nginx — استرجاع الوضع السابق فوراً"
    cp -a "$BK/legalmind" "$BK/legalmind-admin" /etc/nginx/sites-available/
    [ -f "$BK/legalmind-app" ] && cp -a "$BK/legalmind-app" /etc/nginx/sites-available/ && \
        ln -sf /etc/nginx/sites-available/legalmind-app /etc/nginx/sites-enabled/legalmind-app
    nginx -t && systemctl reload nginx
    echo "استُرجع الوضع السابق — لم يتغير شيء"
    exit 1
fi
