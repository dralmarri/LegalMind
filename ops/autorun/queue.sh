#!/bin/bash
# أمر آلي 9: مسح شامل لدفعة "الكتاب السابع عشر - أسواق المال" لاكتشاف كل الجداول المشوهة
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

cat > /root/scan_batch.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re, json
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

SRC_KEY = "SRC-937A1650BC733E4F20CF"
BID = "BATCH-20260813-223443-937A1650"

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""SELECT id, object_type, title, original_text, verification_status, usable_as_citation
                   FROM knowledge_objects WHERE source_key=%s""", (SRC_KEY,))
    rows = cur.fetchall()
    print("إجمالي كائنات هذا الكتاب:", len(rows), flush=True)
    by_type = {}
    for r in rows:
        by_type[r[1]] = by_type.get(r[1], 0) + 1
    print("توزيعها حسب النوع:", by_type, flush=True)

    # بصمة الجدول المشوّه: كثافة أرقام/رموز عالية + مصطلحات مالية إنجليزية + قصر الجمل بشكل غير طبيعي
    EN_MARKERS = ("Venture Capital", "Private Equity", "Off Balance", "off-balance",
                  "Basel", "IFRS", "VaR")
    def looks_like_table(text):
        t = text or ""
        digits = len(re.findall(r"\d", t))
        pct = t.count("%")
        paren_num = len(re.findall(r"\(\s*\d+\s*\)", t))
        en_hit = any(m in t for m in EN_MARKERS)
        density = digits / max(1, len(t))
        # قرائن مركّبة: كثافة أرقام عالية جداً، أو رموز أقواس رقمية متكررة، أو مصطلح إنجليزي داخل نص عربي متصل
        score = 0
        if density > 0.06: score += 1
        if pct >= 2: score += 1
        if paren_num >= 3: score += 1
        if en_hit: score += 2
        # جمل قصيرة جداً متلاحقة (فقرات جدول) — سطور بلا روابط نحوية
        frags = re.split(r"[\n]", t)
        short = sum(1 for f in frags if 0 < len(f.strip()) < 25)
        if short >= 4: score += 1
        return score, density, pct, paren_num, en_hit

    flagged = []
    for oid, ot, title, text, vs, uc in rows:
        if vs != "source_verified" or not uc:
            continue  # سبق حجبها أو لم تُعتمد بعد
        score, density, pct, paren_num, en_hit = looks_like_table(text)
        if score >= 2:
            flagged.append((oid, title, score, density, pct, paren_num, en_hit, (text or "")[:100]))

    flagged.sort(key=lambda x: -x[2])
    print("\nكائنات مشتبه بها إضافية (موثّقة حالياً وقابلة للاستشهاد):", len(flagged), flush=True)
    for f in flagged:
        print("  نقاط=%d كثافة=%.2f%% %%=%d أقواس=%d إنجليزي=%s | %s | %s" %
              (f[2], f[3]*100, f[4], f[5], f[6], f[1][:40], f[7][:70]), flush=True)

    if flagged:
        ids = [f[0] for f in flagged]
        cur.execute("""UPDATE knowledge_objects
                       SET verification_status='machine_pending_human', usable_as_citation=false,
                           metadata = metadata || '{"quarantined":"table_misread_batch_scan"}'::jsonb,
                           updated_at=now()
                       WHERE id = ANY(%s)""", (ids,))
        for oid in ids:
            eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/delete?wait=true",
                               {"filter": {"must": [{"key": "object_id", "match": {"value": oid}}]}})
        print("\nحُجب %d كائناً إضافياً ✓" % len(ids), flush=True)

    # عينة من الكائنات السليمة الباقية (نص سردي طبيعي فعلاً) لتقييم جودة الباقي
    cur.execute("""SELECT id, title, left(original_text,120) FROM knowledge_objects
                   WHERE source_key=%s AND verification_status='source_verified' AND usable_as_citation
                   ORDER BY random() LIMIT 6""", (SRC_KEY,))
    print("\nعينة عشوائية من الكائنات السليمة الباقية:", flush=True)
    for oid, t, tx in cur.fetchall():
        print("  -", t[:50], "|", tx[:70], flush=True)

    cur.execute("""SELECT verification_status, usable_as_citation, count(*)
                   FROM knowledge_objects WHERE source_key=%s GROUP BY 1,2""", (SRC_KEY,))
    print("\nالحصيلة النهائية لهذا الكتاب:", flush=True)
    for vs, uc, c in cur.fetchall():
        print("  %s | استشهاد=%s | %d" % (vs, uc, c), flush=True)
PYEOF
/opt/LegalMind/.venv/bin/python /root/scan_batch.py > /root/scan_batch.log 2>&1
cat /root/scan_batch.log

{
  echo "=== مسح شامل لدفعة أسواق المال — $(date -u +%F' '%T) UTC ==="
  echo ""
  cat /root/scan_batch.log
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشرت نتيجة المسح الشامل ====="
