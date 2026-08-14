#!/bin/bash
# أمر آلي 56: (أ) مسح التسميات الخاطئة عن LEG-UNKNOWN (ب) تشخيص العائلة بمصادرها (ج) نتيجة فرز المبادئ التي اقتُطعت من السجل
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

    print("== (أ) التراجع عن التسميات الخاطئة ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET metadata = metadata - 'library_card_name', updated_at=now()
                   WHERE id LIKE 'LEG-UNKNOWN-%%' AND metadata ? 'library_card_name'""")
    print("مُسحت التسمية الخاطئة عن %d كائناً ✓" % cur.rowcount, flush=True)

    print("\n== (ب) تشخيص عائلة LEG-UNKNOWN عبر ملفات المصدر ==", flush=True)
    cur.execute("""SELECT coalesce(source_key,'(بلا مصدر)'), count(*),
                          min(coalesce(title,'')), max(coalesce(title,''))
                   FROM knowledge_objects
                   WHERE id LIKE 'LEG-UNKNOWN-%%'
                   GROUP BY 1 ORDER BY 2 DESC LIMIT 30""")
    for sk, c, t1, t2 in cur.fetchall():
        print("  مصدر=%s | %d | أول: %s | آخر: %s" % (sk[:60], c, t1[:45], t2[:45]), flush=True)

    cur.execute("""SELECT substring(id from '^LEG-UNKNOWN-(P[0-9]+)'), object_type, branch, count(*)
                   FROM knowledge_objects
                   WHERE id LIKE 'LEG-UNKNOWN-%%'
                   GROUP BY 1,2,3 ORDER BY 1,4 DESC""")
    print("\n  حسب الجزء والنوع والفرع:", flush=True)
    for p, ot, b, c in cur.fetchall():
        print("    %s | %s | %s | %d" % (p or '؟', ot, b or '-', c), flush=True)

    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'LEG-UNKNOWN-%%'")
    print("  الإجمالي:", cur.fetchone()[0], flush=True)

    print("\n  عينات من كل جزء:", flush=True)
    cur.execute("""SELECT DISTINCT ON (substring(id from '^LEG-UNKNOWN-(P[0-9]+)'))
                          substring(id from '^LEG-UNKNOWN-(P[0-9]+)'), id, coalesce(title,'')
                   FROM knowledge_objects WHERE id LIKE 'LEG-UNKNOWN-%%'
                   ORDER BY 1, 2""")
    for p, oid, t in cur.fetchall():
        print("    %s | %s | %s" % (p or '؟', oid[:35], t[:60]), flush=True)

    print("\n== هل تتقاطع مع القانون البحري المفهرس legis-28-1980؟ ==", flush=True)
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-28-1980-%%'")
    print("  مواد legis-28-1980 المفهرسة:", cur.fetchone()[0], flush=True)
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'TBL-%%'")
    print("  كائنات كتاب 17 (TBL):", cur.fetchone()[0], flush=True)

    print("\n== (ج) نتيجة فرز المبادئ (أعيدت طباعتها بعد اقتطاعها من السجل السابق) ==", flush=True)
    cur.execute("""SELECT branch, count(*) FROM knowledge_objects
                   WHERE object_type='judicial_principle' GROUP BY 1 ORDER BY 2 DESC""")
    for b, c in cur.fetchall():
        print("  %s : %d" % (b or '-', c), flush=True)
    cur.execute("""SELECT count(*) FROM knowledge_objects
                   WHERE object_type='judicial_principle' AND branch='تجاري'""")
    print("  (منها في تجاري):", cur.fetchone()[0], flush=True)
PYEOF
echo "===== اكتمل الأمر 56 ====="