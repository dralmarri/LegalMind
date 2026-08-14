#!/bin/bash
# أمر آلي 85: إلحاق مراجع مبادئ الكتاب الخامس عشر الخمسة الأخيرة (مطابقة يدوية بمواضع الصفحات) — يكتمل به الكتاب ١٥
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
import embedding

ASSIGN = [
    ("JUR-تجاري-أنواع-من-الشركات-P1-p2-3-c498c", "قرار مجلس التأديب في المخالفة رقم 83/2019 مجلس تأديب ، 17/2019 شكوى الصادر بتاريخ 19/12/2019."),
    ("JUR-تجاري-أنواع-من-الشركات-P1-p3-1-eec4f", "قرار مجلس التأديب في المخالفة رقم 66/2019 مجلس تأديب ، 128/2019 هيئة الصادر بجلسة 19/12/2019."),
    ("JUR-تجاري-أنواع-من-الشركات-P1-p3-2-407c0", "قرار مجلس التأديب في المخالفة رقم 46/2018 مجلس تأديب - 90/2018 هيئة الصادر بجلسة 12/7/2018."),
    ("JUR-تجاري-أنواع-من-الشركات-P1-p3-3-7338e", "قرار مجلس التأديب في المخالفة رقم 56/2018 مجلس تأديب - 108/2018 هيئة الصادر بجلسة 13/9/2018."),
    ("JUR-تجاري-أنواع-من-الشركات-P2-p9-3-de0cf", "قرار مجلس التأديب في المخالفة رقم 46/2018 مجلس تأديب - 90/2018 هيئة الصادر بجلسة 12/7/2018."),
]

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    updated_ids = []
    for prefix, ref in ASSIGN:
        cur.execute("SELECT id, coalesce(original_text,'') FROM knowledge_objects WHERE id LIKE %s", (prefix + '%',))
        rows = cur.fetchall()
        if len(rows) != 1:
            print("  × غموض في المعرف %s: %d صفوف" % (prefix, len(rows)), flush=True)
            continue
        oid, txt = rows[0]
        if 'المرجع:' in txt or 'قرار مجلس التأديب' in txt:
            print("  - موجود مسبقاً: %s" % oid, flush=True)
            continue
        addition = 'المرجع: ' + ref
        cur.execute("""UPDATE knowledge_objects
                       SET original_text = original_text || '\n\n' || %s,
                           normalized_text = coalesce(normalized_text, original_text, '') || '\n\n' || %s,
                           metadata = coalesce(metadata,'{}'::jsonb)
                             || jsonb_build_object('reference_added_by','visual-transcription-claude-manual'::text),
                           updated_at=now()
                       WHERE id=%s""", (addition, addition, oid))
        updated_ids.append(oid)
        print("  ✓ %s ← %s" % (oid[:46], ref[:60]), flush=True)

    print("\nأُلحق: %d" % len(updated_ids), flush=True)

    if updated_ids:
        cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic, micro_issue, source_key
                       FROM knowledge_objects WHERE id = ANY(%s)""", (updated_ids,))
        rows = cur.fetchall()
        vecs = embedding.embed_passages([r[2] or '' for r in rows])
        pts = []
        for r, v in zip(rows, vecs):
            oid, title, text, otype, branch, topic, subtopic, micro, skey = r
            pts.append({"id": embedding.point_id(oid), "vector": v,
                        "payload": {"object_type": otype, "branch": branch, "topic": topic,
                                    "subtopic": subtopic, "micro_issue": micro,
                                    "source_key": skey, "title": title}})
        eng.qdrant_request("PUT", "/collections/%s/points?wait=true" % eng.COLLECTION, {"points": pts})
        print("أُعيد تضمين المحدثة: %d ✓" % len(rows), flush=True)

    cur.execute("""SELECT count(*) FROM knowledge_objects
                   WHERE object_type='judicial_principle'
                     AND metadata->>'title' LIKE '%%الكتاب ١٥%%'
                     AND original_text NOT LIKE '%%قرار مجلس التأديب%%'
                     AND original_text NOT LIKE '%%المرجع:%%'""")
    print("\nمبادئ الكتاب الخامس عشر المتبقية بلا مرجع: %d" % cur.fetchone()[0], flush=True)
PYEOF
echo "===== اكتمل الأمر 85 ====="
