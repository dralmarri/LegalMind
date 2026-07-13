#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/LegalMind}
INGEST_ROOT=${LEGALMIND_INGEST_ROOT:-/opt/legalmind-ingest}
ENV_FILE="$APP_DIR/deploy/.env"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root" >&2
  exit 1
fi

cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r engine/requirements.txt

mkdir -p "$INGEST_ROOT/inbox" "$INGEST_ROOT/archive" "$INGEST_ROOT/failed"
chmod 750 "$INGEST_ROOT" "$INGEST_ROOT"/*

if ! grep -q '^POSTGRES_HOST_PORT=' "$ENV_FILE"; then
  echo 'POSTGRES_HOST_PORT=55432' >> "$ENV_FILE"
fi

set -a
source "$ENV_FILE"
set +a

DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_HOST_PORT:-55432}/${POSTGRES_DB}"
if grep -q '^DATABASE_URL=' "$ENV_FILE"; then
  sed -i "s#^DATABASE_URL=.*#DATABASE_URL=${DATABASE_URL}#" "$ENV_FILE"
else
  echo "DATABASE_URL=${DATABASE_URL}" >> "$ENV_FILE"
fi

cp deploy/legalmind-ingest.service /etc/systemd/system/legalmind-ingest.service
systemctl daemon-reload
systemctl enable --now legalmind-ingest.service

sleep 2
systemctl status legalmind-ingest.service --no-pager

echo
printf 'Inbox: %s\n' "$INGEST_ROOT/inbox"
printf 'Archive: %s\n' "$INGEST_ROOT/archive"
printf 'Failed: %s\n' "$INGEST_ROOT/failed"
