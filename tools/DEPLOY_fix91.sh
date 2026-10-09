#!/usr/bin/env bash
# تصحيح النفاذ المؤجَّل لـ91/2026 على قانون أسواق المال + وسم البطاقات المؤجَّلة + اسم قانون الصكوك (2026-10-09)
# القناة: git show. التشغيل من ملف يدخل خلفية صامدة؛ السجل /tmp/deploy_fix91_*.log
# لا مساس بالكود ولا إعادة تشغيل خدمات. أي فشل بعد الكتابة ⇒ استرداد حرفي + إعادة فهرسة ما استُرد ⇒ ROLLED_BACK
BR="claude/inspiring-pasteur-0cpn0m"
LOG="/tmp/deploy_fix91_$(date +%s).log"
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
SAFE="/opt/legalmind-data/fix91_safe_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$SAFE"

reindex_ids() {   # كل معرّف نمطٌ حرفي في reindex_delta (بلا %)
  mapfile -t IDS < "$1"
  [ "${#IDS[@]}" -gt 0 ] || { echo "لا معرّفات للفهرسة"; return 0; }
  $HPY tools/reindex_delta.py "${IDS[@]}"
}
rollback() {
  echo "!!! تراجع: $1"
  if $HPY tools/fix_deferred_91_2026.py --restore "$SAFE/rows_before.jsonl"; then reindex_ids "$SAFE/ids.txt"
  else echo "RESTORE_FAILED — الاسترداد اليدوي من $SAFE/rows_before.jsonl"; fi
  echo "ROLLED_BACK"; exit 1
}

echo "== 1) جلب السكربت من الفرع"
git fetch -q origin "$BR" || { echo "FAIL: git fetch"; exit 1; }
git show "origin/$BR:tools/fix_deferred_91_2026.py" > tools/fix_deferred_91_2026.py.new \
  && mv -f tools/fix_deferred_91_2026.py.new tools/fix_deferred_91_2026.py || { echo "FAIL: جلب"; exit 1; }
$HPY -m py_compile tools/fix_deferred_91_2026.py || { echo "FAIL: نحو"; exit 1; }

echo "== 2) التصحيح (معاملة واحدة بحُرّاسها)"
$HPY tools/fix_deferred_91_2026.py --backup-dir "$SAFE" --ids-out "$SAFE/ids.txt" \
  || { echo "لم يُكتب شيء — توقّف"; echo "ROLLED_BACK"; exit 1; }

echo "== 3) فهرسة تفاضلية لما تغيّر نصه أو عنوانه وحده"
reindex_ids "$SAFE/ids.txt" || rollback "الفهرسة التفاضلية"

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

echo "== 5) تحقق حي من القاعدة"
$APY - <<'PYC' || rollback "التحقق الحي"
import os, psycopg
with psycopg.connect(os.environ["DATABASE_URL"]) as c, c.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id = ANY(%s) AND usable_as_citation AND "
                "verification_status <> 'superseded' AND original_text LIKE %s",
                (["legis-7-2010-m%d" % n for n in (108,109,110,111,112,113,116)], "%إلغاءٌ مُعلَّق%"))
    n = cur.fetchone()[0]; assert n == 7, "الملغاة المؤجَّلة القابلة للاستشهاد = %d" % n
    cur.execute("SELECT title, split_part(original_text, 'ـــ نصٌّ مُعلَّق', 1) FROM knowledge_objects WHERE id='legis-7-2010-m1'")
    t, body = cur.fetchone()
    assert "وزير التجارة والصناعة" in body and "2027/10/1" in t, "م1"
    cur.execute("SELECT DISTINCT metadata->>'library_card_name' FROM knowledge_objects WHERE id LIKE 'legis-90-2026-%%'")
    assert [r[0] for r in cur.fetchall()] == ["قانون الصكوك الحكومية"], "بطاقة 90/2026"
    print("م1:", t)
    print("LIVE_FIX91_OK")
PYC

echo "== 6) البطارية (فشلٌ مفرد يُعاد مرة — §17)"
B1=$($APY tools/battery_run.py 2>&1); echo "$B1" | tail -3
if ! echo "$B1" | grep -q "BATTERY_PASS"; then
  echo "-- إعادة مرة واحدة"
  B2=$($APY tools/battery_run.py 2>&1); echo "$B2" | tail -3
  echo "$B2" | grep -q "BATTERY_PASS" || rollback "البطارية سقطت مرتين"
fi

echo "== 7) تقرير الجولة التالية (قراءة خالصة — تشخيصي لا يُسقط شيئًا)"
set +e
$APY tools/fix_deferred_91_2026.py --report 2>&1 | head -150

echo ""
echo "النسخة الآمنة: $SAFE"
echo "DONE_FIX91"
