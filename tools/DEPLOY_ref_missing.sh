#!/usr/bin/env bash
# إدخال سبعة قوانين غائبة من «مجموعة التشريعات» (التعديلات حتى 2026/10/5) — 505 كائنًا (2026-10-09، 505 منذ فصل م8 مكرر 1 من 61/2015 في 2026-10-10)
# القناة: git show. التشغيل من ملف يدخل خلفية صامدة؛ السجل /tmp/deploy_refmissing_*.log
# لا كود ولا إعادة تشغيل خدمات. فهرسة تفاضلية لما أُدخل وحده (لا فهرسة كاملة — §10).
# أي فشل بعد الكتابة ⇒ استرداد الرفوف ← حذف ما أدخلته الدفعة (PG + Qdrant) ← استعادة لقطة الصفوف القائمة
# (إعادة التشغيل تُحدِّث صفوف التشغيلة السابقة — ON CONFLICT DO UPDATE) ← فهرسة تفاضلية تعيد Qdrant إلى نصوصها ⇒ ROLLED_BACK
BR="claude/inspiring-pasteur-0cpn0m"
LOG="/tmp/deploy_refmissing_$(date +%s).log"
SELF="${BASH_SOURCE[0]:-}"
if [ "${1:-}" != "--worker" ] && [ -n "$SELF" ] && [ -f "$SELF" ]; then
  nohup bash "$SELF" --worker > "$LOG" 2>&1 & disown
  echo "يعمل في الخلفية — السجل: $LOG"; exit 0
fi
set -uo pipefail
cd /opt/LegalMind || { echo "FAIL: /opt/LegalMind"; exit 1; }
set -a; . deploy/.env; set +a
HPY=/opt/LegalMind/.venv/bin/python
APY=/opt/LegalMind/admin/.venv/bin/python
SAFE="/opt/legalmind-data/refmissing_safe_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$SAFE/shelves"
INGESTED=0; SHELVED=0; REINDEXED=0
PATS=('legis-12-1963-%' 'legis-120-2023-%' 'legis-15-1959-%' 'legis-63-2015-%' 'legis-37-2014-%' 'legis-61-2015-%' 'legis-70-2020-%')

rollback() {
  echo "!!! تراجع: $1"
  if [ "$SHELVED" = 1 ]; then $APY tools/apply_library_shelves.py --restore "$SAFE/shelves/metadata_before.jsonl"; fi
  if [ "$INGESTED" = 1 ]; then
    $HPY tools/ingest_reference_missing_20261005.py --rollback "$SAFE/new_ids.txt" \
       || echo "ROLLBACK_INCOMPLETE — راجع $SAFE/new_ids.txt"
    $HPY tools/ingest_reference_missing_20261005.py --restore "$SAFE/snapshot.jsonl" \
       || echo "RESTORE_INCOMPLETE — راجع $SAFE/snapshot.jsonl"
    if [ "$REINDEXED" = 1 ]; then
      HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $HPY tools/reindex_delta.py "${PATS[@]}" > "$SAFE/reindex_restore.txt" 2>&1
      grep -q "REINDEX_DELTA_OK" "$SAFE/reindex_restore.txt" && echo "أُعيدت فهرسة النصوص المستعادة" \
        || echo "REINDEX_RESTORE_FAILED — شغّل reindex_delta يدويًا على البادئات السبع"
    fi
  fi
  cp -f "$SAFE/library_shelves.json" taxonomy/library_shelves.json && echo "استُعيدت الخريطة"
  echo "ROLLED_BACK"; exit 1
}

echo "== 1) جلب الملفات من الفرع"
cp -f taxonomy/library_shelves.json "$SAFE/library_shelves.json" || { echo "FAIL: نسخ الخريطة"; exit 1; }
git fetch -q origin "$BR" || { echo "FAIL: git fetch"; exit 1; }
for f in tools/ingest_reference_missing_20261005.py tools/apply_library_shelves.py taxonomy/library_shelves.json; do
  git show "origin/$BR:$f" > "$f.new" && mv -f "$f.new" "$f" \
    || { echo "FAIL: جلب $f"; cp -f "$SAFE/library_shelves.json" taxonomy/library_shelves.json; exit 1; }
done
for f in tools/ingest_reference_missing_20261005.py tools/apply_library_shelves.py; do
  $HPY -m py_compile "$f" || { echo "FAIL: نحو $f"; cp -f "$SAFE/library_shelves.json" taxonomy/library_shelves.json; exit 1; }
done

echo "== 2) الإدخال (معاملة واحدة بحُرّاسها)"
$HPY tools/ingest_reference_missing_20261005.py --ids-out "$SAFE/new_ids.txt" --snapshot-out "$SAFE/snapshot.jsonl" > "$SAFE/ingest.txt" 2>&1
cat "$SAFE/ingest.txt" | tail -14
grep -q "INGEST_REFMISSING_OK" "$SAFE/ingest.txt" || { echo "الإدخال لم يكتمل — المعاملة تراجعت وحدها، لا شيء كُتب"; cp -f "$SAFE/library_shelves.json" taxonomy/library_shelves.json; echo "ROLLED_BACK"; exit 1; }
INGESTED=1

echo "== 3) فهرسة تفاضلية للبادئات السبع وحدها"
REINDEXED=1
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $HPY tools/reindex_delta.py "${PATS[@]}" > "$SAFE/reindex.txt" 2>&1
tail -3 "$SAFE/reindex.txt"
grep -q "REINDEX_DELTA_OK" "$SAFE/reindex.txt" || rollback "الفهرسة التفاضلية"

echo "== 4) اتساق PG/Qdrant"
$HPY - <<'PYC' || rollback "الاتساق"
import os, sys, psycopg
sys.path.insert(0, "/opt/LegalMind"); os.chdir("/opt/LegalMind")
from engine import legalmind_engine as eng
with psycopg.connect(os.environ["DATABASE_URL"]) as c, c.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects"); pg = cur.fetchone()[0]
r = eng.qdrant_request("POST", f"/collections/{eng.COLLECTION}/points/count", {"exact": True})
qd = (r.get("result") or {}).get("count")
print("PG=%s Qdrant=%s" % (pg, qd))
assert pg == qd, "عدم اتساق"
print("CONSISTENT_OK")
PYC

echo "== 5) الرفوف بالخريطة الجديدة (القوانين السبعة في رفوف المرجع)"
SHELVED=1
$APY tools/apply_library_shelves.py --backup-dir "$SAFE/shelves" > "$SAFE/shelves.txt" 2>&1
grep -E "SHELVES_APPLIED|ROLLED|UNSHELVED|SHELF_KEY" "$SAFE/shelves.txt"
grep -q "SHELVES_APPLIED" "$SAFE/shelves.txt" || rollback "الرفوف"

echo "== 6) تحقق حي من المتصفح نفسه"
$APY - <<'PYCHK' || rollback "التحقق الحي"
import sys, json
sys.path.insert(0, "/opt/LegalMind"); sys.path.insert(0, "/opt/LegalMind/admin")
from admin import app as A
M = json.load(open("/opt/LegalMind/taxonomy/library_shelves.json", encoding="utf-8"))
name = {s["order"]: s["name"] for s in M["shelves"]}
want = {1: ["legis-12-1963", "legis-120-2023", "legis-15-1959"],
        3: ["legis-63-2015", "legis-37-2014", "legis-61-2015"], 5: ["legis-70-2020"]}
for o, keys in want.items():
    g = {x["key"]: x for x in A.browse_kb("laws", b=name[o], _="probe")["groups"]}
    for k in keys:
        assert k in g, "%s غائب عن رفّ %s" % (k, name[o])
        print("  %-16s %4d  %s" % (k, g[k]["count"], g[k]["name"]))
print("LIVE_BROWSE_OK")
PYCHK

echo "== 7) اختبار استرجاع حي (تشخيصي — لا يُسقط شيئًا ولا يُوقف ما بعده)"
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $HPY - <<'PYTEST'
import sys, os, subprocess, json
sys.path.insert(0, "/opt/LegalMind"); os.chdir("/opt/LegalMind")
from engine import legalmind_engine as eng
PY = "/opt/LegalMind/.venv/bin/python"
CASES = [("شروط منح الجنسية الكويتية بالتجنس وسحبها وإسقاطها", "legis-15-1959-"),
         ("الاستجواب الموجه إلى رئيس مجلس الوزراء أو الوزراء في مجلس الأمة", "legis-12-1963-"),
         ("الدخول غير المشروع إلى نظام معلوماتي أو حاسب آلي", "legis-63-2015-"),
         ("المسؤولية الطبية والخطأ الطبي وحقوق المريض", "legis-70-2020-"),
         ("الطعن في الجداول الانتخابية والمفوضية العامة للانتخابات", "legis-120-2023-"),
         ("حفظ تسجيلات كاميرات المراقبة الأمنية في المنشآت", "legis-61-2015-"),
         ("ترخيص شبكات وخدمات الاتصالات وإدارة الترددات", "legis-37-2014-")]
ok = 0
for q, want in CASES:
    p = subprocess.run([PY, "engine/embed_query_cli.py"], input=q, capture_output=True, text=True,
                       env=dict(os.environ), timeout=240)
    vec = json.loads((p.stdout or "").strip() or "[]")
    if not vec:
        print("  EMBED_EMPTY «%s»" % q[:40]); continue
    r = eng.qdrant_request("POST", "/collections/%s/points/search" % eng.COLLECTION,
          {"vector": vec, "limit": 6, "with_payload": True,
           "filter": {"must": [{"key": "object_type", "match": {"any": [
             "legislation_article", "legislation_issuing_article", "legislation_preamble"]}}]}})
    hits = [(h["score"], h["payload"]["object_id"]) for h in r["result"]]
    hit = any(o.startswith(want) for _, o in hits); ok += hit
    print("  «%s» -> %s | %s" % (q[:46], "OK" if hit else "MISS", ", ".join("%.3f %s" % x for x in hits[:2])))
print("RETRIEVAL %d/%d" % (ok, len(CASES)))
PYTEST

echo "== 8) البطارية (فشلٌ مفرد يُعاد مرة — §17)"
$APY tools/battery_run.py > "$SAFE/battery1.txt" 2>&1; grep -E "^✗|البطاقة|BATTERY_" "$SAFE/battery1.txt"
if ! grep -q "BATTERY_PASS" "$SAFE/battery1.txt"; then
  echo "-- إعادة مرة واحدة"
  $APY tools/battery_run.py > "$SAFE/battery2.txt" 2>&1; grep -E "^✗|البطاقة|BATTERY_" "$SAFE/battery2.txt"
  grep -q "BATTERY_PASS" "$SAFE/battery2.txt" || rollback "البطارية سقطت مرتين"
fi

echo ""
echo "النسخة الآمنة: $SAFE"
echo "DONE_REFMISSING"
