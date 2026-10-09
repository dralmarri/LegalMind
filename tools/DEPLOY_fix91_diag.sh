#!/usr/bin/env bash
# جولة تشخيص لا اعتماد (2026-10-09): تُطبّق تصحيح 91/2026، وتحفظ مخرج البطارية كاملًا،
# وتشخّص كل حالة ساقطة بعشر جولات، ثم تسترد القاعدة كما كانت **دائمًا** — نجحت البطارية أم سقطت.
# السبب: دفعة DEPLOY_fix91 سقطت 14/15 مرتين ولم يُحفظ سطر الحالة الساقطة (عيب في ملف النشر).
BR="claude/inspiring-pasteur-0cpn0m"
LOG="/tmp/deploy_fix91diag_$(date +%s).log"
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
SAFE="/opt/legalmind-data/fix91diag_$(date +%Y%m%d_%H%M%S)"; mkdir -p "$SAFE"
reindex_ids() { mapfile -t IDS < "$1"; [ "${#IDS[@]}" -gt 0 ] && $HPY tools/reindex_delta.py "${IDS[@]}" | tail -1; }

git fetch -q origin "$BR" || { echo "FAIL: fetch"; exit 1; }
for f in tools/fix_deferred_91_2026.py tools/diag_battery_case.py; do
  git show "origin/$BR:$f" > "$f.new" && mv -f "$f.new" "$f" || { echo "FAIL: $f"; exit 1; }
done

echo "== 1) تطبيق التصحيح مؤقتًا"
$HPY tools/fix_deferred_91_2026.py --backup-dir "$SAFE" --ids-out "$SAFE/ids.txt" > "$SAFE/fix.txt" 2>&1
grep -E "APPLIED|ROLLED|FAIL|UNEXPECTED|IDS_FOR" "$SAFE/fix.txt"
grep -q "FIX91_APPLIED" "$SAFE/fix.txt" || { echo "لم يُطبَّق — لا شيء يُسترد"; exit 1; }
reindex_ids "$SAFE/ids.txt"

echo "== 2) البطارية — المخرج كاملًا في $SAFE/battery.txt"
$APY tools/battery_run.py > "$SAFE/battery.txt" 2>&1
grep -E "^✗|البطاقة|BATTERY_" "$SAFE/battery.txt"

echo "== 3) تشخيص كل حالة ساقطة (10 جولات لكلٍّ منها)"
$APY - "$SAFE/battery.txt" > "$SAFE/failed_cases.txt" <<'PYC'
import json, sys
names = [c["name"] for c in json.load(open("/opt/LegalMind/battery.json"))]
for line in open(sys.argv[1], encoding="utf-8"):
    if line.startswith("✗"):
        nm = line[1:].split("|")[0].strip()
        for i, n in enumerate(names, 1):
            if n == nm:
                print(i)
PYC
for N in $(cat "$SAFE/failed_cases.txt"); do
  echo "-- الحالة $N"
  $APY tools/diag_battery_case.py --case "$N" --runs 10 > "$SAFE/diag_case$N.txt" 2>&1
  grep -E "^جولة|الحضور|مرشَّح يُقص|غائب كليًا|رتب المتجه|الحكم|DIAG_CASE" "$SAFE/diag_case$N.txt"
done
[ -s "$SAFE/failed_cases.txt" ] || echo "لا حالة ساقطة في هذه الجولة"

echo "== 4) الاسترداد (دائمًا)"
$HPY tools/fix_deferred_91_2026.py --restore "$SAFE/rows_before.jsonl" && reindex_ids "$SAFE/ids.txt"
echo "الملفات: $SAFE"
echo "DIAG91_DONE"
