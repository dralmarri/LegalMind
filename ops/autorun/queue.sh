#!/bin/bash
# أمر آلي 75: تشخيص — كل الكائنات الشقيقة لملفات المراجع المنفصلة (المعرف والعنوان والنوع)
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python
$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
with eng.psycopg.connect(eng.database_url()) as conn:
    cur = conn.cursor()
    cur.execute("""SELECT DISTINCT substring(id from '([0-9a-f]{12,})$') FROM knowledge_objects
                   WHERE title LIKE 'مرجع المبدأ%%'""")
    hashes = [r[0] for r in cur.fetchall() if r[0]]
    print("بصمات ملفات المراجع:", hashes, flush=True)
    for h in hashes:
        print("\n==== الملف %s ====" % h, flush=True)
        cur.execute("""SELECT id, object_type, coalesce(title,''), coalesce(source_key,'')
                       FROM knowledge_objects WHERE id LIKE %s
                       ORDER BY length(id), id""", ('%' + h,))
        for oid, ot, t, sk in cur.fetchall():
            print("  %s | %s | %s" % (oid[:60], ot[:22], t[:50]), flush=True)
PYEOF
echo "===== اكتمل الأمر 75 ====="
