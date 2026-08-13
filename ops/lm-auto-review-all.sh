#!/bin/bash
# المراجعة الآلية الشاملة لكل الدفعات المعلقة: تدقيق مقابل المصدر، اعتماد/تصحيح، وترميم الفهرسة
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
cat > /root/auto_review_all.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, os, re, io, json, glob, time, base64, urllib.request
from collections import defaultdict
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
from pypdf import PdfReader, PdfWriter

MODEL = os.environ.get("LEGALMIND_INGEST_MODEL", "claude-sonnet-5")
KEY = os.environ["ANTHROPIC_API_KEY"]
PAGES = 15
MAX_ITEMS = 12
MIN_CONF = 0.75

TOOL = {
    "name": "save_verdicts",
    "description": "حفظ نتائج مراجعة نصوص مقابل المصدر",
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

PROMPT = ("أنت مدقق نصوص قانونية. راجع كل نص من النصوص التالية حرفياً مقابل المصدر المرفق:\n"
          "- إن طابق النصُ المصدرَ حرفياً (بتسامح في التشكيل وفواصل الأسطر والترقيم) → correct.\n"
          "- إن اختلف في الكلمات أو نقص أو زاد → اكتب النص الصحيح كاملاً كما في المصدر في corrected_text → corrected.\n"
          "- إن لم تجد النص في هذا الجزء من المصدر → not_found.\n"
          "لا تخمن أبداً ولا تكمل من معرفتك؛ انسخ فقط ما تراه في المصدر.\n\n")

def call_api(content_blocks, items):
    listing = "\n\n".join("### %s\nالعنوان: %s\nالنص المخزن:\n%s" % (i["id"], i["title"], i["text"][:6000])
                          for i in items)
    body = {"model": MODEL, "max_tokens": 30000,
            "tools": [TOOL], "tool_choice": {"type": "tool", "name": "save_verdicts"},
            "messages": [{"role": "user", "content": content_blocks + [{"type": "text", "text": PROMPT + listing}]}]}
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
            print("    محاولة %d فشلت: %s" % (attempt + 1, str(exc)[:120]), flush=True)
            time.sleep(15 * (attempt + 1))
    return []

def pdf_slice_b64(reader, start, end):
    w = PdfWriter()
    for p in range(max(0, start), min(end, len(reader.pages))):
        w.add_page(reader.pages[p])
    buf = io.BytesIO(); w.write(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def part_of(oid):
    m = re.search(r"-P(\d+)-", oid)
    return int(m.group(1)) if m else None

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""SELECT DISTINCT metadata->>'batch_id' FROM knowledge_objects
                   WHERE verification_status='machine_pending_human'
                     AND coalesce(metadata->>'human_edited','') <> 'true'
                     AND metadata->>'batch_id' IS NOT NULL""")
    batches = [r[0] for r in cur.fetchall()]
    print("دفعات فيها نصوص معلقة:", len(batches), flush=True)

    cur.execute("""SELECT authority_status FROM knowledge_objects
                   WHERE verification_status='source_verified' AND authority_status IS NOT NULL
                   LIMIT 1""")
    r = cur.fetchone()
    AUTH_DEFAULT = r[0] if r else None

    total = {"correct": 0, "corrected": 0, "left": 0}

    def apply(vd, row_by_id, auth_ok, leftovers):
        oid = vd.get("id"); row = row_by_id.get(oid)
        if row is None:
            return
        status, conf = vd.get("status"), float(vd.get("confidence") or 0)
        if status == "not_found":
            leftovers.append(row); return
        if conf < MIN_CONF:
            total["left"] += 1
            print("    ثقة منخفضة (%.2f) بقي معلقاً: %s" % (conf, oid), flush=True); return
        patch = {"auto_review": status, "auto_review_conf": conf,
                 "auto_review_note": (vd.get("note") or "")[:300]}
        text = (vd.get("corrected_text") or "").strip() if status == "corrected" else ""
        if text:
            cur.execute("""UPDATE knowledge_objects SET original_text=%s, normalized_text=%s,
                           verification_status='source_verified', usable_as_citation=true,
                           authority_status=coalesce(%s, authority_status),
                           metadata = metadata || %s::jsonb, updated_at=now() WHERE id=%s""",
                        (text, eng.normalize_text(text), auth_ok, json.dumps(patch), oid))
            common = {"object_type": row[3], "branch": row[4], "topic": row[5],
                      "subtopic": row[6], "micro_issue": row[7], "source_key": row[8]}
            eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                               {"points": eng.build_points([(oid, row[1], text)], common)})
            total["corrected"] += 1
        else:
            cur.execute("""UPDATE knowledge_objects SET verification_status='source_verified',
                           usable_as_citation=true, authority_status=coalesce(%s, authority_status),
                           metadata = metadata || %s::jsonb, updated_at=now() WHERE id=%s""",
                        (auth_ok, json.dumps(patch), oid))
            total["correct"] += 1

    for BID in batches:
        try:
            cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,''),
                                  object_type, branch, topic, subtopic, metadata->>'micro_issue', source_key
                           FROM knowledge_objects
                           WHERE metadata->>'batch_id'=%s AND verification_status='machine_pending_human'
                             AND coalesce(metadata->>'human_edited','') <> 'true'""", (BID,))
            pending = cur.fetchall()
            if not pending:
                continue
            files = [f for f in glob.glob("/opt/legalmind-ingest/archive/%s__*" % BID)
                     if not f.endswith(".json") and not f.endswith(".canonical.md")]
            if not files:
                cur.execute("""SELECT file_name FROM sources WHERE source_key=%s LIMIT 1""", (pending[0][8],))
                fr = cur.fetchone()
                if fr:
                    files = [f for f in glob.glob("/opt/legalmind-ingest/archive/*__" + fr[0])
                             if not f.endswith(".json") and not f.endswith(".canonical.md")]
            if not files:
                print("\n== %s: %d معلقاً | لم أجد ملف المصدر في الأرشيف — تُترك معلقة ==" % (BID, len(pending)), flush=True)
                total["left"] += len(pending)
                continue
            src = files[0]
            is_pdf = src.lower().endswith(".pdf")
            cur.execute("""SELECT authority_status FROM knowledge_objects
                           WHERE metadata->>'batch_id'=%s AND verification_status='source_verified'
                           LIMIT 1""", (BID,))
            ar = cur.fetchone()
            AUTH_OK = (ar[0] if ar else None) or AUTH_DEFAULT
            print("\n== %s: %d معلقاً | المصدر: %s ==" % (BID, len(pending), os.path.basename(src)[:60]), flush=True)

            if is_pdf:
                reader = PdfReader(src)
                npages = len(reader.pages)
                groups = defaultdict(list)
                for row in pending:
                    groups[part_of(row[0]) or 0].append(row)
                for part in sorted(groups):
                    rows_p = groups[part]
                    if part:
                        b64 = pdf_slice_b64(reader, (part - 1) * PAGES, part * PAGES)
                    else:
                        b64 = pdf_slice_b64(reader, 0, min(npages, 90))
                    for s in range(0, len(rows_p), MAX_ITEMS):
                        chunk = rows_p[s:s + MAX_ITEMS]
                        row_by_id = {r[0]: r for r in chunk}
                        items = [{"id": r[0], "title": r[1], "text": r[2]} for r in chunk]
                        print("  الجزء P%s: مراجعة %d نص..." % (part or "؟", len(items)), flush=True)
                        leftovers = []
                        for vd in call_api([{"type": "document",
                                             "source": {"type": "base64", "media_type": "application/pdf",
                                                        "data": b64}}], items):
                            apply(vd, row_by_id, AUTH_OK, leftovers)
                        if leftovers and part:
                            b64w = pdf_slice_b64(reader, (part - 1) * PAGES - 4, part * PAGES + 6)
                            row_by_id2 = {r[0]: r for r in leftovers}
                            items2 = [{"id": r[0], "title": r[1], "text": r[2]} for r in leftovers]
                            print("    نافذة موسعة لـ %d نص..." % len(items2), flush=True)
                            fin = []
                            for vd in call_api([{"type": "document",
                                                 "source": {"type": "base64", "media_type": "application/pdf",
                                                            "data": b64w}}], items2):
                                apply(vd, row_by_id2, AUTH_OK, fin)
                            total["left"] += len(fin)
                            for r in fin:
                                print("    لم يوجد في صفحاته: %s | %s" % (r[0], r[1][:50]), flush=True)
                        elif leftovers:
                            total["left"] += len(leftovers)
            else:
                try:
                    text_src = open(src, encoding="utf-8", errors="replace").read()
                except Exception as exc:
                    print("  تعذرت قراءة المصدر النصي: %s" % exc, flush=True)
                    total["left"] += len(pending); continue
                windows = [text_src[i:i + 90000] for i in range(0, max(1, len(text_src)), 80000)][:8]
                remaining = list(pending)
                for wi, wtext in enumerate(windows):
                    if not remaining:
                        break
                    nxt = []
                    for s in range(0, len(remaining), MAX_ITEMS):
                        chunk = remaining[s:s + MAX_ITEMS]
                        row_by_id = {r[0]: r for r in chunk}
                        items = [{"id": r[0], "title": r[1], "text": r[2]} for r in chunk]
                        print("  نافذة نصية %d/%d: مراجعة %d نص..." % (wi + 1, len(windows), len(items)), flush=True)
                        leftovers = []
                        for vd in call_api([{"type": "text",
                                             "text": "المصدر (جزء %d من %d):\n%s" % (wi + 1, len(windows), wtext)}],
                                           items):
                            apply(vd, row_by_id, AUTH_OK, leftovers)
                        nxt += leftovers
                    remaining = nxt
                total["left"] += len(remaining)

            # ترميم الفهرسة: القاعدة مقابل الفهرس لهذا المصدر
            sk = pending[0][8]
            cur.execute("SELECT count(*) FROM knowledge_objects WHERE source_key=%s", (sk,))
            db_n = cur.fetchone()[0]
            qn = eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/count",
                                    {"exact": True, "filter": {"must": [{"key": "source_key",
                                                                         "match": {"value": sk}}]}})["result"]["count"]
            if qn < db_n:
                print("  ترميم الفهرس: %d في القاعدة مقابل %d في الفهرس — إعادة فهرسة..." % (db_n, qn), flush=True)
                cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,''),
                                      object_type, branch, topic, subtopic, metadata->>'micro_issue', source_key
                               FROM knowledge_objects WHERE source_key=%s""", (sk,))
                allr = cur.fetchall()
                for s in range(0, len(allr), 48):
                    w = allr[s:s + 48]
                    common = {"object_type": w[0][3], "branch": w[0][4], "topic": w[0][5],
                              "subtopic": w[0][6], "micro_issue": w[0][7], "source_key": w[0][8]}
                    eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                                       {"points": eng.build_points([(r[0], r[1], r[2]) for r in w], common)})
                print("  اكتمل الترميم ✓", flush=True)
        except Exception as exc:
            print("  خطأ في الدفعة %s: %s — نكمل البقية" % (BID, str(exc)[:150]), flush=True)

    print("\n===== الخلاصة الكلية =====", flush=True)
    print("اعتُمد كما هو: %d | صُحّح واعتُمد: %d | بقي معلقاً: %d" %
          (total["correct"], total["corrected"], total["left"]), flush=True)
    cur.execute("""SELECT verification_status, count(*) FROM knowledge_objects
                   GROUP BY 1 ORDER BY 2 DESC""")
    for vs, c in cur.fetchall():
        print("  %s | %d" % (vs, c), flush=True)
    print("===== انتهت المراجعة الشاملة =====", flush=True)
PYEOF
nohup /opt/LegalMind/.venv/bin/python /root/auto_review_all.py > /root/auto-review-all.log 2>&1 &
echo "انطلقت المراجعة الشاملة في الخلفية"
echo "تابع التقدم: tail -20 /root/auto-review-all.log"

echo ""
echo "== إصلاح وقائي: ضم أنواع مجموعات المبادئ الجديدة لقوائم بحث الاستوديو =="
python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
import re
p = "/opt/LegalMind/admin/app.py"
src = open(p, encoding="utf-8").read()
hits = 0
def add(m):
    global hits
    seg = m.group(0)
    if '"judicial_principles_collection"' in seg:
        return seg
    hits += 1
    return seg.replace('"judicial_principle"', '"judicial_principle", "judicial_principles_collection"', 1)
src = re.sub(r'\[[^\[\]]*"judicial_principle"[^\[\]]*\]', add, src)
src = re.sub(r'\((?:\s*"[a-z_]+"\s*,)*\s*"judicial_principle"\s*(?:,\s*"[a-z_]+"\s*)*,?\s*\)', add, src)
open(p, "w", encoding="utf-8").write(src)
print("قوائم عُدلت:", hits)
PYEOF
/opt/LegalMind/.venv/bin/python -m py_compile /opt/LegalMind/admin/app.py && echo "الكود سليم ✓"
systemctl restart legalmind-admin
sleep 2
systemctl is-active legalmind-admin && echo "الخدمة تعمل ✓"
echo "===== اكتمل الإعداد ====="
