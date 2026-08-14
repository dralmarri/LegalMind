#!/bin/bash
# أمر آلي 43: تثبيت عناوين الكتب 15-19 (الأخيرة) + الإثبات الختامي للبنية الكاملة
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

TITLES = {
    "الكتاب الخامس عشر": "حوكمة الشركات",
    "الكتاب السادس عشر": "مكافحة غسل الأموال وتمويل الإرهاب",
    "الكتاب السابع عشر": "تعليمات كفاية رأس المال للأشخاص المرخص لهم",
    "الكتاب الثامن عشر": "التسجيل البيني للمنتجات المالية",
    "الكتاب التاسع عشر": "التقنيات المالية",
}

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    for book, subject in TITLES.items():
        old = "اللائحة التنفيذية — " + book
        new = "اللائحة التنفيذية — " + book + " — " + subject
        cur.execute("""UPDATE knowledge_objects
                       SET metadata = metadata || jsonb_build_object('doc_part', %s::text),
                           updated_at=now()
                       WHERE metadata->>'library_group'='cma-authority-unified'
                         AND metadata->>'doc_part' = %s""", (new, old))
        print("%s -> %s | %d كائن" % (book, subject[:45], cur.rowcount), flush=True)

    print("\n===== البنية الختامية الكاملة لبطاقة هيئة أسواق المال =====", flush=True)
    cur.execute("""SELECT metadata->>'doc_part', count(*) FROM knowledge_objects
                   WHERE metadata->>'library_group'='cma-authority-unified'
                   GROUP BY 1 ORDER BY 1""")
    tot = 0
    for p, c in cur.fetchall():
        tot += c
        print("  %s : %d" % (p, c), flush=True)
    print("  الإجمالي:", tot, flush=True)

    print("\n===== حماية المستهلك =====", flush=True)
    cur.execute("""SELECT branch, metadata->>'doc_part', count(*) FROM knowledge_objects
                   WHERE metadata->>'library_group'='cp-unified' GROUP BY 1,2""")
    for b, p, c in cur.fetchall():
        print("  فرع=%s / %s : %d" % (b, p, c), flush=True)
PYEOF
echo "===== اكتمل — كل عناوين الكتب مثبتة ====="
