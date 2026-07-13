#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/LegalMind}
cd "$APP_DIR/deploy"
set -a
source .env
set +a

STAMP=$(date +%Y%m%d-%H%M%S)
DEST="$LEGALMIND_BACKUP_DIR/$STAMP"
mkdir -p "$DEST"

docker exec legalmind-postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$DEST/postgres.dump"
tar -C "$LEGALMIND_DATA_DIR" -czf "$DEST/qdrant.tar.gz" qdrant
cp "$APP_DIR/knowledge-system/RESUME_STATE.md" "$DEST/RESUME_STATE.md" 2>/dev/null || true
git -C "$APP_DIR" rev-parse HEAD > "$DEST/git-commit.txt"
sha256sum "$DEST"/* > "$DEST/SHA256SUMS"
find "$LEGALMIND_BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +

echo "$DEST"
