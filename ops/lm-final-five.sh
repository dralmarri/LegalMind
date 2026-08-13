#!/bin/bash
# جولة الختام: مراجعة مركزة للكائنات غير المحسومة + فصل المادة 256 إلى كائن مستقل
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
cat > /root/final_five.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, os, re, io, json, glob, time, base64, hashlib, urllib.request
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
from pypdf import PdfReader, PdfWriter

MODEL = os.environ.get("LEGALMIND_INGEST_MODEL", "claude-sonnet-5")
KEY = os.environ["ANTHROPIC_API_KEY"]
PAGES = 15

TOOL = {
    "name": "save_verdicts",
    "description": "حفظ نتيجة مراجعة نص واحد مقابل صفحات المصدر",
    "input_schema": {
        "type": "object", "required": ["verdicts"],
        "properties": {"verdicts": {"type": "array", "items": {
            "type": "object", "required": ["id", "status", "confidence"],
            "properties": {
                "id": {"type": "string"},
                "status": {"type": "string", "enum": ["correct", "corrected", "not_found", "non_legal_fragment"]},
                "corrected_text": {"type": "string"},
                "confidence": {"type": "number"},
                "note": {"type": "string"}}}}}}}

def call_api(pdf_b64, oid, title, text):
    prompt = ("أنت مدقق نصوص قانونية دقيق. ابحث في الصفحات المرفقة عن النص الآتي وقارنه حرفياً بالمطبوع:\n"
              "المعرف: %s\nالعنوان: %s\nالنص المخزن:\n%s\n\n"
              "التعليمات:\n"
              "- إن طابق المطبوعَ حرفياً (بتسامح في التشكيل وفواصل الأسطر) → correct.\n"
              "- إن اختلف → انسخ النص المطبوع كاملاً بدقة تامة في corrected_text → corrected.\n"
              "- إن لم تجده في هذه الصفحات → not_found.\n"
              "- إن كان المقطع مجرد شذرة غير قانونية (أسماء موقعين، بقايا صفحة) وموجوداً في الصفحات → "
              "non_legal_fragment مع نسخه المصحح في corrected_text إن أمكن.\n"
              "خذ وقتك في المطابقة كلمةً كلمة. لا تخمن أبداً." % (oid, title, text))
    body = {"model": MODEL, "max_tokens": 16000,
            "tools": [TOOL], "tool_choice": {"type": "tool", "name": "save_verdicts"},
            "messages": [{"role": "user", "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64}},
                {"type": "text", "text": prompt}]}]}
    data = json.dumps(body).encode("utf-8")
    for attempt in range(4):
        try:
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=data,
                                         headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
                                                  "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=900) as r:
                res = json.loads(r.read())
            for blk in res.get("content", []):
                if blk.get("type") == "tool_use":
                    v = blk["input"].get("verdicts", [])
                    return v[0] if v else None
        except Exception as exc:
            print("  محاولة %d فشلت: %s" % (attempt + 1, exc), flush=True)
            time.sleep(15 * (attempt + 1))
    return None

def slice_pdf(reader, start, end):
    w = PdfWriter()
    for p in range(max(0, start), min(end, len(reader.pages))):
        w.add_page(reader.pages[p])
    buf = io.BytesIO(); w.write(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def part_of(oid):
    m = re.match(r"LEG-UNKNOWN-P(\d+)-", oid)
    return int(m.group(1)) if m else 1

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""SELECT batch_id FROM ingestion_batches
                   WHERE object_count > 400 AND status='completed'
                   ORDER BY started_at DESC LIMIT 1""")
    BID = cur.fetchone()[0]
    pdfs = [f for f in glob.glob("/opt/legalmind-ingest/archive/*.pdf") if "بحري" in f]
    SRC = sorted(pdfs, key=os.path.getsize, reverse=True)[0]
    reader = PdfReader(SRC)
    cur.execute("""SELECT authority_status FROM knowledge_objects
                   WHERE metadata->>'batch_id'=%s AND verification_status='source_verified' LIMIT 1""", (BID,))
    AUTH_OK = (cur.fetchone() or [None])[0]

    # ===== 1) الكائنات غير المحسومة =====
    cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,''),
                          object_type, branch, topic, subtopic, metadata->>'micro_issue', source_key,
                          verification_status
                   FROM knowledge_objects
                   WHERE metadata->>'batch_id'=%s AND verification_status <> 'source_verified'""", (BID,))
    todo = cur.fetchall()
    print("كائنات غير محسومة:", len(todo), flush=True)
    for row in todo:
        oid, title = row[0], row[1]
        p = part_of(oid)
        print("\n== %s | %s | الحالة: %s ==" % (oid, title[:60], row[9]), flush=True)
        b64 = slice_pdf(reader, (p - 1) * PAGES - 3, p * PAGES + 5)
        vd = call_api(b64, oid, title, row[2][:6000])
        if not vd:
            print("  تعذر الحصول على حكم — يبقى كما هو", flush=True); continue
        status, conf = vd.get("status"), float(vd.get("confidence") or 0)
        print("  الحكم: %s | الثقة: %.2f | %s" % (status, conf, (vd.get("note") or "")[:100]), flush=True)
        patch = {"auto_review": status, "auto_review_conf": conf,
                 "auto_review_note": (vd.get("note") or "")[:300], "final_pass": True}
        if status in ("correct", "corrected", "non_legal_fragment") and conf >= 0.75:
            text = (vd.get("corrected_text") or "").strip() if status != "correct" else ""
            citable = status != "non_legal_fragment"
            if text:
                cur.execute("""UPDATE knowledge_objects
                               SET original_text=%s, normalized_text=%s,
                                   verification_status='source_verified', usable_as_citation=%s,
                                   authority_status=coalesce(%s, authority_status),
                                   metadata = metadata || %s::jsonb, updated_at=now() WHERE id=%s""",
                            (text, eng.normalize_text(text), citable, AUTH_OK, json.dumps(patch), oid))
                common = {"object_type": row[3], "branch": row[4], "topic": row[5],
                          "subtopic": row[6], "micro_issue": row[7], "source_key": row[8]}
                eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                                   {"points": eng.build_points([(oid, title, text)], common)})
                print("  → صُحّح واعتُمد وأعيدت فهرسته (استشهاد=%s)" % citable, flush=True)
            else:
                cur.execute("""UPDATE knowledge_objects
                               SET verification_status='source_verified', usable_as_citation=%s,
                                   authority_status=coalesce(%s, authority_status),
                                   metadata = metadata || %s::jsonb, updated_at=now() WHERE id=%s""",
                            (citable, AUTH_OK, json.dumps(patch), oid))
                print("  → اعتُمد كما هو (استشهاد=%s)" % citable, flush=True)
        else:
            cur.execute("""UPDATE knowledge_objects SET metadata = metadata || %s::jsonb, updated_at=now()
                           WHERE id=%s""", (json.dumps(patch), oid))
            print("  → لم يُحسم — بقي على حاله مع تسجيل الملاحظة", flush=True)

    # ===== 2) فصل المادة 256 =====
    print("\n== فصل المادة 256 من مقطع استكمال المادة 255 ==", flush=True)
    cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic,
                          metadata->>'micro_issue', source_key, metadata, authority_status
                   FROM knowledge_objects
                   WHERE metadata->>'batch_id'=%s AND title LIKE %s""", (BID, 'استكمال المادة 255%'))
    host = cur.fetchone()
    cur.execute("SELECT 1 FROM knowledge_objects WHERE metadata->>'batch_id'=%s AND title LIKE %s",
                (BID, 'المادة 256%'))
    if cur.fetchone():
        print("  المادة 256 موجودة ككائن مستقل مسبقاً — لا حاجة للفصل", flush=True)
    elif not host:
        print("  لم أجد مقطع الاستكمال!", flush=True)
    else:
        text = host[2]
        m = re.search(r"\(?\s*مادة\s*256\s*\)?", text)
        if not m:
            print("  لم أجد علامة المادة 256 داخل النص!", flush=True)
        else:
            text256 = text[m.start():].strip()
            rest = text[:m.start()].strip()
            new_id = "LEG-UNKNOWN-P15-c2b-" + hashlib.sha256(text256.encode()).hexdigest()[:16]
            meta = dict(host[9] or {})
            meta.update({"auto_review": "split_from_" + host[0], "final_pass": True})
            cur.execute("""INSERT INTO knowledge_objects
                           (id, object_type, branch, topic, subtopic, micro_issue, title,
                            original_text, normalized_text, source_key, verification_status,
                            authority_status, usable_as_citation, metadata)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'source_verified',%s,true,%s)
                           ON CONFLICT (id) DO NOTHING""",
                        (new_id, host[3], host[4], host[5], host[6], host[7],
                         "المادة 256 - المجموعة المدينة وتقدير الأموال",
                         text256, eng.normalize_text(text256), host[8], host[10],
                         eng.psycopg.types.json.Jsonb(meta)))
            cur.execute("""UPDATE knowledge_objects SET original_text=%s, normalized_text=%s,
                           updated_at=now() WHERE id=%s""",
                        (rest, eng.normalize_text(rest), host[0]))
            common = {"object_type": host[3], "branch": host[4], "topic": host[5],
                      "subtopic": host[6], "micro_issue": host[7], "source_key": host[8]}
            eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                               {"points": eng.build_points(
                                   [(new_id, "المادة 256 - المجموعة المدينة وتقدير الأموال", text256),
                                    (host[0], host[1], rest)], common)})
            print("  → أُنشئت المادة 256 كائناً مستقلاً (%s) وأعيدت فهرسة المقطعين ✓" % new_id, flush=True)

    # ===== 3) الحصيلة النهائية =====
    print("\n===== الحصيلة النهائية للدفعة =====", flush=True)
    cur.execute("""SELECT verification_status, usable_as_citation, count(*)
                   FROM knowledge_objects WHERE metadata->>'batch_id'=%s
                   GROUP BY 1,2 ORDER BY 3 DESC""", (BID,))
    for vs, uc, c in cur.fetchall():
        print("  %s | استشهاد=%s | %d" % (vs, uc, c), flush=True)
    cur.execute("SELECT source_key FROM knowledge_objects WHERE metadata->>'batch_id'=%s LIMIT 1", (BID,))
    sk = cur.fetchone()[0]
    cnt = eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/count",
                             {"exact": True, "filter": {"must": [{"key": "source_key", "match": {"value": sk}}]}})
    print("  نقاط الفهرس للمصدر البحري:", cnt["result"]["count"], flush=True)
    print("===== انتهت جولة الختام =====", flush=True)
PYEOF
nohup /opt/LegalMind/.venv/bin/python /root/final_five.py > /root/final-five.log 2>&1 &
echo "انطلقت جولة الختام في الخلفية (5-10 دقائق) — تابع: tail -40 /root/final-five.log"
