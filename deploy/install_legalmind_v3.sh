#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/LegalMind}
DOMAIN=${DOMAIN:-admin.soutaladalah.com}
WEB_ROOT=${WEB_ROOT:-/var/www/legalmind-v3}
ADMIN_PASSWORD_FILE=${ADMIN_PASSWORD_FILE:-/root/legalmind-admin-password.txt}
HTPASSWD_FILE=${HTPASSWD_FILE:-/etc/nginx/.htpasswd-legalmind}

if [[ $EUID -ne 0 ]]; then
  echo "Run as root" >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs npm nginx apache2-utils

cd "$APP_DIR/web"
npm install
npm run build

test -f "$APP_DIR/web/out/index.html"
rm -rf "$WEB_ROOT"
mkdir -p "$WEB_ROOT"
cp -a "$APP_DIR/web/out/." "$WEB_ROOT/"
chown -R www-data:www-data "$WEB_ROOT"

if [[ ! -s "$ADMIN_PASSWORD_FILE" ]]; then
  echo "Admin password file missing: $ADMIN_PASSWORD_FILE" >&2
  exit 1
fi
htpasswd -bc "$HTPASSWD_FILE" admin "$(cat "$ADMIN_PASSWORD_FILE")"
chmod 640 "$HTPASSWD_FILE"
chown root:www-data "$HTPASSWD_FILE"

CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
if [[ -f "$CERT_DIR/fullchain.pem" && -f "$CERT_DIR/privkey.pem" ]]; then
cat > /etc/nginx/sites-available/legalmind-admin <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate ${CERT_DIR}/fullchain.pem;
    ssl_certificate_key ${CERT_DIR}/privkey.pem;

    client_max_body_size 100m;
    auth_basic "LegalMind";
    auth_basic_user_file ${HTPASSWD_FILE};

    root ${WEB_ROOT};
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8088;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300;
    }

    location = /health {
        proxy_pass http://127.0.0.1:8088/health;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
else
cat > /etc/nginx/sites-available/legalmind-admin <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    client_max_body_size 100m;
    auth_basic "LegalMind";
    auth_basic_user_file ${HTPASSWD_FILE};

    root ${WEB_ROOT};
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8088;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300;
    }

    location = /health {
        proxy_pass http://127.0.0.1:8088/health;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
fi

ln -sfn /etc/nginx/sites-available/legalmind-admin /etc/nginx/sites-enabled/legalmind-admin
nginx -t
systemctl reload nginx
systemctl restart legalmind-admin.service

READY=0
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8088/health >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [[ "$READY" -ne 1 ]]; then
  echo "LegalMind Admin API did not become ready" >&2
  systemctl status legalmind-admin.service --no-pager >&2 || true
  journalctl -u legalmind-admin.service -n 100 --no-pager >&2 || true
  exit 1
fi

curl -fsS -u "admin:$(cat "$ADMIN_PASSWORD_FILE")" -H "Host: ${DOMAIN}" http://127.0.0.1/ >/dev/null

echo "LegalMind 3 deployed successfully"
echo "URL: https://${DOMAIN}"
echo "Username: admin"
echo "Password file: ${ADMIN_PASSWORD_FILE}"
