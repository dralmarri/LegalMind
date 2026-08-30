# -*- coding: utf-8 -*-
"""فهرسة جزئية آمنة: تُدرج/تُحدّث نقاط Qdrant لمعرفات محددة فقط، بلا حذف أي شيء —
البديل الصحيح عن `engine.legalmind_engine reindex` (الحذف والبناء الكامل) في أي دفعة
صغيرة (عشرات إلى بضع مئات). ثبت نجاحها عمليًا في جولة قانون تنظيم القضاء 80/2026
(169 كائنًا، أثناء انشغال الفهرسة الكاملة بالمعالج، بلا أي تصادم).

الاستعمال:
    /opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/reindex_delta.py 'legis-80-2026-%' 'legis-23-1990-%'
(كل وسيط نمط LIKE على id؛ يقبل عدة أنماط في نداء واحد)
"""
import sys, os
sys.path.insert(0, "/opt/LegalMind")
os.chdir("/opt/LegalMind")
import psycopg
from engine import legalmind_engine as eng
from engine import embedding


def main():
    patterns = sys.argv[1:]
    if not patterns:
        print("الاستعمال: reindex_delta.py 'نمط-LIKE-1' ['نمط-LIKE-2' ...]")
        sys.exit(1)

    dsn = os.environ["DATABASE_URL"]
    where = " OR ".join(["id LIKE %s"] * len(patterns))
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT id,title,original_text,object_type,branch,topic,subtopic,
                           micro_issue,source_key
                    FROM knowledge_objects WHERE {where} ORDER BY id""",
                patterns,
            )
            rows = cur.fetchall()
    print("عدد الصفوف المستهدفة:", len(rows))
    if not rows:
        print("لا صفوف مطابقة — تحقق من الأنماط.")
        sys.exit(1)

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
    print("REINDEX_DELTA_OK: %d نقطة أُدرجت/حُدِّثت (بلا حذف أي شيء آخر)" % len(points))


if __name__ == "__main__":
    main()
