#!/bin/bash
# أمر آلي 7: حجب طارئ — جدول "تعليمات كفاية رأس المال" مصنّف خطأً كمبدأ قضائي وموثّق للاستشهاد
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

cat > /root/quarantine.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re, json
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

# بصمات فريدة من المقطع الذي أرسله المستخدم — لتحديد الكائن والمصدر بيقين
FINGERPRINTS = [
    "Venture Capital", "Private Equity",
    "تعليمات كفاية رأس المال",
    "الأشخاص المرخص لهم",
    "متطلبات رأس المال لمخاطر الائتمان",
]

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    # 1) تحديد الكائن الأصلي بيقين ومصدره
    like_clauses = " OR ".join(["original_text ILIKE %s"] * len(FINGERPRINTS))
    cur.execute(f"""SELECT id, title, source_key, metadata->>'batch_id'
                    FROM knowledge_objects WHERE {like_clauses} LIMIT 5""",
                tuple("%" + f + "%" for f in FINGERPRINTS))
    hits = cur.fetchall()
    print("كائنات مطابقة للبصمة الأصلية:", len(hits), flush=True)
    for h in hits:
        print("  ", h, flush=True)
    if not hits:
        print("لم يُعثر على الكائن بالبصمة — توقف بلا حذف", flush=True)
        sys.exit(0)

    source_keys = {h[2] for h in hits}
    batch_ids = {h[3] for h in hits if h[3]}
    cur.execute("SELECT file_name FROM sources WHERE source_key = ANY(%s)", (list(source_keys),))
    files = [r[0] for r in cur.fetchall()]
    print("ملف/ملفات المصدر:", files, flush=True)
    print("الدفعات:", batch_ids, flush=True)

    # 2) مسح شامل لأمثاله: نفس المصدر + بصمة الجدول التنظيمي (لا يقتصر على judicial_principle)
    MARKERS = ["Venture Capital", "Private Equity", "تعليمات كفاية رأس المال",
               "متطلبات رأس المال", "جدول رقم", "الأشخاص المرخص لهم",
               "الفترة المالية المنتهية في", "Off Balance Sheet", "off-balance"]
    marker_sql = " OR ".join(["original_text ILIKE %s"] * len(MARKERS))
    cur.execute(f"""SELECT id, object_type, title, verification_status, usable_as_citation, source_key
                    FROM knowledge_objects
                    WHERE source_key = ANY(%s) AND ({marker_sql})""",
                (list(source_keys), *["%" + m + "%" for m in MARKERS]))
    poisoned = cur.fetchall()
    print("\nكائنات مسمومة من نفس المصدر (بنفس بصمة الجدول):", len(poisoned), flush=True)
    by_type = {}
    for r in poisoned:
        by_type[r[1]] = by_type.get(r[1], 0) + 1
    print("توزيعها حسب النوع:", by_type, flush=True)

    ids = [r[0] for r in poisoned]
    if ids:
        cur.execute("""UPDATE knowledge_objects
                       SET verification_status='machine_pending_human', usable_as_citation=false,
                           metadata = metadata || '{"quarantined":"table_misread_as_prose"}'::jsonb,
                           updated_at=now()
                       WHERE id = ANY(%s)""", (ids,))
        for oid in ids:
            eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/delete?wait=true",
                               {"filter": {"must": [{"key": "object_id", "match": {"value": oid}}]}})
        print("حُجب %d كائناً عن الاستشهاد وأُزيلت نقاطهم من الفهرس ✓" % len(ids), flush=True)

    # 3) هل نفس المصدر يحوي كائنات سليمة (مواد نصية حقيقية) يجب الإبقاء عليها؟
    cur.execute("""SELECT count(*) FROM knowledge_objects WHERE source_key = ANY(%s)""",
                (list(source_keys),))
    total_src = cur.fetchone()[0]
    print("\nإجمالي كائنات هذا المصدر:", total_src, "| المحجوب منها:", len(ids), flush=True)

    # 4) عينة من الكائنات السليمة الباقية (إن وُجدت) لعرضها للتقييم
    cur.execute("""SELECT title, left(original_text,80) FROM knowledge_objects
                   WHERE source_key = ANY(%s) AND id != ALL(%s) LIMIT 8""",
                (list(source_keys), ids or ['']))
    remain = cur.fetchall()
    print("\nعينة من الكائنات الباقية (غير محجوبة) من نفس المصدر:", flush=True)
    for t, tx in remain:
        print("  -", t[:60], "|", tx[:60], flush=True)
PYEOF
/opt/LegalMind/.venv/bin/python /root/quarantine.py > /root/quarantine.log 2>&1
cat /root/quarantine.log

# نشر النتيجة
{
  echo "=== حجب طارئ لجدول تنظيمي مصنّف خطأً — $(date -u +%F' '%T) UTC ==="
  echo ""
  cat /root/quarantine.log
  echo ""
  echo "-- حالة القاعدة الآن --"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
    "SELECT verification_status, count(*) FROM knowledge_objects GROUP BY 1 ORDER BY 2 DESC;"
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشرت نتيجة الحجب ====="
