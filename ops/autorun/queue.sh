#!/bin/bash
# أمر آلي 74: دمج المراجع بمبادئها عبر تسلسل المعرفات (مرجع = تسلسل المبدأ + 1 وبنفس بصمة الملف)
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
import embedding

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,'')
                   FROM knowledge_objects
                   WHERE object_type='judicial_principle' AND title LIKE 'مرجع المبدأ%%'""")
    refs = cur.fetchall()
    print("المراجع المنفصلة:", len(refs), flush=True)

    merged = 0
    unmatched = []
    deleted_ids = []
    updated_ids = []
    for rid, rt, rtext in refs:
        m = re.match(r'^(.*-)(\d+)-([0-9a-f]{8,})$', rid)
        if not m:
            unmatched.append(rid[:50] + " | لا يطابق النمط")
            continue
        prefix, seq, h = m.group(1), int(m.group(2)), m.group(3)
        pid = "%s%d-%s" % (prefix, seq - 1, h)
        cur.execute("""SELECT coalesce(title,''), coalesce(original_text,'') FROM knowledge_objects
                       WHERE id=%s AND object_type='judicial_principle'""", (pid,))
        row = cur.fetchone()
        if not row or row[0].startswith('مرجع'):
            unmatched.append(rid[:50] + " | لا مبدأ عند التسلسل السابق")
            continue
        ptitle, ptext = row
        addition = rtext.strip()
        if not addition.startswith('المرجع'):
            addition = 'المرجع: ' + addition
        probe = addition.replace('المرجع: ', '')[:30]
        if probe and probe in ptext:
            print("  (المرجع موجود مسبقاً في %s)" % pid[:45], flush=True)
        else:
            cur.execute("""UPDATE knowledge_objects
                           SET original_text = original_text || '\n\n' || %s,
                               normalized_text = coalesce(normalized_text, original_text, '') || '\n\n' || %s,
                               updated_at=now()
                           WHERE id=%s""", (addition, addition, pid))
        cur.execute("DELETE FROM knowledge_objects WHERE id=%s", (rid,))
        deleted_ids.append(rid)
        updated_ids.append(pid)
        merged += 1
        print("  دُمج: %s → %s (%s)" % (rt[:30], pid[:42], ptitle[:35]), flush=True)

    print("\nدُمج وحُذف:", merged, "| لم يُربط:", len(unmatched), flush=True)
    for u in unmatched[:10]:
        print("  ×", u, flush=True)

    if deleted_ids:
        eng.qdrant_request("POST", "/collections/%s/points/delete" % eng.COLLECTION,
                           {"points": [embedding.point_id(i) for i in deleted_ids]})
        print("نُظف الفهرس الدلالي من المحذوف ✓", flush=True)
    if updated_ids:
        ids = sorted(set(updated_ids))
        cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic, micro_issue, source_key
                       FROM knowledge_objects WHERE id = ANY(%s)""", (ids,))
        rows = cur.fetchall()
        for s in range(0, len(rows), 32):
            win = rows[s:s+32]
            vecs = embedding.embed_passages([r[2] or '' for r in win])
            pts = []
            for r, v in zip(win, vecs):
                oid, title, text, otype, branch, topic, subtopic, micro, skey = r
                pts.append({"id": embedding.point_id(oid), "vector": v,
                            "payload": {"object_type": otype, "branch": branch, "topic": topic,
                                        "subtopic": subtopic, "micro_issue": micro,
                                        "source_key": skey, "title": title}})
            eng.qdrant_request("PUT", "/collections/%s/points?wait=true" % eng.COLLECTION, {"points": pts})
        print("أُعيد تضمين المبادئ المحدثة: %d ✓" % len(rows), flush=True)
PYEOF
echo "===== اكتمل الأمر 74 ====="
