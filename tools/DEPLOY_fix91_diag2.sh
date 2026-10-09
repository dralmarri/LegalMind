#!/usr/bin/env bash
# جولة تشخيص ثانية لا اعتماد (2026-10-09): هل يرفع تصحيح 91/2026 معدّل سقوط الحالة 15؟
# تقرأ تشخيص القاعدة الأصلية (30 جولة، محفوظ سلفًا في /tmp/diag15b_*.log)، ثم تطبّق التصحيح
# مؤقتًا وتشغّل البطارية مرتين بمخرج كامل وتشخّص الحالة 15 عشرين جولة وكل حالة ساقطة عشرًا،
# ثم تسترد القاعدة **دائمًا**.
BR="claude/inspiring-pasteur-0cpn0m"
LOG="/tmp/deploy_fix91diag2_$(date +%s).log"
SELF="${BASH_SOURCE[0]:-}"
if [ "${1:-}" != "--worker" ] && [ -n "$SELF" ] && [ -f "$SELF" ]; then
  nohup bash "$SELF" --worker > "$LOG" 2>&1 & disown
  echo "يعمل في الخلفية — السجل: $LOG"; exit 0
fi
set -uo pipefail
cd /opt/LegalMind || { echo "FAIL"; exit 1; }
set -a; . deploy/.env; set +a
HPY=/opt/LegalMind/.venv/bin/python
APY=/opt/LegalMind/admin/.venv/bin/python
SAFE="/opt/legalmind-data/fix91diag2_$(date +%Y%m%d_%H%M%S)"; mkdir -p "$SAFE"
reindex_ids() { mapfile -t IDS < "$1"; [ "${#IDS[@]}" -gt 0 ] && $HPY tools/reindex_delta.py "${IDS[@]}" 2>&1 | tail -1; }
summ() { grep -E "الحضور|مرشَّح يُقص|غائب كليًا|رتب المتجه|DIAG_CASE" "$1"; }

git fetch -q origin "$BR" || { echo "FAIL: fetch"; exit 1; }
for f in tools/fix_deferred_91_2026.py tools/diag_battery_case.py; do
  git show "origin/$BR:$f" > "$f.new" && mv -f "$f.new" "$f" || { echo "FAIL: $f"; exit 1; }
done

echo "== 0) الحالة 15 على القاعدة الأصلية (تشخيص الثلاثين جولة المحفوظ)"
B=$(ls -1t /tmp/diag15b_*.log 2>/dev/null | head -1)
if [ -n "$B" ]; then echo "السجل: $B"; summ "$B"; else echo "لا سجل محفوظ — يُشغَّل الآن 20 جولة على الأصل"
  $APY tools/diag_battery_case.py --case 15 --runs 20 > "$SAFE/base15.txt" 2>&1; summ "$SAFE/base15.txt"; fi

echo "== 1) تطبيق التصحيح مؤقتًا"
$HPY tools/fix_deferred_91_2026.py --backup-dir "$SAFE" --ids-out "$SAFE/ids.txt" > "$SAFE/fix.txt" 2>&1
grep -q "FIX91_APPLIED" "$SAFE/fix.txt" || { grep -E "ROLLED|FAIL" "$SAFE/fix.txt"; echo "لم يُطبَّق — لا شيء يُسترد"; exit 1; }
reindex_ids "$SAFE/ids.txt"

echo "== 2) البطارية مرتين بعد التصحيح"
for R in 1 2; do
  $APY tools/battery_run.py > "$SAFE/battery$R.txt" 2>&1
  echo "-- الجولة $R"; grep -E "^✗|البطاقة|BATTERY_" "$SAFE/battery$R.txt"
done

echo "== 3) الحالة 15 بعد التصحيح (20 جولة)"
$APY tools/diag_battery_case.py --case 15 --runs 20 > "$SAFE/fixed15.txt" 2>&1
summ "$SAFE/fixed15.txt"

echo "== 4) أي حالة أخرى ساقطة (10 جولات لكلٍّ منها)"
cat "$SAFE"/battery1.txt "$SAFE"/battery2.txt > "$SAFE/battery_all.txt"
$APY - "$SAFE/battery_all.txt" > "$SAFE/failed.txt" <<'PYC'
import json, sys
names = [c["name"] for c in json.load(open("/opt/LegalMind/battery.json"))]
seen = set()
for line in open(sys.argv[1], encoding="utf-8"):
    if line.startswith("✗"):
        nm = line[1:].split("|")[0].strip()
        for i, n in enumerate(names, 1):
            if n == nm and i != 15 and i not in seen:
                seen.add(i); print(i)
PYC
for N in $(cat "$SAFE/failed.txt"); do
  echo "-- الحالة $N"
  $APY tools/diag_battery_case.py --case "$N" --runs 10 > "$SAFE/fixed$N.txt" 2>&1; summ "$SAFE/fixed$N.txt"
done
[ -s "$SAFE/failed.txt" ] || echo "لا حالة أخرى ساقطة"

echo "== 5) الاسترداد (دائمًا)"
$HPY tools/fix_deferred_91_2026.py --restore "$SAFE/rows_before.jsonl" && reindex_ids "$SAFE/ids.txt"
echo "الملفات: $SAFE"
echo "DIAG91B_DONE"
