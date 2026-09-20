#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
# DEPLOY_gazette1809.sh — دفعة الكويت اليوم العدد 1809 (الأحد 2026/9/20)
#
#   (أ) مرسوم بقانون 91/2026 بتعديل قانون هيئة أسواق المال 7/2010 — 6 كائنات
#       (ديباجة + أربع مواد + مذكرة إيضاحية)
#   (ب) قاعدة التحديث على legis-7-2010:
#         • م1: استبدال تعريفَي (الوزير المختص) و(المحكمة المختصة) على المعرّف
#           نفسه، والنص القديم إلى metadata.previous_versions[] — لا يُمحى نص قط
#         • المواد 108-113 و116: تُوسم superseded + repealed_by، ونصوصها باقية
#   (ج) المذكرة الإيضاحية للمرسوم بقانون 93/2026 — كائن واحد،
#       وتوسيم legis-20-2019-m11 بأنه معدَّل بانتظار النص الرسمي (النص لا يُمس)
#   (د) تحقق أن القرار الوزاري 590/2026 (اللائحة التنفيذية لقانون التوثيق)
#       مُدخَل سلفًا وكاملًا تحت regl-10-2020 — لا إعادة إدخال
#
#   ثم فهرسة تفاضلية فقط (لا فهرسة كاملة أبدًا — قاعدة §10)، ثم اختبار استرجاع
#   حي، ثم بطارية 13/13.  الاعتماد النهائي = DONE_GAZETTE_1809
#
#   كل الكتابات داخل معاملة واحدة: أي بوابة تفشل تُرجع القاعدة كما كانت.
#   نسخة احتياطية دقيقة للصفوف الممسوسة تُكتب قبل أي تعديل.
# ══════════════════════════════════════════════════════════════════════════
set -euo pipefail

if [ "${1:-}" != "--worker" ]; then
  SELF="/opt/LegalMind/tools/DEPLOY_gazette1809.sh"
  mkdir -p /opt/LegalMind/tools
  cp -f "$0" "$SELF" 2>/dev/null || true
  chmod +x "$SELF"
  LOG=/tmp/deploy_1809_$(date +%s).log
  echo "التشغيل في الخلفية (يصمد لانقطاع الطرفية). السجل: $LOG"
  nohup bash "$SELF" --worker > "$LOG" 2>&1 &
  disown
  echo "تابع بـ:  tail -f $LOG"
  exit 0
fi

cd /opt/LegalMind
set -a; . /opt/LegalMind/deploy/.env; set +a

echo "═══ 1) كتابة سكربت الإدخال ═══"
mkdir -p /opt/LegalMind/tools
base64 -d <<'B64LM' | gunzip > /opt/LegalMind/tools/ingest_gazette1809.py
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
B64LM
python3 -c "import ast,io;ast.parse(io.open('/opt/LegalMind/tools/ingest_gazette1809.py',encoding='utf-8').read());print('SYNTAX_OK')"

echo
echo "═══ 2) نسخة احتياطية دقيقة للصفوف التي ستُمسّ ═══"
mkdir -p /opt/legalmind-data
BK=/opt/legalmind-data/backup_1809_$(date +%Y%m%d_%H%M%S).json
psql "$DATABASE_URL" -At -c "SELECT json_agg(row_to_json(k)) FROM knowledge_objects k
  WHERE id IN ('legis-7-2010-m1','legis-20-2019-m11','legis-7-2010-m108',
               'legis-7-2010-m109','legis-7-2010-m110','legis-7-2010-m111',
               'legis-7-2010-m112','legis-7-2010-m113','legis-7-2010-m116');" > "$BK"
echo "النسخة: $BK ($(wc -c < "$BK") بايت)"
test -s "$BK" || { echo "BACKUP_EMPTY — أوقفت الدفعة."; exit 1; }

echo
echo "═══ 3) الإدخال (بيئة المحرك الثقيلة) ═══"
/opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/ingest_gazette1809.py

echo
echo "═══ 4) فهرسة تفاضلية فقط ═══"
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
/opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/reindex_delta.py \
  'legis-91-2026-%' 'legis-93-2026-%' 'legis-7-2010-m1'

echo
echo "═══ 5) اتساق العدّادين ═══"
PG=$(psql "$DATABASE_URL" -At -c "SELECT count(*) FROM knowledge_objects;")
QD=$(curl -s http://127.0.0.1:6333/collections/legalmind_multilingual_e5_base_v1 \
     | python3 -c "import sys,json;print(json.load(sys.stdin)['result']['points_count'])")
echo "PG=$PG  Qdrant=$QD"
if [ "$PG" = "$QD" ]; then echo "CONSISTENT_OK"; else
  echo "COUNT_MISMATCH — يُنظر فيه يدويًا (لا فهرسة كاملة آلية أبدًا)"; fi

echo
echo "═══ 6) اختبار استرجاع حي مرشَّح بالتشريعات ═══"
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /opt/LegalMind/.venv/bin/python - <<'PYTEST'
import sys, os, subprocess, json
sys.path.insert(0, "/opt/LegalMind"); os.chdir("/opt/LegalMind")
from engine import legalmind_engine as eng
q = "المحكمة المختصة بمنازعات هيئة أسواق المال بعد إنشاء الدوائر الاقتصادية"
out = subprocess.run(["/opt/LegalMind/.venv/bin/python", "engine/embed_query_cli.py", q],
                     capture_output=True, text=True, env=dict(os.environ))
vec = json.loads(out.stdout)
r = eng.qdrant_request("POST", "/collections/%s/points/search" % eng.COLLECTION,
      {"vector": vec, "limit": 8, "with_payload": True,
       "filter": {"must": [{"key": "object_type", "match": {"any": [
         "legislation_article", "legislation_issuing_article", "legislation_preamble"]}}]}})
hits = [(h["score"], h["payload"]["object_id"]) for h in r["result"]]
for s, oid in hits:
    print("   %.3f  %s" % (s, oid))
print("RETRIEVAL_91_2026_" + ("OK" if any(o.startswith("legis-91-2026-") for _, o in hits) else "MISS"))
PYTEST

echo
echo "═══ 7) بطارية القياس (صمام الانتكاس) ═══"
set +e
/opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py > /tmp/battery_1809.log 2>&1
set -e
tail -20 /tmp/battery_1809.log
echo
if grep -q "BATTERY_PASS" /tmp/battery_1809.log; then
  echo "DONE_GAZETTE_1809"
else
  echo "BATTERY_FAIL — أعد التشغيل مرة واحدة قبل أي تشخيص"
  echo "  (بروتوكول عدم تصديق الفشل المفرد — سابقة جولة تنظيف gradetrackpro §11):"
  echo "  cd /opt/LegalMind; set -a; . deploy/.env; set +a"
  echo "  /opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py"
  echo "وإن تكرر الفشل فالتراجع الدقيق من: $BK"
  exit 1
fi
