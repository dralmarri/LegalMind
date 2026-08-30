# -*- coding: utf-8 -*-
"""قارئ مخصص للمستندات الجدولية (تعليمات/جداول تنظيمية): يستخرج كل جدول كوحدة
منظمة (عنوان الجدول + الأعمدة + الصفوف كـ markdown table) بدل تفكيكه كسرد مبادئ."""
import sys, os, io, json, base64, hashlib, time, urllib.request
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
from pypdf import PdfReader, PdfWriter

MODEL = os.environ.get("LEGALMIND_INGEST_MODEL", "claude-sonnet-5")
KEY = os.environ["ANTHROPIC_API_KEY"]
PAGES_PER_BATCH = 12

TOOL = {
    "name": "save_tables",
    "description": "حفظ محتوى الصفحات كوحدات: جداول منظمة أو نصوص سردية عادية",
    "input_schema": {
        "type": "object", "required": ["units"],
        "properties": {"units": {"type": "array", "items": {
            "type": "object", "required": ["kind", "title", "content"],
            "properties": {
                "kind": {"type": "string", "enum": ["table", "narrative", "definition"]},
                "title": {"type": "string"},
                "content": {"type": "string",
                           "description": "للجداول: جدول Markdown كامل بعنوان الأعمدة والصفوف. للنص السردي: الفقرة كاملة."},
                "notes": {"type": "string"}}}}}}}

def slice_pdf(reader, a, b):
    w = PdfWriter()
    for p in range(max(0, a), min(b, len(reader.pages))):
        w.add_page(reader.pages[p])
    buf = io.BytesIO(); w.write(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def call(b64):
    prompt = ("هذه صفحات من مستند تنظيمي (تعليمات/لوائح) قد تحتوي جداول أرقام ونسب مالية.\n"
              "لكل عنصر محتوى في هذه الصفحات:\n"
              "- إن كان جدولاً (أعمدة وصفوف، أرقام، نسب، بنود مرقمة داخل جدول) → "
              "استخرجه كاملاً بصيغة جدول Markdown (| عمود | عمود |) محافظاً على ترتيب الأعمدة والصفوف "
              "كما تراه بصرياً في الصفحة تماماً، مع عنوان الجدول إن وُجد، kind=table.\n"
              "- إن كان نصاً سردياً متصلاً (مادة قانونية، شرح، تعريف) → انسخه حرفياً، kind=narrative أو definition.\n"
              "لا تخلط عناصر جدول مع سرد في وحدة واحدة. لا تخترع بيانات غير موجودة في الصفحة.")
    body = {"model": MODEL, "max_tokens": 30000,
            "tools": [TOOL], "tool_choice": {"type": "tool", "name": "save_tables"},
            "messages": [{"role": "user", "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}},
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
                    raw = blk["input"].get("units", [])
                    clean = [u for u in raw if isinstance(u, dict)]
                    if len(clean) != len(raw):
                        print("    تجاهلت %d عنصراً غير سليم النوع من رد النموذج" %
                              (len(raw) - len(clean)), flush=True)
                    return clean
            return []
        except Exception as exc:
            print("  محاولة %d: %s" % (attempt + 1, str(exc)[:120]), flush=True)
            time.sleep(15 * (attempt + 1))
    return []

def run(path, branch, topic):
    reader = PdfReader(path)
    npg = len(reader.pages)
    print("الملف: %s (%d صفحة)" % (path, npg), flush=True)
    src_key = "SRC-" + hashlib.sha256(os.path.basename(path).encode()).hexdigest()[:20].upper()
    file_sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    ckpt_path = "/root/table_reader_checkpoint.json"

    # استئناف تراكمي: تحميل ما أُنجز سابقاً، وتخطي دُفعات الصفحات المكتملة فقط
    all_units, done_parts = [], set()
    if os.path.exists(ckpt_path):
        try:
            ck = json.load(open(ckpt_path, encoding="utf-8"))
            if ck.get("path") == path:
                all_units = [(u["part"], u["unit"]) for u in ck.get("units", [])]
                done_parts = set(ck.get("done_parts", []))
                print("استئناف: %d عنصر محفوظ | %d دفعة صفحات مكتملة مسبقاً" %
                      (len(all_units), len(done_parts)), flush=True)
        except Exception as exc:
            print("تعذرت قراءة نقطة الحفظ (سنبدأ من الصفر): %s" % exc, flush=True)

    def save_ckpt():
        json.dump({"path": path, "done_parts": sorted(done_parts),
                   "units": [{"part": part, "unit": u} for part, u in all_units]},
                  open(ckpt_path, "w", encoding="utf-8"), ensure_ascii=False)

    for p in range(0, npg, PAGES_PER_BATCH):
        if p in done_parts:
            continue
        b64 = slice_pdf(reader, p, p + PAGES_PER_BATCH)
        print("  صفحات %d-%d..." % (p, min(p + PAGES_PER_BATCH, npg)), flush=True)
        units = call(b64)
        tbl_n = sum(1 for u in units if u.get("kind") == "table")
        print("    استُخرج %d عنصراً (%d جدول)" % (len(units), tbl_n), flush=True)
        all_units += [(p, u) for u in units]
        done_parts.add(p)
        save_ckpt()   # حفظ فوري بعد كل دفعة — لا خسارة عند أي عطل لاحق
    print("اكتمل الاستخراج: %d عنصر إجمالاً عبر %d دفعة" % (len(all_units), len(done_parts)), flush=True)

    with eng.psycopg.connect(eng.database_url()) as conn:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""INSERT INTO sources (source_key, source_type, title, file_name, sha256,
                                            content_sha256, verification_status, metadata)
                       VALUES (%s,'document',%s,%s,%s,%s,'source_verified','{}'::jsonb)
                       ON CONFLICT (source_key) DO NOTHING""",
                    (src_key, os.path.basename(path), os.path.basename(path), file_sha, file_sha))
        n = 0
        for part, u in all_units:
            title = (u.get("title") or "").strip()[:200] or ("جدول" if u.get("kind") == "table" else "نص")
            content = (u.get("content") or "").strip()
            if not content:
                continue
            oid = "TBL-%s-P%d-%s" % (os.path.basename(path)[:20], part,
                                     hashlib.sha256(content.encode()).hexdigest()[:16])
            otype = "regulatory_table" if u.get("kind") == "table" else "legal_document"
            cur.execute("""INSERT INTO knowledge_objects
                           (id, object_type, branch, topic, title, original_text, normalized_text,
                            source_key, verification_status, usable_as_citation, metadata)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'source_verified',true,%s)
                           ON CONFLICT (id) DO NOTHING""",
                        (oid, otype, branch, topic, title, content, eng.normalize_text(content),
                         src_key, json.dumps({"kind": u.get("kind"), "table_reader": True})))
            n += 1
        conn.commit()
        print("\nأُدرج %d كائناً (جداول ونصوص) في القاعدة" % n, flush=True)

        cur.execute("""SELECT id, title, original_text, object_type, branch, topic
                       FROM knowledge_objects WHERE source_key=%s""", (src_key,))
        rows = cur.fetchall()
        for s in range(0, len(rows), 40):
            w = rows[s:s + 40]
            common = {"object_type": w[0][3], "branch": w[0][4], "topic": w[0][5],
                      "subtopic": None, "micro_issue": None, "source_key": src_key}
            eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                               {"points": eng.build_points([(r[0], r[1], r[2]) for r in w], common)})
        print("فُهرست %d نقطة في محرك البحث ✓" % len(rows), flush=True)
    try:
        os.remove(ckpt_path)
    except Exception:
        pass

if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "تجاري",
        sys.argv[3] if len(sys.argv) > 3 else "أسواق المال")
