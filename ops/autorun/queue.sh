#!/bin/bash
# أمر آلي 35: إصلاح مستهدف صريح — لا بحث تخميني هذه المرة
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python
$PY -c "import psycopg; print('psycopg متاح ✓')"

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

LAW_TYPES = ('legislation', 'legislation_article', 'legislation_issuing_article', 'legislation_preamble')
GEXPR = ("COALESCE(metadata->>'library_group', substring(id from '^(legis-[a-z0-9]+-[0-9]+)'), "
         "substring(id from '^(lreg-[0-9]+-[0-9]+-k[0-9]+)'), "
         "substring(id from '^(regl-[0-9]+-[0-9]+)'), "
         "substring(id from '^(reg-[0-9]+-[0-9]+)'))")

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    ph = ",".join(["%s"] * len(LAW_TYPES))

    print("== 1) تحديد القانون الأساسي لأسواق المال بعنوانه مباشرة (711 كائناً) ==", flush=True)
    cur.execute(f"""SELECT {GEXPR} AS g, count(*), min(id) FROM knowledge_objects
                    WHERE object_type IN ({ph})
                      AND (title ILIKE '%%هيئة أسواق المال%%' OR title ILIKE '%%أسواق المال%%')
                      AND coalesce(metadata->>'library_group','') <> 'cma-authority-unified'
                    GROUP BY g ORDER BY count(*) DESC LIMIT 3""", LAW_TYPES)
    rows = cur.fetchall()
    print("  مرشحون:", rows, flush=True)
    if rows:
        base_g = rows[0][0]
        print("  عيّنة معرّف من هذه المجموعة:", rows[0][2], flush=True)
        cur.execute(f"""UPDATE knowledge_objects
                        SET metadata = metadata || '{{"library_group":"cma-authority-unified",
                              "library_card_name":"هيئة أسواق المال","doc_part":"القانون"}}'::jsonb
                        WHERE object_type IN ({ph}) AND {GEXPR} = %s""", LAW_TYPES + (base_g,))
        print("  دُمج القانون الأساسي:", cur.rowcount, "كائن ✓", flush=True)
    else:
        print("  لم يبق شيء غير مدموج — قد يكون اكتمل مسبقاً", flush=True)

    print("\n== 2) دمج حماية المستهلك صراحةً (القانون + اللائحة) ==", flush=True)
    cur.execute(f"""SELECT {GEXPR} AS g, count(*), min(id) FROM knowledge_objects
                    WHERE object_type IN ({ph})
                      AND (title ILIKE '%%حماية المستهلك%%' OR metadata->>'title' ILIKE '%%حماية المستهلك%%')
                    GROUP BY g""", LAW_TYPES)
    cp_rows = cur.fetchall()
    print("  مجموعات حماية المستهلك الحالية:", cp_rows, flush=True)

    UNIFIED_CP = "cp-unified"
    for g, c, sample_id in cp_rows:
        cur.execute(f"""SELECT count(*) FROM knowledge_objects
                        WHERE object_type IN ({ph}) AND {GEXPR} = %s
                          AND (title ILIKE '%%اللائحة التنفيذية%%' OR metadata->>'title' ILIKE '%%اللائحة التنفيذية%%')""",
                    LAW_TYPES + (g,))
        is_bylaw_majority = cur.fetchone()[0] > c / 2
        part = "اللائحة التنفيذية" if is_bylaw_majority else "القانون"
        cur.execute(f"""UPDATE knowledge_objects
                        SET metadata = metadata || jsonb_build_object(
                              'library_group', %s::text, 'library_card_name', 'قانون حماية المستهلك (39/2014)'::text,
                              'doc_part', %s::text),
                            branch='مدني', updated_at=now()
                        WHERE object_type IN ({ph}) AND {GEXPR} = %s""",
                    (UNIFIED_CP, part, *LAW_TYPES, g))
        print("  مجموعة", g[:30] if g else g, "->", part, "|", cur.rowcount, "كائن (وفرع=مدني) ✓", flush=True)

    print("\n== 3) التحقق النهائي: بطاقات كل فرع الآن ==", flush=True)
    cur.execute(f"""SELECT branch, count(DISTINCT {GEXPR}) FROM knowledge_objects
                    WHERE object_type IN ({ph}) GROUP BY branch ORDER BY 2 DESC""", LAW_TYPES)
    for b, c in cur.fetchall():
        print("  فرع '%s': %d بطاقة" % (b, c), flush=True)

    print("\n== 4) تفصيل بطاقة أسواق المال بعد الدمج ==", flush=True)
    cur.execute(f"""SELECT metadata->>'doc_part', count(*) FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND metadata->>'library_group'='cma-authority-unified'
                    GROUP BY 1""", LAW_TYPES)
    for p, c in cur.fetchall():
        print("  ", p, ":", c, flush=True)
    cur.execute(f"""SELECT count(*) FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND title ILIKE '%%أسواق المال%%'
                      AND coalesce(metadata->>'library_group','') <> 'cma-authority-unified'""", LAW_TYPES)
    print("  متبقٍّ خارج الدمج (يجب أن يكون 0):", cur.fetchone()[0], flush=True)

    print("\n== 5) تفصيل بطاقة حماية المستهلك بعد الدمج ==", flush=True)
    cur.execute(f"""SELECT metadata->>'doc_part', branch, count(*) FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND metadata->>'library_group'='cp-unified'
                    GROUP BY 1,2""", LAW_TYPES)
    for p, b, c in cur.fetchall():
        print("  جزء=%s فرع=%s: %d" % (p, b, c), flush=True)
PYEOF
echo ""
echo "===== اكتمل الإصلاح المستهدف ====="
