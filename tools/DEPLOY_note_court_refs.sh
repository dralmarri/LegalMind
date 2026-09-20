#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
# DEPLOY_note_court_refs.sh — الخيار (2): ملاحظة مرجعية على م114 وم130
# من القانون 7/2010 (النافذتان المحيلتان إلى «محكمة سوق المال») — **بلا مساس
# بحرف واحد من النص**، والتنبيه في `metadata.source_note` وحدها.
#
#   • الاكتشاف من البيانات لا بقائمة ثابتة، ويُطبع قبل أي كتابة.
#   • حارس صارم: بصمة md5 لنصوص القانون كله (original + normalized) قبل وبعد —
#     أي تغيّر يُسقط المعاملة (`TEXT_TOUCHED`)، وكذلك تغيّر عدد الكائنات.
#   • الملاحظات القائمة سلفًا لا تُمحى، وإعادة التشغيل بلا أثر.
#   • **لا فهرسة**: لم يتغير نص ولا عنوان، فنقاط Qdrant كما هي.
#
# النجاح النهائي = DONE_NOTE_COURT_REFS
# ══════════════════════════════════════════════════════════════════════════
set -euo pipefail

SELF="${BASH_SOURCE[0]:-}"
if [ "${1:-}" != "--worker" ] && [ -n "$SELF" ] && [ -f "$SELF" ]; then
  LOG=/tmp/deploy_note_$(date +%s).log
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
base64 -d <<'B64LM' | gunzip > /opt/LegalMind/tools/add_source_note_court_refs.py
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
OqgcVGn/BYwcx3SrKAAA
B64LM
python3 -c "import ast,io;ast.parse(io.open('/opt/LegalMind/tools/add_source_note_court_refs.py',encoding='utf-8').read());print('SYNTAX_OK')"

echo
echo "═══ 2) نسخة احتياطية لكل كائنات القانون 7/2010 ═══"
BK=/opt/legalmind-data/backup_note_7_2010_$(date +%Y%m%d_%H%M%S).json
psql "$DATABASE_URL" -At -c "SELECT json_agg(row_to_json(k)) FROM knowledge_objects k
  WHERE k.id LIKE 'legis-7-2010-%';" > "$BK"
echo "النسخة: $BK ($(wc -c < "$BK") بايت)"
test -s "$BK" || { echo "BACKUP_EMPTY — أوقفت الدفعة."; exit 1; }

echo
echo "═══ 3) الاكتشاف ثم كتابة التنبيه في metadata وحدها ═══"
/opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/add_source_note_court_refs.py

echo
echo "═══ 4) تشخيص: النصوص لم تُمسّ (لا بوابة) ═══"
set +e
psql "$DATABASE_URL" -At -c "
  SELECT id||' | نص يحمل الصيغة: '||
         (original_text ~ 'محكمة\s+سوق\s+المال')::text||
         ' | تنبيه مسجَّل: '||(metadata->>'note_kind' IS NOT NULL)::text
  FROM knowledge_objects
  WHERE id IN ('legis-7-2010-m114','legis-7-2010-m130') ORDER BY id;"
[ $? -eq 0 ] || echo "DIAG_ERROR — تشخيص فقط، لا يوقف الدفعة"
set -e

echo
echo "═══ 5) اتساق العدّادين (يجب ألا يتغيّر شيء) ═══"
PG=$(psql "$DATABASE_URL" -At -c "SELECT count(*) FROM knowledge_objects;")
QD=$(curl -s http://127.0.0.1:6333/collections/legalmind_multilingual_e5_base_v1 \
     | python3 -c "import sys,json;print(json.load(sys.stdin)['result']['points_count'])")
echo "PG=$PG  Qdrant=$QD"
if [ "$PG" = "$QD" ]; then echo "CONSISTENT_OK"; else
  echo "COUNT_MISMATCH — يُنظر فيه يدويًا (لا فهرسة كاملة آلية أبدًا)"; fi

echo
echo "═══ 6) بطارية القياس (صمّام الانتكاس) ═══"
set +e
/opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py > /tmp/battery_note.log 2>&1
set -e
tail -20 /tmp/battery_note.log
echo
if grep -q "BATTERY_PASS" /tmp/battery_note.log; then
  echo "DONE_NOTE_COURT_REFS"
else
  echo "BATTERY_FAIL — أعد تشغيل البطارية وحدها مرة واحدة قبل أي تشخيص"
  echo "  cd /opt/LegalMind; set -a; . deploy/.env; set +a"
  echo "  /opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py"
  echo "وإن تكرر الفشل فالتراجع الدقيق من: $BK"
  exit 1
fi
