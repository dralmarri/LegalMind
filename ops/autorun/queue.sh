#!/bin/bash
# أمر آلي 87: إلحاق مراجع مبادئ الكتاب الثالث عشر — أنظمة الاستثمار الجماعي (25 مرجعاً منسوخاً بصرياً) بمبادئها في القاعدة
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python
curl -fsSL "https://raw.githubusercontent.com/dralmarri/LegalMind/af43a2e82ca7479e2feb219c170af842e1c34202/ops/autorun/refs-book13.json" -o /tmp/refs-book13.json

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re, json
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
import embedding

AR = re.compile(r'[؀-ۿ]{2,}')
def norm(w):
    return w.replace('أ','ا').replace('إ','ا').replace('آ','ا').replace('ى','ي').replace('ة','ه').replace('ـ','')
def sig(w):
    return ''.join(sorted(norm(w)))
def sigset(t):
    return {sig(x) for x in AR.findall(t) if len(x) >= 3}

entries = json.load(open('/tmp/refs-book13.json', encoding='utf-8'))
for e in entries:
    e['sig'] = sigset(e['k'])
print("مفاتيح المراجع:", len(entries), flush=True)

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,'') FROM knowledge_objects
                   WHERE object_type='judicial_principle'
                     AND metadata->>'title' LIKE '%%الكتاب ١٣%%'""")
    objs = cur.fetchall()
    print("مبادئ الكتاب الثالث عشر في القاعدة:", len(objs), flush=True)

    ok = skipped = amb = 0
    updated_ids = []
    for oid, t, txt in objs:
        if 'قرار مجلس التأديب' in txt or 'المرجع:' in txt:
            skipped += 1
            continue
        osig = sigset(t + ' ' + txt)
        scored = []
        for e in entries:
            cov = sum(1 for x in e['sig'] if x in osig) / max(1, len(e['sig']))
            scored.append((cov, e))
        scored.sort(key=lambda x: -x[0])
        best, e1 = scored[0]
        second, e2 = scored[1] if len(scored) > 1 else (0, None)
        if best < 0.55:
            amb += 1
            print("  × بلا مطابقة كافية (%.0f%%): %s | %s" % (best*100, oid[:40], t[:40]), flush=True)
            continue
        if e2 is not None and e2['r'] != e1['r'] and (best - second) < 0.05:
            amb += 1
            print("  × التباس بين مرجعين (%.0f%% مقابل %.0f%%): %s" % (best*100, second*100, t[:40]), flush=True)
            continue
        addition = 'المرجع: ' + e1['r']
        cur.execute("""UPDATE knowledge_objects
                       SET original_text = original_text || '\n\n' || %s,
                           normalized_text = coalesce(normalized_text, original_text, '') || '\n\n' || %s,
                           metadata = coalesce(metadata,'{}'::jsonb)
                             || jsonb_build_object('reference_added_by','visual-transcription-claude'::text)
                             || jsonb_build_object('reference_match', round(%s::numeric,2)),
                           updated_at=now()
                       WHERE id=%s""", (addition, addition, best, oid))
        ok += 1
        updated_ids.append(oid)
        print("  ✓ (%.0f%%) %s ← %s" % (best*100, t[:38], e1['r'][:52]), flush=True)

    print("\nأُلحق المرجع: %d | كان موجوداً: %d | التباس/بلا مطابقة: %d" % (ok, skipped, amb), flush=True)

    if updated_ids:
        cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic, micro_issue, source_key
                       FROM knowledge_objects WHERE id = ANY(%s)""", (updated_ids,))
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
        print("أُعيد تضمين المحدثة: %d ✓" % len(rows), flush=True)
PYEOF
echo "===== اكتمل الأمر 87 ====="
