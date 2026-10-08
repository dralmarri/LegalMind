#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
# DEPLOY_fix_blanklines.sh — تنقية أسطر فارغة دخيلة من ثماني مواد في 102/2026.
# التغيير فراغٌ خالص تحت حارس قاطع: النص بعد تجريد المحارف البيضاء يجب أن يبقى
# مطابقًا بايتًا ببايت، وإلا سقطت المعاملة. أهمّها م51 التي كان السطر الفارغ
# يشقّ جملة واحدة في منتصفها.
# النجاح النهائي = DONE_FIX_BLANKLINES
# ══════════════════════════════════════════════════════════════════════════
set -euo pipefail
SELF="${BASH_SOURCE[0]:-}"
if [ "${1:-}" != "--worker" ] && [ -n "$SELF" ] && [ -f "$SELF" ]; then
  LOG=/tmp/deploy_fixblank_$(date +%s).log
  echo "running in background (survives terminal disconnect). log: $LOG"
  nohup bash "$SELF" --worker > "$LOG" 2>&1 &
  disown
  echo "follow with:  tail -f $LOG"
  exit 0
fi
[ "${1:-}" = "--worker" ] || echo "(pasted mode: running in the foreground)"

cd /opt/LegalMind
set -a; . /opt/LegalMind/deploy/.env; set +a
mkdir -p /opt/LegalMind/tools /opt/legalmind-data

echo "═══ 1) كتابة السكربت ═══"
base64 -d <<'B64LM' | gunzip > /opt/LegalMind/tools/fix_media102_blanklines.py
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
B64LM
python3 -c "import ast,io;ast.parse(io.open('/opt/LegalMind/tools/fix_media102_blanklines.py',encoding='utf-8').read());print('SYNTAX_OK')"

echo
echo "═══ 2) نسخة احتياطية لكائنات 102/2026 ═══"
BK=/opt/legalmind-data/backup_fixblank_$(date +%Y%m%d_%H%M%S).json
psql "$DATABASE_URL" -At -c "SELECT json_agg(row_to_json(k)) FROM knowledge_objects k
  WHERE k.id LIKE 'legis-102-2026-%';" > "$BK"
echo "النسخة: $BK ($(wc -c < "$BK") بايت)"
test -s "$BK" || { echo "BACKUP_EMPTY — أوقفت الدفعة."; exit 1; }

echo
echo "═══ 3) الإزالة (معاملة واحدة بحارس المحتوى) ═══"
/opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/fix_media102_blanklines.py

echo
echo "═══ 4) فهرسة تفاضلية لما تغيّر وحده ═══"
IDS=/opt/legalmind-data/media102_blank_changed_ids.txt
if [ -s "$IDS" ]; then
  echo "معرفات ستُفهرس: $(wc -l < "$IDS")"
  mapfile -t CHANGED < "$IDS"
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/reindex_delta.py "${CHANGED[@]}"
else
  echo "REINDEX_SKIPPED: لا كائن تغيّر."
fi

echo
echo "═══ 5) اتساق العدّادين ═══"
PG=$(psql "$DATABASE_URL" -At -c "SELECT count(*) FROM knowledge_objects;")
QD=$(curl -s http://127.0.0.1:6333/collections/legalmind_multilingual_e5_base_v1 \
     | python3 -c "import sys,json;print(json.load(sys.stdin)['result']['points_count'])")
echo "PG=$PG  Qdrant=$QD"
if [ "$PG" = "$QD" ]; then echo "CONSISTENT_OK"; else
  echo "COUNT_MISMATCH — يُنظر فيه يدويًا (لا فهرسة كاملة آلية أبدًا)"; fi

echo
echo "═══ 6) تشخيص (لا بوابة) ═══"
set +e
psql "$DATABASE_URL" -At -c "
  SELECT 'مواد 102/2026 فيها سطر فارغ (يجب 0) = '||count(*) FROM knowledge_objects
    WHERE id LIKE 'legis-102-2026-%' AND original_text LIKE E'%\n\n%'
  UNION ALL SELECT 'كائنات 102/2026 = '||count(*) FROM knowledge_objects
    WHERE id LIKE 'legis-102-2026-%';"
[ $? -eq 0 ] || echo "DIAG_ERROR — تشخيص فقط"
set -e

echo
echo "═══ 7) بطارية القياس ═══"
set +e
/opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py > /tmp/battery_fixblank.log 2>&1
set -e
tail -12 /tmp/battery_fixblank.log
echo
if grep -q "BATTERY_PASS" /tmp/battery_fixblank.log; then
  echo "DONE_FIX_BLANKLINES"
else
  echo "BATTERY_FAIL — أعد تشغيل البطارية وحدها مرة واحدة قبل أي تشخيص:"
  echo "  cd /opt/LegalMind; set -a; . deploy/.env; set +a"
  echo "  /opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py"
  echo "وإن تكرر الفشل فالتراجع الدقيق من: $BK"
  exit 1
fi
