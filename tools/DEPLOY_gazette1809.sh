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
AA==
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
