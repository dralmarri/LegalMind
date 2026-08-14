#!/bin/bash
# أمر آلي 73: دمج كائنات «مرجع المبدأ» داخل مبادئها ثم حذف المكرر وتحديث الفهرس الدلالي محلياً
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
import embedding

ONES = {'الأول':1,'الاول':1,'الحادي':1,'الثاني':2,'الثالث':3,'الرابع':4,'الخامس':5,
        'السادس':6,'السابع':7,'الثامن':8,'التاسع':9,'العاشر':10}
def parse_num(t):
    t = t.replace('مرجع المبدأ','').replace('المبدأ','').strip().rstrip(':').strip()
    m = re.search(r'\d+', t.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩','0123456789')))
    if m:
        return int(m.group(0))
    n = 0
    words = t.split()
    for w in words:
        w2 = w.lstrip('و')
        if w2 in ONES:
            n += ONES[w2]
        elif w2 == 'عشر':
            n += 10
        elif w2 in ('العشرين','العشرون'):
            n += 20
        elif w2 in ('الثلاثين','الثلاثون'):
            n += 30
        elif w2 in ('الأربعين','الأربعون'):
            n += 40
    return n or None

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,''), coalesce(source_key,'')
                   FROM knowledge_objects
                   WHERE object_type='judicial_principle' AND title LIKE 'مرجع المبدأ%%'""")
    refs = cur.fetchall()
    print("كائنات المراجع المنفصلة:", len(refs), flush=True)

    cur.execute("""SELECT id, coalesce(title,''), coalesce(source_key,'')
                   FROM knowledge_objects
                   WHERE object_type='judicial_principle' AND title LIKE 'المبدأ%%'""")
    prin = {}
    dups = set()
    for oid, t, sk in cur.fetchall():
        n = parse_num(t)
        if n:
            key = (sk, n)
            if key in prin:
                dups.add(key)
            else:
                prin[key] = oid
    print("مبادئ مرقمة قابلة للربط:", len(prin), flush=True)

    merged = 0
    unmatched = []
    deleted_ids = []
    updated_ids = []
    for rid, rt, rtext, rsk in refs:
        n = parse_num(rt)
        key = (rsk, n)
        if not n or key in dups or key not in prin:
            unmatched.append("%s | %s" % (rid[:40], rt[:40]))
            continue
        pid = prin[key]
        addition = rtext.strip()
        if not addition.startswith('المرجع'):
            addition = 'المرجع: ' + addition
        cur.execute("SELECT coalesce(original_text,'') FROM knowledge_objects WHERE id=%s", (pid,))
        ptext = cur.fetchone()[0]
        if addition[8:40] and addition[8:40] in ptext:
            pass  # المرجع موجود مسبقاً
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
    print("دُمج وحُذف المكرر:", merged, flush=True)
    if unmatched:
        print("لم يُربط (%d) — تُرك كما هو:" % len(unmatched), flush=True)
        for u in unmatched[:10]:
            print("  ×", u, flush=True)

    if deleted_ids:
        eng.qdrant_request("POST", "/collections/%s/points/delete" % eng.COLLECTION,
                           {"points": [embedding.point_id(i) for i in deleted_ids]})
        print("حُذفت نقاطها من الفهرس الدلالي ✓", flush=True)

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
        print("أُعيد تضمين المبادئ المحدثة محلياً: %d ✓" % len(rows), flush=True)

    cur.execute("""SELECT count(*) FROM knowledge_objects
                   WHERE object_type='judicial_principle' AND topic='مبادئ هيئة أسواق المال'""")
    print("\nمبادئ هيئة أسواق المال الآن:", cur.fetchone()[0], flush=True)
PYEOF
echo "===== اكتمل الأمر 73 ====="
