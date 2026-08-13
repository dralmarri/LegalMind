#!/bin/bash
# نسب كل كائن في دفعة القانون البحري إلى مصدره الصحيح (متن القانون / المذكرة / القوانين المكملة)
# + التحقق من وجود نص المادة 256 في متن القانون
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
cat > /root/attribute_laws.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, os, re, json, time, urllib.request
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

MODEL = os.environ.get("LEGALMIND_INGEST_MODEL", "claude-sonnet-5")
KEY = os.environ["ANTHROPIC_API_KEY"]

TOOL = {
    "name": "save_attribution",
    "description": "نسب كل كائن معرفي إلى القانون أو الوثيقة التي ينتمي إليها داخل المجلد",
    "input_schema": {
        "type": "object", "required": ["sections"],
        "properties": {"sections": {"type": "array", "items": {
            "type": "object", "required": ["key", "publication", "ids"],
            "properties": {
                "key": {"type": "string",
                        "enum": ["main_law", "main_memo", "issuing_decree",
                                 "passport_law", "passport_memo",
                                 "masters_law", "masters_memo",
                                 "discipline_law", "discipline_memo",
                                 "bol_treaty", "bol_memo",
                                 "front_matter", "annex_regulation", "other"]},
                "publication": {"type": "string"},
                "law_number": {"type": ["string", "null"]},
                "law_year": {"type": ["string", "null"]},
                "ids": {"type": "array", "items": {"type": "string"}}}}}}}}

def sort_key(oid):
    m = re.match(r"LEG-UNKNOWN-P(\d+)-c(\d+)", oid)
    if m:
        return (int(m.group(1)), 0, int(m.group(2)))
    m = re.match(r"LEG-UNKNOWN-P(\d+)-(\d+)-", oid)
    if m:
        return (int(m.group(1)), 0, int(m.group(2)))
    m = re.match(r"LEG-UNKNOWN-P(\d+)-art(\d+)_(\w+)", oid)
    if m:
        return (int(m.group(1)), 1 if m.group(3) != "law" else 2, int(m.group(2)))
    m = re.match(r"LEG-UNKNOWN-P(\d+)", oid)
    return (int(m.group(1)) if m else 999, 3, 0)

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""SELECT batch_id FROM ingestion_batches
                   WHERE object_count > 400 AND status='completed'
                   ORDER BY started_at DESC LIMIT 1""")
    BID = cur.fetchone()[0]
    cur.execute("""SELECT id, coalesce(title,'') FROM knowledge_objects
                   WHERE metadata->>'batch_id'=%s""", (BID,))
    rows = sorted(cur.fetchall(), key=lambda r: sort_key(r[0]))
    all_ids = {r[0] for r in rows}
    print("الدفعة:", BID, "| كائنات للنسب:", len(rows), flush=True)

    listing = "\n".join("%s | %s" % (i, t[:65]) for i, t in rows)
    prompt = ("أمامك قائمة كائنات معرفية مستخرجة بترتيب صفحات مجلد «مجموعة التشريعات الكويتية - الجزء السادس: "
              "قانون التجارة البحرية والقوانين المكملة له» (وزارة العدل، فبراير 2011). كل سطر: المعرف | العنوان.\n"
              "المجلد يضم: المرسوم بقانون رقم 28 لسنة 1980 بإصدار قانون التجارة البحرية (الديباجة ومواد الإصدار ثم "
              "متن القانون مواد 1-325)، ومذكرته الإيضاحية، وقانون الجواز البحري ومذكرته، والمرسوم بقانون 30 لسنة 1980 "
              "في شأن الربابنة وضباط الملاحة والمهندسين البحريين ومذكرته، والمرسوم بقانون 31 لسنة 1980 في شأن الأمن "
              "والنظام والتأديب في السفن ومذكرته، والمعاهدة الدولية لتوحيد بعض القواعد المتعلقة بسندات الشحن (بروكسل 1924) "
              "ومذكرتها التفسيرية بشأن انضمام الكويت، إضافة إلى الغلاف والفهرس وبيانات الطبعة، وقد توجد لوائح أو مراسيم "
              "تنظيمية ملحقة (كأحكام تسجيل السفن).\n"
              "انسب كل معرف إلى قسم واحد فقط من الأقسام المعرفة في الأداة. ملاحظات:\n"
              "- الترتيب في القائمة يطابق ترتيب الصفحات، ومتن القانون الرئيسي مقسوم: مواده 292-325 في أول الملف ومواده 1-291 في آخره.\n"
              "- عناوين شرح المذكرة الإيضاحية تشبه عناوين المواد؛ ميّزها بالسياق (تقع بين بداية «مذكرة إيضاحية» وبداية القسم التالي).\n"
              "- publication: صيغة النسبة الرسمية بالعربية كما ستظهر في الاستشهاد، مثل «المرسوم بقانون رقم 28 لسنة 1980 "
              "بإصدار قانون التجارة البحرية» أو «المذكرة الإيضاحية لقانون التجارة البحرية (28/1980)». وإن لم يظهر رقم "
              "قانون الجواز البحري في العناوين فاكتب «قانون الجواز البحري» واترك law_number فارغاً — لا تخمن رقماً.\n"
              "- يجب أن يظهر كل معرف مرة واحدة بالضبط في مجموع الأقسام.\n\n" + listing)

    body = {"model": MODEL, "max_tokens": 60000,
            "tools": [TOOL], "tool_choice": {"type": "tool", "name": "save_attribution"},
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]}
    data = json.dumps(body).encode("utf-8")
    sections = None
    for attempt in range(4):
        try:
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=data,
                                         headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
                                                  "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=900) as r:
                res = json.loads(r.read())
            for blk in res.get("content", []):
                if blk.get("type") == "tool_use":
                    sections = blk["input"]["sections"]
            break
        except Exception as exc:
            print("محاولة %d فشلت: %s" % (attempt + 1, exc), flush=True)
            time.sleep(20 * (attempt + 1))
    if not sections:
        print("تعذر الحصول على النسب — لم يتغير شيء", flush=True); sys.exit(1)

    assigned = [i for s in sections for i in s["ids"]]
    dup = len(assigned) - len(set(assigned))
    missing = all_ids - set(assigned)
    extra = set(assigned) - all_ids
    print("فحص السلامة: مكرر=%d | ناقص=%d | دخيل=%d" % (dup, len(missing), len(extra)), flush=True)
    if dup or extra:
        print("النسب غير سليم — أُلغي التطبيق. عينة ناقص:", list(missing)[:5], "دخيل:", list(extra)[:5], flush=True)
        sys.exit(1)
    if missing:
        print("تنبيه: كائنات بلا نسبة ستبقى كما هي:", list(missing)[:10], flush=True)

    for s in sections:
        patch = {"publication": s["publication"], "law_ref": s["key"]}
        if s.get("law_number"): patch["law_number"] = s["law_number"]
        if s.get("law_year"): patch["law_year"] = s["law_year"]
        cur.execute("""UPDATE knowledge_objects SET metadata = metadata || %s::jsonb, updated_at=now()
                       WHERE id = ANY(%s)""", (json.dumps(patch, ensure_ascii=False), s["ids"]))
        print("  %-16s | %4d كائناً | %s" % (s["key"], len(s["ids"]), s["publication"][:60]), flush=True)

    print("\n== التحقق من المادة 256 في متن القانون ==", flush=True)
    cur.execute("""SELECT id, title, original_text FROM knowledge_objects
                   WHERE metadata->>'batch_id'=%s AND id LIKE '%%P15-c1-%%'
                      OR metadata->>'batch_id'=%s AND id LIKE '%%P15-c2-%%'
                      OR metadata->>'batch_id'=%s AND id LIKE '%%P15-c3-%%'""", (BID, BID, BID))
    found256 = False
    for oid, ti, tx in cur.fetchall():
        has = "256" in (tx or "")
        if has: found256 = True
        print("  %s | %s | يحتوي «256»: %s" % (oid, ti[:50], has), flush=True)
        if has:
            k = tx.find("256")
            print("    ...", tx[max(0, k-120):k+250].replace("\n", " "), "...", flush=True)
    if not found256:
        print("  نص المادة 256 غير موجود في مقاطع P15 الأولى — يلزم استخراجها بصرياً من صفحتها", flush=True)
    print("===== انتهى النسب =====", flush=True)
PYEOF
nohup /opt/LegalMind/.venv/bin/python /root/attribute_laws.py > /root/attribute-laws.log 2>&1 &
echo "انطلق النسب في الخلفية (دقائق قليلة) — تابع: tail -30 /root/attribute-laws.log"
