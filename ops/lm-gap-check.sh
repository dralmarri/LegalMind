#!/bin/bash
# فحص خفيف (قاعدة بيانات فقط): أين اختفت المواد 9-44 و256؟ وما خريطة أقسام المجلد؟
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
/opt/LegalMind/.venv/bin/python - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

with eng.psycopg.connect(eng.database_url()) as conn, conn.cursor() as cur:
    cur.execute("""SELECT batch_id FROM ingestion_batches
                   WHERE object_count > 400 AND status='completed'
                   ORDER BY started_at DESC LIMIT 1""")
    BID = cur.fetchone()[0]
    cur.execute("""SELECT id, coalesce(title,''), left(coalesce(original_text,''),120)
                   FROM knowledge_objects WHERE metadata->>'batch_id'=%s""", (BID,))
    rows = cur.fetchall()

def key(r):
    m = re.match(r"LEG-UNKNOWN-P(\d+)-c?(\d+)", r[0])
    return (int(m.group(1)), int(m.group(2))) if m else (999, 999)
rows.sort(key=key)

def artnum(t):
    m = re.search(r"المادة\s*\(?\s*(\d+)", t)
    return int(m.group(1)) if m else None

print("== خريطة المجلد: أول وآخر 3 عناوين في كل جزء ==")
from collections import defaultdict
byp = defaultdict(list)
for r in rows:
    byp[key(r)[0]].append(r)
for p in sorted(byp):
    seg = byp[p]
    print("\n-- الجزء P%d (%d كائناً | الصفحات %d-%d تقريباً) --" % (p, len(seg), (p-1)*15+1, p*15))
    for r in seg[:3]:
        print("   أول:", r[1][:70])
    for r in seg[-3:]:
        print("   آخر:", r[1][:70])

print("\n== جوار المواد المفقودة ==")
for target in (8, 45, 255, 257):
    idxs = [i for i, r in enumerate(rows) if artnum(r[1]) == target]
    if not idxs:
        print("\nالمادة %d: غير موجودة أصلاً!" % target)
        continue
    for ix in idxs:
        print("\n--- حول المادة %d (الموضع %s) ---" % (target, rows[ix][0]))
        for j in range(max(0, ix-3), min(len(rows), ix+4)):
            mark = ">>>" if j == ix else "   "
            print(mark, rows[j][0].split("-", 3)[2] if rows[j][0].count("-")>2 else rows[j][0], "|", rows[j][1][:70])

print("\n== العناوين التي تشبه رؤوس الأقسام (لرسم حدود القوانين) ==")
HEADS = ("غلاف", "مرسوم", "مذكرة", "معاهدة", "قانون الجواز", "ديباجة", "فهرس", "بيان")
for i, r in enumerate(rows):
    t = r[1]
    if artnum(t) is None and any(h in t for h in HEADS):
        m = re.match(r"LEG-UNKNOWN-(P\d+-c?\d+)", r[0])
        print("  %s | %s" % (m.group(1) if m else r[0], t[:85]))
PYEOF
echo ""
echo "===== انتهى فحص الفجوة ====="
