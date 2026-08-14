#!/bin/bash
# أمر آلي 76: دمج المراجع بمبادئها — البادئة نفسها والتسلسل السابق بأي بصمة، مع ضمانة الانفراد
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
        m = re.match(r'^(.*-)(\d+)-[0-9a-f]{8,}$', rid)
        if not m:
            unmatched.append(rid[:50] + " | نمط غير متوقع")
            continue
        prefix, seq = m.group(1), int(m.group(2))
        cur.execute("""SELECT id, coalesce(title,'') FROM knowledge_objects
                       WHERE object_type='judicial_principle'
                         AND id ~ %s""", ('^' + re.escape(prefix) + str(seq - 1) + '-[0-9a-f]+$',))
        cands = [r for r in cur.fetchall() if not r[1].startswith('مرجع')]
        if len(cands) != 1:
            unmatched.append("%s | مرشحون=%d" % (rid[:50], len(cands)))
            continue
        pid, ptitle = cands[0]
        addition = rtext.strip()
        if not addition.startswith('المرجع'):
            addition = 'المرجع: ' + addition
        probe = addition.replace('المرجع: ', '')[:30]
        cur.execute("SELECT coalesce(original_text,'') FROM knowledge_objects WHERE id=%s", (pid,))
        ptext = cur.fetchone()[0]
        if not (probe and probe in ptext):
            cur.execute("""UPDATE knowledge_objects
                           SET original_text = original_text || '\n\n' || %s,
                               normalized_text = coalesce(normalized_text, original_text, '') || '\n\n' || %s,
                               updated_at=now()
                           WHERE id=%s""", (addition, addition, pid))
        cur.execute("DELETE FROM knowledge_objects WHERE id=%s", (rid,))
        deleted_ids.append(rid)
        updated_ids.append(pid)
        merged += 1
        print("  ✓ %s ← %s (%s)" % (rt[:28], pid[:45], ptitle[:38]), flush=True)

    print("\nدُمج وحُذف:", merged, "| لم يُربط:", len(unmatched), flush=True)
    for u in unmatched:
        print("  ×", u, flush=True)

    if deleted_ids:
        eng.qdrant_request("POST", "/collections/%s/points/delete" % eng.COLLECTION,
                           {"points": [embedding.point_id(i) for i in deleted_ids]})
        print("نُظف الفهرس الدلالي ✓", flush=True)
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
echo "===== اكتمل الأمر 76 ====="
