#!/bin/bash
# أمر آلي 20: تقرير قراءة فقط — صفر استدعاء للنموذج، صفر تكلفة
# الصورة الكاملة: أي كتب من 5-19 مفهرسة سليمة، كم بقي، ونسبة العطب
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

cat > /root/full_picture.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

BOOK_NUM = {
    "التاسع عشر": 19, "الثامن عشر": 18, "السابع عشر": 17, "السادس عشر": 16,
    "الخامس عشر": 15, "الرابع عشر": 14, "الثالث عشر": 13, "الثاني عشر": 12,
    "الحادي عشر": 11, "العاشر": 10, "التاسع": 9, "الثامن": 8, "السابع": 7,
    "السادس": 6, "الخامس": 5, "الرابع": 4, "الثالث": 3, "الثاني": 2,
    "الاول": 1, "الأول": 1,
}

def book_number(fname):
    f = (fname or "").replace("-", " ").replace("_", " ")
    for key in sorted(BOOK_NUM, key=len, reverse=True):
        if key in f:
            return BOOK_NUM[key]
    return None

def looks_garbled(text):
    t = text or ""
    digits = len(re.findall(r"\d", t))
    density = digits / max(1, len(t))
    en_hit = any(m in t for m in ("Venture Capital", "Private Equity", "Off Balance"))
    frags = [x for x in t.split("\n") if x.strip()]
    short = sum(1 for x in frags if 0 < len(x.strip()) < 25)
    return ((density > 0.06) + (en_hit * 2) + (short >= 4)) >= 2

with eng.psycopg.connect(eng.database_url()) as conn, conn.cursor() as cur:
    cur.execute("""SELECT source_key, file_name FROM sources
                   WHERE file_name ILIKE '%الكتاب%' AND file_name ILIKE '%اسواق-المال%'""")
    sources = cur.fetchall()
    print("مصادر كتب موجودة في سجل sources بنمط 'الكتاب...اسواق-المال':", len(sources), flush=True)

    books = {}
    for sk, fname in sources:
        n = book_number(fname)
        cur.execute("""SELECT object_type, verification_status, usable_as_citation, original_text
                       FROM knowledge_objects WHERE source_key=%s""", (sk,))
        rows = cur.fetchall()
        garbled = sum(1 for r in rows if looks_garbled(r[3]))
        by_type = {}
        for r in rows:
            by_type[r[0]] = by_type.get(r[0], 0) + 1
        books[n or fname] = {"file": fname, "total": len(rows), "garbled": garbled,
                             "by_type": by_type, "sk": sk}

    print("\n=== حالة كل كتاب (5 إلى 19) ===", flush=True)
    healthy = missing = garbled_books = misclassified = 0
    for n in range(5, 20):
        b = books.get(n)
        if not b:
            print("  كتاب %d: غير مرفوع إطلاقاً ✗" % n, flush=True)
            missing += 1
            continue
        gr = b["garbled"] / b["total"] if b["total"] else 0
        jur = b["by_type"].get("judicial_principle", 0)
        jur_ratio = jur / b["total"] if b["total"] else 0
        if gr > 0.15:
            status = "مشوّه (يحتاج إعادة قراءة مكلفة)"
            garbled_books += 1
        elif jur_ratio > 0.1:
            status = "بقي فيه تصنيف خاطئ (يحتاج مراجعة)"
            misclassified += 1
        else:
            status = "سليم ✓"
            healthy += 1
        print("  كتاب %d: %d كائن | عطب=%.0f%% | مبدأ_قضائي_متبقٍ=%d | %s | %s" %
              (n, b["total"], gr * 100, jur, status, b["file"][:45]), flush=True)

    total_books = 15  # من 5 إلى 19
    print("\n=== الخلاصة (من أصل %d كتاباً: 5 إلى 19) ===" % total_books, flush=True)
    print("  سليمة تماماً: %d" % healthy, flush=True)
    print("  غير مرفوعة إطلاقاً: %d" % missing, flush=True)
    print("  مشوّهة (تحتاج إعادة قراءة بصرية مكلفة): %d" % garbled_books, flush=True)
    print("  يبقى فيها تصنيف خاطئ بسيط (قابل للإصلاح المجاني): %d" % misclassified, flush=True)
    if garbled_books:
        print("  نسبة الكتب المعطوبة فعلاً: %.0f%%" % (garbled_books / total_books * 100), flush=True)

    # ملفات المبادئ القضائية المنفصلة (مجلس التأديب) — للتأكد أنها سليمة ولم تُمس
    cur.execute("""SELECT count(*) FROM knowledge_objects
                   WHERE object_type='judicial_principle'
                     AND (original_text ILIKE '%جلسة%' OR original_text ILIKE '%مجلس التأديب%'
                          OR original_text ILIKE '%الطعن%')""")
    real_principles = cur.fetchone()[0]
    print("\nمبادئ قضائية حقيقية سليمة (فيها جلسة/قرار مجلس تأديب/طعن):", real_principles, flush=True)

    cur.execute("SELECT count(*) FROM knowledge_objects WHERE object_type='judicial_principle'")
    total_jur = cur.fetchone()[0]
    print("إجمالي المصنّف حالياً 'مبدأ قضائي' في كل القاعدة:", total_jur,
          "(منها %d مؤكد سليم، والباقي إما مبادئ أخرى أو محتاج مراجعة)" % real_principles, flush=True)

    # الحالة العامة لكل القاعدة (ليست مقتصرة على أسواق المال)
    cur.execute("""SELECT verification_status, count(*) FROM knowledge_objects GROUP BY 1 ORDER BY 2 DESC""")
    print("\nحالة التوثيق في كامل مكتبتك (كل الفروع):", flush=True)
    for vs, c in cur.fetchall():
        print("  %s: %d" % (vs, c), flush=True)
PYEOF
/opt/LegalMind/.venv/bin/python /root/full_picture.py > /root/full_picture.log 2>&1
cat /root/full_picture.log

{
  echo "=== الصورة الكاملة (قراءة فقط — صفر تكلفة) — $(date -u +%F' '%T) UTC ==="
  echo ""
  cat /root/full_picture.log
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشر تقرير الصورة الكاملة ====="
