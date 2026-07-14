#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/LegalMind}
DOMAIN=${DOMAIN:-admin.soutaladalah.com}
WEB_ROOT=${WEB_ROOT:-/var/www/legalmind-v3}

if [[ $EUID -ne 0 ]]; then
  echo "Run as root" >&2
  exit 1
fi

cd "$APP_DIR"
set -a
source deploy/.env
set +a

# Apply the persistent case-workspace schema to the existing LegalMind database.
docker exec -i legalmind-postgres \
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  < deploy/sql/002_cases_workspace.sql

# Install the API service definition that exposes /api/cases.
cp deploy/legalmind-admin.service /etc/systemd/system/legalmind-admin.service
systemctl daemon-reload
systemctl restart legalmind-admin.service

for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8088/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:8088/health >/dev/null || {
  systemctl status legalmind-admin.service --no-pager || true
  journalctl -u legalmind-admin.service -n 100 --no-pager || true
  exit 1
}

# Build and publish the static Next.js interface without replacing SSL settings.
cd "$APP_DIR/web"
npm install
npm run build

test -f "$APP_DIR/web/out/index.html"
rm -rf "$WEB_ROOT"
mkdir -p "$WEB_ROOT"
cp -a "$APP_DIR/web/out/." "$WEB_ROOT/"
chown -R www-data:www-data "$WEB_ROOT"

nginx -t
systemctl reload nginx

# Verify the new case API and the external protected site.
curl -fsS -u "admin:$(cat /root/legalmind-admin-password.txt)" \
  "https://${DOMAIN}/api/cases" >/dev/null
curl -fsS -u "admin:$(cat /root/legalmind-admin-password.txt)" \
  "https://${DOMAIN}/" >/dev/null

echo "LegalMind 4 deployed successfully"
echo "URL: https://${DOMAIN}"
echo "Case workspace API: /api/cases"
