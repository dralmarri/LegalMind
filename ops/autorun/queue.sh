#!/bin/bash
# أمر آلي 67: تشخيص — أسماء ملفات المصادر المعلقة وما هو موجود فعلاً على القرص
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
with eng.psycopg.connect(eng.database_url()) as conn:
    cur = conn.cursor()
    cur.execute("""SELECT s.source_key, coalesce(s.file_name,'(فارغ)'), coalesce(s.title,'-'),
                          s.created_at::date, count(k.id)
                   FROM sources s
                   JOIN knowledge_objects k ON k.source_key = s.source_key
                   WHERE k.verification_status = 'machine_pending_human'
                   GROUP BY 1,2,3,4 ORDER BY 5 DESC""")
    for sk, fn, t, d, c in cur.fetchall():
        print("%s | ملف=%s | عنوان=%s | %s | %d" % (sk[:24], fn[:45], t[:40], d, c), flush=True)
PYEOF

echo ""
echo "== مجلدات الأرشيف والرفع الموجودة =="
find /opt/LegalMind /root /srv /var/lib -maxdepth 4 -type d \( -iname '*archive*' -o -iname '*upload*' -o -iname '*inbox*' -o -iname '*ingest*' -o -iname '*failed*' -o -iname '*files*' -o -iname '*docs*' \) 2>/dev/null
echo ""
echo "== ملفات PDF على القرص (أول 40 بالحجم) =="
find /opt/LegalMind /root /srv /var/lib /home -maxdepth 6 -type f -iname '*.pdf' -printf '%s\t%p\n' 2>/dev/null | sort -rn | head -40
echo ""
echo "== إعدادات مسارات المحرك =="
grep -nE "archive|upload|inbox|Path\(" /opt/LegalMind/engine/legalmind_engine.py 2>/dev/null | head -15
echo "===== اكتمل الأمر 67 ====="
