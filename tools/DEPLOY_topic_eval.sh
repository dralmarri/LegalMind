#!/bin/bash
# تقييم قناة الاسترجاع بالموضوع — قياس خالص: app.py الحي لا يُمسّ (نسخة مرقّعة مؤقتة تُحذف)، ولا كتابة في القاعدة.
# 32 سؤالًا × ذراعان (القناة مطفأة/مشغّلة). يعمل في الخلفية الصامدة (~40–60 دقيقة).
# المتابعة: tail -5 /tmp/topic_eval.log — والنهاية سطر DONE_TOPIC_EVAL مع TOPIC_EVAL_PASS أو TOPIC_EVAL_FAIL.
set -uo pipefail
LOG=/tmp/topic_eval.log
SELF="${BASH_SOURCE[0]:-}"
if [ "${1:-}" != "--worker" ] && [ -n "$SELF" ] && [ -f "$SELF" ]; then
  nohup bash "$SELF" --worker > "$LOG" 2>&1 & disown
  echo "بدأ في الخلفية — المتابعة: tail -5 $LOG"; exit 0
fi
BR=claude/inspiring-pasteur-0cpn0m
cd /opt/LegalMind || { echo "FAIL: /opt/LegalMind"; exit 1; }
git fetch -q origin "$BR" || { echo "FETCH_FAIL"; exit 1; }
mkdir -p tools/topic_channel
for f in tools/topic_channel/patch_topic_channel.py tools/topic_channel/eval_topic_channel.py tools/topic_channel/bench.json; do
  git show "origin/$BR:$f" > "$f.new" && mv -f "$f.new" "$f" || { echo "SHOW_FAIL $f"; exit 1; }
done
if grep -qE '\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE)[[:space:]]' tools/topic_channel/eval_topic_channel.py; then
  echo "WRITE_STATEMENT_FOUND — أُوقف"; exit 1; fi
MD5_BEFORE=$(md5sum admin/app.py | cut -d' ' -f1)
set -a; . deploy/.env; set +a
/opt/LegalMind/admin/.venv/bin/python tools/topic_channel/eval_topic_channel.py
RC=$?
MD5_AFTER=$(md5sum admin/app.py | cut -d' ' -f1)
[ "$MD5_BEFORE" = "$MD5_AFTER" ] && echo "APP_UNTOUCHED" || echo "APP_CHANGED — تحقق فورًا"
ls admin/_app_topic_eval.py 2>/dev/null && echo "TEMP_LEFT" || echo "TEMP_CLEAN"
echo "RC=$RC"
echo DONE_TOPIC_EVAL
