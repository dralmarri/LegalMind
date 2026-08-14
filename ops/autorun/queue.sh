#!/bin/bash
# أمر آلي 39: إصلاح فتح الكتب (بنية مستويين تدعمها الواجهة) + الكتاب العاشر (نمط اسم مرن)
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

    # 1) تحويل البنية لمستويين تدعمهما الواجهة:
    #    doc_part='القانون' يبقى | doc_subpart يُدمج في doc_part: 'اللائحة التنفيذية — الكتاب X'
    print("== 1) تحويل بنية هيئة أسواق المال لمستويين ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET metadata = (metadata - 'doc_subpart') ||
                       jsonb_build_object('doc_part',
                           'اللائحة التنفيذية — ' || (metadata->>'doc_subpart')),
                       updated_at=now()
                   WHERE metadata->>'library_group'='cma-authority-unified'
                     AND coalesce(metadata->>'doc_subpart','') <> ''""")
    print("  دُمج doc_subpart في doc_part لـ:", cur.rowcount, "كائن", flush=True)

    # 2) الكتاب العاشر بنمط مرن (مسافات أو شرطات)
    print("\n== 2) الكتاب العاشر ==", flush=True)
    cur.execute("""SELECT k.id, k.object_type, s.file_name FROM knowledge_objects k
                   LEFT JOIN sources s ON s.source_key=k.source_key
                   WHERE (k.metadata->>'title' ILIKE '%الكتاب%العاشر%اسواق%'
                          OR s.file_name ILIKE '%العاشر%اسواق%')""")
    found = cur.fetchall()
    print("  وجدت:", found, flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET object_type='legislation_article', branch='تجاري',
                       metadata = metadata || '{"library_group":"cma-authority-unified",
                         "library_card_name":"هيئة أسواق المال",
                         "doc_part":"اللائحة التنفيذية — الكتاب العاشر"}'::jsonb,
                       updated_at=now()
                   WHERE (metadata->>'title' ILIKE '%الكتاب%العاشر%اسواق%'
                          OR source_key IN (SELECT source_key FROM sources
                                            WHERE file_name ILIKE '%العاشر%اسواق%'))
                     AND object_type NOT IN ('judicial_principle')""")
    print("  دُمج:", cur.rowcount, "كائن", flush=True)

    # 3) حماية المستهلك بمستويين أيضاً (إن لم تكن)
    print("\n== 3) حماية المستهلك: تأكيد المستويين والفرع ==", flush=True)
    cur.execute("""SELECT branch, metadata->>'doc_part', count(*) FROM knowledge_objects
                   WHERE metadata->>'library_group'='cp-unified' GROUP BY 1,2""")
    print("  حالتها:", cur.fetchall(), flush=True)

    # 4) الإثبات النهائي
    print("\n===== الإثبات النهائي: مجلدات بطاقة هيئة أسواق المال =====", flush=True)
    cur.execute("""SELECT metadata->>'doc_part', count(*) FROM knowledge_objects
                   WHERE metadata->>'library_group'='cma-authority-unified'
                   GROUP BY 1 ORDER BY 1""")
    tot = 0
    for p, c in cur.fetchall():
        tot += c
        print("  %s : %d" % (p, c), flush=True)
    print("  الإجمالي:", tot, flush=True)
PYEOF
echo ""
echo "===== اكتمل ====="
