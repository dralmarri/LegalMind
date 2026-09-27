#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
# DEPLOY_tenders94.sh — مرسوم بقانون 94/2026 بتعديل قانون المناقصات العامة
# 49/2016 (الكويت اليوم، العدد 1810، 2026/9/27، ص أ2-أ5).
#
#   • 7 كائنات جديدة على البادئة legis-94-2026 (ديباجة + 5 مواد + مذكرة).
#   • و14 كائنًا من legis-49-2016 يُسجَّل عليها التعديل **معلَّقًا**، لأن
#     المادة الخامسة تؤجّل النفاذ ثلاثة أشهر من النشر — فلا يُستبدل نصٌّ
#     نافذٌ اليوم بنصٍّ لم يبدأ العمل به. الإلحاق موسوم صراحةً، وبلا حذف
#     حرف واحد، والمتن الأصلي محفوظ في metadata.text_before_pending_block.
#   • فهرسة **تفاضلية** لما تغيّر وحده (لا فهرسة كاملة أبدًا — قاعدة §10).
#   • الخطوات التشخيصية معزولة عن set -e (درس §13: مِشجب تشخيصي حجب بوابة).
#
# النجاح النهائي = DONE_TENDERS94
# ══════════════════════════════════════════════════════════════════════════
set -euo pipefail

# لا يُعتمد على $0 أبدًا (درس §13): عند اللصق يكون «bash» لا مسار ملف.
SELF="${BASH_SOURCE[0]:-}"
if [ "${1:-}" != "--worker" ] && [ -n "$SELF" ] && [ -f "$SELF" ]; then
  LOG=/tmp/deploy_tenders94_$(date +%s).log
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

echo "═══ 1) كتابة سكربت الإدخال ═══"
base64 -d <<'B64LM' | gunzip > /opt/LegalMind/tools/ingest_tenders94_2026.py
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
B64LM
python3 -c "import ast,io;ast.parse(io.open('/opt/LegalMind/tools/ingest_tenders94_2026.py',encoding='utf-8').read());print('SYNTAX_OK')"

echo
echo "═══ 2) نسخة احتياطية دقيقة لكل كائنات القانون 49/2016 ═══"
BK=/opt/legalmind-data/backup_tenders94_49_2016_$(date +%Y%m%d_%H%M%S).json
psql "$DATABASE_URL" -At -c "SELECT json_agg(row_to_json(k)) FROM knowledge_objects k
  WHERE k.id LIKE 'legis-49-2016-%';" > "$BK"
echo "النسخة: $BK ($(wc -c < "$BK") بايت)"
test -s "$BK" || { echo "BACKUP_EMPTY — أوقفت الدفعة."; exit 1; }

echo
echo "═══ 3) الإدخال + تسجيل التعديل المعلَّق (معاملة واحدة) ═══"
/opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/ingest_tenders94_2026.py

echo
echo "═══ 4) فهرسة تفاضلية لما تغيّر وحده ═══"
IDS=/opt/legalmind-data/tenders94_changed_ids.txt
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
echo "═══ 6) تشخيص: جرد الدفعة (لا بوابة) ═══"
set +e
psql "$DATABASE_URL" -At -c "
  SELECT 'كائنات 94/2026 = '||count(*) FROM knowledge_objects WHERE id LIKE 'legis-94-2026-%'
  UNION ALL SELECT 'كائنات 49/2016 = '||count(*) FROM knowledge_objects WHERE id LIKE 'legis-49-2016-%'
  UNION ALL SELECT 'منها تحمل تعديلًا معلَّقًا = '||count(*) FROM knowledge_objects
      WHERE id LIKE 'legis-49-2016-%' AND metadata ? 'pending_amendment'
  UNION ALL SELECT 'منها تحمل إلغاءً معلَّقًا = '||count(*) FROM knowledge_objects
      WHERE id LIKE 'legis-49-2016-%' AND metadata ? 'pending_repeal'
  UNION ALL SELECT 'موسومة superseded (يجب أن تبقى كما كانت) = '||count(*)
      FROM knowledge_objects WHERE id LIKE 'legis-49-2016-%' AND verification_status='superseded';"
[ $? -eq 0 ] || echo "DIAG_ERROR — تشخيص فقط، لا يوقف الدفعة"

echo
echo "─── اختبار استرجاع حي (السؤال عبر stdin — درس §13) ───"
for Q in "حظر استخدام الوكيل المحلي أو الوكيل بالعمولة في إجراءات التعاقد" \
         "نصاب التعاقد بدون إذن الجهاز المركزي للمناقصات" \
         "أفضلية عطاءات المشروعات الصغيرة والمتوسطة في المناقصات العامة"; do
  echo "س: $Q"
  VEC=$(printf '%s' "$Q" | HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
        /opt/LegalMind/.venv/bin/python /opt/LegalMind/engine/embed_query_cli.py)
  python3 - "$VEC" <<'PYQ'
import sys, json, urllib.request
v = json.loads(sys.argv[1])
if not v:
    print("   (متجه فارغ — تشخيص فقط)"); raise SystemExit(0)
req = urllib.request.Request(
    "http://127.0.0.1:6333/collections/legalmind_multilingual_e5_base_v1/points/search",
    data=json.dumps({"vector": v, "limit": 4, "with_payload": True}).encode(),
    headers={"Content-Type": "application/json"})
for h in json.load(urllib.request.urlopen(req))["result"]:
    p = h.get("payload") or {}
    print("   %.3f  %s" % (h["score"], p.get("object_id") or p.get("id")))
PYQ
done
set -e

echo
echo "═══ 7) بطارية القياس (صمّام الانتكاس) ═══"
set +e
/opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py > /tmp/battery_tenders94.log 2>&1
set -e
tail -20 /tmp/battery_tenders94.log
echo
if grep -q "BATTERY_PASS" /tmp/battery_tenders94.log; then
  echo "DONE_TENDERS94"
else
  echo "BATTERY_FAIL — أعد تشغيل البطارية وحدها مرة واحدة قبل أي تشخيص"
  echo "  (بروتوكول عدم تصديق الفشل المفرد):"
  echo "  cd /opt/LegalMind; set -a; . deploy/.env; set +a"
  echo "  /opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py"
  echo "وإن تكرر الفشل فالتراجع الدقيق من: $BK"
  exit 1
fi
