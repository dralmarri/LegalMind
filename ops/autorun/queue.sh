#!/bin/bash
# أمر آلي 15: verify_tables.py كان يبحث بنمط معرّف خاطئ (TBL-الكتاب...) فأعلن فشلاً كاذباً
# رغم أن السجل نفسه أثبت: أُدرج 449 كائناً وفُهرست 448 نقطة بنجاح فعلي
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

cat > /root/verify_tables2.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re, hashlib, os
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

PATH = "/opt/legalmind-ingest/inbox/BATCH-20260813-223443-937A1650__الكتاب-السابع-عشر-اسواق-المال.pdf"
SRC_KEY = "SRC-" + hashlib.sha256(os.path.basename(PATH).encode()).hexdigest()[:20].upper()
print("مفتاح المصدر المُعاد حسابه:", SRC_KEY, flush=True)

with eng.psycopg.connect(eng.database_url()) as conn, conn.cursor() as cur:
    cur.execute("""SELECT id, object_type, title, original_text FROM knowledge_objects
                   WHERE source_key=%s ORDER BY id""", (SRC_KEY,))
    rows = cur.fetchall()

print("إجمالي الكائنات المستخرجة (بالبحث الصحيح عبر source_key):", len(rows), flush=True)
if not rows:
    print("فحص=فشل حقيقي — لا كائنات لهذا المصدر", flush=True)
    print("\n=== الحكم النهائي: FAIL ===", flush=True)
else:
    tables = [r for r in rows if r[1] == "regulatory_table"]
    narr = [r for r in rows if r[1] != "regulatory_table"]
    print("جداول:", len(tables), "| نصوص سردية/تعريفات:", len(narr), flush=True)

    ok = fail = 0
    sample = tables[:8] if tables else []
    for oid, ot, title, text in sample:
        t = text or ""
        pipes = t.count("|")
        lines = [l for l in t.split("\n") if l.strip()]
        rowlike = sum(1 for l in lines if l.count("|") >= 2)
        good = pipes >= 6 and rowlike >= 2
        status = "سليم ✓" if good else "مشكوك فيه ✗"
        if good: ok += 1
        else: fail += 1
        print("  [%s] %s | أسطر جدولية: %d | %s" % (status, title[:45], rowlike, oid[-16:]), flush=True)
        print("     عيّنة:", t[:220].replace("\n", " ¶ "), flush=True)

    print("\nعيّنة من النصوص السردية:", flush=True)
    for oid, ot, title, text in narr[:4]:
        print("  -", title[:45], "|", (text or "")[:100], flush=True)

    print("\nنتيجة فحص عيّنة الجداول: سليم=%d | مشكوك فيه=%d من %d" % (ok, fail, len(sample)), flush=True)

    cnt = eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/count",
                             {"exact": True, "filter": {"must": [{"key": "source_key",
                              "match": {"value": SRC_KEY}}]}})["result"]["count"]
    print("نقاط الفهرس لهذا المصدر:", cnt, "| كائنات القاعدة:", len(rows),
          "| الفارق:", len(rows) - cnt, flush=True)

    VERDICT = "PASS" if (tables and fail == 0 and abs(len(rows) - cnt) <= 2) else \
              ("PARTIAL" if rows else "FAIL")
    print("\n=== الحكم النهائي: %s ===" % VERDICT, flush=True)
PYEOF
/opt/LegalMind/.venv/bin/python /root/verify_tables2.py > /root/verify4.log 2>&1
cat /root/verify4.log
VERDICT=$(grep "الحكم النهائي" /root/verify4.log | grep -o "PASS\|PARTIAL\|FAIL" || echo "UNKNOWN")

{
  echo "=== تصحيح فحص التحقق + النتيجة الحقيقية — $(date -u +%F' '%T) UTC ==="
  echo "الحكم: $VERDICT"
  echo "(الفحص السابق أعلن FAIL كاذباً بسبب خطأ في نمط البحث داخل أداة التحقق نفسها — ليس في القراءة الجدولية)"
  echo ""
  cat /root/verify4.log
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشرت النتيجة الحقيقية - الحكم: $VERDICT ====="
