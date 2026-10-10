#!/usr/bin/env bash
# رفوف مكتبة التشريعات (2026-10-09) — تسجيل رفّ كل قانون في الميتاداتا + مجلدات المتصفح على الرفوف.
# القناة: git show من فرع الجلسة (لا لصق). التشغيل من ملف يدخل خلفية صامدة؛ السجل في /tmp/deploy_shelves_*.log
# أي فشل بعد الكتابة ⇒ تراجع آلي كامل (app.py + الميتاداتا حرفيًا + إعادة تشغيل الخدمة) ⇒ ROLLED_BACK
BR="claude/inspiring-pasteur-0cpn0m"
LOG="/tmp/deploy_shelves_$(date +%s).log"
SELF="${BASH_SOURCE[0]:-}"
if [ "${1:-}" != "--worker" ] && [ -n "$SELF" ] && [ -f "$SELF" ]; then
  nohup bash "$SELF" --worker > "$LOG" 2>&1 & disown
  echo "يعمل في الخلفية — السجل: $LOG"; exit 0
fi
set -uo pipefail
cd /opt/LegalMind || { echo "FAIL: /opt/LegalMind غير موجود"; exit 1; }
set -a; . deploy/.env; set +a
PY=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
SAFE="/opt/legalmind-data/shelves_safe_$(date +%Y%m%d_%H%M%S)"
APPLIED=0; PATCHED=0

rollback() {
  echo "!!! تراجع: $1"
  if [ "$PATCHED" = 1 ]; then cp -f "$SAFE/app.py" "$APP" && echo "استُعيد app.py"; systemctl restart legalmind-admin; fi
  if [ "$APPLIED" = 1 ]; then $PY tools/apply_library_shelves.py --restore "$SAFE/metadata_before.jsonl"; fi
  echo "ROLLED_BACK"; exit 1
}

echo "== 1) جلب الملفات من الفرع"
git fetch -q origin "$BR" || { echo "FAIL: git fetch"; exit 1; }
for f in tools/apply_library_shelves.py tools/patch_browse_shelves.py taxonomy/library_shelves.json; do
  mkdir -p "$(dirname "$f")"
  git show "origin/$BR:$f" > "$f.new" && mv -f "$f.new" "$f" || { echo "FAIL: لم يُجلب $f"; exit 1; }
done
$PY -m py_compile tools/apply_library_shelves.py tools/patch_browse_shelves.py || { echo "FAIL: نحو"; exit 1; }

echo "== 2) نسخة آمنة لـ app.py — يُتحقق من وجودها قبل أي لمس"
mkdir -p "$SAFE" && cp -f "$APP" "$SAFE/app.py"
cmp -s "$APP" "$SAFE/app.py" || { echo "FAIL: النسخة الآمنة لم تُكتب"; exit 1; }
echo "النسخة الآمنة: $SAFE"

echo "== 3) تسجيل الرفوف في الميتاداتا (معاملة واحدة بحُرّاسها)"
$PY tools/apply_library_shelves.py --backup-dir "$SAFE" || { echo "لم يُكتب شيء — توقّف"; echo "ROLLED_BACK"; exit 1; }
APPLIED=1

echo "== 4) رقعة المتصفح"
$PY tools/patch_browse_shelves.py "$APP" || rollback "رقعة المتصفح"
PATCHED=1
$PY -m py_compile "$APP" || rollback "نحو app.py"

echo "== 5) إعادة تشغيل الخدمة"
systemctl restart legalmind-admin
CODE=""
for i in $(seq 1 30); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8088/api/whoami || true)
  [ "$CODE" = "401" ] && break; sleep 1
done
[ "$CODE" = "401" ] || rollback "الخدمة لم تعد (whoami=$CODE)"
echo "whoami=401 ✓"

echo "== 6) تحقق حي من المتصفح نفسه"
$PY - <<'PYCHK' || rollback "التحقق الحي"
import sys, json, os
sys.path.insert(0, "/opt/LegalMind"); sys.path.insert(0, "/opt/LegalMind/admin")
from admin import app as A
import psycopg
M = json.load(open("/opt/LegalMind/taxonomy/library_shelves.json", encoding="utf-8"))
names = [s["name"] for s in M["shelves"]]
r = A.browse_kb("laws", _="probe")
keys = [g["key"] for g in r["groups"]]
assert keys == names, "المجلدات ليست الرفوف العشرة بترتيبها: %s" % keys
total = sum(g["count"] for g in r["groups"])
with psycopg.connect(os.environ["DATABASE_URL"]) as c, c.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE object_type = ANY(%s) AND metadata ? 'library_shelf'",
                (list(A._kb.LEGISLATION_TYPES),))
    shelved = cur.fetchone()[0]
assert total == shelved, "مجموع الرفوف %d لا يساوي المُرفَّف %d" % (total, shelved)
l3 = [g["key"] for g in A.browse_kb("laws", b=names[2], _="probe")["groups"]]
assert "legis-102-2026" in l3 and "legis-20-2014" in l3, l3
l6 = A.browse_kb("laws", b=names[5], _="probe")["groups"]
assert any(g["key"] == "LEG-75-2026" for g in l6), "LEG-75 غير ظاهر"
pr = [g["key"] for g in A.browse_kb("principles", _="probe")["groups"]]
assert "مدني" in pr and not set(pr) & set(names), "تصفّح المبادئ تغيّر: %s" % pr
for g in r["groups"]:
    print("  %-48s %6d" % (g["key"], g["count"]))
print("LIVE_BROWSE_OK — %d كائنًا في %d رفوف" % (total, len(keys)))
PYCHK

echo "== 7) البطارية (فشلٌ مفرد يُعاد مرة — بروتوكول §17)"
B1=$($PY tools/battery_run.py 2>&1); echo "$B1" | tail -4
if ! echo "$B1" | grep -q "BATTERY_PASS"; then
  echo "-- إعادة مرة واحدة"
  B2=$($PY tools/battery_run.py 2>&1); echo "$B2" | tail -4
  echo "$B2" | grep -q "BATTERY_PASS" || rollback "البطارية سقطت مرتين"
fi

echo ""
echo "النسخة الآمنة: $SAFE"
echo "DONE_SHELVES"
