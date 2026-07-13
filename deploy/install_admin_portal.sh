#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/LegalMind}
DOMAIN=${DOMAIN:-admin.soutaladalah.com}

if [[ $EUID -ne 0 ]]; then
  echo "Run as root" >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y nginx python3-venv openssl

cd "$APP_DIR"
python3 -m venv admin/.venv
admin/.venv/bin/pip install --upgrade pip
admin/.venv/bin/pip install -r admin/requirements.txt

set -a
source deploy/.env
set +a

ADMIN_PASSWORD_FILE=/root/legalmind-admin-password.txt
if [[ ! -f "$ADMIN_PASSWORD_FILE" ]]; then
  openssl rand -hex 16 > "$ADMIN_PASSWORD_FILE"
  chmod 600 "$ADMIN_PASSWORD_FILE"
fi
ADMIN_PASSWORD=$(cat "$ADMIN_PASSWORD_FILE")

cat > deploy/admin.env <<EOF
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:55432/${POSTGRES_DB}
LEGALMIND_INGEST_ROOT=/opt/legalmind-ingest
LEGALMIND_ADMIN_USER=admin
LEGALMIND_ADMIN_PASSWORD=${ADMIN_PASSWORD}
LEGALMIND_MAX_UPLOAD_MB=100
EOF
chmod 600 deploy/admin.env

cp deploy/legalmind-admin.service /etc/systemd/system/legalmind-admin.service
systemctl daemon-reload
systemctl enable --now legalmind-admin.service

cat > /etc/nginx/sites-available/legalmind-admin <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    client_max_body_size 100m;
    location / {
        proxy_pass http://127.0.0.1:8088;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300;
    }
}
EOF
ln -sfn /etc/nginx/sites-available/legalmind-admin /etc/nginx/sites-enabled/legalmind-admin
nginx -t
systemctl reload nginx
curl -fsS http://127.0.0.1:8088/health >/dev/null

echo "LegalMind Admin installed at http://${DOMAIN}"
echo "Username: admin"
echo "Password is stored in ${ADMIN_PASSWORD_FILE}"
