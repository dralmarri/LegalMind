#!/bin/bash
# أمر آلي 32: إصلاح شامل نهائي — كتاب 10 + كتاب 17 + تسمية كل مجموعة مجهولة الاسم
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python
$PY -c "import psycopg; print('psycopg متاح ✓')"

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

LAW_TYPES = ('legislation', 'legislation_article', 'legislation_issuing_article', 'legislation_preamble')

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    ph = ",".join(["%s"] * len(LAW_TYPES))

    # ===== 1) الكتاب السابع عشر: نوعه مختلف (regulatory_table/legal_document) فلم يظهر =====
    print("== 1) الكتاب السابع عشر ==", flush=True)
    cur.execute("""SELECT count(*), array_agg(DISTINCT object_type) FROM knowledge_objects
                   WHERE id LIKE 'TBL-الكتاب-السابع%%'""")
    n17, types17 = cur.fetchone()
    print("  كائنات الكتاب 17 الحالية:", n17, "| أنواعها:", types17, flush=True)
    if n17:
        cur.execute("""UPDATE knowledge_objects SET object_type='legislation_article', updated_at=now()
                       WHERE id LIKE 'TBL-الكتاب-السابع%%' AND object_type NOT IN ('legislation_article')""")
        print("  عُدِّل نوعه إلى legislation_article:", cur.rowcount, flush=True)
        cur.execute("""UPDATE knowledge_objects
                       SET metadata = metadata || '{"library_group":"cma-book-الكتاب-السابع-عشر",
                                                     "library_card_name":"اللائحة التنفيذية — الكتاب السابع عشر"}'::jsonb
                       WHERE id LIKE 'TBL-الكتاب-السابع%%'""")
        print("  أُضيف مفتاح التجميع:", cur.rowcount, flush=True)

    # ===== 2) الكتاب العاشر: عنصر واحد، عنوانه لا يطابق نمط البحث السابق =====
    print("\n== 2) الكتاب العاشر ==", flush=True)
    cur.execute("""SELECT k.id, k.object_type FROM knowledge_objects k
                   JOIN sources s ON s.source_key = k.source_key
                   WHERE s.file_name ILIKE '%%الكتاب-العاشر-اسواق-المال%%'""")
    b10 = cur.fetchall()
    print("  كائنات موجودة:", b10, flush=True)
    if b10:
        cur.execute(f"""UPDATE knowledge_objects
                        SET metadata = metadata || '{{"library_group":"cma-book-الكتاب-العاشر",
                                                       "library_card_name":"اللائحة التنفيذية — الكتاب العاشر"}}'::jsonb
                        WHERE source_key IN (SELECT source_key FROM sources
                                             WHERE file_name ILIKE '%%الكتاب-العاشر-اسواق-المال%%')
                          AND object_type IN ({ph})""", LAW_TYPES)
        print("  أُضيف مفتاح التجميع:", cur.rowcount, flush=True)

    # ===== 3) تشخيص المجموعات مجهولة الاسم (كما تراها الواجهة فعلياً بمنطقها الحقيقي) =====
    print("\n== 3) تشخيص المجموعات مجهولة الاسم ==", flush=True)
    GEXPR = ("COALESCE(metadata->>'library_group', substring(id from '^(legis-[a-z0-9]+-[0-9]+)'), "
             "substring(id from '^(lreg-[0-9]+-[0-9]+-k[0-9]+)'), "
             "substring(id from '^(regl-[0-9]+-[0-9]+)'), "
             "substring(id from '^(reg-[0-9]+-[0-9]+)'))")
    cur.execute(f"""SELECT {GEXPR} AS g, count(*), min(id), min(title), min(metadata->>'title')
                    FROM knowledge_objects WHERE object_type IN ({ph}) AND branch='تجاري'
                      AND coalesce(metadata->>'library_card_name','') = ''
                    GROUP BY g HAVING g IS NOT NULL ORDER BY count(*) DESC""", LAW_TYPES)
    unnamed = cur.fetchall()
    print("  عدد المجموعات بلا library_card_name صريح:", len(unnamed), flush=True)

    fixed_unnamed = 0
    for g, c, sample_id, sample_title, meta_title in unnamed:
        # محاكاة منطق الإنتاج الحقيقي: إن كان العنوان يحوي '—' فالإنتاج يستخرج اسماً بنفسه تلقائياً
        derived_ok = bool(sample_title and "—" in sample_title)
        print("  مجموعة g=%s | %d كائن | عيّنة id=%s | title='%s' | meta_title='%s' | الإنتاج يشتق اسماً تلقائياً=%s" %
              (str(g)[:35], c, sample_id[:30], (sample_title or "")[:50], (meta_title or "")[:40], derived_ok),
              flush=True)
        if not derived_ok:
            # لا يوجد '—' في العنوان فلن يشتق الإنتاج اسماً مفيداً — نحدد اسماً صريحاً بأنفسنا
            base = (meta_title or sample_title or g or "مصدر قانوني غير مسمّى").strip()
            card_name = base if len(base) > 3 else ("مصدر قانوني: " + str(g)[:30])
            cur.execute(f"""UPDATE knowledge_objects
                            SET metadata = metadata || jsonb_build_object('library_card_name', %s::text)
                            WHERE object_type IN ({ph}) AND branch='تجاري' AND {GEXPR} = %s""",
                        (card_name, *LAW_TYPES, g))
            fixed_unnamed += 1
            print("    -> عُيِّن اسم صريح: '%s' (%d كائن)" % (card_name[:50], cur.rowcount), flush=True)
    print("\n  مجموعات صُحِّحت بتسمية صريحة:", fixed_unnamed, flush=True)

    # ===== 4) التحقق النهائي الشامل =====
    print("\n== 4) التحقق النهائي: كل البطاقات تحت 'تجاري' الآن ==", flush=True)
    cur.execute(f"""SELECT {GEXPR} AS g, count(*),
                    COALESCE(min(metadata->>'library_card_name'), 'لا يزال بلا اسم صريح')
                    FROM knowledge_objects WHERE object_type IN ({ph}) AND branch='تجاري'
                    GROUP BY g ORDER BY g""", LAW_TYPES)
    final = [r for r in cur.fetchall() if r[0]]
    still_bad = [r for r in final if r[2] == 'لا يزال بلا اسم صريح']
    print("  إجمالي البطاقات:", len(final), "| بلا اسم صريح متبقٍّ:", len(still_bad), flush=True)
    for g, c, name in final:
        flag = " ⚠️" if name == 'لا يزال بلا اسم صريح' else ""
        print("    -", name[:55], "|", c, "كائن" + flag, flush=True)
PYEOF
echo ""
echo "===== اكتمل الإصلاح الشامل ====="
