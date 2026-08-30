# -*- coding: utf-8 -*-
"""تنظيف تشوهات ترتيب الحروف العربية داخل الكلمات (مثل اخلامس بدل الخامس، اإلجمالية بدل
الإجمالية) — فلترة رخيصة بالأنماط ثم تصحيح موثوق عبر النموذج مع حارس أقصى نسبة تغيير."""
import sys, os, re, json, time, difflib, urllib.request
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

MODEL = os.environ.get("LEGALMIND_INGEST_MODEL", "claude-sonnet-5")
KEY = os.environ["ANTHROPIC_API_KEY"]
BATCH_TEXTS = 6
MAX_PER_RUN = 150
EDIT_RATIO_MAX = 0.08

WORD_RE = re.compile(r'[ء-ي]+')

def has_candidate(text):
    for w in WORD_RE.findall(text or ""):
        if len(w) >= 3 and w[0] == 'ا' and w[1] != 'ل' and 'ل' in w[1:4]:
            return True
    return False

def edit_ratio(a, b):
    if not a:
        return 1.0
    return 1 - difflib.SequenceMatcher(None, a, b).ratio()

TOOL = {
    "name": "save_fixes",
    "description": "تصحيح تشوهات ترتيب الحروف العربية داخل الكلمات فقط",
    "input_schema": {
        "type": "object", "required": ["fixes"],
        "properties": {"fixes": {"type": "array", "items": {
            "type": "object", "required": ["id", "has_defect"],
            "properties": {
                "id": {"type": "string"},
                "has_defect": {"type": "boolean"},
                "fixed_text": {"type": "string"}}}}}}}

PROMPT = ("النصوص التالية مستخرجة بصرياً من مستندات قانونية عربية. بعض الكلمات فيها تشوّه طباعي محلي: "
          "حروف داخل الكلمة الواحدة تبدّل ترتيبها (أمثلة حقيقية: 'الخامس' ظهرت 'اخلامس'، 'الإجمالية' ظهرت "
          "'اإلجمالية'، 'المحتسب' ظهرت 'احملتسب'، 'الملاحق' ظهرت 'املالحق'، 'الاستثمار' ظهرت 'االستثمار'). "
          "هذا خلل حرفي محلي داخل الكلمة فقط، وليس خطأً إملائياً حقيقياً ولا معنوياً.\n\n"
          "لكل نص أدناه: افحص كل كلمة تبدأ بألف وفيها هذا النمط تحديداً. إن وجدت كلمة مشوهة بهذا النمط بعينه "
          "صحّح ترتيب حروفها فقط لتعود كلمة عربية صحيحة (غالباً 'ال' + بقية الكلمة) دون أي تغيير آخر في النص — "
          "لا تُضف ولا تحذف ولا تُعِد الصياغة ولا تصحح أخطاء إملائية أو نحوية أخرى غير هذا النمط تحديداً. "
          "إن لم تجد أي تشوه من هذا النوع بالذات اجعل has_defect=false ولا ترسل fixed_text.\n\n")

def call_api(items):
    listing = "\n\n".join("### %s\n%s" % (i["id"], i["text"][:3000]) for i in items)
    body = {"model": MODEL, "max_tokens": 16000,
            "tools": [TOOL], "tool_choice": {"type": "tool", "name": "save_fixes"},
            "messages": [{"role": "user", "content": [{"type": "text", "text": PROMPT + listing}]}]}
    data = json.dumps(body).encode("utf-8")
    for attempt in range(3):
        try:
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=data,
                                         headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
                                                  "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                res = json.loads(r.read())
            for blk in res.get("content", []):
                if blk.get("type") == "tool_use":
                    return blk["input"].get("fixes", [])
            return []
        except Exception as exc:
            print("  محاولة %d: %s" % (attempt + 1, str(exc)[:120]), flush=True)
            time.sleep(15 * (attempt + 1))
    return []

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,''),
                          object_type, branch, topic, subtopic, metadata->>'micro_issue', source_key
                   FROM knowledge_objects
                   WHERE coalesce(metadata->>'typo_checked','') <> 'true'
                     AND verification_status IN ('source_verified','operationally_accepted')
                   LIMIT 6000""")
    pool = cur.fetchall()
    print("مجموعة الفحص الأولية:", len(pool), flush=True)
    candidates = [r for r in pool if has_candidate(r[2])]
    print("كائنات مرشّحة (نمط مشتبه به):", len(candidates), flush=True)

    todo = candidates[:MAX_PER_RUN]
    fixed_n = checked_n = rejected_n = 0
    for s in range(0, len(todo), BATCH_TEXTS):
        chunk = todo[s:s + BATCH_TEXTS]
        by_id = {r[0]: r for r in chunk}
        items = [{"id": r[0], "text": r[2]} for r in chunk]
        results = call_api(items)
        for res in results:
            oid = res.get("id"); row = by_id.get(oid)
            if not row:
                continue
            checked_n += 1
            if not res.get("has_defect"):
                cur.execute("""UPDATE knowledge_objects
                               SET metadata = metadata || '{"typo_checked":"true"}'::jsonb WHERE id=%s""", (oid,))
                continue
            fixed = (res.get("fixed_text") or "").strip()
            orig = row[2]
            if not fixed or edit_ratio(orig, fixed) > EDIT_RATIO_MAX:
                rejected_n += 1
                cur.execute("""UPDATE knowledge_objects
                               SET metadata = metadata || '{"typo_checked":"true","typo_rejected_large_diff":"true"}'::jsonb
                               WHERE id=%s""", (oid,))
                print("  رُفض (تغيير كبير %.0f%%): %s" % (edit_ratio(orig, fixed) * 100, oid[-14:]), flush=True)
                continue
            cur.execute("""UPDATE knowledge_objects
                           SET original_text=%s, normalized_text=%s,
                               metadata = metadata || '{"typo_checked":"true","typo_fixed":"true"}'::jsonb,
                               updated_at=now() WHERE id=%s""",
                        (fixed, eng.normalize_text(fixed), oid))
            common = {"object_type": row[3], "branch": row[4], "topic": row[5],
                      "subtopic": row[6], "micro_issue": row[7], "source_key": row[8]}
            eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                               {"points": eng.build_points([(oid, row[1], fixed)], common)})
            fixed_n += 1
            print("  صُحّح %s | قبل: %s | بعد: %s" %
                  (oid[-14:], orig[:55].replace(chr(10), " "), fixed[:55].replace(chr(10), " ")), flush=True)

    print("\nنتيجة الجولة: فُحص=%d | صُحّح=%d | رُفض(تغيير كبير)=%d" % (checked_n, fixed_n, rejected_n), flush=True)
    cur.execute("""SELECT count(*) FROM knowledge_objects
                   WHERE coalesce(metadata->>'typo_checked','') <> 'true'
                     AND verification_status IN ('source_verified','operationally_accepted')""")
    print("إجمالي متبقٍ للفحص في الجولات القادمة:", cur.fetchone()[0], flush=True)
