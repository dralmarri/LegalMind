#!/bin/bash
# أمر آلي 59 (يشمل 58): عزل نسخة كفاية رأس المال القديمة + البحث عن الكتاب العاشر (الإفصاح والشفافية) أينما كان
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

CAP = 'SRC-937A1650BC733E4F20CF'
with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    print("== (أ) عزل نسخة كفاية رأس المال القديمة ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET usable_as_citation=false,
                       metadata = coalesce(metadata,'{}'::jsonb)
                         || jsonb_build_object('library_card_name',
                              'تعليمات كفاية رأس المال — نسخة قديمة (معزولة، مكررة مع الكتاب 17)'::text)
                         || jsonb_build_object('superseded_by', 'كتاب 17 الجديد (TBL)'::text),
                       updated_at=now()
                   WHERE source_key=%s AND usable_as_citation IS DISTINCT FROM false""", (CAP,))
    print("عُزلت الآن: %d (0 = كانت معزولة مسبقاً)" % cur.rowcount, flush=True)

    print("\n== (ب) أين الكتاب العاشر (الإفصاح والشفافية)؟ ==", flush=True)
    print("-- 1) مجلدات بطاقة هيئة أسواق المال الحالية:", flush=True)
    cur.execute("""SELECT coalesce(metadata->>'doc_part','(بلا مجلد)'), count(*) FROM knowledge_objects
                   WHERE metadata->>'library_group'='cma-authority-unified'
                   GROUP BY 1 ORDER BY 1""")
    for p, c in cur.fetchall():
        print("   %s : %d" % (p, c), flush=True)

    print("\n-- 2) كل الكائنات التي تذكر الكتاب العاشر في عناوينها أو ملفها:", flush=True)
    cur.execute("""SELECT coalesce(source_key,'-'), object_type,
                          coalesce(metadata->>'library_group','(بلا مجموعة)'),
                          coalesce(NULLIF(topic,''),'-'), count(*),
                          min(id), min(coalesce(title, metadata->>'title', ''))
                   FROM knowledge_objects
                   WHERE title ILIKE '%%الكتاب العاشر%%'
                      OR metadata->>'title' ILIKE '%%الكتاب العاشر%%'
                      OR metadata->>'title' ILIKE '%%العاشر%%اسواق%%'
                      OR metadata->>'doc_part' ILIKE '%%العاشر%%'
                   GROUP BY 1,2,3,4 ORDER BY 5 DESC LIMIT 20""")
    for sk, ot, g, tp, c, mid, mt in cur.fetchall():
        print("   مصدر=%s | نوع=%s | مجموعة=%s | موضوع=%s | %d | %s | %s"
              % (sk[:24], ot, g[:28], tp[:28], c, mid[:38], mt[:45]), flush=True)

    print("\n-- 3) كائنات تذكر (الإفصاح والشفافية) خارج بطاقة أسواق المال:", flush=True)
    cur.execute("""SELECT coalesce(source_key,'-'), object_type,
                          coalesce(metadata->>'library_group','(بلا مجموعة)'), count(*),
                          min(id), min(coalesce(title,''))
                   FROM knowledge_objects
                   WHERE (title ILIKE '%%الإفصاح والشفافية%%' OR original_text ILIKE '%%كتاب العاشر%%الإفصاح%%')
                     AND coalesce(metadata->>'library_group','') != 'cma-authority-unified'
                   GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 15""")
    rows = cur.fetchall()
    if not rows:
        print("   (لا شيء)", flush=True)
    for sk, ot, g, c, mid, mt in rows:
        print("   مصدر=%s | نوع=%s | مجموعة=%s | %d | %s | %s" % (sk[:24], ot, g[:28], c, mid[:38], mt[:45]), flush=True)

    print("\n-- 4) الملفات المصدرية التي لم يدخل منها شيء لبطاقة أسواق المال (مرشحة أن تكون الكتاب العاشر):", flush=True)
    cur.execute("""SELECT source_key, count(*),
                          min(coalesce(title, metadata->>'title','')),
                          min(coalesce(verification_status,'-'))
                   FROM knowledge_objects
                   WHERE (original_text ILIKE '%%هيئة أسواق المال%%' OR metadata->>'title' ILIKE '%%اسواق المال%%')
                     AND coalesce(metadata->>'library_group','') NOT IN ('cma-authority-unified','cap-adequacy-legacy')
                     AND object_type NOT IN ('judicial_principle','judicial_principles_collection','full_judgment')
                     AND id NOT LIKE 'LEG-UNKNOWN-%%'
                   GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")
    rows = cur.fetchall()
    if not rows:
        print("   (لا شيء)", flush=True)
    for sk, c, mt, vs in rows:
        print("   مصدر=%s | %d | حالة=%s | %s" % ((sk or '-')[:28], c, vs, mt[:55]), flush=True)
PYEOF
echo "===== اكتمل الأمر 59 ====="