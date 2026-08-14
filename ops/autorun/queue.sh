#!/bin/bash
# أمر آلي 29: تحقق مباشر (بلا API، بلا تسجيل دخول) — كل شيء يُطبع مباشرة في السجل الظاهر
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

LAW_TYPES = ('legislation', 'legislation_article', 'legislation_issuing_article', 'legislation_preamble')

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    ph = ",".join(["%s"] * len(LAW_TYPES))

    print("== 1) عمود branch الفعلي الآن لكتب أسواق المال ==", flush=True)
    cur.execute(f"""SELECT coalesce(branch,'(NULL)'), count(*) FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND metadata->>'title' ILIKE '%اسواق%المال%'
                    GROUP BY 1 ORDER BY 2 DESC""", LAW_TYPES)
    for b, c in cur.fetchall():
        print("  branch='%s' | %d" % (b, c), flush=True)

    print("\n== 2) هل library_group موجود فعلاً الآن؟ ==", flush=True)
    cur.execute(f"""SELECT count(*) FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND metadata->>'title' ILIKE '%اسواق%المال%'
                      AND coalesce(metadata->>'library_group','') <> ''""", LAW_TYPES)
    print("  عدد الكائنات فيها library_group:", cur.fetchone()[0], flush=True)

    cur.execute(f"""SELECT count(*) FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND metadata->>'title' ILIKE '%اسواق%المال%'""", LAW_TYPES)
    print("  إجمالي كائنات كتب أسواق المال:", cur.fetchone()[0], flush=True)

    print("\n== 3) محاكاة استعلام /api/browse الحرفي (المستوى الأول: الفروع) ==", flush=True)
    BR = "CASE WHEN branch LIKE 'أحوال شخصية%%' THEN 'أحوال شخصية' ELSE COALESCE(NULLIF(branch,''),'غير مصنّف') END"
    cur.execute(f"""SELECT {BR} AS g, count(*) FROM knowledge_objects
                    WHERE object_type IN ({ph}) GROUP BY g ORDER BY count(*) DESC""", LAW_TYPES)
    print("  الفروع الظاهرة فعلياً لأنواع 'قوانين':", flush=True)
    for g, c in cur.fetchall():
        print("    '%s' | %d" % (g, c), flush=True)

    print("\n== 4) محاكاة المستوى الثاني (بطاقات الكتب تحت فرع 'تجاري') ==", flush=True)
    GEXPR = ("COALESCE(metadata->>'library_group', substring(id from '^(legis-[a-z0-9]+-[0-9]+)'), "
             "substring(id from '^(lreg-[0-9]+-[0-9]+-k[0-9]+)'), "
             "substring(id from '^(regl-[0-9]+-[0-9]+)'), "
             "substring(id from '^(reg-[0-9]+-[0-9]+)'))")
    cur.execute(f"""SELECT {GEXPR} AS g, count(*),
                    COALESCE(min(metadata->>'library_card_name'), 'بلا اسم بطاقة')
                    FROM knowledge_objects WHERE object_type IN ({ph}) AND branch=%s
                    GROUP BY g ORDER BY g""", LAW_TYPES + ('تجاري',))
    rows = cur.fetchall()
    print("  عدد الصفوف الخام (قبل استبعاد الفارغ):", len(rows), flush=True)
    non_null = [r for r in rows if r[0]]
    print("  عدد البطاقات الفعلية (بعد استبعاد g الفارغ، هذا ما تراه الواجهة):", len(non_null), flush=True)
    for g, c, name in rows:
        marker = "✓ ستظهر" if g else "✗ مستبعدة (g فارغ/NULL)"
        print("    key=%s | name=%s | %d كائن | %s" % (str(g)[:40], name[:45], c, marker), flush=True)

    print("\n== 5) عيّنة: هل هناك كائنات object_type IN law-types لكن metadata->>'title' لا يحتوي 'اسواق المال'؟ ==", flush=True)
    cur.execute(f"""SELECT count(*) FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND branch='تجاري'
                      AND coalesce(metadata->>'title','') NOT ILIKE '%اسواق%المال%'""", LAW_TYPES)
    print("  عدد كائنات 'تجاري' بنوع قانون لا تخص أسواق المال:", cur.fetchone()[0], flush=True)
PYEOF
echo ""
echo "===== انتهى التحقق المباشر ====="
