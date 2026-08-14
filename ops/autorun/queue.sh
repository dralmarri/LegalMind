#!/bin/bash
# أمر آلي 26: إصلاح عدم ظهور كتب اللائحة كبطاقات — إضافة library_group لكل كتاب
# قاعدة بيانات فقط، صفر تكلفة (لا إعادة فهرسة، هذا العرض يقرأ من postgres مباشرة)
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re, json
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

LAW_TYPES = ('legislation', 'legislation_article', 'legislation_issuing_article', 'legislation_preamble')

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    ph = ",".join(["%s"] * len(LAW_TYPES))
    cur.execute(f"""SELECT DISTINCT metadata->>'title' FROM knowledge_objects
                    WHERE object_type IN ({ph})
                      AND metadata->>'title' ILIKE '%اسواق%المال%'
                      AND coalesce(metadata->>'library_group','') = ''""", LAW_TYPES)
    titles = [r[0] for r in cur.fetchall() if r[0]]
    print("عناوين كتب لم تُجمَّع بعد:", len(titles), flush=True)

    total_updated = 0
    for title in titles:
        # مفتاح تجميع فريد ومستقر: نستخدم العنوان نفسه (فريد فعلاً لكل كتاب)
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
        total_updated += cur.rowcount
        print("  '%s' → مفتاح=%s | اسم البطاقة='%s' | %d كائن" %
              (title[:40], key[:35], card_name[:45], cur.rowcount), flush=True)

    print("\nإجمالي الكائنات المحدَّثة:", total_updated, flush=True)

    # تحقق: كم بطاقة ستظهر الآن تحت فرع تجاري؟
    cur.execute(f"""SELECT COALESCE(metadata->>'library_group',
                          substring(id from '^(legis-[a-z0-9]+-[0-9]+)'),
                          substring(id from '^(lreg-[0-9]+-[0-9]+-k[0-9]+)'),
                          substring(id from '^(regl-[0-9]+-[0-9]+)'),
                          substring(id from '^(reg-[0-9]+-[0-9]+)')) AS g, count(*)
                   FROM knowledge_objects
                   WHERE object_type IN ({ph}) AND branch='تجاري'
                   GROUP BY g HAVING g IS NOT NULL ORDER BY g""", LAW_TYPES)
    rows = cur.fetchall()
    print("\nبطاقات ستظهر الآن تحت فرع 'تجاري' (المحاكاة الفعلية لاستعلام /api/browse):", len(rows), flush=True)
    for g, c in rows:
        print("  ", g[:60], "|", c, flush=True)
PYEOF

{
  echo "=== إصلاح ظهور بطاقات كتب اللائحة التنفيذية — $(date -u +%F' '%T) UTC ==="
  echo "(قاعدة بيانات فقط — صفر تكلفة، لا إعادة فهرسة)"
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== اكتمل الإصلاح — جرّبي الآن فتح تبويب 'القوانين' في النظام ====="
