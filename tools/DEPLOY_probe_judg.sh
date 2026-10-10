#!/bin/bash
# مسبار قراءة فقط: هل مبادئ ملفات الوورد (2026-10-10) موجودة في القاعدة؟ — SELECT حصرًا، لا يكتب شيئًا.
# القناة: git show من الفرع. يستغرق نحو دقيقة. النجاح = PROBE_JUDG_OK
set -euo pipefail
BR=claude/inspiring-pasteur-0cpn0m
cd /opt/LegalMind || { echo "FAIL: /opt/LegalMind"; exit 1; }
git fetch -q origin "$BR"
mkdir -p tools/judg_probe
for f in tools/probe_judg_dedup.py tools/judg_probe/items.json; do
  git show "origin/$BR:$f" > "$f.new" && mv -f "$f.new" "$f"
done
# حارس: المسبار لا يحمل أي جملة كتابة
if grep -qE '\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE)[[:space:]]' tools/probe_judg_dedup.py; then
  echo "WRITE_STATEMENT_FOUND — أُوقف"; exit 1; fi
set -a; . deploy/.env; set +a
/opt/LegalMind/admin/.venv/bin/python tools/probe_judg_dedup.py
