#!/bin/bash
# أمر آلي 80: إلحاق 5 مراجع محسومة يدوياً لمبادئ الكتاب الخامس + طباعة نصوص الأربعة المتبقية كاملة
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
import embedding

# مطابقات محسومة يدوياً (مراجعة بصرية للملف مقابل عناوين القاعدة)
ASSIGN = [
    ("JUR-تجاري-أنواع-من-الشركات-P1-p12-2-d009", "قرار مجلس التأديب في المخالفة رقم 98/2018 مجلس تأديب - 155/2018 هيئة الصادر بتاريخ 3/1/2019."),
    ("JUR-تجاري-أنواع-من-الشركات-P1-p4-3-f71db", "قرار مجلس التأديب في المخالفة رقم 94/2018 مجلس تأديب، 128/2018 هيئة الصادر بجلسة 20/12/2018."),
    ("JUR-تجاري-أنواع-من-الشركات-P1-p11-1-7487", "قرار مجلس التأديب في المخالفة رقم 4/2019 مجلس تأديب - 179/2018 هيئة الصادر بتاريخ 27/2/2019."),
    ("JUR-تجاري-أنواع-من-الشركات-P1-p6-1-4c2ea", "قرار مجلس التأديب في المخالفة رقم 56/2019 مجلس تأديب، 74/2019 هيئة الصادر بجلسة 5/12/2019."),
    ("JUR-تجاري-أنواع-من-الشركات-P1-p7-2-4d981", "قرار مجلس التأديب في المخالفة رقم 87/2018 مجلس تأديب - 132/2018 هيئة الصادر بجلسة 7/4/2019."),
]
# تحتاج نص الملخص للتمييز
PRINT_PREFIXES = [
    "JUR-تجاري-أنواع-من-الشركات-P1-p8-3-cbedf",
    "JUR-تجاري-أنواع-من-الشركات-P1-p9-1-bfc24",
    "JUR-تجاري-أنواع-من-الشركات-P1-p13-2-2ada",
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
        print("  ✓ %s ← %s" % (oid[:44], ref[:60]), flush=True)

    print("\nأُلحق يدوياً: %d" % len(updated_ids), flush=True)

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

    print("\n===== النصوص الكاملة للمبادئ الأربعة المتبقية =====", flush=True)
    targets = list(PRINT_PREFIXES)
    for prefix in targets:
        cur.execute("SELECT id, coalesce(title,''), coalesce(original_text,'') FROM knowledge_objects WHERE id LIKE %s", (prefix + '%',))
        for oid, t, txt in cur.fetchall():
            print("\n--- %s\nالعنوان: %s\nالنص:\n%s" % (oid, t, txt[:1400]), flush=True)
    cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,'') FROM knowledge_objects
                   WHERE object_type='judicial_principle'
                     AND metadata->>'title' LIKE '%%الكتاب ٥%%'
                     AND title LIKE 'وجوب أن يقوم الشخص المرخص له بحفظ الدفات%%'""")
    for oid, t, txt in cur.fetchall():
        print("\n--- %s\nالعنوان: %s\nالنص:\n%s" % (oid, t, txt[:1400]), flush=True)
PYEOF
echo "===== اكتمل الأمر 80 ====="
