#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${APP_DIR:-/opt/LegalMind}
cd "$APP_DIR"
set -a
source deploy/.env
set +a

curl -fsS http://127.0.0.1:6333/readyz >/dev/null
PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -p "${POSTGRES_HOST_PORT:-55432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc 'select 1' | grep -qx 1

TMP=$(mktemp --suffix=.md)
cat > "$TMP" <<'EOF'
المادة 1
اختبار تشغيل محرك LegalMind.

المادة 2
يجب حفظ المصدر والكائنات دون اختلاق.
EOF
cat > "$TMP.json" <<'EOF'
{"source_type":"legislation","source_key":"TEST-LEGALMIND-ENGINE","law_id":"TEST-ENGINE","title":"اختبار محرك الإدخال","branch":"اختبار","topic":"اختبار تشغيلي"}
EOF

.venv/bin/python engine/legalmind_engine.py ingest "$TMP" >/tmp/legalmind-engine-test.json
cat /tmp/legalmind-engine-test.json

PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -p "${POSTGRES_HOST_PORT:-55432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select count(*) from knowledge_objects where source_key='TEST-LEGALMIND-ENGINE'" | grep -qx 2

echo 'OK: LegalMind ingestion engine smoke test passed'
