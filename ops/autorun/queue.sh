#!/bin/bash
# أمر آلي 77: أين مراجع بقية مبادئ أسواق المال؟ تشخيص البيانات الوصفية وإدراج المرجع في النص إن وجد
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, json
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
import embedding

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    print("== عينة: الكائن المعروض في الشاشة ==", flush=True)
    cur.execute("""SELECT id, metadata FROM knowledge_objects
                   WHERE id LIKE 'JUR-تجاري-أنواع-من-الشركات-P1-p13-1-%%' LIMIT 1""")
    row = cur.fetchone()
    if row:
        print("id:", row[0], flush=True)
        print("metadata:", json.dumps(row[1], ensure_ascii=False)[:900], flush=True)

    print("\n== إحصاء مبادئ أسواق المال بلا مرجع في نصها ==", flush=True)
    cur.execute("""SELECT id, coalesce(original_text,''), metadata FROM knowledge_objects
                   WHERE object_type='judicial_principle' AND topic='مبادئ هيئة أسواق المال'""")
    rows = cur.fetchall()
    missing = []
    meta_keys = {}
    for oid, txt, meta in rows:
        if ('قرار مجلس التأديب' in txt) or ('المرجع' in txt):
            continue
        missing.append((oid, meta or {}))
        for k in (meta or {}):
            meta_keys[k] = meta_keys.get(k, 0) + 1
    print("الإجمالي: %d | بلا مرجع في النص: %d" % (len(rows), len(missing)), flush=True)
    print("مفاتيح البيانات الوصفية لدى الناقصة:", sorted(meta_keys.items(), key=lambda kv: -kv[1])[:15], flush=True)

    REF_KEYS = ['reference', 'مرجع', 'المرجع', 'ref', 'source_reference', 'decision', 'citation']
    fixed = 0
    updated_ids = []
    for oid, meta in missing:
        val = None
        for k, v in (meta or {}).items():
            if any(rk in k.lower() or rk in k for rk in REF_KEYS) and isinstance(v, str) and len(v) > 15:
                val = v.strip()
                break
        if val:
            addition = val if val.startswith('المرجع') else ('المرجع: ' + val)
            cur.execute("""UPDATE knowledge_objects
                           SET original_text = original_text || '\n\n' || %s,
                               normalized_text = coalesce(normalized_text, original_text, '') || '\n\n' || %s,
                               updated_at=now()
                           WHERE id=%s""", (addition, addition, oid))
            fixed += 1
            updated_ids.append(oid)
    print("\nأُدرج المرجع من البيانات الوصفية في النص: %d ✓" % fixed, flush=True)
    still = len(missing) - fixed
    if still:
        print("ما زال بلا مرجع إطلاقاً (لا في النص ولا في الوصفية): %d" % still, flush=True)
        shown = 0
        for oid, meta in missing:
            if oid in updated_ids:
                continue
            print("  ×", oid[:60], flush=True)
            shown += 1
            if shown >= 8:
                break

    if updated_ids:
        cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic, micro_issue, source_key
                       FROM knowledge_objects WHERE id = ANY(%s)""", (updated_ids,))
        rows2 = cur.fetchall()
        for s in range(0, len(rows2), 32):
            win = rows2[s:s+32]
            vecs = embedding.embed_passages([r[2] or '' for r in win])
            pts = []
            for r, v in zip(win, vecs):
                oid, title, text, otype, branch, topic, subtopic, micro, skey = r
                pts.append({"id": embedding.point_id(oid), "vector": v,
                            "payload": {"object_type": otype, "branch": branch, "topic": topic,
                                        "subtopic": subtopic, "micro_issue": micro,
                                        "source_key": skey, "title": title}})
            eng.qdrant_request("PUT", "/collections/%s/points?wait=true" % eng.COLLECTION, {"points": pts})
        print("أُعيد تضمين المحدثة: %d ✓" % len(rows2), flush=True)
PYEOF
echo "===== اكتمل الأمر 77 ====="
