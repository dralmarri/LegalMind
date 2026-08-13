#!/bin/bash
# حذف الشذرة الوحيدة المتبقية (أسماء المفوضين — نصها غير موجود في المصدر) من القاعدة والفهرس
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
/opt/LegalMind/.venv/bin/python - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

OID = "LEG-UNKNOWN-P8-20-9612527fc9da1414"
with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT title, left(original_text,200) FROM knowledge_objects WHERE id=%s", (OID,))
    r = cur.fetchone()
    if not r:
        print("الكائن غير موجود — ربما حُذف مسبقاً"); sys.exit(0)
    print("سيُحذف:", r[0])
    print("مطلع نصه:", (r[1] or "").replace("\n", " ")[:150])
    cur.execute("DELETE FROM legislation_mentions WHERE knowledge_object_id=%s", (OID,))
    cur.execute("DELETE FROM knowledge_objects WHERE id=%s", (OID,))
    eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/delete?wait=true",
                       {"filter": {"must": [{"key": "object_id", "match": {"value": OID}}]}})
    cur.execute("""SELECT verification_status, usable_as_citation, count(*)
                   FROM knowledge_objects
                   WHERE metadata->>'batch_id'=(SELECT batch_id FROM ingestion_batches
                                                WHERE object_count > 400 AND status='completed'
                                                ORDER BY started_at DESC LIMIT 1)
                   GROUP BY 1,2""")
    print("\nالحصيلة بعد التنظيف:")
    for vs, uc, c in cur.fetchall():
        print("  %s | استشهاد=%s | %d" % (vs, uc, c))
print("===== اكتمل التنظيف =====")
PYEOF
