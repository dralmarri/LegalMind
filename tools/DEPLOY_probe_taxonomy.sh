#!/bin/bash
# مسبار قراءة فقط: تبويب المصدر في القاعدة وفي حمولة Qdrant — SELECT وقراءة Qdrant حصرًا. النجاح = PROBE_TAXONOMY_OK
set -euo pipefail
BR=claude/inspiring-pasteur-0cpn0m
cd /opt/LegalMind || { echo "FAIL: /opt/LegalMind"; exit 1; }
git fetch -q origin "$BR"
mkdir -p tools/topic_channel
f=tools/topic_channel/probe_taxonomy.py
git show "origin/$BR:$f" > "$f.new" && mv -f "$f.new" "$f"
if grep -qE '\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE)[[:space:]]|"PUT"|/points/delete' "$f"; then
  echo "WRITE_STATEMENT_FOUND — أُوقف"; exit 1; fi
set -a; . deploy/.env; set +a
/opt/LegalMind/admin/.venv/bin/python "$f"
