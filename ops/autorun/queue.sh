#!/bin/bash
# أمر آلي 51: تشخيص ديناميكي لبنية الجدول ثم نصوص القرار 99/2025 ومواد 152/2023
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_name='knowledge_objects' ORDER BY ordinal_position""")
    cols = [r[0] for r in cur.fetchall()]
    print("== أعمدة الجدول ==", flush=True)
    print("  " + ", ".join(cols), flush=True)

    TEXTCOL = next((c for c in ['content','text','body','raw_text','chunk_text',
                                'document_text','markdown','payload'] if c in cols), None)
    print("عمود النص المكتشف:", TEXTCOL, flush=True)
    text_expr = TEXTCOL if TEXTCOL else "''"

    hay = "coalesce(metadata->>'library_card_name','') || ' ' || coalesce(metadata->>'title','')"
    if 'title' in cols:
        hay += " || ' ' || coalesce(title,'')"
    if TEXTCOL:
        hay_full = hay + " || ' ' || left(coalesce(%s,''),200)" % TEXTCOL
    else:
        hay_full = hay

    print("\n== المجموعات المطابقة (مقيمي العقار / 99/2025 / 152/2023) ==", flush=True)
    cur.execute("""SELECT coalesce(metadata->>'library_group','(بلا مجموعة)'),
                          coalesce(metadata->>'library_card_name','(بلا اسم بطاقة)'),
                          coalesce(metadata->>'doc_part','(بلا مجلد)'),
                          count(*)
                   FROM knowledge_objects
                   WHERE """ + hay_full + """ ILIKE %s
                      OR """ + hay_full + """ ILIKE %s
                      OR """ + hay_full + """ ILIKE %s
                   GROUP BY 1,2,3 ORDER BY 4 DESC""",
                ('%مقيمي العقار%', '%99/2025%', '%152/2023%'))
    groups = {}
    for g, cn, dp, c in cur.fetchall():
        print("  مجموعة=%s | بطاقة=%s | مجلد=%s | %d" % (g[:45], cn[:55], dp[:40], c), flush=True)
        groups[g] = groups.get(g, 0) + c

    for g, total in groups.items():
        print("\n==== المجموعة: %s (إجمالي %d) ====" % (g[:60], total), flush=True)
        if g == '(بلا مجموعة)':
            cur.execute("""SELECT id, coalesce(metadata->>'article_number','؟'),
                                  coalesce(metadata->>'title','-'),
                                  left(coalesce(""" + text_expr + """,''), 300)
                           FROM knowledge_objects
                           WHERE metadata->>'library_group' IS NULL
                             AND (""" + hay_full + """ ILIKE %s OR """ + hay_full + """ ILIKE %s)
                           ORDER BY id LIMIT 40""",
                        ('%مقيمي العقار%', '%99/2025%'))
        else:
            cur.execute("""SELECT id, coalesce(metadata->>'article_number','؟'),
                                  coalesce(metadata->>'title','-'),
                                  left(coalesce(""" + text_expr + """,''), 300)
                           FROM knowledge_objects
                           WHERE metadata->>'library_group' = %s
                           ORDER BY id LIMIT 60""", (g,))
        rows = cur.fetchall()
        small = len(rows) <= 6
        for oid, an, t, txt in rows:
            if small:
                print("\n--- %s | مادة=%s | %s" % (oid[:50], an, t[:60]), flush=True)
                cur.execute("SELECT left(coalesce(" + text_expr + ",''), 1800) FROM knowledge_objects WHERE id=%s", (oid,))
                print(cur.fetchone()[0], flush=True)
            else:
                print("  م%s | %s | %s" % (an, oid[:42], txt[:80].replace(chr(10),' ')), flush=True)
PYEOF
echo "===== اكتمل الأمر 51 ====="