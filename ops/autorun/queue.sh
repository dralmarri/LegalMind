#!/bin/bash
# أمر آلي 45: تشخيص وضبط مبادئ هيئة أسواق المال: topic موحد + subtopic حسب الكتاب وعنوانه
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

BOOK_TITLES = {
    "الاول": "الكتاب الأول — التعريفات", "الأول": "الكتاب الأول — التعريفات",
    "١": "الكتاب الأول — التعريفات",
    "٢": "الكتاب الثاني — هيئة أسواق المال",
    "٣": "الكتاب الثالث — إنفاذ القانون",
    "٤": "الكتاب الرابع — بورصات الأوراق المالية ووكالات المقاصة",
    "٥": "الكتاب الخامس — أنشطة الأوراق المالية والأشخاص المسجلون",
    "٦": "الكتاب السادس — السياسات والإجراءات الداخلية للشخص المرخص له",
    "٧": "الكتاب السابع — أموال العملاء وأصولهم",
    "٨": "الكتاب الثامن — أخلاقيات العمل",
    "٩": "الكتاب التاسع — الاندماج والاستحواذ",
    "١٠": "الكتاب العاشر — الإفصاح والشفافية",
    "١١": "الكتاب الحادي عشر — التعامل في الأوراق المالية",
    "١٢": "الكتاب الثاني عشر — قواعد الإدراج",
    "١٣": "الكتاب الثالث عشر — أنظمة الاستثمار الجماعي",
    "١٤": "الكتاب الرابع عشر — سلوكيات السوق",
    "١٥": "الكتاب الخامس عشر — حوكمة الشركات",
    "١٦": "الكتاب السادس عشر — مكافحة غسل الأموال وتمويل الإرهاب",
    "١٧": "الكتاب السابع عشر — تعليمات كفاية رأس المال للأشخاص المرخص لهم",
    "١٨": "الكتاب الثامن عشر — التسجيل البيني للمنتجات المالية",
    "١٩": "الكتاب التاسع عشر — التقنيات المالية",
}

def book_of(meta_title):
    t = (meta_title or "").strip()
    m = re.search(r"الكتاب\s+([٠-٩]+|الاول|الأول)", t)
    if not m:
        return None
    return BOOK_TITLES.get(m.group(1).strip())

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    print("== التشخيص: مبادئ فرع تجاري حسب الموضوع الحالي ==", flush=True)
    cur.execute("""SELECT coalesce(NULLIF(topic,''),'عام'), count(*) FROM knowledge_objects
                   WHERE object_type='judicial_principle' AND branch='تجاري'
                   GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")
    for t, c in cur.fetchall():
        print("  '%s': %d" % (t[:50], c), flush=True)

    print("\n== كائنات مبادئ ملفات أسواق المال وأنماط عناوينها ==", flush=True)
    cur.execute("""SELECT DISTINCT metadata->>'title' FROM knowledge_objects
                   WHERE object_type='judicial_principle'
                     AND metadata->>'title' ILIKE '%اسواق%مال%'""")
    titles = [r[0] for r in cur.fetchall() if r[0]]
    print("  أنماط الملفات:", len(titles), flush=True)

    total = 0
    unmatched = []
    for mt in titles:
        sub = book_of(mt)
        if not sub:
            unmatched.append(mt)
            continue
        cur.execute("""UPDATE knowledge_objects
                       SET topic='مبادئ هيئة أسواق المال', subtopic=%s, branch='تجاري',
                           updated_at=now()
                       WHERE object_type='judicial_principle' AND metadata->>'title' = %s""",
                    (sub, mt))
        total += cur.rowcount
        print("  '%s' -> %s | %d" % (mt[:45], sub[:40], cur.rowcount), flush=True)
    for mt in unmatched:
        cur.execute("""UPDATE knowledge_objects
                       SET topic='مبادئ هيئة أسواق المال', branch='تجاري', updated_at=now()
                       WHERE object_type='judicial_principle' AND metadata->>'title' = %s""", (mt,))
        total += cur.rowcount
        print("  '%s' -> (بلا كتاب محدد) | %d" % (mt[:45], cur.rowcount), flush=True)

    print("\nإجمالي المبادئ المنظمة:", total, flush=True)

    print("\n== التوزيع النهائي داخل 'مبادئ هيئة أسواق المال' ==", flush=True)
    cur.execute("""SELECT coalesce(subtopic,'-'), count(*) FROM knowledge_objects
                   WHERE object_type='judicial_principle' AND topic='مبادئ هيئة أسواق المال'
                   GROUP BY 1 ORDER BY 1""")
    for s, c in cur.fetchall():
        print("  %s : %d" % (s[:55], c), flush=True)
PYEOF
echo "===== اكتمل التنظيم ====="
