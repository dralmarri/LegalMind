#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل كتب اللائحة التنفيذية لقانون هيئة أسواق المال (7/2010) — بنية «مادة X-Y».

يتعامل مع:
  • ترقيم «مادة فصل-مادة» (وثلاثي «مادة فصل-قسم-مادة») في الفقرات وفي الجداول معًا.
  • رؤوس/تذييلات الصفحات المتكرّرة (تكرار رقم آخر مادة، اسم الفصل، «كتاب هيئة أسواق
    المال»، التواريخ، أرقام الصفحات) ⇒ تُزال بإزالة التكرار حسب رقم المادة والضجيج.
  • عناوين الفصول (topic) من أول سطر بعد «الفصل ...».
  • جدول المحتويات في مقدّمة الملف ⇒ يُتخطّى (البداية = أول «الفصل ...» فقرةً).
  • الملاحق: النماذج (ملحق 1..3) وجدول الرسوم (ملحق 4) ⇒ كائنات منفصلة.
يوسَم الكل «لائحة تنفيذية (دون القانون)»، النوع legislation_article ليُسترجَع في الصياغة.
معرّفات: lreg-7-2010-k{book}-m{X-Y}  |  ...-fee{n}  |  ...-annex{n}
"""
from __future__ import annotations
import argparse, os, re, sys, zipfile
from collections import OrderedDict
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
LAW_ID  = "lreg-7-2010"
LAW_TAG = "لائحة أسواق المال (7/2010)"
BRANCH  = "تجاري"
PARENT  = "legis-7-2010"
INSTRUMENT = "اللائحة التنفيذية لقانون هيئة أسواق المال رقم 7 لسنة 2010"

MONTH = r"(يناير|فبراير|مارس|أبريل|إبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)"
ART   = re.compile(r"^(?:المادة|مادة)\s+(\d+(?:-\d+)+)\s*(.*)$")
FASL  = re.compile(r"^(?:الفصل|الباب)\s+\S")
DATE  = re.compile(r"^" + MONTH + r"\s*\d{4}$")
APPX  = re.compile(r"^(?:ملحق رقم|الملحق رقم|الملاحق)\b")
FEE_SEC = re.compile(r"^\s*(\d+)\s*[-–]\s*(.+?)\s*:?\s*$")     # «1 - التراخيص:»


def read_docx(path):
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read("word/document.xml").decode("utf-8"))
    body = root.find(W + "body")

    def cell_text(tc):
        return "\n".join("".join(x.text or "" for x in p.iter(W + "t")).strip()
                         for p in tc.findall(W + "p")).strip()
    seq = []
    for child in body:
        if child.tag == W + "p":
            seq.append(("p", "".join(x.text or "" for x in child.iter(W + "t")).strip()))
        elif child.tag == W + "tbl":
            rows = [[cell_text(tc) for tc in tr.findall(W + "tc")] for tr in child.findall(W + "tr")]
            seq.append(("tbl", rows))
    return seq


def _is_noise(t):
    if not t:
        return True
    if re.match(r"^\d{1,4}$", t):                 # رقم صفحة
        return True
    if DATE.match(t):                              # تاريخ إصدار في التذييل
        return True
    if t == "كتاب هيئة أسواق المال":              # رأس صفحة متكرّر
        return True
    if re.match(r"^[أ-ي]$", t):                    # حرف مفرد شارد («ق»)
        return True
    return False


def _is_art_table(rows):
    return any(r and ART.match((r[0] or "")) for r in rows)


def _row_join(cells):
    return "\n".join(c for c in cells if c).strip()


def parse(seq, book_no):
    # بداية المحتوى = أول فقرة «الفصل ...» (يتخطّى صفحة العنوان + جدول المحتويات)
    start = next((i for i, (k, v) in enumerate(seq) if k == "p" and FASL.match(v or "")), 0)

    arts = OrderedDict()      # N -> {num, topic, subtopic, body:[]}
    fees = []                 # (section_no, section_name, [ (bnd, service, fee, due) ... ])
    annexes = []              # (annex_no, title, [lines])
    order = []                # ترتيب ظهور المواد

    cur = None                # المادة المفتوحة (فقرات)
    cur_topic = "أحكام عامة"
    expect_title = False
    in_appendix = False
    cur_annex = None
    cur_fee_sec = None

    def open_art(N, first_text, topic, subtopic):
        if N in arts:                             # رأس صفحة مكرّر ⇒ تجاهل
            return arts[N]
        a = {"num": N, "topic": topic, "subtopic": subtopic, "body": []}
        if first_text:
            a["body"].append(first_text)
        arts[N] = a
        order.append(N)
        return a

    i = start
    while i < len(seq):
        k, v = seq[i]

        if k == "p":
            t = v
            if not in_appendix and APPX.match(t or ""):
                in_appendix = True
            if in_appendix:
                m = APPX.match(t or "")
                if m:
                    an = re.search(r"(\d+)", t)
                    cur_annex = {"no": int(an.group(1)) if an else len(annexes) + 1,
                                 "title": "", "lines": []}
                    annexes.append(cur_annex)
                elif cur_annex is not None and t and not _is_noise(t):
                    if not cur_annex["title"]:
                        cur_annex["title"] = t
                    else:
                        cur_annex["lines"].append(t)
                i += 1
                continue

            if FASL.match(t or ""):
                expect_title = True
                cur = None
                i += 1
                continue
            if expect_title:
                if t and not _is_noise(t):
                    cur_topic = re.sub(r"\s+", " ", t).strip(" :")
                    expect_title = False
                i += 1
                continue
            ma = ART.match(t or "")
            if ma:
                N = ma.group(1); rest = (ma.group(2) or "").strip()
                if N in arts:                     # رأس صفحة مكرّر ⇒ تجاهل ولا تُغلق cur
                    cur = arts[N]
                    i += 1
                    continue
                cur = open_art(N, rest, cur_topic, None)
                i += 1
                continue
            if _is_noise(t):
                i += 1
                continue
            if cur is not None:
                cur["body"].append(t)
            i += 1
            continue

        # جدول
        rows = v
        if in_appendix:
            # جدول رسوم؟ (يحوي «د.ك» أو رأس قسم «N - ...»)  أو نموذج
            flat = " ".join(_row_join(r) for r in rows)
            if "د.ك" in flat or FEE_SEC.match((rows[0][0] if rows and rows[0] else "")):
                for r in rows:
                    c0 = (r[0] if len(r) > 0 else "").strip()
                    fs = FEE_SEC.match(c0)
                    if fs and "د.ك" not in _row_join(r):
                        cur_fee_sec = {"no": int(fs.group(1)), "name": fs.group(2).strip(" :"),
                                       "rows": []}
                        fees.append(cur_fee_sec)
                        continue
                    cells = [c.strip() for c in r]
                    if not any(cells):
                        continue
                    if cur_fee_sec is None:
                        cur_fee_sec = {"no": 0, "name": "رسوم", "rows": []}
                        fees.append(cur_fee_sec)
                    cur_fee_sec["rows"].append(cells)
            elif cur_annex is not None:
                for r in rows:
                    line = _row_join(r)
                    if line and not _is_noise(line):
                        cur_annex["lines"].append(line)
            i += 1
            continue

        if _is_art_table(rows):
            pending = None
            last = None
            for r in rows:
                c0 = (r[0] if len(r) > 0 else "").strip()
                body = _row_join(r[1:]) if len(r) > 1 else ""
                ma = ART.match(c0)
                if ma:
                    N = ma.group(1); rest = (ma.group(2) or "").strip()
                    txt = ((pending + "\n") if pending else "") + (rest + "\n" if rest else "") + body
                    a = open_art(N, "", cur_topic, pending)
                    if txt.strip():
                        a["body"].append(txt.strip())
                    pending = None
                    last = a
                elif c0 and not ART.match(c0):
                    # صفٌّ بلا رقم: عنوان للمادة التالية (أو تكملة)
                    pending = c0 if not body else (c0 + "\n" + body)
                elif body:
                    if last is not None:
                        last["body"].append(body)
                    else:
                        pending = ((pending + "\n") if pending else "") + body
            if pending and last is not None:
                last["body"].append(pending)
            cur = last
            i += 1
            continue

        # جدول غير مادّي قبل الملاحق (نادر) ⇒ تجاهل
        i += 1

    articles = []
    for N in order:
        a = arts[N]
        text = "\n".join(x for x in a["body"] if x).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        articles.append({"num": N, "topic": a["topic"], "subtopic": a["subtopic"], "text": text})
    return articles, fees, annexes


def build_rows(articles, fees, annexes, book_no, book_title):
    rows = []
    kb = f"{LAW_ID}-k{book_no}"

    def meta(extra=None):
        m = {"instrument": INSTRUMENT, "instrument_rank": "لائحة تنفيذية (دون القانون)",
             "book_number": book_no, "book_title": book_title, "parent_law": PARENT,
             "upload_origin": "docx_regulation_import"}
        if extra:
            m.update(extra)
        return m

    for a in articles:
        head = f" ({a['subtopic']})" if a["subtopic"] else ""
        rows.append({
            "id": f"{kb}-m{a['num']}", "object_type": "legislation_article",
            "branch": BRANCH, "topic": a["topic"], "subtopic": a["subtopic"], "micro_issue": None,
            "title": f"مادة {a['num']}{head} — {LAW_TAG}",
            "text": a["text"],
            "meta": meta({"article_number": a["num"], "chapter": a["num"].split("-")[0]})})

    for fs in fees:
        if not fs["rows"]:
            continue
        lines = []
        for cells in fs["rows"]:
            lines.append(" | ".join(c for c in cells if c))
        txt = f"جدول رسوم خدمات الهيئة — {fs['name']}\n" + "\n".join(lines)
        rows.append({
            "id": f"{kb}-fee{fs['no']}", "object_type": "legislation_article",
            "branch": BRANCH, "topic": "ملحق: جدول رسوم خدمات الهيئة", "subtopic": fs["name"],
            "micro_issue": None,
            "title": f"رسوم: {fs['name']} — {LAW_TAG}",
            "text": txt, "meta": meta({"annex": "جدول الرسوم", "fee_section": fs["name"],
                                       "chunk": "fee_schedule"})})

    for an in annexes:
        if not an["title"] and not an["lines"]:
            continue
        txt = (an["title"] + "\n" + "\n".join(an["lines"])).strip()
        rows.append({
            "id": f"{kb}-annex{an['no']}", "object_type": "legislation_article",
            "branch": BRANCH, "topic": "ملحق: نماذج", "subtopic": an["title"][:60] or None,
            "micro_issue": None,
            "title": f"ملحق ({an['no']}) {an['title'][:50]} — {LAW_TAG}",
            "text": txt, "meta": meta({"annex": f"ملحق {an['no']}", "chunk": "annex_form"})})
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
    args = ap.parse_args()

    seq = read_docx(args.docx)
    articles, fees, annexes = parse(seq, args.book_number)
    rows = build_rows(articles, fees, annexes, args.book_number, args.book_title)

    # تقرير السلامة
    by_chap = OrderedDict()
    for a in articles:
        by_chap.setdefault(a["num"].split("-")[0], []).append(a["num"])
    empties = [a["num"] for a in articles if not a["text"]]
    print("== تقرير كتاب اللائحة ==")
    print(f"اللائحة: {INSTRUMENT}")
    print(f"الكتاب: ({args.book_number}) {args.book_title}   | الفرع: {BRANCH}   | البادئة: {LAW_ID}-k{args.book_number}")
    print(f"عدد المواد: {len(articles)}   مواد فارغة النص: {empties or 'لا'}")
    print(f"أقسام الرسوم: {len(fees)}   ملاحق نماذج: {len(annexes)}   إجمالي الكائنات: {len(rows)}")
    print("\n== المواد حسب الفصل ==")
    for ch, ns in by_chap.items():
        print(f"  فصل {ch} [{len(ns)}]: {'، '.join(ns)}")
    print("\n== عيّنات مواد ==")
    for a in articles[:3] + articles[-2:]:
        print(f"\n--- مادة {a['num']}  (topic={a['topic']}; sub={a['subtopic']}) ---")
        print(a["text"][:300])
    if fees:
        print("\n== عيّنة رسوم ==")
        print(next(r for r in rows if r["id"].endswith("fee" + str(fees[0]["no"])))["text"][:300])
    if annexes:
        print("\n== ملاحق نماذج ==")
        for an in annexes:
            print(f"  ملحق {an['no']}: {an['title'][:60]}  ({len(an['lines'])} سطرًا)")

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
