#!/bin/bash
# تشخيص: لماذا لا يسترجع الاستوديو مواد القانون البحري رغم اكتمال الفهرسة؟
set -e
APP=/opt/LegalMind/admin/app.py

echo "===== (1) مواضع استدعاء البحث في الاستوديو (لمعرفة قائمة الأنواع المطلوبة) ====="
grep -n "_draft_search(" "$APP" | grep -v "def _draft_search" | while IFS=: read -r ln _; do
  s=$((ln>6 ? ln-6 : 1)); e=$((ln+2))
  echo "--- السطر $ln ---"
  sed -n "${s},${e}p" "$APP"
done

echo ""
echo "===== (2) توزيع أنواع الكائنات وحالات التوثيق في القاعدة ====="
docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
  "SELECT object_type, count(*) FROM knowledge_objects GROUP BY 1 ORDER BY 2 DESC;"
docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
  "SELECT object_type, verification_status, usable_as_citation, count(*)
   FROM knowledge_objects
   WHERE metadata->>'batch_id' = (SELECT batch_id FROM ingestion_batches
                                  WHERE object_count > 400 AND status='completed'
                                  ORDER BY started_at DESC LIMIT 1)
   GROUP BY 1,2,3 ORDER BY 4 DESC;"

echo ""
echo "===== (3) بحث مباشر في الفهرس بسؤال المستخدم نفسه ====="
set -a; source /opt/LegalMind/deploy/.env; set +a
cat > /root/draft_trace.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
from sentence_transformers import SentenceTransformer

Q = "ما حالات ترك السفينة للمؤمن؟"
model = SentenceTransformer("intfloat/multilingual-e5-base")
vec = model.encode(["query: " + Q], normalize_embeddings=True).tolist()[0]

with eng.psycopg.connect(eng.database_url()) as conn:
    with conn.cursor() as cur:
        cur.execute("""SELECT batch_id FROM ingestion_batches
                       WHERE object_count > 400 AND status='completed'
                       ORDER BY started_at DESC LIMIT 1""")
        BID = cur.fetchone()[0]
        cur.execute("""SELECT DISTINCT object_type FROM knowledge_objects
                       WHERE metadata->>'batch_id'=%s""", (BID,))
        mar_types = [r[0] for r in cur.fetchall()]

        def title_of(oid):
            cur.execute("SELECT coalesce(title,'') FROM knowledge_objects WHERE id=%s", (oid,))
            r = cur.fetchone()
            return (r[0][:70] if r else "غير موجود في القاعدة!")

        def show(label, flt, limit=10):
            body = {"vector": vec, "limit": limit, "with_payload": True}
            if flt is not None:
                body["filter"] = flt
            res = eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/search", body)
            print("\n--- %s ---" % label, flush=True)
            for h in res["result"]:
                p = h.get("payload") or {}
                oid = p.get("object_id") or p.get("id") or h.get("id")
                print("  %.4f | نوع=%s | %s | %s" % (
                    h["score"], p.get("object_type"), oid, title_of(str(oid))), flush=True)

        print("دفعة القانون البحري:", BID, "| أنواعها في القاعدة:", mar_types, flush=True)

        # عيّنة من حمولة نقطة بحرية في الفهرس (هل الحقول موجودة؟)
        cur.execute("""SELECT id FROM knowledge_objects
                       WHERE metadata->>'batch_id'=%s LIMIT 1""", (BID,))
        sample_id = cur.fetchone()[0]
        sc = eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/scroll",
                                {"filter": {"must": [{"key": "object_id", "match": {"value": sample_id}}]},
                                 "limit": 1, "with_payload": True})
        pts = sc["result"]["points"]
        if pts:
            print("حمولة نقطة بحرية نموذجية:", {k: str(v)[:50] for k, v in (pts[0]["payload"] or {}).items()}, flush=True)
        else:
            print("تحذير: لم أجد نقطة بحمولة object_id =", sample_id, "— قد تكون الحمولة بمفتاح مختلف", flush=True)

        show("أ) بدون أي فلتر (أفضل 10)", None)
        show("ب) بفلتر نوع البحري نفسه %s" % mar_types,
             {"must": [{"key": "object_type", "match": {"any": mar_types}}]}, 5)
        cur.execute("""SELECT DISTINCT object_type FROM knowledge_objects
                       WHERE id LIKE 'legis-%'""")
        old_types = [r[0] for r in cur.fetchall()]
        print("\nأنواع الكائنات القديمة (legis-*):", old_types, flush=True)
        show("ج) بفلتر أنواع الكائنات القديمة %s" % old_types,
             {"must": [{"key": "object_type", "match": {"any": old_types}}]}, 5)
PYEOF
/opt/LegalMind/.venv/bin/python /root/draft_trace.py
echo ""
echo "===== انتهى التشخيص ====="
