#!/bin/bash
# أمر آلي 37: الدمج النهائي الكامل دفعة واحدة
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

    # ===== 1) القانون الأساسي 7/2010 (711 كائناً: نص القانون + كتب 1-4 القديمة) =====
    print("== 1) دمج قانون هيئة أسواق المال الأساسي وكتبه الأربعة القديمة ==", flush=True)
    cur.execute("""SELECT DISTINCT metadata->>'library_group' FROM knowledge_objects
                   WHERE metadata->>'library_card_name' ILIKE '%%هيئة أسواق المال ولائحته%%'""")
    old_groups = [r[0] for r in cur.fetchall() if r[0]]
    print("  مجموعات قديمة وجدتها:", old_groups, flush=True)

    # إن لم توجد عبر الاسم، جرّب عبر بادئات المعرفات القديمة legis-7-2010 / lreg-7-2010
    if not old_groups:
        cur.execute("""SELECT DISTINCT coalesce(metadata->>'library_group','') FROM knowledge_objects
                       WHERE id LIKE 'legis-7-2010%%' OR id LIKE 'lreg-7-2010%%'""")
        old_groups = [r[0] for r in cur.fetchall() if r[0]]
        print("  عبر المعرفات القديمة:", old_groups, flush=True)

    PART_MAP = [
        ("تعريفات",  "الكتاب الأول — التعريفات"),
        ("إنفاذ",    "الكتاب الثالث — إنفاذ القانون"),
        ("بورصات",   "الكتاب الرابع — بورصات الأوراق المالية ووكالات المقاصة"),
        ("هيئة أسواق المال", "الكتاب الثاني — هيئة أسواق المال"),
    ]
    moved = 0
    targets = old_groups if old_groups else [None]
    for og in targets:
        if og:
            cond, args = "metadata->>'library_group' = %s", (og,)
        else:
            cond, args = "(id LIKE 'legis-7-2010%%' OR id LIKE 'lreg-7-2010%%')", ()
        # نص القانون
        cur.execute(f"""UPDATE knowledge_objects
                        SET metadata = metadata || '{{"library_group":"cma-authority-unified",
                              "library_card_name":"هيئة أسواق المال","doc_part":"القانون"}}'::jsonb
                              - 'doc_subpart',
                            updated_at=now()
                        WHERE {cond} AND (coalesce(metadata->>'doc_part','') ILIKE '%%نص القانون%%'
                                          OR id LIKE 'legis-7-2010%%')""", args)
        moved += cur.rowcount
        print("  نص القانون -> القانون:", cur.rowcount, flush=True)
        # الكتب الأربعة القديمة
        for kw, subname in PART_MAP:
            cur.execute(f"""UPDATE knowledge_objects
                            SET metadata = metadata || jsonb_build_object(
                                  'library_group','cma-authority-unified',
                                  'library_card_name','هيئة أسواق المال',
                                  'doc_part','اللائحة التنفيذية','doc_subpart', %s::text),
                                updated_at=now()
                            WHERE {cond}
                              AND coalesce(metadata->>'doc_part','') ILIKE '%%اللائحة%%'
                              AND coalesce(metadata->>'doc_part','') ILIKE %s""",
                        args + (subname, "%" + kw + "%"))
            moved += cur.rowcount
            print("  %s -> اللائحة/%s: %d" % (kw, subname[:30], cur.rowcount), flush=True)
    print("  إجمالي المدموج من القديم:", moved, flush=True)

    # ===== 2) الكتاب العاشر =====
    print("\n== 2) الكتاب العاشر ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET metadata = metadata || '{"library_group":"cma-authority-unified",
                         "library_card_name":"هيئة أسواق المال",
                         "doc_part":"اللائحة التنفيذية","doc_subpart":"الكتاب العاشر"}'::jsonb,
                       branch='تجاري', updated_at=now()
                   WHERE source_key IN (SELECT source_key FROM sources
                                        WHERE file_name ILIKE '%%الكتاب-العاشر-اسواق-المال%%')
                     AND object_type IN ('legislation','legislation_article',
                                         'legislation_issuing_article','legislation_preamble')""")
    print("  دُمج:", cur.rowcount, "كائن", flush=True)

    # ===== 3) الكتاب السابع عشر (TBL-*) =====
    print("\n== 3) الكتاب السابع عشر ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET object_type='legislation_article', branch='تجاري',
                       metadata = metadata || '{"library_group":"cma-authority-unified",
                         "library_card_name":"هيئة أسواق المال",
                         "doc_part":"اللائحة التنفيذية","doc_subpart":"الكتاب السابع عشر"}'::jsonb,
                       updated_at=now()
                   WHERE id LIKE 'TBL-%%'""")
    n17 = cur.rowcount
    print("  دُمج وعُدِّل نوعه:", n17, "كائن", flush=True)
    if n17:
        cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,''),
                              object_type, branch, topic, subtopic, metadata->>'micro_issue', source_key
                       FROM knowledge_objects WHERE id LIKE 'TBL-%%'""")
        allr = cur.fetchall()
        for s in range(0, len(allr), 48):
            w = allr[s:s + 48]
            common = {"object_type": w[0][3], "branch": w[0][4], "topic": w[0][5],
                      "subtopic": w[0][6], "micro_issue": w[0][7], "source_key": w[0][8]}
            eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                               {"points": eng.build_points([(r[0], r[1], r[2]) for r in w], common)})
        print("  أُعيدت فهرسته بالنوع الجديد ✓", flush=True)

    # ===== 4) حماية المستهلك: بطاقة واحدة، فرع مدني =====
    print("\n== 4) حماية المستهلك ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET branch='مدني',
                       metadata = metadata || jsonb_build_object(
                             'library_group','cp-unified',
                             'library_card_name','قانون حماية المستهلك (39/2014)',
                             'doc_part',
                             CASE WHEN coalesce(metadata->>'library_card_name', title, '')
                                       ILIKE '%%اللائحة التنفيذية%%'
                                  THEN 'اللائحة التنفيذية' ELSE 'القانون' END),
                       updated_at=now()
                   WHERE object_type IN ('legislation','legislation_article',
                                         'legislation_issuing_article','legislation_preamble')
                     AND (title ILIKE '%%حماية المستهلك%%'
                          OR metadata->>'title' ILIKE '%%حماية المستهلك%%'
                          OR metadata->>'library_card_name' ILIKE '%%حماية المستهلك%%')""")
    print("  دُمج وصُحِّح فرعه لمدني:", cur.rowcount, "كائن", flush=True)

    # ===== 5) الإثبات النهائي =====
    print("\n===== الإثبات النهائي =====", flush=True)
    cur.execute("""SELECT metadata->>'doc_part', coalesce(metadata->>'doc_subpart','-'), count(*)
                   FROM knowledge_objects
                   WHERE metadata->>'library_group'='cma-authority-unified'
                   GROUP BY 1,2 ORDER BY 1,2""")
    print("بنية بطاقة هيئة أسواق المال:", flush=True)
    total_cma = 0
    for p, sp, c in cur.fetchall():
        total_cma += c
        print("  %s / %s : %d" % (p, sp, c), flush=True)
    print("  الإجمالي:", total_cma, flush=True)

    cur.execute("""SELECT branch, metadata->>'doc_part', count(*)
                   FROM knowledge_objects WHERE metadata->>'library_group'='cp-unified'
                   GROUP BY 1,2""")
    print("\nبنية بطاقة حماية المستهلك:", flush=True)
    for b, p, c in cur.fetchall():
        print("  فرع=%s / %s : %d" % (b, p, c), flush=True)
PYEOF
echo ""
echo "===== اكتمل الدمج النهائي ====="
