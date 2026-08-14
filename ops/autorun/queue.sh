#!/bin/bash
# أمر آلي 41: تثبيت عناوين الكتب 5-10 (من أغلفتها الرسمية)
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

TITLES = {
    "الكتاب الخامس":  "أنشطة الأوراق المالية والأشخاص المسجلون",
    "الكتاب السادس":  "السياسات والإجراءات الداخلية للشخص المرخص له",
    "الكتاب السابع":  "أموال العملاء وأصولهم",
    "الكتاب الثامن":  "أخلاقيات العمل",
    "الكتاب التاسع":  "الاندماج والاستحواذ",
    "الكتاب العاشر":  "الإفصاح والشفافية",
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
        print("%s -> %s | %d كائن" % (book, subject[:40], cur.rowcount), flush=True)

    print("\n== البنية الآن ==", flush=True)
    cur.execute("""SELECT metadata->>'doc_part', count(*) FROM knowledge_objects
                   WHERE metadata->>'library_group'='cma-authority-unified'
                   GROUP BY 1 ORDER BY 1""")
    for p, c in cur.fetchall():
        print("  %s : %d" % (p, c), flush=True)
PYEOF
echo "===== اكتمل ====="
