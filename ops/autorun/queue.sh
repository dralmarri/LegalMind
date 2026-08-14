#!/bin/bash
# أمر آلي 83: طباعة النصوص الكاملة لمبادئ الكتاب الخامس عشر الخمسة المتبقية بلا مرجع
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

with eng.psycopg.connect(eng.database_url()) as conn:
    cur = conn.cursor()
    cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,'') FROM knowledge_objects
                   WHERE object_type='judicial_principle'
                     AND metadata->>'title' LIKE '%%الكتاب ١٥%%'
                     AND original_text NOT LIKE '%%قرار مجلس التأديب%%'
                     AND original_text NOT LIKE '%%المرجع:%%'
                   ORDER BY id""")
    rows = cur.fetchall()
    print("المتبقية بلا مرجع: %d" % len(rows), flush=True)
    for oid, t, txt in rows:
        print("\n--- %s\nالعنوان: %s\nالنص الكامل:\n%s" % (oid, t, txt[:2000]), flush=True)
PYEOF
echo "===== اكتمل الأمر 83 ====="
