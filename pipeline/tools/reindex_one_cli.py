#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إعادة فهرسة كائن واحد فقط في Qdrant (تضمين مادة/مبدأ محرَّر ثم upsert لنقطة واحدة).
سريعة وغير هدّامة: لا تحذف المجموعة ولا تلمس بقيّة النقاط — تكتب/تستبدل النقطة ذات
`point_id(object_id)` فقط، بحمولةٍ مطابقة تمامًا لِما يبنيه reindex الكامل.
تُستدعى من admin عبر مفسّر المحرّك (حيث sentence_transformers).
الاستعمال:  python reindex_one_cli.py <object_id>   أو  المعرّف من stdin.
المخرَج: سطر JSON على stdout: {"ok":true,"id":...,"point_id":...} أو {"ok":false,"error":...}."""
import sys, json
sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/engine")


def main():
    object_id = (sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()).strip()
    if not object_id:
        print(json.dumps({"ok": False, "error": "معرّف فارغ"}, ensure_ascii=False)); return
    try:
        import psycopg
        from engine import embedding
        from engine.legalmind_engine import COLLECTION, qdrant_request, database_url
    except Exception as exc:  # noqa
        print(json.dumps({"ok": False, "error": f"تعذّر تحميل المحرّك: {exc}"}, ensure_ascii=False)); return

    with psycopg.connect(database_url()) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id,title,original_text,object_type,branch,topic,subtopic,micro_issue,source_key
               FROM knowledge_objects WHERE id=%s""", (object_id,))
        row = cur.fetchone()
    if not row:
        print(json.dumps({"ok": False, "error": "المصدر غير موجود في قاعدة البيانات"}, ensure_ascii=False)); return

    oid, title, text, object_type, branch, topic, subtopic, micro_issue, source_key = row
    if not (text or "").strip():
        print(json.dumps({"ok": False, "error": "نصّ المصدر فارغ"}, ensure_ascii=False)); return

    # التضمين ببادئة passage: (نفس دالّة reindex) وبناء الحمولة بنفس ترتيب المفاتيح تمامًا
    vector = embedding.embed_passages([text])[0]
    point = {
        "id": embedding.point_id(oid),
        "vector": vector,
        "payload": {"object_type": object_type, "branch": branch, "topic": topic,
                    "subtopic": subtopic, "micro_issue": micro_issue,
                    "source_key": source_key, "object_id": oid,
                    "title": title or "",
                    **embedding.meta_for(oid, text).as_payload()},
    }
    qdrant_request("PUT", f"/collections/{COLLECTION}/points?wait=true", {"points": [point]})
    print(json.dumps({"ok": True, "id": oid, "point_id": point["id"], "collection": COLLECTION},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
