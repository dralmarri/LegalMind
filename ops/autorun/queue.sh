#!/bin/bash
# أمر آلي 30: التصحيح الجذري — الأوامر 26 و27 كانت تستخدم python3 النظام بدل بيئة النظام
# الافتراضية (venv) فتعطّلت فوراً بـ ModuleNotFoundError ولم تُنفَّذ إطلاقاً. هذا هو السبب
# الحقيقي الوحيد وراء عدم ظهور البطاقات طوال الوقت. الإصلاح الآن بالمفسّر الصحيح.
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

echo "== التحقق من المفسّر الصحيح =="
$PY -c "import psycopg; print('psycopg متاح ✓')"

echo ""
echo "== تنفيذ الإصلاح الكامل بالمفسّر الصحيح =="
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

    print("== 1) حالة branch قبل الإصلاح ==", flush=True)
    cur.execute(f"""SELECT coalesce(branch,'(NULL)'), count(*) FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND metadata->>'title' ILIKE '%اسواق%المال%'
                    GROUP BY 1 ORDER BY 2 DESC""", LAW_TYPES)
    before_branch = cur.fetchall()
    for b, c in before_branch:
        print("  branch='%s' | %d" % (b, c), flush=True)

    print("\n== 2) تصحيح branch إلى 'تجاري' حيث يلزم ==", flush=True)
    cur.execute(f"""UPDATE knowledge_objects SET branch='تجاري', updated_at=now()
                    WHERE object_type IN ({ph}) AND metadata->>'title' ILIKE '%اسواق%المال%'
                      AND (branch IS NULL OR branch <> 'تجاري')""", LAW_TYPES)
    print("  عُدِّل:", cur.rowcount, "كائن", flush=True)

    print("\n== 3) إضافة library_group + library_card_name ==", flush=True)
    cur.execute(f"""SELECT DISTINCT metadata->>'title' FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND metadata->>'title' ILIKE '%اسواق%المال%'
                      AND coalesce(metadata->>'library_group','') = ''""", LAW_TYPES)
    titles = [r[0] for r in cur.fetchall() if r[0]]
    print("  عناوين تحتاج تجميعاً:", len(titles), flush=True)
    total = 0
    for title in titles:
        key = "cma-book-" + re.sub(r"\s+", "-", title.strip())
        card_name = "اللائحة التنفيذية — " + title.replace("اسواق المال", "").replace("اسواق-المال", "").strip()
        card_name = re.sub(r"\s+", " ", card_name).strip(" —")
        if not card_name.startswith("اللائحة"):
            card_name = "اللائحة التنفيذية — " + card_name
        cur.execute(f"""UPDATE knowledge_objects
                        SET metadata = metadata || jsonb_build_object(
                              'library_group', %s::text, 'library_card_name', %s::text)
                        WHERE object_type IN ({ph}) AND metadata->>'title' = %s""",
                    (key, card_name, *LAW_TYPES, title))
        total += cur.rowcount
        print("    '%s' -> %s | %d كائن" % (title[:35], card_name[:40], cur.rowcount), flush=True)
    print("  إجمالي محدَّث:", total, flush=True)

    print("\n== 4) التحقق النهائي: محاكاة استعلام /api/browse الحرفي ==", flush=True)
    GEXPR = ("COALESCE(metadata->>'library_group', substring(id from '^(legis-[a-z0-9]+-[0-9]+)'), "
             "substring(id from '^(lreg-[0-9]+-[0-9]+-k[0-9]+)'), "
             "substring(id from '^(regl-[0-9]+-[0-9]+)'), "
             "substring(id from '^(reg-[0-9]+-[0-9]+)'))")
    cur.execute(f"""SELECT {GEXPR} AS g, count(*),
                    COALESCE(min(metadata->>'library_card_name'), 'بلا اسم')
                    FROM knowledge_objects WHERE object_type IN ({ph}) AND branch='تجاري'
                    GROUP BY g ORDER BY g""", LAW_TYPES)
    rows = [r for r in cur.fetchall() if r[0]]
    print("  عدد البطاقات التي ستظهر فعلياً تحت 'القوانين ← تجاري':", len(rows), flush=True)
    for g, c, name in rows:
        print("    -", name[:55], "|", c, "كائن", flush=True)
PYEOF
echo ""
echo "===== اكتمل الإصلاح الفعلي هذه المرة ====="
