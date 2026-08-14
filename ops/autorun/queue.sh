#!/bin/bash
# أمر آلي 38: إعادة الدمج بتشخيص صريح + تنظيف ملف nginx معطوب من محاولة قديمة
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

echo "== تنظيف ملف nginx المعطوب المتبقي من محاولة قديمة =="
rm -f /etc/nginx/conf.d/no-cache-reports.conf
nginx -t && echo "إعدادات nginx سليمة الآن ✓" || echo "تحذير: nginx -t ما زال يفشل!"

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    print("== تشخيص 0: هل نُفِّذ الأمر السابق أصلاً؟ ==", flush=True)
    cur.execute("""SELECT count(*) FROM knowledge_objects
                   WHERE metadata->>'library_group'='cma-authority-unified'
                     AND metadata->>'doc_part'='القانون'""")
    print("  كائنات 'القانون' داخل البطاقة الموحدة:", cur.fetchone()[0], flush=True)

    print("\n== تشخيص 1: أين القانون الأساسي 7/2010 الآن؟ ==", flush=True)
    cur.execute("""SELECT count(*), coalesce(min(metadata->>'library_group'),'(لا مجموعة)'),
                          coalesce(min(metadata->>'doc_part'),'(لا جزء)'), min(id)
                   FROM knowledge_objects WHERE id LIKE 'legis-7-2010%'""")
    print("  legis-7-2010*:", cur.fetchone(), flush=True)
    cur.execute("""SELECT count(*), coalesce(min(metadata->>'library_group'),'(لا مجموعة)'),
                          min(metadata->>'doc_part'), min(id)
                   FROM knowledge_objects WHERE id LIKE 'lreg-7-2010%'""")
    print("  lreg-7-2010*:", cur.fetchone(), flush=True)
    cur.execute("""SELECT DISTINCT metadata->>'doc_part' FROM knowledge_objects
                   WHERE id LIKE 'lreg-7-2010%' OR id LIKE 'legis-7-2010%'""")
    print("  قيم doc_part الفعلية للقديم:", [r[0] for r in cur.fetchall()], flush=True)

    # ===== الدمج (يعمل مهما كانت الحالة) =====
    print("\n== دمج legis-7-2010 (نص القانون) ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET metadata = (metadata - 'doc_subpart') || '{"library_group":"cma-authority-unified",
                         "library_card_name":"هيئة أسواق المال","doc_part":"القانون"}'::jsonb,
                       branch='تجاري', updated_at=now()
                   WHERE id LIKE 'legis-7-2010%'""")
    print("  عُدِّل:", cur.rowcount, flush=True)

    print("\n== دمج lreg-7-2010 (الكتب 1-4 القديمة) حسب رقم الكتاب في المعرف ==", flush=True)
    K_MAP = {"k1": "الكتاب الأول — التعريفات", "k2": "الكتاب الثاني — هيئة أسواق المال",
             "k3": "الكتاب الثالث — إنفاذ القانون", "k4": "الكتاب الرابع — بورصات الأوراق المالية ووكالات المقاصة"}
    for k, subname in K_MAP.items():
        cur.execute("""UPDATE knowledge_objects
                       SET metadata = metadata || jsonb_build_object(
                             'library_group','cma-authority-unified',
                             'library_card_name','هيئة أسواق المال',
                             'doc_part','اللائحة التنفيذية','doc_subpart', %s::text),
                           branch='تجاري', updated_at=now()
                       WHERE id LIKE %s""", (subname, "lreg-7-2010-" + k + "%"))
        print("  %s -> %s: %d" % (k, subname[:35], cur.rowcount), flush=True)

    print("\n== الكتاب العاشر ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET metadata = metadata || '{"library_group":"cma-authority-unified",
                         "library_card_name":"هيئة أسواق المال",
                         "doc_part":"اللائحة التنفيذية","doc_subpart":"الكتاب العاشر"}'::jsonb,
                       branch='تجاري', updated_at=now()
                   WHERE source_key IN (SELECT source_key FROM sources
                                        WHERE file_name ILIKE '%الكتاب-العاشر-اسواق-المال%')
                     AND object_type IN ('legislation','legislation_article',
                                         'legislation_issuing_article','legislation_preamble')""")
    print("  عُدِّل:", cur.rowcount, flush=True)

    print("\n== الكتاب السابع عشر (TBL-*) ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET object_type='legislation_article', branch='تجاري',
                       metadata = metadata || '{"library_group":"cma-authority-unified",
                         "library_card_name":"هيئة أسواق المال",
                         "doc_part":"اللائحة التنفيذية","doc_subpart":"الكتاب السابع عشر"}'::jsonb,
                       updated_at=now()
                   WHERE id LIKE 'TBL-%'""")
    print("  عُدِّل:", cur.rowcount, flush=True)

    print("\n== حماية المستهلك ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET branch='مدني',
                       metadata = metadata || jsonb_build_object(
                             'library_group','cp-unified',
                             'library_card_name','قانون حماية المستهلك (39/2014)',
                             'doc_part',
                             CASE WHEN coalesce(metadata->>'library_card_name','') || ' ' || coalesce(title,'')
                                       ILIKE '%اللائحة التنفيذية%'
                                  THEN 'اللائحة التنفيذية' ELSE 'القانون' END),
                       updated_at=now()
                   WHERE object_type IN ('legislation','legislation_article',
                                         'legislation_issuing_article','legislation_preamble')
                     AND (title ILIKE '%حماية المستهلك%'
                          OR metadata->>'title' ILIKE '%حماية المستهلك%'
                          OR metadata->>'library_card_name' ILIKE '%حماية المستهلك%')""")
    print("  عُدِّل:", cur.rowcount, flush=True)

    print("\n===== الإثبات النهائي =====", flush=True)
    cur.execute("""SELECT metadata->>'doc_part', coalesce(metadata->>'doc_subpart','-'), count(*)
                   FROM knowledge_objects WHERE metadata->>'library_group'='cma-authority-unified'
                   GROUP BY 1,2 ORDER BY 1,2""")
    tot = 0
    print("بطاقة هيئة أسواق المال:", flush=True)
    for p, sp, c in cur.fetchall():
        tot += c
        print("  %s / %s : %d" % (p, sp, c), flush=True)
    print("  الإجمالي:", tot, flush=True)
    cur.execute("""SELECT branch, metadata->>'doc_part', count(*) FROM knowledge_objects
                   WHERE metadata->>'library_group'='cp-unified' GROUP BY 1,2""")
    print("بطاقة حماية المستهلك:", flush=True)
    for b, p, c in cur.fetchall():
        print("  فرع=%s / %s : %d" % (b, p, c), flush=True)
PYEOF
echo ""
echo "===== اكتمل ====="
