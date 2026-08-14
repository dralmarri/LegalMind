#!/bin/bash
# أمر آلي 49: (أ) دمج القرار الوزاري 99/2025 داخل بطاقة القرار 152/2023 بمجلدين (ب) تصحيح اسم بطاقة قرار 109/2026
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

    print("== التشخيص: مجموعات مقيمي العقار والقرار المعدل ==", flush=True)
    cur.execute("""SELECT coalesce(metadata->>'library_group','(بلا مجموعة)'),
                          coalesce(metadata->>'library_card_name','(بلا اسم)'),
                          count(*), min(id), min(metadata->>'title')
                   FROM knowledge_objects
                   WHERE metadata->>'library_card_name' ILIKE '%%مقيمي العقار%%'
                      OR metadata->>'library_card_name' ILIKE '%%99/2025%%'
                      OR metadata->>'title' ILIKE '%%مقيمي العقار%%'
                      OR metadata->>'title' ILIKE '%%99/2025%%'
                   GROUP BY 1,2 ORDER BY 3 DESC""")
    rows = cur.fetchall()
    target = source = None
    for g, cn, c, mid, mt in rows:
        print("  مجموعة=%s | بطاقة=%s | %d | مثال=%s" % (g[:40], cn[:60], c, mid[:40]), flush=True)
        if 'مقيمي العقار' in cn and c > 10:
            target = g
        if '99/2025' in cn and 'مقيمي العقار' not in cn and c <= 10:
            source = g

    if target and source and target != source and target != '(بلا مجموعة)' and source != '(بلا مجموعة)':
        NEWNAME = 'تنظيم مهنة مقيمي العقار ومقدمي خدمات التقييم (152/2023 وتعديله)'
        cur.execute("""UPDATE knowledge_objects
                       SET metadata = metadata
                           || jsonb_build_object('doc_part', 'القرار 152/2023'::text)
                           || jsonb_build_object('library_card_name', %s::text),
                           updated_at=now()
                       WHERE metadata->>'library_group' = %s""", (NEWNAME, target))
        n1 = cur.rowcount
        cur.execute("""UPDATE knowledge_objects
                       SET metadata = metadata
                           || jsonb_build_object('library_group', %s::text)
                           || jsonb_build_object('doc_part', 'القرار الوزاري 99/2025 المعدِّل'::text)
                           || jsonb_build_object('library_card_name', %s::text),
                           updated_at=now()
                       WHERE metadata->>'library_group' = %s""", (target, NEWNAME, source))
        n2 = cur.rowcount
        print("دُمج: %d مادة أصلية + %d مادة من القرار المعدل في بطاقة واحدة بمجلدين ✓" % (n1, n2), flush=True)
    else:
        print("!! لم أتعرف على المجموعتين بأمان — لا تغيير. (target=%s, source=%s)" % (target, source), flush=True)

    print("\n== التشخيص: بطاقة قرار توصيل الطلبات 109/2026 ==", flush=True)
    cur.execute("""SELECT coalesce(metadata->>'library_group','(بلا مجموعة)'),
                          coalesce(metadata->>'library_card_name','(بلا اسم)'),
                          count(*), min(metadata->>'title')
                   FROM knowledge_objects
                   WHERE metadata->>'library_card_name' ILIKE '%%توصيل الطلبات%%'
                      OR metadata->>'title' ILIKE '%%توصيل الطلبات%%'
                   GROUP BY 1,2 ORDER BY 3 DESC""")
    rows = cur.fetchall()
    for g, cn, c, mt in rows:
        print("  مجموعة=%s | بطاقة=%s | %d | عنوان الملف=%s" % (g[:40], cn[:70], c, (mt or '-')[:70]), flush=True)
    if len(rows) == 1 and rows[0][0] != '(بلا مجموعة)':
        g, cn, c, mt = rows[0]
        good = None
        if mt and re.search(r'(قرار|مرسوم|قانون)', mt) and '109' in mt:
            good = mt.strip()[:90]
        if not good:
            good = 'القرار 109/2026 — تنظيم قطاع توصيل الطلبات عبر المنصات'
        cur.execute("""UPDATE knowledge_objects
                       SET metadata = metadata || jsonb_build_object('library_card_name', %s::text),
                           updated_at=now()
                       WHERE metadata->>'library_group' = %s""", (good, g))
        print("سُمّيت البطاقة: '%s' (%d) ✓" % (good, cur.rowcount), flush=True)
    else:
        print("!! أكثر من مجموعة أو بلا مجموعة — لا تغيير.", flush=True)
PYEOF
echo "===== اكتمل الأمر 49 ====="