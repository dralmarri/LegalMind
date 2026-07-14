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

# لا تدهس بيانات اعتماد قائمة. إعادة تشغيل المُثبِّت على نظام يعمل كانت
# ستمحو التجزئة وتُخرج التطبيق من الخدمة (يفشل مغلقًا بلا تجزئة).
if [[ -f deploy/admin.env ]] && grep -q '^LEGALMIND_ADMIN_PASSWORD_HASH=.\+' deploy/admin.env; then
  echo "deploy/admin.env موجود بتجزئة صالحة — لن يُدهس."
  echo "لتغيير بيانات الدخول: admin/.venv/bin/python -m admin.manage_admin_credentials"
else
  ADMIN_USER=${ADMIN_USER:-admin}
  ADMIN_PASSWORD=$(openssl rand -hex 16)
  # كلمة المرور الصريحة لا تدخل ملف البيئة ولا Git ولا سجل الأوامر:
  # تُخزَّن التجزئة وحدها، وتُسلَّم الكلمة مرة واحدة عبر ملف للجذر فقط.
  ADMIN_PASSWORD_HASH=$(
    printf '%s' "$ADMIN_PASSWORD" |
    admin/.venv/bin/python -c 'import sys; from admin.security import hash_password; print(hash_password(sys.stdin.read()))'
  )

  cat > deploy/admin.env <<EOF
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:55432/${POSTGRES_DB}
LEGALMIND_INGEST_ROOT=/opt/legalmind-ingest
LEGALMIND_ADMIN_USER=${ADMIN_USER}
LEGALMIND_ADMIN_PASSWORD_HASH=${ADMIN_PASSWORD_HASH}
LEGALMIND_MAX_UPLOAD_MB=100
EOF
  chmod 600 deploy/admin.env

  umask 077
  printf 'المستخدم: %s\nكلمة المرور المؤقتة: %s\n\nدوّرها ثم احذف هذا الملف.\n' \
    "$ADMIN_USER" "$ADMIN_PASSWORD" > /root/legalmind-admin-initial-password
  unset ADMIN_PASSWORD
  echo "بيانات الدخول الأولية في /root/legalmind-admin-initial-password (0600)."
fi

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
