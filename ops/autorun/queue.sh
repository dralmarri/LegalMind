#!/bin/bash
# أمر آلي 69: اعتماد مبدأ الكتاب 12 (مدقق بصرياً) + إقفال معلقات النسخة المؤرشفة بقيمة مسموحة + الحصيلة
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

    print("== (أ) اعتماد مبدأ الكتاب 12 بعد التدقيق البصري ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET verification_status='source_verified', usable_as_citation=true,
                       metadata = coalesce(metadata,'{}'::jsonb)
                         || jsonb_build_object('verified_by','visual-review-claude-session'::text)
                         || jsonb_build_object('verified_ref','المخالفة 5/2021 و133/2020 جلسة 10/3/2021'::text),
                       updated_at=now()
                   WHERE id='JUR-تجاري-أنواع-من-الشركات-p4-3-5800a66c5eadb5ad'
                     AND verification_status='machine_pending_human'""")
    print("اعتُمد:", cur.rowcount, flush=True)

    print("\n== (ب) القيم المسموحة لحالة التحقق ==", flush=True)
    cur.execute("""SELECT pg_get_constraintdef(oid) FROM pg_constraint
                   WHERE conname='ko_verification_status_valid'""")
    cdef = cur.fetchone()[0]
    print(cdef[:400], flush=True)
    allowed = re.findall(r"'([a-z_]+)'", cdef)
    print("المسموح:", allowed, flush=True)
    target = 'operationally_accepted' if 'operationally_accepted' in allowed else None
    if target:
        cur.execute("""UPDATE knowledge_objects
                       SET verification_status=%s, usable_as_citation=false,
                           metadata = coalesce(metadata,'{}'::jsonb)
                             || jsonb_build_object('closed_reason','نسخة مؤرشفة مكررة مع كتاب 17'::text),
                           updated_at=now()
                       WHERE source_key='SRC-937A1650BC733E4F20CF'
                         AND verification_status='machine_pending_human'""", (target,))
        print("أُقفلت معلقات النسخة المؤرشفة:", cur.rowcount, flush=True)
    else:
        print("!! لا قيمة مناسبة — تُترك كما هي (مخفية وغير مستشهد بها أصلاً).", flush=True)

    print("\n== (ج) الحصيلة: المتبقي معلقاً حسب الملف ==", flush=True)
    cur.execute("""SELECT coalesce(s.file_name, k.source_key), count(*)
                   FROM knowledge_objects k LEFT JOIN sources s ON s.source_key=k.source_key
                   WHERE k.verification_status='machine_pending_human'
                   GROUP BY 1 ORDER BY 2 DESC""")
    tot = 0
    for fn, c in cur.fetchall():
        tot += c
        print("  %s : %d" % (str(fn)[:55], c), flush=True)
    print("الإجمالي المتبقي:", tot, flush=True)
PYEOF
echo "===== اكتمل الأمر 69 ====="
