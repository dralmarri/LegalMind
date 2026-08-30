# -*- coding: utf-8 -*-
"""إضافة سريعة ومتوازية (لا تحذف شيئًا، لا تُصادم العملية الكاملة الجارية) —
تُدرج فقط نقاط legis-80-2026-* (87) وlegis-23-1990-* (82) في Qdrant فورًا،
باستعمال نفس دوال الفهرسة الحقيقية من المحرك (engine.legalmind_engine) حرفيًا."""
import sys, os
sys.path.insert(0, "/opt/LegalMind")
os.chdir("/opt/LegalMind")
import psycopg
from engine import legalmind_engine as eng
from engine import embedding

def main():
    dsn = os.environ["DATABASE_URL"]
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id,title,original_text,object_type,branch,topic,subtopic,micro_issue,source_key
                FROM knowledge_objects
                WHERE id LIKE 'legis-80-2026-%%' OR id LIKE 'legis-23-1990-%%'
                ORDER BY id
            """)
            rows = cur.fetchall()
    print("عدد الصفوف المستهدفة:", len(rows))
    assert len(rows) == 169, "العدد غير متوقع: %d (المتوقع 169)" % len(rows)

    vectors = embedding.embed_passages([r[2] for r in rows])
    points = []
    for row, vector in zip(rows, vectors):
        object_id, title, text, object_type, branch, topic, subtopic, micro_issue, source_key = row
        points.append({
            "id": embedding.point_id(object_id),
            "vector": vector,
            "payload": {"object_type": object_type, "branch": branch, "topic": topic,
                        "subtopic": subtopic, "micro_issue": micro_issue,
                        "source_key": source_key, "object_id": object_id,
                        "title": title or "",
                        **embedding.meta_for(object_id, text).as_payload()},
        })
    eng.qdrant_request("PUT", f"/collections/{eng.COLLECTION}/points?wait=true", {"points": points})
    print("FAST_DELTA_INDEX_OK: %d نقطة أُدرجت/حُدِّثت" % len(points))

if __name__ == "__main__":
    main()
