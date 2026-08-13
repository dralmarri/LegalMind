#!/bin/bash
# مراجعة آلية للمواد المعلقة (machine_pending_human) في دفعة القانون البحري:
# قراءة بصرية ثانية مستقلة لصفحات المصدر، اعتماد المطابق، تصحيح المختلف وإعادة فهرسته.
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
cat > /root/auto_review.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, os, re, io, json, glob, time, base64, urllib.request
from collections import defaultdict
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
from pypdf import PdfReader, PdfWriter

MODEL = os.environ.get("LEGALMIND_INGEST_MODEL", "claude-sonnet-5")
KEY = os.environ["ANTHROPIC_API_KEY"]
PAGES = 15          # حجم جزء المعالجة الأصلي
MAX_ITEMS = 12      # أقصى عدد نصوص في نداء واحد
MIN_CONF = 0.75

TOOL = {
    "name": "save_verdicts",
    "description": "حفظ نتائج مراجعة نصوص المواد مقابل صفحات المصدر",
    "input_schema": {
        "type": "object", "required": ["verdicts"],
        "properties": {"verdicts": {"type": "array", "items": {
            "type": "object", "required": ["id", "status", "confidence"],
            "properties": {
                "id": {"type": "string"},
                "status": {"type": "string", "enum": ["correct", "corrected", "not_found"]},
                "corrected_text": {"type": "string"},
                "confidence": {"type": "number"},
                "note": {"type": "string"}}}}}}}

def call_api(pdf_b64, items):
    listing = "\n\n".join("### %s\nالعنوان: %s\nالنص المخزن:\n%s" % (i["id"], i["title"], i["text"])
                          for i in items)
    prompt = ("أنت مدقق نصوص قانونية. أمامك صفحات ممسوحة من مجلد قانون التجارة البحرية الكويتي "
              "(مجموعة التشريعات الكويتية - الجزء السادس). راجع كل نص من النصوص التالية حرفياً "
              "مقابل ما هو مطبوع في الصفحات المرفقة:\n"
              "- إن طابق النصُ المصدرَ حرفياً (مع التسامح في التشكيل وفواصل الأسطر وعلامات الترقيم) فالحكم correct.\n"
              "- إن وجدت اختلافاً في الكلمات أو نقصاً أو زيادة فاكتب النص الصحيح كاملاً كما هو مطبوع والحكم corrected مع وضع النص في corrected_text.\n"
              "- إن لم تجد المادة في هذه الصفحات إطلاقاً فالحكم not_found.\n"
              "لا تخمن أبداً ولا تكمل من معرفتك؛ انسخ فقط ما تراه مطبوعاً.\n\n" + listing)
    body = {"model": MODEL, "max_tokens": 30000,
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
                    return blk["input"].get("verdicts", [])
            return []
        except Exception as exc:
            print("محاولة %d فشلت: %s" % (attempt + 1, exc), flush=True)
            time.sleep(15 * (attempt + 1))
    return []

def slice_pdf(reader, start, end):
    w = PdfWriter()
    for p in range(max(0, start), min(end, len(reader.pages))):
        w.add_page(reader.pages[p])
    buf = io.BytesIO(); w.write(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def part_of(oid):
    m = re.match(r"LEG-UNKNOWN-P(\d+)-", oid)
    return int(m.group(1)) if m else None

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""SELECT batch_id FROM ingestion_batches
                   WHERE object_count > 400 AND status='completed'
                   ORDER BY started_at DESC LIMIT 1""")
    BID = cur.fetchone()[0]
    cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,''),
                          object_type, branch, topic, subtopic, metadata->>'micro_issue', source_key
                   FROM knowledge_objects
                   WHERE metadata->>'batch_id'=%s AND verification_status='machine_pending_human'
                     AND coalesce(metadata->>'human_edited','') <> 'true'""", (BID,))
    pending = cur.fetchall()
    cur.execute("""SELECT authority_status FROM knowledge_objects
                   WHERE metadata->>'batch_id'=%s AND verification_status='source_verified'
                   LIMIT 1""", (BID,))
    r = cur.fetchone()
    AUTH_OK = r[0] if r else None

    pdfs = sorted(glob.glob("/opt/legalmind-ingest/archive/*.pdf"),
                  key=os.path.getsize, reverse=True)
    pdfs = [f for f in pdfs if "بحري" in f or "السادس" in f] or pdfs
    SRC = pdfs[0]
    reader = PdfReader(SRC)
    print("الدفعة:", BID, "| معلّق للمراجعة:", len(pending),
          "| المصدر:", SRC, "(%d صفحة)" % len(reader.pages), flush=True)

    groups = defaultdict(list)
    for row in pending:
        groups[part_of(row[0])].append(row)

    stats = {"correct": 0, "corrected": 0, "not_found": 0, "low_conf": 0}
    leftovers = []

    def apply(vd, row_by_id, retry_bucket):
        oid = vd.get("id")
        row = row_by_id.get(oid)
        if row is None:
            return
        status, conf = vd.get("status"), float(vd.get("confidence") or 0)
        if status == "not_found":
            stats["not_found"] += 1
            retry_bucket.append(row)
            return
        if conf < MIN_CONF:
            stats["low_conf"] += 1
            print("  ثقة منخفضة (%s: %.2f) — يبقى معلقاً: %s" % (status, conf, oid), flush=True)
            return
        meta_patch = {"auto_review": status, "auto_review_conf": conf,
                      "auto_review_note": (vd.get("note") or "")[:300]}
        if status == "corrected" and (vd.get("corrected_text") or "").strip():
            text = vd["corrected_text"].strip()
            cur.execute("""UPDATE knowledge_objects
                           SET original_text=%s, normalized_text=%s,
                               verification_status='source_verified', usable_as_citation=true,
                               authority_status=coalesce(%s, authority_status),
                               metadata = metadata || %s::jsonb, updated_at=now()
                           WHERE id=%s""",
                        (text, eng.normalize_text(text), AUTH_OK, json.dumps(meta_patch), oid))
            common = {"object_type": row[3], "branch": row[4], "topic": row[5],
                      "subtopic": row[6], "micro_issue": row[7], "source_key": row[8]}
            pts = eng.build_points([(oid, row[1], text)], common)
            eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                               {"points": pts})
            stats["corrected"] += 1
            print("  صُحّح واعتُمد وأعيدت فهرسته: %s | %s" % (oid, row[1][:60]), flush=True)
        else:
            cur.execute("""UPDATE knowledge_objects
                           SET verification_status='source_verified', usable_as_citation=true,
                               authority_status=coalesce(%s, authority_status),
                               metadata = metadata || %s::jsonb, updated_at=now()
                           WHERE id=%s""", (AUTH_OK, json.dumps(meta_patch), oid))
            stats["correct"] += 1

    for part in sorted(k for k in groups if k):
        rows = groups[part]
        b64 = slice_pdf(reader, (part - 1) * PAGES, part * PAGES)
        for s in range(0, len(rows), MAX_ITEMS):
            chunk = rows[s:s + MAX_ITEMS]
            row_by_id = {r[0]: r for r in chunk}
            items = [{"id": r[0], "title": r[1], "text": r[2]} for r in chunk]
            print("الجزء P%d: مراجعة %d نص..." % (part, len(items)), flush=True)
            retry = []
            for vd in call_api(b64, items):
                apply(vd, row_by_id, retry)
            # المواد غير الموجودة قد تقع على حدود الجزء — جولة ثانية بنافذة موسّعة
            if retry:
                stats["not_found"] -= len(retry)
                b64w = slice_pdf(reader, (part - 1) * PAGES - 3, part * PAGES + 5)
                row_by_id2 = {r[0]: r for r in retry}
                items2 = [{"id": r[0], "title": r[1], "text": r[2]} for r in retry]
                print("  إعادة بنافذة موسعة لـ %d نص..." % len(items2), flush=True)
                final_miss = []
                for vd in call_api(b64w, items2):
                    apply(vd, row_by_id2, final_miss)
                stats["not_found"] += len(final_miss)
                leftovers += [r[0] for r in final_miss]

    print("\n===== الخلاصة =====", flush=True)
    print("اعتُمد كما هو:", stats["correct"], "| صُحّح واعتُمد:", stats["corrected"],
          "| لم يُعثر عليه:", stats["not_found"], "| ثقة منخفضة (بقي معلقاً):", stats["low_conf"], flush=True)
    if leftovers:
        print("بقيت معلقة (لم توجد في صفحات جزئها):", leftovers, flush=True)
    cur.execute("""SELECT verification_status, usable_as_citation, count(*)
                   FROM knowledge_objects WHERE metadata->>'batch_id'=%s
                   GROUP BY 1,2 ORDER BY 3 DESC""", (BID,))
    for vs, uc, c in cur.fetchall():
        print("  %s | استشهاد=%s | %d" % (vs, uc, c), flush=True)
    print("===== انتهت المراجعة الآلية =====", flush=True)
PYEOF
nohup /opt/LegalMind/.venv/bin/python /root/auto_review.py > /root/auto-review.log 2>&1 &
echo "انطلقت المراجعة الآلية في الخلفية (تقديراً 15-40 دقيقة)"
echo "تابع التقدم: tail -15 /root/auto-review.log"
