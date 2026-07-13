#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/LegalMind}
DOMAIN=${DOMAIN:-admin.soutaladalah.com}
SERVER_IP=${SERVER_IP:-72.61.237.80}
EMAIL=${CERTBOT_EMAIL:-dralmarri@gmail.com}

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/deploy_admin_portal.sh" >&2
  exit 1
fi

cd "$APP_DIR"
git fetch origin
git reset --hard origin/main

chmod +x deploy/install_admin_portal.sh
APP_DIR="$APP_DIR" DOMAIN="$DOMAIN" bash deploy/install_admin_portal.sh

systemctl restart legalmind-ingest.service
systemctl restart legalmind-admin.service

curl -fsS http://127.0.0.1:8088/health >/dev/null

echo "Admin application is healthy on 127.0.0.1:8088"

RESOLVED_IP=$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk 'NR==1{print $1}' || true)
if [[ "$RESOLVED_IP" == "$SERVER_IP" ]]; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y certbot python3-certbot-nginx
  certbot --nginx -d "$DOMAIN" --redirect --non-interactive --agree-tos -m "$EMAIL" || true
  URL="https://${DOMAIN}"
else
  URL="http://${SERVER_IP}"
  echo "DNS is not ready yet: $DOMAIN resolves to '${RESOLVED_IP:-nothing}', expected $SERVER_IP"
  echo "Create DNS A record: admin -> $SERVER_IP, then rerun this script for HTTPS."
fi

echo
echo "=== LegalMind Admin ==="
echo "URL: $URL"
echo "Username: admin"
echo "Password: $(cat /root/legalmind-admin-password.txt)"
echo
echo "=== Services ==="
systemctl --no-pager --full status legalmind-admin.service | sed -n '1,12p'
systemctl --no-pager --full status legalmind-ingest.service | sed -n '1,12p'
