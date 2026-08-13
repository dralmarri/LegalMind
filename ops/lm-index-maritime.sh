#!/bin/bash
# فحص فهرسة دفعة القانون البحري في Qdrant وإعادة فهرسة الناقص
set -e
echo "== أخطاء المحرك في آخر ٣ ساعات (للتشخيص) =="
journalctl -u legalmind-ingest --since "3 hours ago" --no-pager 2>/dev/null | grep -iE "error|traceback|qdrant|fail" | tail -8 || true
set -a; source /opt/LegalMind/deploy/.env; set +a
cat > /root/maritime_index.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

with eng.psycopg.connect(eng.database_url()) as conn:
    with conn.cursor() as cur:
        cur.execute("""SELECT batch_id FROM ingestion_batches
                       WHERE object_count > 400 AND status='completed'
                       ORDER BY started_at DESC LIMIT 1""")
        BID = cur.fetchone()[0]
        cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,''), object_type, branch, topic, subtopic,
                              metadata->>'micro_issue', source_key
                       FROM knowledge_objects WHERE metadata->>'batch_id'=%s ORDER BY id""", (BID,))
        rows = cur.fetchall()
print("الدفعة:", BID, "| كائنات القاعدة:", len(rows), flush=True)
src_key = rows[0][8] if rows else None
cnt = eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/count",
                         {"exact": True, "filter": {"must": [{"key": "source_key", "match": {"value": src_key}}]}})
print("نقاط الفهرس قبل الإصلاح:", cnt["result"]["count"], flush=True)

total = 0
for s in range(0, len(rows), 48):
    w = rows[s:s + 48]
    embed_rows = [(r[0], r[1], r[2]) for r in w]
    common = {"object_type": w[0][3], "branch": w[0][4], "topic": w[0][5],
              "subtopic": w[0][6], "micro_issue": w[0][7], "source_key": w[0][8]}
    pts = eng.build_points(embed_rows, common)
    eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true", {"points": pts})
    total += len(w)
    print("فهرسة:", total, "/", len(rows), flush=True)

cnt2 = eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/count",
                          {"exact": True, "filter": {"must": [{"key": "source_key", "match": {"value": src_key}}]}})
print("نقاط الفهرس بعد الإصلاح:", cnt2["result"]["count"], flush=True)
print("== اكتملت فهرسة القانون البحري ==", flush=True)
PYEOF
nohup /opt/LegalMind/.venv/bin/python /root/maritime_index.py > /root/maritime-index.log 2>&1 &
echo "انطلقت الفهرسة في الخلفية (3-6 دقائق)"
echo "تابع: tail -8 /root/maritime-index.log"
