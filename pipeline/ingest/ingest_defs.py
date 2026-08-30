#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل كتاب التعريفات (اللائحة التنفيذية لقانون هيئة أسواق المال 7/2010).

مسرد مصطلحات بتخطيط عمودين لا يقبل الاقتران الآلي الموثوق ⇒ يُخزَّن ككُتل بحثية:
  • كل صفحة (مجموعة مصطلحات + تعريفاتها) = كائن واحد قابل للاسترجاع الدلالي.
  • الجداول الموجودة في الملف (مصطلح|تعريف) = أزواج دقيقة إضافية.
يُوسم الكل «لائحة تنفيذية دون القانون»، النوع legislation_article ليُسترجَع في الصياغة.
"""
from __future__ import annotations
import argparse, os, re, sys, zipfile
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
LAW_ID   = "lreg-7-2010"        # بادئة مميّزة (لائحة) لا تصطدم بقانون legis-7-2010
LAW_TAG  = "لائحة أسواق المال (7/2010)"
BOOK_NO  = 1
BOOK_TT  = "التعريفات"
BRANCH   = "تجاري"
INSTRUMENT = "اللائحة التنفيذية لقانون هيئة أسواق المال رقم 7 لسنة 2010"

MONTH = r"(يناير|فبراير|مارس|أبريل|إبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)"
PGMARK = re.compile(r"^[أ-ي]\s*\d*$")                 # علامة حرف/صفحة (أ / أ 1 / ب 2)
DATE   = re.compile(r"^" + MONTH + r"\s*\d{4}$")
HDR    = re.compile(r"^(كتاب التعريفات|التعريفات|اللائحة التنفيذية.*|الكتاب الأول.*)$")

def _base_meta(extra=None):
    m = {"instrument": INSTRUMENT, "instrument_rank": "لائحة تنفيذية (دون القانون)",
         "book_number": BOOK_NO, "book_title": BOOK_TT, "parent_law": "legis-7-2010",
         "upload_origin": "docx_regulation_import"}
    if extra:
        m.update(extra)
    return m

def read_docx(path):
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read("word/document.xml").decode("utf-8"))
    body = root.find(W + "body")
    def cell_paras(tc):
        out = []
        for p in tc.findall(W + "p"):
            t = "".join(x.text or "" for x in p.iter(W + "t")).strip()
            if t:
                out.append(t)
        return out
    top = []          # (kind, payload) in document order: ('p', text) | ('tbl', rows)
    for child in body:
        if child.tag == W + "p":
            t = "".join(x.text or "" for x in child.iter(W + "t")).strip()
            top.append(("p", t))
        elif child.tag == W + "tbl":
            rows = []
            for tr in child.findall(W + "tr"):
                cells = [cell_paras(tc) for tc in tr.findall(W + "tc")]
                if len(cells) >= 2 and (cells[0] or cells[1]):
                    rows.append((cells[0], cells[1]))   # (term-paras, def-paras)
            top.append(("tbl", rows))
    return top

def build_rows(top):
    rows = []
    # 1) مقدمة الكتاب (أول فقرات نصّية حتى أول علامة صفحة)
    intro = []
    i = 0
    flat = [(k, v) for k, v in top if k == "p"]
    for k, t in top:
        if k == "p" and PGMARK.match(t or ""):
            break
        if k == "p" and t and not HDR.match(t) and not DATE.match(t):
            intro.append(t)
    if intro:
        rows.append({"id": f"{LAW_ID}-k1-intro", "object_type": "legislation_article",
                     "branch": BRANCH, "topic": f"كتاب {BOOK_TT}", "subtopic": "مقدمة", "micro_issue": None,
                     "title": f"مقدمة كتاب التعريفات — {LAW_TAG}",
                     "text": "\n".join(intro), "meta": _base_meta()})

    # 2) الكُتل النصّية (صفحات المسرد) — الفصل على علامات الصفحة
    blocks = []          # (letter, [content paras])
    cur, letter = [], "أ"
    started = False
    for k, t in top:
        if k != "p":
            continue
        if PGMARK.match(t or ""):
            if cur:
                blocks.append((letter, cur)); cur = []
            letter = t.split()[0]; started = True
            continue
        if not t or DATE.match(t) or HDR.match(t):
            continue
        if started:
            cur.append(t)
    if cur:
        blocks.append((letter, cur))
    bn = 0
    for letter, paras in blocks:
        if not paras:
            continue
        bn += 1
        rows.append({"id": f"{LAW_ID}-k1-b{bn}", "object_type": "legislation_article",
                     "branch": BRANCH, "topic": f"كتاب {BOOK_TT}", "subtopic": f"حرف {letter}",
                     "micro_issue": None,
                     "title": f"تعريفات (حرف {letter}) — {LAW_TAG}",
                     "text": "\n".join(paras),
                     "meta": _base_meta({"section_letter": letter, "chunk": "page_block"})})

    # 3) الجداول (مصطلح | تعريف) — أزواج دقيقة
    tn = 0
    for k, payload in top:
        if k != "tbl":
            continue
        for term_paras, def_paras in payload:
            term = " ".join(term_paras).strip()
            defn = "\n".join(def_paras).strip()
            if not term or not defn or DATE.match(term) or HDR.match(term) or PGMARK.match(term):
                continue
            tn += 1
            rows.append({"id": f"{LAW_ID}-k1-d{tn}", "object_type": "legislation_article",
                         "branch": BRANCH, "topic": f"كتاب {BOOK_TT}", "subtopic": "تعريف",
                         "micro_issue": None,
                         "title": f"تعريف: {term[:60]} — {LAW_TAG}",
                         "text": f"{term}:\n{defn}",
                         "meta": _base_meta({"term": term, "chunk": "exact_pair"})})
    return rows

def normalize_text(text):
    try:
        sys.path.insert(0, "/opt/LegalMind/engine")
        from normalizer.canonical import normalize_text as nt
        return nt(text)
    except Exception:
        import unicodedata
        t = unicodedata.normalize("NFKC", text).replace("ـ", "")
        t = re.sub(r"[ \t]+", " ", t); t = re.sub(r" *\n *", "\n", t)
        return re.sub(r"\n{3,}", "\n\n", t).strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    top = read_docx(args.docx)
    rows = build_rows(top)

    blocks = [r for r in rows if r["meta"].get("chunk") == "page_block"]
    pairs = [r for r in rows if r["meta"].get("chunk") == "exact_pair"]
    print("== تقرير كتاب التعريفات ==")
    print(f"اللائحة: {INSTRUMENT}  | الفرع: {BRANCH}  | البادئة: {LAW_ID}")
    print(f"كُتل بحثية (صفحات): {len(blocks)}   أزواج دقيقة (جداول): {len(pairs)}   مقدمة: {'نعم' if any(r['id'].endswith('intro') for r in rows) else 'لا'}")
    print(f"إجمالي الكائنات: {len(rows)}")
    print("\n== عيّنة كتلة ==")
    if blocks:
        b = blocks[0]
        print(f"[{b['id']}] {b['title']}")
        print(b["text"][:400])
    print("\n== عيّنة زوج دقيق ==")
    if pairs:
        print(pairs[0]["text"][:220])

    if args.dry_run:
        print("\n[dry-run] لم يُدخَل شيء.")
        return 0

    import psycopg
    from psycopg.types.json import Jsonb
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    ins = 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(
                    """INSERT INTO knowledge_objects
                       (id,object_type,branch,topic,subtopic,micro_issue,title,original_text,normalized_text,
                        source_key,verification_status,authority_status,usable_as_citation,metadata)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,'source_verified','source_authority',TRUE,%s)
                       ON CONFLICT (id) DO UPDATE SET
                        object_type=EXCLUDED.object_type,branch=EXCLUDED.branch,topic=EXCLUDED.topic,
                        subtopic=EXCLUDED.subtopic,micro_issue=EXCLUDED.micro_issue,title=EXCLUDED.title,
                        original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                        metadata=EXCLUDED.metadata,updated_at=now()""",
                    (r["id"], r["object_type"], r["branch"], r["topic"], r["subtopic"], r["micro_issue"],
                     r["title"], r["text"], normalize_text(r["text"]), Jsonb(r["meta"])))
                ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل الآن: python -m engine.legalmind_engine reindex")
    return 0

if __name__ == "__main__":
    sys.exit(main())
