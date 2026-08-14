#!/bin/bash
# أمر آلي 12: انتظار اكتمال القراءة الجدولية ثم تحقق ذاتي حقيقي من الجودة قبل أي إعلان نجاح
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

echo "== انتظار اكتمال القراءة الجدولية (حتى 25 دقيقة) =="
for i in $(seq 1 150); do
  pgrep -f "table_reader.py" > /dev/null || break
  sleep 10
done
if pgrep -f "table_reader.py" > /dev/null; then
  echo "لا تزال تعمل بعد 25 دقيقة — لن أقاطعها، لكن هذا التقرير مبكر"
  STILL_RUNNING=1
else
  echo "انتهت المعالجة ✓"
  STILL_RUNNING=0
fi

echo ""
echo "== سجل التنفيذ الكامل =="
cat /root/tables-reingest2.log 2>/dev/null || echo "لا سجل"

echo ""
echo "== تحقق ذاتي حقيقي (لا إعلان نجاح دون دليل) =="
cat > /root/verify_tables.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

with eng.psycopg.connect(eng.database_url()) as conn, conn.cursor() as cur:
    cur.execute("""SELECT id, object_type, title, original_text FROM knowledge_objects
                   WHERE id LIKE 'TBL-الكتاب-السابع%' ORDER BY id""")
    rows = cur.fetchall()

ok = fail = 0
print("إجمالي الكائنات المستخرجة:", len(rows), flush=True)
if not rows:
    print("فحص=فشل | لا كائنات على الإطلاق — القراءة لم تنتج شيئاً", flush=True)
else:
    tables = [r for r in rows if r[1] == "regulatory_table"]
    narr = [r for r in rows if r[1] != "regulatory_table"]
    print("جداول:", len(tables), "| نصوص سردية:", len(narr), flush=True)

    # فحص جودة حقيقي: هل الجداول فعلاً جداول Markdown متماسكة، لا فوضى؟
    for oid, ot, title, text in tables[:6]:
        t = text or ""
        pipes = t.count("|")
        lines = [l for l in t.split("\n") if l.strip()]
        has_header_sep = any(re.match(r"^\s*\|?\s*:?-{2,}", l) for l in lines)
        # يجب أن يكون فيه بنية جدول حقيقية: أعمدة | متعددة عبر أسطر متعددة
        rowlike = sum(1 for l in lines if l.count("|") >= 2)
        good = pipes >= 6 and rowlike >= 2
        status = "سليم ✓" if good else "مشكوك فيه ✗"
        if good: ok += 1
        else: fail += 1
        print("  [%s] %s | أعمدة/صفوف صالحة: %d سطر | %s" % (status, title[:40], rowlike, oid[-16:]),
              flush=True)
        print("     عيّنة:", t[:180].replace("\n", " ¶ "), flush=True)

    for oid, ot, title, text in narr[:3]:
        print("  [نص سردي] %s | %s" % (title[:40], (text or "")[:120]), flush=True)

    print("\nنتيجة الفحص الذاتي: سليم=%d | مشكوك فيه=%d من أصل %d عُوينت" %
          (ok, fail, min(6, len(tables))), flush=True)

    # مطابقة الفهرس
    cur = conn.cursor()
    src_keys = {r[0].split("-P")[0] for r in []}  # غير مستخدم
    cur.execute("""SELECT DISTINCT source_key FROM knowledge_objects WHERE id LIKE 'TBL-الكتاب-السابع%'""")
    sk = cur.fetchone()
    if sk:
        cnt = eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/count",
                                 {"exact": True, "filter": {"must": [{"key": "source_key",
                                  "match": {"value": sk[0]}}]}})["result"]["count"]
        print("نقاط الفهرس لهذا المصدر:", cnt, "| كائنات القاعدة:", len(rows),
              "| مطابق:" , cnt == len(rows), flush=True)

VERDICT = "PASS" if rows and fail == 0 and ok > 0 else ("PARTIAL" if rows and ok > 0 else "FAIL")
print("\n=== الحكم النهائي: %s ===" % VERDICT, flush=True)
PYEOF
/opt/LegalMind/.venv/bin/python /root/verify_tables.py > /root/verify.log 2>&1
cat /root/verify.log

VERDICT=$(grep "الحكم النهائي" /root/verify.log | grep -o "PASS\|PARTIAL\|FAIL" || echo "UNKNOWN")

{
  echo "=== نتيجة التحقق الذاتي من القراءة الجدولية — $(date -u +%F' '%T) UTC ==="
  echo "الحكم: $VERDICT $([ "$STILL_RUNNING" = "1" ] && echo '(لا تزال المعالجة جارية — تقرير جزئي)')"
  echo ""
  cat /root/verify.log
  echo ""
  echo "-- آخر سطور سجل التنفيذ --"
  tail -15 /root/tables-reingest2.log 2>/dev/null
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشر التحقق الذاتي - الحكم: $VERDICT ====="
