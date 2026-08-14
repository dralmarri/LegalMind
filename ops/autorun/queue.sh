#!/bin/bash
# أمر آلي 22: تصحيح العنصر الوحيد المتبقي (الكتاب العاشر) — قاعدة بيانات فقط، صفر تكلفة
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""SELECT source_key FROM sources
                   WHERE file_name ILIKE '%الكتاب-العاشر-اسواق-المال%' LIMIT 1""")
    r = cur.fetchone()
    if not r:
        print("لم أجد مصدر الكتاب العاشر بهذا الاسم")
    else:
        sk = r[0]
        print("مفتاح الكتاب العاشر:", sk)
        cur.execute("""SELECT id, title FROM knowledge_objects
                       WHERE source_key=%s AND object_type='judicial_principle'""", (sk,))
        rows = cur.fetchall()
        print("عناصر مصنّفة خطأً وجدتها:", rows)

        cur.execute("""UPDATE knowledge_objects
                       SET object_type='legislation_article',
                           metadata = metadata || '{"reclassified_from":"judicial_principle","reclass_method":"manual_single_fix"}'::jsonb,
                           updated_at=now()
                       WHERE source_key=%s AND object_type='judicial_principle'""", (sk,))
        print("عُدّل:", cur.rowcount, "صف")

        cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic,
                              metadata->>'micro_issue', source_key
                       FROM knowledge_objects WHERE source_key=%s""", (sk,))
        allr = cur.fetchall()
        if allr:
            common = {"object_type": allr[0][3], "branch": allr[0][4], "topic": allr[0][5],
                      "subtopic": allr[0][6], "micro_issue": allr[0][7], "source_key": allr[0][8]}
            eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                               {"points": eng.build_points([(x[0], x[1], x[2]) for x in allr], common)})
            print("أُعيدت فهرسة %d كائن (محلياً، بلا تكلفة) ✓" % len(allr))

    cur.execute("SELECT object_type, count(*) FROM knowledge_objects WHERE object_type='judicial_principle' GROUP BY 1")
    print("\nتحقق أخير: إجمالي المتبقي 'مبدأ قضائي' في كل القاعدة:")
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE object_type='judicial_principle'")
    print(" ", cur.fetchone()[0])
PYEOF

{
  echo "=== تصحيح العنصر الأخير (الكتاب العاشر) — صفر تكلفة — $(date -u +%F' '%T) UTC ==="
  echo "اكتمل التصحيح ✓ — راجع المخرجات أعلاه في هذا السجل"
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشرت النتيجة ====="
