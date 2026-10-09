#!/usr/bin/env bash
# ضمّ 91/2026 وتعليمات كفاية رأس المال القديمة إلى مجموعة قانون أسواق المال + بطاقة 78/2026 (2026-10-09)
# القناة: git show. التشغيل من ملف يدخل خلفية صامدة؛ السجل /tmp/deploy_merge_cma_*.log
# ميتاداتا عرض وحدها: لا نص ولا عنوان ولا كود ⇒ لا فهرسة ولا إعادة تشغيل خدمات.
# أي فشل بعد الكتابة ⇒ استرداد حرفي للميتاداتا وللخريطة ⇒ ROLLED_BACK
BR="claude/inspiring-pasteur-0cpn0m"
LOG="/tmp/deploy_merge_cma_$(date +%s).log"
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
SAFE="/opt/legalmind-data/merge_cma_safe_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$SAFE/merge" "$SAFE/shelves"
MERGED=0; SHELVED=0

rollback() {
  echo "!!! تراجع: $1"
  if [ "$SHELVED" = 1 ]; then $APY tools/apply_library_shelves.py --restore "$SAFE/shelves/metadata_before.jsonl"; fi
  if [ "$MERGED" = 1 ]; then $HPY tools/merge_cma_group.py --restore "$SAFE/merge/metadata_before.jsonl"; fi
  cp -f "$SAFE/library_shelves.json" taxonomy/library_shelves.json && echo "استُعيدت الخريطة"
  echo "ROLLED_BACK"; exit 1
}

echo "== 1) جلب الملفات من الفرع"
cp -f taxonomy/library_shelves.json "$SAFE/library_shelves.json" || { echo "FAIL: نسخ الخريطة"; exit 1; }
git fetch -q origin "$BR" || { echo "FAIL: git fetch"; exit 1; }
for f in tools/merge_cma_group.py tools/fix_deferred_91_2026.py tools/apply_library_shelves.py taxonomy/library_shelves.json; do
  git show "origin/$BR:$f" > "$f.new" && mv -f "$f.new" "$f" || { echo "FAIL: جلب $f"; cp -f "$SAFE/library_shelves.json" taxonomy/library_shelves.json; exit 1; }
done
for f in tools/merge_cma_group.py tools/fix_deferred_91_2026.py tools/apply_library_shelves.py; do
  $HPY -m py_compile "$f" || { echo "FAIL: نحو $f"; cp -f "$SAFE/library_shelves.json" taxonomy/library_shelves.json; exit 1; }
done

echo "== 2) الضمّ (معاملة واحدة بحُرّاسها)"
$HPY tools/merge_cma_group.py --backup-dir "$SAFE/merge" || rollback "الضمّ لم يُطبَّق"
MERGED=1

echo "== 3) الرفوف بالخريطة الجديدة — بوابة اتساق (UNSHELVED/SHELF_KEY_MISSING)"
SHELVED=1
$APY tools/apply_library_shelves.py --backup-dir "$SAFE/shelves" > "$SAFE/shelves.txt" 2>&1
grep -E "SHELVES_APPLIED|ROLLED|UNSHELVED|SHELF_KEY" "$SAFE/shelves.txt"
grep -q "SHELVES_APPLIED" "$SAFE/shelves.txt" || rollback "الرفوف"

echo "== 4) تحقق حي من المتصفح نفسه"
$APY - <<'PYCHK' || rollback "التحقق الحي"
import sys, json
sys.path.insert(0, "/opt/LegalMind"); sys.path.insert(0, "/opt/LegalMind/admin")
from admin import app as A
M = json.load(open("/opt/LegalMind/taxonomy/library_shelves.json", encoding="utf-8"))
com = [s["name"] for s in M["shelves"] if s["order"] == 10][0]
l2 = {g["key"]: g for g in A.browse_kb("laws", b=com, _="probe")["groups"]}
assert "cma-authority-unified" in l2, "أسواق المال غابت عن رفّها"
assert "legis-91-2026" not in l2 and "cap-adequacy-legacy" not in l2, "بقيت بطاقة مستقلة: %s" % sorted(l2)
assert "ستة أشهر" in (l2["legis-78-2026"]["name"] or ""), "بطاقة 78: %s" % l2["legis-78-2026"]["name"]
print("بطاقة أسواق المال: %s (%d)" % (l2["cma-authority-unified"]["name"], l2["cma-authority-unified"]["count"]))
print("بطاقة 78/2026:   %s" % l2["legis-78-2026"]["name"])
parts = A.browse_kb("laws", b=com, group="cma-authority-unified", _="probe")
assert parts["mode"] == "groups", parts["mode"]
keys = [g["key"] for g in parts["groups"]]
assert any("91/2026" in k and "2027/10/1" in k for k in keys), "جزء 91 غائب"
assert any("نسخة سابقة" in k for k in keys), "جزء النسخة السابقة غائب"
for g in parts["groups"]:
    print("  %-90s %5d" % (g["key"], g["count"]))
print("LIVE_BROWSE_OK")
PYCHK

echo "== 5) البطارية (فشلٌ مفرد يُعاد مرة — §17)"
$APY tools/battery_run.py > "$SAFE/battery1.txt" 2>&1; grep -E "^✗|البطاقة|BATTERY_" "$SAFE/battery1.txt"
if ! grep -q "BATTERY_PASS" "$SAFE/battery1.txt"; then
  echo "-- إعادة مرة واحدة"
  $APY tools/battery_run.py > "$SAFE/battery2.txt" 2>&1; grep -E "^✗|البطاقة|BATTERY_" "$SAFE/battery2.txt"
  grep -q "BATTERY_PASS" "$SAFE/battery2.txt" || rollback "البطارية سقطت مرتين"
fi

echo ""
echo "النسخة الآمنة: $SAFE"
echo "DONE_MERGE_CMA"
