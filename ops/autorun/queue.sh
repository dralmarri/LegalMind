#!/bin/bash
# أمر آلي 58: عزل نسخة كفاية رأس المال القديمة (307) عن الاستشهاد + فحص احترام البحث للعلامة
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
    cur.execute("""UPDATE knowledge_objects
                   SET usable_as_citation=false,
                       metadata = coalesce(metadata,'{}'::jsonb)
                         || jsonb_build_object('library_card_name',
                              'تعليمات كفاية رأس المال — نسخة قديمة (معزولة، مكررة مع الكتاب 17)'::text)
                         || jsonb_build_object('superseded_by', 'كتاب 17 الجديد (TBL)'::text),
                       updated_at=now()
                   WHERE source_key=%s""", (CAP,))
    print("عُزلت عن الاستشهاد: %d كائناً ✓" % cur.rowcount, flush=True)

    cur.execute("""SELECT usable_as_citation, count(*) FROM knowledge_objects
                   WHERE source_key=%s GROUP BY 1""", (CAP,))
    for f, c in cur.fetchall():
        print("  usable_as_citation=%s : %d" % (f, c), flush=True)
PYEOF

echo ""
echo "== هل يحترم محرك البحث علامة usable_as_citation؟ =="
grep -n "usable_as_citation" /opt/LegalMind/admin/app.py | head -20 || echo "لا ذكر لها في app.py"
grep -rn "usable_as_citation" /opt/LegalMind/engine/*.py 2>/dev/null | head -10 || echo "لا ذكر لها في المحرك"
echo "===== اكتمل الأمر 58 ====="