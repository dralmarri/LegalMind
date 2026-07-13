#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/LegalMind}
DATA_DIR=${LEGALMIND_DATA_DIR:-/opt/legalmind-data}
BACKUP_DIR=${LEGALMIND_BACKUP_DIR:-/opt/legalmind-backups}
REPO_URL=${REPO_URL:-https://github.com/dralmarri/LegalMind.git}

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/bootstrap_vps.sh" >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl git unzip jq python3 python3-venv docker.io docker-compose-v2
systemctl enable --now docker

mkdir -p "$DATA_DIR/postgres" "$DATA_DIR/qdrant" "$BACKUP_DIR"
chown -R root:docker "$DATA_DIR" "$BACKUP_DIR"
chmod 750 "$DATA_DIR" "$BACKUP_DIR"

if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" fetch origin
  git -C "$APP_DIR" reset --hard origin/main
fi

cd "$APP_DIR/deploy"
if [[ ! -f .env ]]; then
  cp .env.example .env
  PASSWORD=$(openssl rand -base64 36 | tr -d '\n=/+' | cut -c1-32)
  sed -i "s/CHANGE_ME_LONG_RANDOM_PASSWORD/$PASSWORD/" .env
fi

set -a
source .env
set +a
mkdir -p "$LEGALMIND_DATA_DIR/postgres" "$LEGALMIND_DATA_DIR/qdrant" "$LEGALMIND_BACKUP_DIR"
docker compose up -d

for i in {1..30}; do
  if docker compose ps --status running | grep -q legalmind-postgres && docker compose ps --status running | grep -q legalmind-qdrant; then
    break
  fi
  sleep 2
done

docker compose ps
python3 "$APP_DIR/knowledge-system/scripts/validate_knowledge.py" || true

echo "LegalMind infrastructure is running. PostgreSQL and Qdrant listen on localhost only."
