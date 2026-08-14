#!/bin/bash
# أمر آلي 36: (أ) تسريع القناة: تنفيذ الأوامر كل دقيقة بدل كل 5 دقائق — لا مزيد من الانتظار
#            (ب) فصل ملفات المبادئ القانونية نهائياً عن بطاقات القوانين -> تبويب المبادئ والأحكام
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

echo "== (أ) تسريع قناة التنفيذ إلى كل دقيقة =="
cat > /etc/cron.d/legalmind-autopilot <<'EOF'
* * * * * root /opt/legalmind-autopilot/pull.sh >/dev/null 2>&1
* * * * * root /opt/legalmind-autopilot/pushlog.sh >/dev/null 2>&1
EOF
chmod 644 /etc/cron.d/legalmind-autopilot
echo "القناة الآن تلتقط الأوامر خلال دقيقة واحدة ✓"

echo ""
echo "== (ب) فصل المبادئ عن بطاقات القوانين =="
$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    # 1) كل كائن مصدره ملف "المبادئ القانونية ..." أياً كان نوعه الحالي
    cur.execute("""SELECT id, object_type FROM knowledge_objects
                   WHERE metadata->>'title' ILIKE '%%المبادئ القانونية%%'""")
    rows = cur.fetchall()
    print("كائنات ملفات المبادئ القانونية (كل الأنواع):", len(rows), flush=True)
    by_type = {}
    for _, ot in rows:
        by_type[ot] = by_type.get(ot, 0) + 1
    print("توزيعها الحالي:", by_type, flush=True)

    # 2) التصحيح الشامل: نوع=مبدأ قضائي، فرع=تجاري، موضوع=مبادئ هيئة أسواق المال
    #    وإزالة كل مفاتيح العرض المكتبي حتى تختفي من بطاقات القوانين نهائياً
    cur.execute("""UPDATE knowledge_objects
                   SET object_type='judicial_principle', branch='تجاري',
                       topic='مبادئ هيئة أسواق المال',
                       metadata = (metadata - 'library_group' - 'library_card_name'
                                            - 'doc_part' - 'doc_subpart'),
                       updated_at=now()
                   WHERE metadata->>'title' ILIKE '%%المبادئ القانونية%%'""")
    n = cur.rowcount
    print("عُدِّل:", n, "كائن -> مبدأ قضائي / تجاري / مبادئ هيئة أسواق المال ✓", flush=True)

    # 3) إعادة فهرسة حمولة النوع في محرك البحث (محلي، بلا تكلفة)
    cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,''),
                          object_type, branch, topic, subtopic, metadata->>'micro_issue', source_key
                   FROM knowledge_objects WHERE metadata->>'title' ILIKE '%%المبادئ القانونية%%'""")
    allr = cur.fetchall()
    for s in range(0, len(allr), 48):
        w = allr[s:s + 48]
        common = {"object_type": w[0][3], "branch": w[0][4], "topic": w[0][5],
                  "subtopic": w[0][6], "micro_issue": w[0][7], "source_key": w[0][8]}
        eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                           {"points": eng.build_points([(r[0], r[1], r[2]) for r in w], common)})
    print("أُعيدت فهرسة", len(allr), "كائن بحمولة النوع الجديد ✓", flush=True)

    # 4) تحقق نهائي
    LAW_TYPES = ('legislation', 'legislation_article', 'legislation_issuing_article', 'legislation_preamble')
    ph = ",".join(["%s"] * len(LAW_TYPES))
    cur.execute(f"""SELECT count(*) FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND metadata->>'title' ILIKE '%%المبادئ القانونية%%'""",
                LAW_TYPES)
    leak = cur.fetchone()[0]
    print("\nمتبقٍّ داخل أنواع القوانين (يجب أن يكون 0):", leak, flush=True)

    cur.execute("""SELECT metadata->>'doc_part', metadata->>'doc_subpart', count(*)
                   FROM knowledge_objects
                   WHERE metadata->>'library_group'='cma-authority-unified'
                   GROUP BY 1,2 ORDER BY 1,2""")
    print("\nبنية بطاقة هيئة أسواق المال الآن (يجب ألا تحوي أي 'مبادئ'):", flush=True)
    for p, sp, c in cur.fetchall():
        print("  %s / %s : %d" % (p, sp, c), flush=True)

    cur.execute("""SELECT count(*) FROM knowledge_objects
                   WHERE object_type='judicial_principle' AND topic='مبادئ هيئة أسواق المال'""")
    print("\nمبادئ هيئة أسواق المال في تبويب المبادئ والأحكام:", cur.fetchone()[0], flush=True)
PYEOF
echo ""
echo "===== اكتمل الفصل ====="
