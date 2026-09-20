#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
# DEPLOY_termsub_7_2010.sh — إنهاء البند المؤجَّل من دفعة العدد 1809:
# الاستبدال اللفظي الشامل الذي أمرت به الفقرة الثانية من المادة الأولى من
# المرسوم بقانون 91/2026 («الوزير المختص» و«المحكمة المختصة» بدل «وزير التجارة
# والصناعة» و«محكمة أسواق المال» أينما وردتا في القانون 7/2010).
#
#   • قياسٌ شاملٌ أولًا (TERM_BLAST_RADIUS بسياق كل ورود وفئته) قبل أي كتابة.
#   • ولا يُستبدل إلا الورود **الحرفي** في **مواد المتن النافذة** — أما المواد
#     الملغاة (108-113 و116) ومواد الإصدار والديباجة والمذكرة والصيغ التي لم
#     يسمِّها المرسوم («محكمة سوق المال») فتُعرض في التقرير ولا تُمسّ.
#   • كل الكتابات في معاملة واحدة، والنص القديم كاملًا إلى previous_versions[]،
#     وإعادة التشغيل بلا أثر (منع التكرار ببصمة sha256).
#   • فهرسة **تفاضلية** لما تغيّر وحده (لا فهرسة كاملة أبدًا — قاعدة §10).
#
# النجاح النهائي = DONE_TERMSUB
# ══════════════════════════════════════════════════════════════════════════
set -euo pipefail

# لا يُعتمد على $0 أبدًا (درس §13): عند اللصق يكون «bash» لا مسار ملف.
SELF="${BASH_SOURCE[0]:-}"
if [ "${1:-}" != "--worker" ] && [ -n "$SELF" ] && [ -f "$SELF" ]; then
  LOG=/tmp/deploy_termsub_$(date +%s).log
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
base64 -d <<'B64LM' | gunzip > /opt/LegalMind/tools/apply_term_substitution_7_2010.py
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
B64LM
python3 -c "import ast,io;ast.parse(io.open('/opt/LegalMind/tools/apply_term_substitution_7_2010.py',encoding='utf-8').read());print('SYNTAX_OK')"

echo
echo "═══ 2) نسخة احتياطية لكل كائنات القانون 7/2010 ═══"
BK=/opt/legalmind-data/backup_termsub_7_2010_$(date +%Y%m%d_%H%M%S).json
psql "$DATABASE_URL" -At -c "SELECT json_agg(row_to_json(k)) FROM knowledge_objects k
  WHERE k.id LIKE 'legis-7-2010-%';" > "$BK"
echo "النسخة: $BK ($(wc -c < "$BK") بايت)"
test -s "$BK" || { echo "BACKUP_EMPTY — أوقفت الدفعة."; exit 1; }

echo
echo "═══ 3) القياس ثم الاستبدال الضيّق ═══"
/opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/apply_term_substitution_7_2010.py

echo
echo "═══ 4) فهرسة تفاضلية لما تغيّر وحده ═══"
IDS=/opt/legalmind-data/termsub_7_2010_changed_ids.txt
if [ -s "$IDS" ]; then
  echo "معرفات ستُفهرس: $(wc -l < "$IDS")"
  # كل معرّف يُمرَّر نمطًا حرفيًا (بلا %) فلا يُصاب غيره
  mapfile -t CHANGED < "$IDS"
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/reindex_delta.py "${CHANGED[@]}"
else
  echo "REINDEX_SKIPPED: لا كائن تغيّر — لا شيء يُفهرس."
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
echo "═══ 6) تشخيص: صورة القانون بعد الجولة (لا بوابة) ═══"
# معزول عن set -e — درس §13: مِشجب تشخيصي أسقط بوابةً حقيقية مرة واحدة، لا مرتين.
set +e
psql "$DATABASE_URL" -At -c "
  SELECT 'كائنات 7/2010 = '||count(*) FROM knowledge_objects WHERE id LIKE 'legis-7-2010-%'
  UNION ALL SELECT 'منها موسومة بالإلغاء = '||count(*) FROM knowledge_objects
      WHERE id LIKE 'legis-7-2010-%' AND verification_status='superseded'
  UNION ALL SELECT 'تحمل «وزير التجارة والصناعة» = '||count(*) FROM knowledge_objects
      WHERE id LIKE 'legis-7-2010-%' AND original_text LIKE '%وزير التجارة والصناعة%'
  UNION ALL SELECT 'تحمل «محكمة أسواق المال» = '||count(*) FROM knowledge_objects
      WHERE id LIKE 'legis-7-2010-%' AND original_text LIKE '%محكمة أسواق المال%'
  UNION ALL SELECT 'تحمل «محكمة سوق المال» (صيغة لم يسمِّها المرسوم) = '||count(*)
      FROM knowledge_objects
      WHERE id LIKE 'legis-7-2010-%' AND original_text LIKE '%محكمة سوق المال%';"
[ $? -eq 0 ] || echo "DIAG_ERROR — تشخيص فقط، لا يوقف الدفعة"
set -e

echo
echo "═══ 7) بطارية القياس (صمّام الانتكاس) ═══"
set +e
/opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py > /tmp/battery_termsub.log 2>&1
set -e
tail -20 /tmp/battery_termsub.log
echo
if grep -q "BATTERY_PASS" /tmp/battery_termsub.log; then
  echo "DONE_TERMSUB"
else
  echo "BATTERY_FAIL — أعد تشغيل البطارية وحدها مرة واحدة قبل أي تشخيص"
  echo "  (بروتوكول عدم تصديق الفشل المفرد):"
  echo "  cd /opt/LegalMind; set -a; . deploy/.env; set +a"
  echo "  /opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py"
  echo "وإن تكرر الفشل فالتراجع الدقيق من: $BK"
  exit 1
fi
