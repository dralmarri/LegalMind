#!/bin/bash
# أمر آلي 6: إصلاح عطل حرج — bump() كانت تفشل بخطأ postgres في كل استدعاء منذ الإطلاق
# (القاعدة والفهرس متطابقان بلا أي تحرك منذ 6 ساعات = صفر تقدم فعلي)
set -e

python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
p = "/opt/LegalMind/tools/reviewer.py"
src = open(p, encoding="utf-8").read()

OLD = '''    def bump(oid, note=""):
        cur.execute("""UPDATE knowledge_objects
                       SET metadata = metadata || jsonb_build_object(
                             'review_attempts', (coalesce(metadata->>'review_attempts','0')::int + 1),
                             'review_last_note', %s)
                       WHERE id=%s""", (note[:200], oid))'''

NEW = '''    def bump(oid, note=""):
        cur.execute("""UPDATE knowledge_objects
                       SET metadata = metadata || jsonb_build_object(
                             'review_attempts', (coalesce(metadata->>'review_attempts','0')::int + 1),
                             'review_last_note', %s::text)
                       WHERE id = %s::text""", (str(note)[:200], str(oid)))'''

assert OLD in src, "لم أجد الدالة المتوقعة — ربما أُصلحت مسبقاً"
src = src.replace(OLD, NEW, 1)
open(p, "w", encoding="utf-8").write(src)
print("أُصلح خطأ نوع البارامتر في bump() ✓")
PYEOF

/opt/LegalMind/.venv/bin/python -m py_compile /opt/LegalMind/tools/reviewer.py && echo "الكود سليم ✓"

echo ""
echo "== تشغيل تجريبي مباشر (لا cron) لرؤية أول جولة حقيقية فوراً =="
set -a; source /opt/LegalMind/deploy/.env; set +a
timeout 280 /opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/reviewer.py > /root/reviewer-test.log 2>&1 || true
tail -40 /root/reviewer-test.log

echo ""
echo "== حالة القاعدة بعد الاختبار =="
docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
  "SELECT verification_status, count(*) FROM knowledge_objects GROUP BY 1 ORDER BY 2 DESC;"

# نشر النتيجة الحقيقية الآن
CODE=$(curl -s -o /tmp/ac2.json -w '%{http_code}' https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" -H 'anthropic-version: 2023-06-01' \
  -H 'content-type: application/json' \
  -d '{"model":"claude-sonnet-5","max_tokens":8,"messages":[{"role":"user","content":"hi"}]}')
{
  echo "=== إصلاح العطل القاتل — $(date -u +%F' '%T) UTC ==="
  echo "السبب: bump() كانت تفشل بخطأ postgres في كل استدعاء — 0 تقدم منذ 02:19 UTC"
  echo "الإصلاح: تحديد نوع البارامتر النصي صراحة ✓"
  echo ""
  echo "محرك القراءة: $([ "$CODE" = "200" ] && echo 'يعمل ✓' || echo "متوقف ✗ (رمز $CODE)")"
  [ "$CODE" != "200" ] && { head -c 300 /tmp/ac2.json; echo; }
  echo ""
  echo "-- نتيجة أول جولة حقيقية بعد الإصلاح --"
  tail -40 /root/reviewer-test.log
  echo ""
  echo "-- حالة القاعدة الآن --"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
    "SELECT verification_status, count(*) FROM knowledge_objects GROUP BY 1 ORDER BY 2 DESC;"
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
rm -f /tmp/ac2.json
echo "===== نُشرت نتيجة الإصلاح الحقيقية ====="
