#!/bin/bash
# أمر آلي 50: تشخيص — طباعة نصوص مواد القرار المعدل 99/2025 كاملة + قائمة مواد القرار الأصلي 152/2023
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

    print("== حالة المجموعات الآن ==", flush=True)
    cur.execute("""SELECT coalesce(metadata->>'library_group','-'),
                          coalesce(metadata->>'library_card_name','-'),
                          coalesce(metadata->>'doc_part','-'), count(*)
                   FROM knowledge_objects
                   WHERE metadata->>'library_card_name' ILIKE '%%مقيمي العقار%%'
                      OR metadata->>'title' ILIKE '%%مقيمي العقار%%'
                      OR metadata->>'title' ILIKE '%%99/2025%%'
                   GROUP BY 1,2,3 ORDER BY 4 DESC""")
    amend_group = None
    base_group = None
    for g, cn, dp, c in cur.fetchall():
        print("  مجموعة=%s | بطاقة=%s | مجلد=%s | %d" % (g[:35], cn[:50], dp[:40], c), flush=True)

    print("\n== نصوص مواد القرار المعدل 99/2025 كاملة ==", flush=True)
    cur.execute("""SELECT id, coalesce(metadata->>'article_number','؟'),
                          coalesce(metadata->>'title','-'), content
                   FROM knowledge_objects
                   WHERE (metadata->>'title' ILIKE '%%99/2025%%'
                          OR metadata->>'doc_part' ILIKE '%%99/2025%%'
                          OR metadata->>'library_card_name' ILIKE '%%99/2025%%')
                     AND metadata->>'library_card_name' NOT ILIKE '%%152/2023 وتعديله%%'
                      OR metadata->>'doc_part' = 'القرار الوزاري 99/2025 المعدِّل'
                   ORDER BY id""")
    rows = cur.fetchall()
    for oid, an, t, content in rows:
        print("\n--- %s | مادة=%s | %s" % (oid[:50], an, t[:60]), flush=True)
        print((content or '')[:1600], flush=True)

    print("\n== قائمة مواد القرار الأصلي 152/2023 (رقم المادة + أول سطر) ==", flush=True)
    cur.execute("""SELECT id, coalesce(metadata->>'article_number','؟'),
                          left(coalesce(content,''),90)
                   FROM knowledge_objects
                   WHERE (metadata->>'library_card_name' ILIKE '%%مقيمي العقار%%'
                          OR metadata->>'title' ILIKE '%%مقيمي العقار%%')
                     AND coalesce(metadata->>'doc_part','') NOT ILIKE '%%99/2025%%'
                   ORDER BY length(coalesce(metadata->>'article_number','')), metadata->>'article_number'""")
    for oid, an, first in cur.fetchall():
        print("  م%s | %s | %s" % (an, oid[:45], first.replace(chr(10),' ')), flush=True)
PYEOF
echo "===== اكتمل الأمر 50 ====="