#!/bin/bash
# فحص: هل غطّت الفهرسة المجلد كاملاً (القانون الرئيسي + القوانين المكملة)؟
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
cat > /root/maritime_coverage.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
from collections import Counter
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

with eng.psycopg.connect(eng.database_url()) as conn, conn.cursor() as cur:
    cur.execute("""SELECT batch_id FROM ingestion_batches
                   WHERE object_count > 400 AND status='completed'
                   ORDER BY started_at DESC LIMIT 1""")
    BID = cur.fetchone()[0]
    cur.execute("""SELECT id, coalesce(title,''), left(coalesce(original_text,''),150)
                   FROM knowledge_objects WHERE metadata->>'batch_id'=%s""", (BID,))
    rows = cur.fetchall()

def sort_key(r):
    m = re.match(r"LEG-UNKNOWN-P(\d+)-c(\d+)", r[0])
    return (int(m.group(1)), int(m.group(2))) if m else (999, 999)
rows.sort(key=sort_key)

print("الدفعة:", BID, "| إجمالي الكائنات:", len(rows))

parts = Counter()
for i, t, _ in rows:
    m = re.match(r"LEG-UNKNOWN-P(\d+)-", i)
    if m:
        parts[int(m.group(1))] += 1
print("أجزاء المعالجة وعدد كائنات كل جزء:", dict(sorted(parts.items())))

nums = Counter()
for i, t, _ in rows:
    m = re.search(r"المادة\s+(\d+)", t)
    if m:
        nums[int(m.group(1))] += 1
if nums:
    lo, hi = min(nums), max(nums)
    missing = [n for n in range(lo, hi + 1) if n not in nums]
    print("\nأرقام المواد المرصودة: من", lo, "إلى", hi, "| عدد المواد المميزة:", len(nums))
    if missing:
        print("مواد مفقودة ضمن النطاق (%d):" % len(missing), missing[:50],
              "..." if len(missing) > 50 else "")
    else:
        print("لا فجوات في تسلسل المواد ضمن النطاق ✓")
    dups = {k: v for k, v in sorted(nums.items()) if v > 1}
    print("مواد لها أكثر من نسخة (%d):" % len(dups), dict(list(dups.items())[:12]),
          "..." if len(dups) > 12 else "")

print("\n== أثر القوانين المكملة في العناوين ==")
for k in ["الجواز البحري", "الربابنة", "ضباط الملاحة", "التأديب", "سندات الشحن",
          "انضمام", "المذكرة الإيضاحية", "مذكرة إيضاحية"]:
    hits = [t for _, t, _ in rows if k in t]
    print("«%s»: %d" % (k, len(hits)), "| أمثلة:", [h[:60] for h in hits[:2]])

print("\n-- أول 12 عنواناً (بترتيب الصفحات) --")
for i, t, _ in rows[:12]:
    print(" ", i, "|", t[:75])
print("-- آخر 12 عنواناً --")
for i, t, _ in rows[-12:]:
    print(" ", i, "|", t[:75])
PYEOF
/opt/LegalMind/.venv/bin/python /root/maritime_coverage.py

echo ""
echo "== الملف الأصلي في الأرشيف وعدد صفحاته =="
/opt/LegalMind/.venv/bin/python - <<'PYEOF'
# -*- coding: utf-8 -*-
import glob
from pypdf import PdfReader
files = set(glob.glob("/opt/legalmind-ingest/archive/*") )
for f in sorted(files):
    low = f.lower()
    if "بحري" in f or "السادس" in f or low.endswith(".pdf"):
        try:
            print(f, "->", len(PdfReader(f).pages), "صفحة")
        except Exception as e:
            print(f, "-> تعذرت القراءة:", e)
PYEOF
echo ""
echo "===== انتهى فحص التغطية ====="
