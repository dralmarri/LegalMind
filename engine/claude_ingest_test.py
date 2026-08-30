# -*- coding: utf-8 -*-
"""قارئ Claude التجريبي — معاينة فقط، لا يكتب في القاعدة إطلاقاً."""
import base64, json, os, re, sys, urllib.request
sys.path.insert(0, "/opt/LegalMind/engine")

API = "https://api.anthropic.com/v1/messages"

def env(key):
    v = os.environ.get(key)
    if v: return v
    for line in open("/opt/LegalMind/deploy/.env"):
        if line.startswith(key + "="):
            return line.strip().split("=", 1)[1]
    return ""

MODEL = env("LEGALMIND_INGEST_MODEL") or "claude-sonnet-5"

def call_claude(blocks, system, max_tokens=16000):
    body = {"model": MODEL, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": blocks}]}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "x-api-key": env("ANTHROPIC_API_KEY"),
                 "anthropic-version": "2023-06-01"})
    r = json.load(urllib.request.urlopen(req, timeout=600))
    return "".join(b.get("text", "") for b in r.get("content", []))

def call_claude_json(blocks, system, max_tokens=32000):
    body = {"model": MODEL, "max_tokens": max_tokens, "system": system,
            "tools": [{"name": "save_structure", "description": "حفظ الهيكل المستخرج للمستند وفق المخطط المطلوب في التعليمات",
                       "input_schema": {"type": "object", "required": ["document_kind", "title", "branch", "topic", "reading_quality", "chunks"],
 "properties": {
  "document_kind": {"type": "string", "enum": ["legislation", "judicial_principles_collection", "full_judgment", "judicial_template", "legal_memorandum", "legal_document", "compound_document"]},
  "title": {"type": "string"},
  "law_number": {"type": ["string", "null"]},
  "law_year": {"type": ["string", "null"]},
  "branch": {"type": "string"}, "topic": {"type": "string"}, "subtopic": {"type": ["string", "null"]},
  "suggested_new": {"type": ["string", "null"]},
  "reading_quality": {"type": "string", "enum": ["clean", "degraded", "partial"]},
  "warnings": {"type": "array", "items": {"type": "string"}},
  "chunks": {"type": "array", "items": {"type": "object",
    "required": ["local_id", "kind", "title", "text", "confidence"],
    "properties": {
      "local_id": {"type": "string"}, "kind": {"type": "string"}, "number": {"type": ["string", "null"]},
      "title": {"type": "string"}, "text": {"type": "string"},
      "legislation_mentions": {"type": "array", "items": {"type": "object", "properties": {
        "law_number": {"type": ["string", "null"]}, "law_year": {"type": ["string", "null"]},
        "article_number": {"type": ["string", "null"]}}}},
      "confidence": {"type": "number"}, "notes": {"type": ["string", "null"]}}}}}}}],
            "tool_choice": {"type": "tool", "name": "save_structure"},
            "messages": [{"role": "user", "content": blocks}]}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "x-api-key": env("ANTHROPIC_API_KEY"),
                 "anthropic-version": "2023-06-01"})
    r = json.load(urllib.request.urlopen(req, timeout=600))
    if r.get("stop_reason") == "max_tokens":
        print("!! تحذير: الرد بلغ سقف الطول وقد يكون مبتوراً")
    for b in r.get("content", []):
        if b.get("type") == "tool_use":
            return b["input"]
    raise RuntimeError("لا tool_use في الرد: " + str(r)[:300])

def parse_json(s):
    s = re.sub(r"^```(json)?|```$", "", s.strip(), flags=re.M).strip()
    try:
        return json.loads(s[s.index("{"): s.rindex("}") + 1])
    except Exception:
        print("!! الرد لم يحتوِ JSON صالحاً — أوله:")
        print((s or "(رد فارغ)")[:400])
        raise

def taxonomy():
    import psycopg
    with psycopg.connect(env("DATABASE_URL")) as conn:
        rows = conn.execute("""SELECT branch, topic, count(*) FROM knowledge_objects
                               WHERE topic IS NOT NULL GROUP BY 1,2 ORDER BY 3 DESC LIMIT 120""").fetchall()
    tx = {}
    for b, t, _ in rows:
        tx.setdefault(b, []).append(t)
    return tx

def read_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md"):
        return open(path, encoding="utf-8", errors="replace").read(), "text"
    try:
        from normalizer import normalize
        return normalize(__import__("pathlib").Path(path)).body, "normalizer"
    except Exception:
        pass
    try:
        from normalizer.canonical import normalize
        return normalize(__import__("pathlib").Path(path)).body, "normalizer"
    except Exception as e:
        if ext == ".pdf":
            return None, "vision"
        raise SystemExit("تعذرت قراءة الملف نصياً وليس PDF للرؤية: " + str(e))

SYSTEM = """أنت محرر قانوني كويتي خبير تفهرس مستندات لمكتبة قانونية محكمة التوثيق.
اقرأ المستند وهيكله كما يفعل محرر بشري دقيق. قواعد صارمة:
- النص يُنقل حرفياً كما ورد، لا تلخص ولا تعد الصياغة. عند القراءة من صورة صحح أخطاء المسح الواضحة فقط واخفض الثقة.
- قانون/مرسوم/لائحة: قطعه مواد كاملة (كل مادة برقمها ونصها الكامل حتى المادة التالية).
- مجموعة مبادئ أو أحكام تمييز: قطعها مبدأ مبدأ، ولكل مبدأ عنوان وصفي دقيق من مضمونه (رقم الطعن/السنة/الموضوع) — ممنوع عناوين مثل "المبدأ 1".
- حكم كامل واحد: كائن واحد بعنوان دقيق.
- استخرج كل إشارة تشريعية (رقم القانون، السنة، رقم المادة) في legislation_mentions لكل قطعة.
- صنف حصراً على تصنيفات المكتبة المعطاة (branch ثم topic منها). إن لم يطابق شيء ضع الأقرب واقترح الأدق في suggested_new.
- confidence لكل قطعة من 0 إلى 1: أقل من 0.8 = تحتاج مراجعة بشرية مع ذكر السبب في notes.
أجب بـ JSON فقط بهذا المخطط:
{"document_kind":"legislation|judicial_principles_collection|full_judgment|judicial_template|legal_memorandum|legal_document",
 "title":"","law_number":null,"law_year":null,"branch":"","topic":"","subtopic":"","suggested_new":null,
 "reading_quality":"clean|degraded|partial","warnings":[],
 "chunks":[{"local_id":"ART-1 أو PR-1","kind":"article|principle|judgment|section","number":"","title":"","text":"",
            "legislation_mentions":[{"law_number":"","law_year":"","article_number":""}],
            "confidence":1.0,"notes":""}]}"""

def main():
    if len(sys.argv) < 2:
        raise SystemExit("الاستخدام: claude_ingest_test.py <ملف>")
    path = sys.argv[1]
    tx = taxonomy()
    text, how = read_text(path)
    header = "تصنيفات المكتبة الحالية (branch: topics):\n" + json.dumps(tx, ensure_ascii=False)
    if how == "vision":
        raw = open(path, "rb").read()
        if len(raw) > 30 * 1024 * 1024:
            raise SystemExit("الملف أكبر من 30MB — قسّمه أولاً")
        blocks = [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                   "data": base64.b64encode(raw).decode()}},
                  {"type": "text", "text": header + "\n\nاقرأ المستند المرفق (قد يكون مسحاً ضوئياً) وهيكله."}]
        print(">> مسار الرؤية (PDF ممسوح/غير قابل للاستخراج النصي)")
    else:
        if len(text) > 350000:
            print("!! نص طويل (%d حرفاً) — سيعالج أول 350 ألف" % len(text)); text = text[:350000]
        blocks = [{"type": "text", "text": header + "\n\nالمستند:\n" + text + "\n\nهيكل المستند أعلاه."}]
        print(">> مسار النص (قراءة عبر: %s)" % how)
    print(">> إرسال إلى %s ..." % MODEL)
    result = call_claude_json(blocks, SYSTEM)

    ext_pdf = path.lower().endswith(".pdf")
    confs = [float(c.get("confidence", 0)) for c in result.get("chunks", [])] or [0]
    if how != "vision" and ext_pdf and "--no-vision" not in sys.argv and (
            result.get("reading_quality") == "partial" or max(confs) < 0.5):
        print(">> النص المستخرج رديء (%s، أعلى ثقة %.2f) — إعادة القراءة بالرؤية ..." % (result.get("reading_quality"), max(confs)))
        raw = open(path, "rb").read()
        if len(raw) <= 30 * 1024 * 1024:
            vblocks = [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                        "data": base64.b64encode(raw).decode()}},
                       {"type": "text", "text": header + "\n\nاقرأ المستند المرفق قراءة بصرية (مسح ضوئي) وهيكله."}]
            result = call_claude_json(vblocks, SYSTEM)
            text = None; src_ok = False
            print(">> اكتملت قراءة الرؤية")

    norm = lambda s: re.sub(r"\s+", " ", s or "").strip()
    src_norm = norm(text) if text else None
    out = os.path.join("/root", "ingest-preview-" + os.path.basename(path) + ".json")
    json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("\n===== النتيجة =====")
    print("النوع: %s | الجودة: %s" % (result.get("document_kind"), result.get("reading_quality")))
    print("العنوان: %s" % result.get("title"))
    print("التصنيف: %s / %s / %s" % (result.get("branch"), result.get("topic"), result.get("subtopic")))
    if result.get("suggested_new"): print("اقتراح تصنيف جديد: %s" % result["suggested_new"])
    if result.get("warnings"): print("تحذيرات: %s" % " | ".join(result["warnings"]))
    chunks = result.get("chunks", [])
    print("\nالقطع (%d):" % len(chunks))
    need_review = 0
    for c in chunks:
        grounded = ""
        if src_norm is not None:
            probe = norm(c.get("text", ""))[:120]
            grounded = " | حرفي:نعم" if probe and probe in src_norm else " | حرفي:لا!"
        conf = float(c.get("confidence", 0))
        flag = " ⟵ للمراجعة" if conf < 0.8 or "حرفي:لا" in grounded else ""
        if flag: need_review += 1
        m = c.get("legislation_mentions") or []
        print(" %s | %s | %d حرف | ثقة %.2f%s%s" % (c.get("local_id"), (c.get("title") or "")[:60],
              len(c.get("text", "")), conf, grounded, flag))
        if m: print("    إشارات: " + ", ".join("ق%s/%s م%s" % (x.get("law_number"), x.get("law_year"), x.get("article_number")) for x in m[:6]))
        if c.get("notes"): print("    ملاحظة: " + c["notes"][:100])
    print("\nخلاصة: %d قطعة، منها %d تحتاج مراجعة بشرية" % (len(chunks), need_review))
    print("التفاصيل الكاملة: %s" % out)

main()
