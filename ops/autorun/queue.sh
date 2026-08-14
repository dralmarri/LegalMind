#!/bin/bash
# أمر آلي 40: استخراج عناوين موضوعات الكتب من محتواها + طباعة البنية النهائية للتأكيد
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    print("== البنية الحالية لبطاقة هيئة أسواق المال ==", flush=True)
    cur.execute("""SELECT metadata->>'doc_part', count(*) FROM knowledge_objects
                   WHERE metadata->>'library_group'='cma-authority-unified'
                   GROUP BY 1 ORDER BY 1""")
    parts = cur.fetchall()
    for p, c in parts:
        print("  %s : %d" % (p, c), flush=True)

    print("\n== استخراج عناوين موضوعات الكتب من محتواها المخزن ==", flush=True)
    for p, c in parts:
        if not p or not p.startswith("اللائحة التنفيذية — الكتاب") or "—" in p.replace("اللائحة التنفيذية — ", "").replace("الكتاب", ""):
            continue
        book_label = p.replace("اللائحة التنفيذية — ", "")
        # مرشح 1: كائن الغلاف أو المحتويات أو المقدمة
        cur.execute("""SELECT title, left(original_text, 300) FROM knowledge_objects
                       WHERE metadata->>'library_group'='cma-authority-unified'
                         AND metadata->>'doc_part' = %s
                         AND (title ILIKE 'غلاف%%' OR title ILIKE '%%جدول المحتويات%%'
                              OR title ILIKE '%%محتويات%%' OR title ILIKE '%%نطاق التطبيق%%'
                              OR title ILIKE '%%مقدمة%%')
                       LIMIT 3""", (p,))
        cands = cur.fetchall()
        # مرشح 2: البحث في نص أي كائن عن نمط "بشأن ..."
        cur.execute("""SELECT left(original_text, 400) FROM knowledge_objects
                       WHERE metadata->>'library_group'='cma-authority-unified'
                         AND metadata->>'doc_part' = %s
                         AND original_text ILIKE '%%' || %s || '%%'
                       LIMIT 2""", (p, book_label))
        texts = cur.fetchall()
        print("\n  ▶ %s (%d كائن):" % (book_label, c), flush=True)
        for t, tx in cands:
            print("     غلاف/محتويات: %s | %s" % (t[:60], (tx or "").replace("\n", " ")[:90]), flush=True)
        for (tx,) in texts:
            # اقتطاع الجملة المحيطة باسم الكتاب
            i = tx.find(book_label)
            if i >= 0:
                print("     سياق: ...%s..." % tx[max(0, i-20):i+120].replace("\n", " "), flush=True)

    print("\n== حماية المستهلك (تأكيد) ==", flush=True)
    cur.execute("""SELECT branch, metadata->>'doc_part', count(*) FROM knowledge_objects
                   WHERE metadata->>'library_group'='cp-unified' GROUP BY 1,2""")
    for b, p, c in cur.fetchall():
        print("  فرع=%s / %s : %d" % (b, p, c), flush=True)
PYEOF
echo ""
echo "===== انتهى الاستخراج — راجع العناوين المقترحة أعلاه ====="
