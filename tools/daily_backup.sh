#!/bin/bash
# daily_backup: نسخة يومية تكميلية (فوق لقطات Hostinger الأسبوعية/اليومية للخادم كله) —
# PostgreSQL كاملة + ملفات القضايا + .env — بصيغة قابلة للاستعادة، مع تدوير 14 يومًا.
set -e
cd /opt/LegalMind
set -a; . deploy/.env; set +a
STAMP=$(date +%Y%m%d_%H%M%S)
PGDIR=/opt/legalmind-data/backups/pg
CFDIR=/opt/legalmind-data/backups/case_files
mkdir -p "$PGDIR" "$CFDIR"

pg_dump "$DATABASE_URL" -F c -f "$PGDIR/legalmind_${STAMP}.dump"
gzip -f "$PGDIR/legalmind_${STAMP}.dump" 2>/dev/null || true  # pg_dump -F c مضغوطة أصلًا؛ محاولة إضافية غير ضارة

if [ -d /opt/legalmind-data/case_files ]; then
  tar -czf "$CFDIR/case_files_${STAMP}.tar.gz" -C /opt/legalmind-data case_files
fi

cp /opt/LegalMind/deploy/.env "$PGDIR/env_${STAMP}.bak"
chmod 600 "$PGDIR/env_${STAMP}.bak"

# تدوير: الاحتفاظ بآخر 14 نسخة من كل نوع فقط
ls -1t "$PGDIR"/legalmind_*.dump* 2>/dev/null | tail -n +15 | xargs -r rm -f
ls -1t "$CFDIR"/case_files_*.tar.gz 2>/dev/null | tail -n +15 | xargs -r rm -f
ls -1t "$PGDIR"/env_*.bak 2>/dev/null | tail -n +15 | xargs -r rm -f

echo "[$(date +%T)] DAILY_BACKUP_OK: $STAMP"
