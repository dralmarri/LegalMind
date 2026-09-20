#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
# DEPLOY_regl590.sh — ترقية اللائحة التنفيذية لقانون التوثيق إلى النص الرسمي
#
#   الكائنات الـ67 تحت regl-10-2020 كانت مُدخَلة من **مسودة قبل النشر الرسمي**:
#   الديباجة وترويسات الجداول الثلاثة تحمل «رقم ( ) لسنة 2026» — الرقم فارغ.
#   المصدر الرسمي: الكويت اليوم ع1809 (2026/9/20) ص29-36 — قرار وزير العدل
#   رقم (590) لسنة 2026، صدر 14 صفر 1448هـ / 28 يوليو 2026م.
#
#   • الديباجة تُستبدل بالنص الرسمي كاملًا، ونوعها يُصحَّح إلى legislation_preamble
#   • ترويسات الجداول 1/2/3 تحمل الرقم (590)
#   • بصمة المصدر الرسمي على الـ67 كلها
#   • تعارض داخلي في الجريدة نفسها (ملاحظة الجدول 2 تحيل لبند (5) من م44 وهو في
#     م45) يُوثَّق في source_note ولا يُصحَّح — النص الأصلي مقدس
#   • تدقيق تغطية كامل: طول/بصمة/إحالات/مدد/رسوم لكل كائن من الـ67
#
#   حارس مُلزِم: `legis-10-2020` (قانون التوثيق نفسه، 30 كائنًا) لا يُمس — تُقاس
#   بصمة نصوصه قبل وبعد، وأي تغيّر يُسقط الدفعة كلها.
#   كل الكتابات في معاملة واحدة، والنصوص القديمة إلى previous_versions[].
#
#   الاعتماد النهائي = DONE_REGL_590
# ══════════════════════════════════════════════════════════════════════════
set -euo pipefail

if [ "${1:-}" != "--worker" ]; then
  SELF="/opt/LegalMind/tools/DEPLOY_regl590.sh"
  mkdir -p /opt/LegalMind/tools
  cp -f "$0" "$SELF" 2>/dev/null || true
  chmod +x "$SELF"
  LOG=/tmp/deploy_regl590_$(date +%s).log
  echo "التشغيل في الخلفية (يصمد لانقطاع الطرفية). السجل: $LOG"
  nohup bash "$SELF" --worker > "$LOG" 2>&1 &
  disown
  echo "تابع بـ:  tail -f $LOG"
  exit 0
fi

cd /opt/LegalMind
set -a; . /opt/LegalMind/deploy/.env; set +a

echo "═══ 1) كتابة سكربت الترقية ═══"
mkdir -p /opt/LegalMind/tools
base64 -d <<'B64LM' | gunzip > /opt/LegalMind/tools/fix_regl_10_2020_official.py
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
B64LM
python3 -c "import ast,io;ast.parse(io.open('/opt/LegalMind/tools/fix_regl_10_2020_official.py',encoding='utf-8').read());print('SYNTAX_OK')"

echo
echo "═══ 2) نسخة احتياطية كاملة للائحة (67 كائنًا) وللقانون (30) ═══"
mkdir -p /opt/legalmind-data
BK=/opt/legalmind-data/backup_regl590_$(date +%Y%m%d_%H%M%S).json
psql "$DATABASE_URL" -At -c "SELECT json_agg(row_to_json(k)) FROM knowledge_objects k
  WHERE k.id LIKE 'regl-10-2020-%' OR k.id LIKE 'legis-10-2020-%';" > "$BK"
echo "النسخة: $BK ($(wc -c < "$BK") بايت)"
test -s "$BK" || { echo "BACKUP_EMPTY — أوقفت الدفعة."; exit 1; }

echo
echo "═══ 3) الترقية إلى النص الرسمي ═══"
/opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/fix_regl_10_2020_official.py

echo
echo "═══ 4) فهرسة تفاضلية للائحة وحدها ═══"
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
/opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/reindex_delta.py 'regl-10-2020-%'

echo
echo "═══ 5) اتساق العدّادين ═══"
PG=$(psql "$DATABASE_URL" -At -c "SELECT count(*) FROM knowledge_objects;")
QD=$(curl -s http://127.0.0.1:6333/collections/legalmind_multilingual_e5_base_v1 \
     | python3 -c "import sys,json;print(json.load(sys.stdin)['result']['points_count'])")
echo "PG=$PG  Qdrant=$QD"
if [ "$PG" = "$QD" ]; then echo "CONSISTENT_OK"; else
  echo "COUNT_MISMATCH — يُنظر فيه يدويًا (لا فهرسة كاملة آلية أبدًا)"; fi

echo
echo "═══ 6) اختبار استرجاع حي ═══"
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /opt/LegalMind/.venv/bin/python - <<'PYTEST'
import sys, os, subprocess, json
sys.path.insert(0, "/opt/LegalMind"); os.chdir("/opt/LegalMind")
from engine import legalmind_engine as eng
for q, want in [
    ("رسوم توثيق التوكيلات العامة والخاصة وإثبات التاريخ لدى إدارة التوثيق", "regl-10-2020-jadwal3"),
    ("شروط الترخيص بمزاولة أعمال الموثق الأهلي ومدة الترخيص وتجديده", "regl-10-2020-m4"),
]:
    out = subprocess.run(["/opt/LegalMind/.venv/bin/python", "engine/embed_query_cli.py", q],
                         capture_output=True, text=True, env=dict(os.environ))
    vec = json.loads(out.stdout)
    r = eng.qdrant_request("POST", "/collections/%s/points/search" % eng.COLLECTION,
          {"vector": vec, "limit": 5, "with_payload": True,
           "filter": {"must": [{"key": "object_type", "match": {"any": [
             "legislation_article", "legislation_issuing_article", "legislation_preamble"]}}]}})
    hits = [(h["score"], h["payload"]["object_id"]) for h in r["result"]]
    print("  «%s»" % q[:50])
    for s, oid in hits:
        print("      %.3f  %s" % (s, oid))
    print("   -> REGL_HIT_" + ("OK" if any(o.startswith("regl-10-2020-") for _, o in hits) else "MISS"))
PYTEST

echo
echo "═══ 7) بطارية القياس ═══"
set +e
/opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py > /tmp/battery_regl590.log 2>&1
set -e
tail -20 /tmp/battery_regl590.log
echo
if grep -q "BATTERY_PASS" /tmp/battery_regl590.log; then
  echo "DONE_REGL_590"
else
  echo "BATTERY_FAIL — أعد التشغيل مرة واحدة قبل أي تشخيص:"
  echo "  cd /opt/LegalMind; set -a; . deploy/.env; set +a"
  echo "  /opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py"
  echo "وإن تكرر الفشل فالتراجع الدقيق من: $BK"
  exit 1
fi
