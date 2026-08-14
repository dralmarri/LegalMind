#!/bin/bash
# أمر آلي 27: فحص عمود branch الفعلي (لا metadata) للكتب — قد يكون السبب الحقيقي لعدم الظهور
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

    print("== عمود branch الفعلي لكتب أسواق المال (قبل أي إصلاح) ==")
    cur.execute(f"""SELECT coalesce(branch,'(NULL)') AS branch_col, count(*)
                    FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND metadata->>'title' ILIKE '%اسواق%المال%'
                    GROUP BY 1 ORDER BY 2 DESC""", LAW_TYPES)
    rows = cur.fetchall()
    for b, c in rows:
        print("  branch='%s' | %d كائن" % (b, c))

    print("\n== تأكيد library_group مطبّق فعلاً (من الأمر السابق) ==")
    cur.execute(f"""SELECT count(*) FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND metadata->>'title' ILIKE '%اسواق%المال%'
                      AND coalesce(metadata->>'library_group','') <> ''""", LAW_TYPES)
    print("  كائنات فيها library_group الآن:", cur.fetchone()[0])

    # الإصلاح: إن كان العمود الفعلي ليس 'تجاري'، صحّحه (قانون أسواق المال منطقياً فرع تجاري)
    bad = [b for b, c in rows if b != 'تجاري']
    if bad:
        cur.execute(f"""UPDATE knowledge_objects SET branch='تجاري', updated_at=now()
                        WHERE object_type IN ({ph}) AND metadata->>'title' ILIKE '%اسواق%المال%'
                          AND (branch IS NULL OR branch <> 'تجاري')""", LAW_TYPES)
        print("\nصُحِّح عمود branch لـ %d كائن إلى 'تجاري' ✓" % cur.rowcount)
    else:
        print("\nعمود branch كان صحيحاً أصلاً — لا حاجة لإصلاحه")

    # محاكاة استعلام /api/browse الحقيقي بعد كل الإصلاحات
    GEXPR = ("COALESCE(metadata->>'library_group', substring(id from '^(legis-[a-z0-9]+-[0-9]+)'), "
             "substring(id from '^(lreg-[0-9]+-[0-9]+-k[0-9]+)'), "
             "substring(id from '^(regl-[0-9]+-[0-9]+)'), "
             "substring(id from '^(reg-[0-9]+-[0-9]+)'))")
    cur.execute(f"""SELECT {GEXPR} AS g, count(*),
                    COALESCE(min(metadata->>'library_card_name'), 'بلا اسم')
                    FROM knowledge_objects WHERE object_type IN ({ph}) AND branch='تجاري'
                    GROUP BY g HAVING g IS NOT NULL ORDER BY g""", LAW_TYPES)
    final = cur.fetchall()
    print("\n== المحاكاة النهائية: البطاقات التي ستظهر فعلاً تحت 'تجاري' ==")
    print("عددها:", len(final))
    for g, c, name in final:
        print("  ", name[:55], "|", c, "كائن")
PYEOF

{
  echo "=== فحص وإصلاح عمود branch الفعلي — $(date -u +%F' '%T) UTC ==="
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== اكتمل — أعيدي تحميل صفحة القوانين بعد دقيقتين وجرّبي مجدداً ====="
