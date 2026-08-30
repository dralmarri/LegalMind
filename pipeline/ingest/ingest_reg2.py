#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل كتب لائحة أسواق المال — إعادة بناء ترتيب القراءة من هندسة الإطارات.

الملف يخزّن أرقام المواد في إطارات هامش مستقلّة (framePr) منفصلة عن نصوصها،
وترتيب XML لا يطابق ترتيب القراءة. نعيد البناء هكذا:
  • نقسّم المستند صفحاتٍ عبر sectPr (صفحة لكل مقطع).
  • داخل كل صفحة نصنّف الإطارات: إطار رقم مادة (ضيّق، Style رقم) مقابل إطار نصّ.
  • نطابق فقرات النصّ بالمواد حسب الإحداثي الرأسي y (أعلى الفقرة مقابل y الرقم).
  • مواد الجداول (بعض فصول 4/6/8) تُلتقط مباشرة صفًّا صفًّا.
  • الإطار المشترك (يضمّ مادتين قصيرتين فأكثر) يُقسَّم بتقدير المواضع ويُعلَّم boundary=approx.
  • يُكشَف تلف الترميز في الفقرات ويُعلَّم source_quality=needs_review (لا يُدخَل بصمت كأنه سليم).
معرّفات: lreg-7-2010-k{book}-m{X-Y} | ...-fee{n} | ...-annex{n}
"""
from __future__ import annotations
import argparse, math, os, re, sys, zipfile
from collections import OrderedDict
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
def q(t): return W + t

LAW_ID  = "lreg-7-2010"
LAW_TAG = "لائحة أسواق المال (7/2010)"
BRANCH  = "تجاري"
PARENT  = "legis-7-2010"
INSTRUMENT = "اللائحة التنفيذية لقانون هيئة أسواق المال رقم 7 لسنة 2010"

ART      = re.compile(r"^(?:المادة|مادة)\s+(\d+(?:-\d+)+)\s*$")      # رقم مادة صِرف
ART_HEAD = re.compile(r"^(?:المادة|مادة)\s+(\d+(?:-\d+)+)\s*(.*)$")  # رقم + بقيّة (للجداول)
FASL     = re.compile(r"^(?:الفصل|الباب)\s+\S")
DATE     = re.compile(r"^(يناير|فبراير|مارس|أبريل|إبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)\s*\d{4}$")
APPX     = re.compile(r"^(?:ملحق رقم|الملحق رقم|الملاحق)\b")
FEE_SEC  = re.compile(r"^\s*(\d+)\s*[-–]\s*(.+?)\s*:?\s*$")
ARW      = re.compile(r"[؀-ۿ]")


def _para_info(p):
    txt = "".join(x.text or "" for x in p.iter(q("t"))).strip()
    pPr = p.find(q("pPr")); fp = pPr.find(q("framePr")) if pPr is not None else None
    st = ""
    if pPr is not None:
        ps = pPr.find(q("pStyle"))
        if ps is not None: st = ps.get(q("val"), "")
    def gi(a):
        if fp is None: return None
        v = fp.get(q(a)); return int(v) if v and v.lstrip("-").isdigit() else None
    return {"text": txt, "style": st, "x": gi("x"), "y": gi("y"), "h": gi("h"), "w": gi("w"),
            "sect": pPr is not None and pPr.find(q("sectPr")) is not None}


def read_pages(path):
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml").decode())
    body = root.find(q("body"))
    def cell_text(tc):
        return "\n".join("".join(x.text or "" for x in pp.iter(q("t"))).strip()
                         for pp in tc.findall(q("p"))).strip()
    pages = []; cur = []
    for child in body:
        if child.tag == q("p"):
            pi = _para_info(child); cur.append(("p", pi))
            if pi["sect"]:
                pages.append(cur); cur = []
        elif child.tag == q("tbl"):
            rows = [[cell_text(tc) for tc in tr.findall(q("tc"))] for tr in child.findall(q("tr"))]
            cur.append(("tbl", rows))
    if cur:
        pages.append(cur)
    return pages


def _is_noise(t):
    if not t: return True
    if re.match(r"^\d{1,4}$", t): return True
    if DATE.match(t): return True
    if t == "كتاب هيئة أسواق المال": return True
    if re.match(r"^[أ-ي]$", t): return True
    if FASL.match(t): return True
    return False


def _corrupt_flags(t):
    if len(t) < 10: return []
    r = []
    if re.search(r"[؀-ۿ][A-Za-z]|[A-Za-z][؀-ۿ]", t): r.append("latin-in-word")
    if re.search(r"\b[A-Za-z]\b", t) and ARW.search(t): r.append("stray-latin")
    words = t.split()
    if any(len(w) >= 20 and ARW.search(w) for w in words): r.append("glued-word")
    singles = sum(1 for w in words if len(w) == 1 and ARW.match(w) and w not in "وأفبلاينمعهةتلا")
    if singles / max(1, len(words)) > 0.25: r.append("many-singles")
    if len(re.findall(r"[؀-ۿ][.،][؀-ۿ]", t)) >= 2: r.append("glued-punct")
    if len(re.findall(r"[٠-٩]", t)) >= 3 and len(words) < 10 and ARW.search(t): r.append("digit-scatter")
    if len(re.findall(r"[ءؤئ٠]", t)) >= 4 and len(t) < 60: r.append("hamza-scatter")
    return r


def _cpl(w):  # حروف/سطر تقديريًا من عرض الإطار
    return max(20, int((w or 9149) / 120))


def page_articles(page):
    """يعيد: {N: {'paras':[...], 'shared':bool}} من الإطارات + مواد الجداول منفصلة."""
    # تجميع كتل الإطارات (فقرات متتالية بنفس framePr)
    blocks = []
    tables = []
    for kind, payload in page:
        if kind == "tbl":
            tables.append(payload); continue
        pi = payload
        key = (pi["x"], pi["y"], pi["h"], pi["w"])
        if blocks and blocks[-1]["key"] == key:
            blocks[-1]["paras"].append(pi)
        else:
            blocks.append({"key": key, "paras": [pi], "y": pi["y"], "h": pi["h"], "w": pi["w"]})

    numbers = []   # (y, N)
    bodies = []    # {y,h,w,paras}
    for b in blocks:
        first = b["paras"][0]["text"]
        if len(b["paras"]) == 1 and ART.match(first) and (b["h"] or 0) < 1200 \
           and (b["w"] or 0) < 3000 and b["y"] is not None:
            numbers.append((b["y"], ART.match(first).group(1)))
        else:
            paras = [p for p in b["paras"] if not _is_noise(p["text"])]
            if paras and b["y"] is not None:
                bodies.append({"y": b["y"], "h": b["h"] or 0, "w": b["w"] or 9149, "paras": paras})
    numbers.sort()

    result = OrderedDict()
    if numbers:
        ys = [y for y, _ in numbers]; ns = [N for _, N in numbers]
        # كم مادة يقع رقمها داخل كل إطار نصّ (لتعليم المشترك)
        for bd in bodies:
            span_nums = [N for (y, N) in numbers if (bd["y"] - 600) <= y <= (bd["y"] + bd["h"] + 200)]
            bd["shared"] = len(span_nums) >= 2
            # مواضع أعلى كل فقرة (تناسبيًا مع طول النص)
            cpl = _cpl(bd["w"]); lines = [max(1, math.ceil(len(p["text"]) / cpl)) for p in bd["paras"]]
            tot = sum(lines); cum = 0
            for p, L in zip(bd["paras"], lines):
                top = bd["y"] + bd["h"] * (cum / tot)
                # المادة = آخر رقم y ≤ أعلى الفقرة (مع تثبيت أول رقم)
                idx = 0
                for i in range(len(ys)):
                    if ys[i] <= top: idx = i
                    else: break
                N = ns[idx]
                rec = result.setdefault(N, {"paras": [], "shared": False})
                rec["paras"].append(p["text"])
                if bd["shared"]:
                    rec["shared"] = True
                cum += L
    return result, tables


def collect(pages):
    articles = OrderedDict()   # N -> {'paras':[], 'shared':bool, 'topic':str}
    fees = []; annexes = []
    cur_topic = "أحكام عامة"; in_appendix = False; cur_annex = None; cur_fee = None

    for page in pages:
        # تحديث topic من عناوين الفصول في هذه الصفحة
        for kind, payload in page:
            if kind == "p" and payload["text"] and FASL.match(payload["text"]):
                # العنوان = أول فقرة غير-ضجيج بعده في نفس الصفحة
                pass
        # الملاحق: نكتشف بدايتها
        page_txt = " ".join(pl["text"] for k, pl in page if k == "p")
        if not in_appendix and APPX.search(page_txt):
            in_appendix = True

        if not in_appendix:
            arts, tables = page_articles(page)
            # topic لهذه الصفحة: آخر عنوان فصل مرئي
            page_topic = None
            seen_fasl = False
            for kind, payload in page:
                if kind != "p": continue
                t = payload["text"]
                if FASL.match(t or ""):
                    seen_fasl = True; continue
                if seen_fasl and t and not _is_noise(t):
                    page_topic = re.sub(r"\s+", " ", t).strip(" :"); break
            if page_topic:
                cur_topic = page_topic
            for N, rec in arts.items():
                a = articles.setdefault(N, {"paras": [], "shared": False, "topic": cur_topic})
                a["paras"].extend(rec["paras"]); a["shared"] = a["shared"] or rec["shared"]
            # مواد الجداول
            for rows in tables:
                if not any(r and ART_HEAD.match((r[0] or "")) for r in rows):
                    continue
                pending = None; last = None
                for r in rows:
                    c0 = (r[0] if r else "").strip()
                    body = "\n".join(c for c in r[1:] if c).strip() if len(r) > 1 else ""
                    m = ART_HEAD.match(c0)
                    if m:
                        N = m.group(1); rest = (m.group(2) or "").strip()
                        txt = ((pending + "\n") if pending else "") + (rest + "\n" if rest else "") + body
                        a = articles.setdefault(N, {"paras": [], "shared": False, "topic": cur_topic})
                        if txt.strip(): a["paras"].append(txt.strip())
                        pending = None; last = a
                    elif c0:
                        pending = c0 if not body else (c0 + "\n" + body)
                    elif body and last is not None:
                        last["paras"].append(body)
                if pending and last is not None:
                    last["paras"].append(pending)
        else:
            # وضع الملاحق: نماذج + جدول رسوم
            for kind, payload in page:
                if kind == "p":
                    t = payload["text"]
                    m = APPX.match(t or "")
                    if m:
                        an = re.search(r"(\d+)", t)
                        cur_annex = {"no": int(an.group(1)) if an else len(annexes) + 1, "title": "", "lines": []}
                        annexes.append(cur_annex)
                    elif cur_annex is not None and t and not _is_noise(t):
                        if not cur_annex["title"]: cur_annex["title"] = t
                        else: cur_annex["lines"].append(t)
                else:
                    rows = payload
                    flat = " ".join(" ".join(c for c in r if c) for r in rows)
                    if "د.ك" in flat or (rows and rows[0] and FEE_SEC.match(rows[0][0] or "")):
                        for r in rows:
                            c0 = (r[0] if r else "").strip()
                            fs = FEE_SEC.match(c0)
                            if fs and "د.ك" not in " ".join(r):
                                cur_fee = {"no": int(fs.group(1)), "name": fs.group(2).strip(" :"), "rows": []}
                                fees.append(cur_fee); continue
                            cells = [c.strip() for c in r]
                            if not any(cells): continue
                            if cur_fee is None:
                                cur_fee = {"no": 0, "name": "رسوم", "rows": []}; fees.append(cur_fee)
                            cur_fee["rows"].append(cells)
                    elif cur_annex is not None:
                        for r in rows:
                            line = " ".join(c for c in r if c).strip()
                            if line and not _is_noise(line): cur_annex["lines"].append(line)
    return articles, fees, annexes


def _artkey(N):
    return tuple(int(x) for x in N.split("-"))


def build_rows(articles, fees, annexes, book_no, book_title):
    rows = []; kb = f"{LAW_ID}-k{book_no}"
    def meta(extra=None):
        m = {"instrument": INSTRUMENT, "instrument_rank": "لائحة تنفيذية (دون القانون)",
             "book_number": book_no, "book_title": book_title, "parent_law": PARENT,
             "upload_origin": "docx_regulation_import"}
        if extra: m.update(extra)
        return m
    for N in sorted(articles, key=_artkey):
        a = articles[N]
        text = "\n".join(x for x in a["paras"] if x).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        flags = sorted({f for p in a["paras"] for f in _corrupt_flags(p)})
        extra = {"article_number": N, "chapter": N.split("-")[0]}
        if a["shared"]: extra["boundary"] = "approx"
        if flags: extra["source_quality"] = "needs_review"; extra["corruption"] = flags
        rows.append({"id": f"{kb}-m{N}", "object_type": "legislation_article",
                     "branch": BRANCH, "topic": a["topic"], "subtopic": None, "micro_issue": None,
                     "title": f"مادة {N} — {LAW_TAG}", "text": text, "meta": meta(extra),
                     "_shared": a["shared"], "_flags": flags})
    for fs in fees:
        if not fs["rows"]: continue
        txt = f"جدول رسوم خدمات الهيئة — {fs['name']}\n" + "\n".join(" | ".join(c for c in cells if c) for cells in fs["rows"])
        rows.append({"id": f"{kb}-fee{fs['no']}", "object_type": "legislation_article",
                     "branch": BRANCH, "topic": "ملحق: جدول رسوم خدمات الهيئة", "subtopic": fs["name"],
                     "micro_issue": None, "title": f"رسوم: {fs['name']} — {LAW_TAG}", "text": txt,
                     "meta": meta({"annex": "جدول الرسوم", "fee_section": fs["name"], "chunk": "fee_schedule"}),
                     "_shared": False, "_flags": []})
    for an in annexes:
        if not an["title"] and not an["lines"]: continue
        txt = (an["title"] + "\n" + "\n".join(an["lines"])).strip()
        rows.append({"id": f"{kb}-annex{an['no']}", "object_type": "legislation_article",
                     "branch": BRANCH, "topic": "ملحق: نماذج", "subtopic": (an["title"][:60] or None),
                     "micro_issue": None, "title": f"ملحق ({an['no']}) {an['title'][:50]} — {LAW_TAG}",
                     "text": txt, "meta": meta({"annex": f"ملحق {an['no']}", "chunk": "annex_form"}),
                     "_shared": False, "_flags": []})
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
    ap.add_argument("--book-number", type=int, required=True)
    ap.add_argument("--book-title", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show", default="", help="أظهر نصّ مادة معيّنة، مثل 8-7")
    args = ap.parse_args()

    pages = read_pages(args.docx)
    articles, fees, annexes = collect(pages)
    rows = build_rows(articles, fees, annexes, args.book_number, args.book_title)

    arts = [r for r in rows if "-m" in r["id"].split(f"k{args.book_number}-")[-1][:2] or r["id"].split("-")[-1].startswith("m")]
    arts = [r for r in rows if re.search(r"-m\d", r["id"])]
    shared = [r for r in arts if r["_shared"]]
    corrupt = [r for r in arts if r["_flags"]]
    empties = [r for r in arts if not r["text"].strip()]
    by_chap = OrderedDict()
    for r in arts:
        by_chap.setdefault(r["meta"]["chapter"], []).append(r["meta"]["article_number"])

    print("== تقرير كتاب اللائحة (إعادة بناء هندسي) ==")
    print(f"الكتاب: ({args.book_number}) {args.book_title}  | الفرع: {BRANCH}  | البادئة: {LAW_ID}-k{args.book_number}")
    print(f"عدد المواد: {len(arts)}   إطارات مشتركة (حدود تقريبية): {len(shared)}   مواد فيها تلف: {len(corrupt)}   مواد فارغة: {len(empties)}")
    print(f"أقسام الرسوم: {len(fees)}   ملاحق نماذج: {len(annexes)}   إجمالي الكائنات: {len(rows)}")
    print("\n== المواد حسب الفصل ==")
    for ch in sorted(by_chap, key=int):
        print(f"  فصل {ch} [{len(by_chap[ch])}]: {'، '.join(by_chap[ch])}")
    print("\n== مواد الحدود التقريبية (إطار مشترك — تحتاج تحقّق يدوي للفصل) ==")
    print("  " + ("، ".join(r["meta"]["article_number"] for r in shared) or "لا"))
    print("\n== مواد فيها تلف ترميز (لن تُدخَل كنصّ سليم — تحتاج نصًّا رسميًا) ==")
    for r in corrupt:
        print(f"  م{r['meta']['article_number']}: {r['_flags']}")
        bad = next((p for p in [r['text']] if p), "")
    if args.show:
        r = next((x for x in arts if x["meta"]["article_number"] == args.show), None)
        if r:
            print(f"\n== نصّ م{args.show} (topic={r['topic']}; shared={r['_shared']}; flags={r['_flags']}) ==")
            print(r["text"])
    else:
        print("\n== عيّنات مواد سليمة ==")
        clean = [r for r in arts if not r["_flags"] and not r["_shared"] and r["text"].strip()]
        for r in clean[:2] + clean[-1:]:
            print(f"\n--- م{r['meta']['article_number']} (topic={r['topic']}) ---\n{r['text'][:300]}")

    if args.dry_run:
        print("\n[dry-run] لم يُدخَل شيء.")
        return 0

    import psycopg
    from psycopg.types.json import Jsonb
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    ins = 0
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """INSERT INTO knowledge_objects
                   (id,object_type,branch,topic,subtopic,micro_issue,title,original_text,normalized_text,
                    source_key,verification_status,authority_status,usable_as_citation,metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,'source_authority',%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                    object_type=EXCLUDED.object_type,branch=EXCLUDED.branch,topic=EXCLUDED.topic,
                    subtopic=EXCLUDED.subtopic,micro_issue=EXCLUDED.micro_issue,title=EXCLUDED.title,
                    original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                    verification_status=EXCLUDED.verification_status,usable_as_citation=EXCLUDED.usable_as_citation,
                    metadata=EXCLUDED.metadata,updated_at=now()""",
                (r["id"], r["object_type"], r["branch"], r["topic"], r["subtopic"], r["micro_issue"],
                 r["title"], r["text"], normalize_text(r["text"]),
                 ("needs_review" if r["_flags"] else "source_verified"),
                 (False if r["_flags"] else True), Jsonb(r["meta"])))
            ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل الآن: python -m engine.legalmind_engine reindex")
    return 0


if __name__ == "__main__":
    sys.exit(main())
