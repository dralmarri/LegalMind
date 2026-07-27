#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل كتاب إنفاذ القانون (الكتاب الثالث من اللائحة التنفيذية 7/2010).

المصدر: نصٌّ منقول يدويًا من الصفحات المُصوَّرة للـPDF الرسمي (طبقتا النصّ في
DOCX/PDF تالفتان) ⇒ النقل البصري هو المصدر الوحيد الدقيق. 133 مادة في 13 فصلًا
+ 9 ملاحق، بلا تلف ولا نقص.
معرّفات: lreg-7-2010-k3-m{X-Y[-Z]} للمواد، lreg-7-2010-k3-annex{n} للملاحق.
النوع legislation_article ليُسترجَع في الصياغة. يوسَم «لائحة تنفيذية (دون
القانون)»، الفرع «تجاري».
"""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID   = "lreg-7-2010"
BOOK_NO  = 3
LAW_TAG  = "لائحة أسواق المال (7/2010)"
BRANCH   = "تجاري"
PARENT   = "legis-7-2010"
INSTRUMENT = "اللائحة التنفيذية لقانون هيئة أسواق المال رقم 7 لسنة 2010"
BOOK_TT  = "إنفاذ القانون"


def _sortkey(n):
    """مفتاح ترتيب متين يتحمّل مقاطع أبجدية-رقمية مثل 12-1-7b."""
    parts = []
    for x in n.split("-"):
        m = re.match(r"^(\d+)(.*)$", x)
        if m:
            parts.append((0, int(m.group(1)), m.group(2)))
        else:
            parts.append((1, 0, x))
    return parts


def build_rows(data):
    chapters = data["chapters"]
    arts = data["articles"]
    annexes = data.get("annexes", {})
    kb = f"{LAW_ID}-k{BOOK_NO}"
    rows = []

    def _meta(extra=None):
        m = {"instrument": INSTRUMENT, "instrument_rank": "لائحة تنفيذية (دون القانون)",
             "book_number": BOOK_NO, "book_title": BOOK_TT, "parent_law": PARENT,
             "upload_origin": "pdf_visual_transcription"}
        if extra:
            m.update(extra)
        return m

    for n in sorted(arts, key=_sortkey):
        a = arts[n]
        chap = n.split("-")[0]
        topic = chapters.get(chap, "أحكام عامة")
        label = a.get("article_label", n)   # للمواد المكرّرة الترقيم في المصدر
        heading = a.get("heading", "").strip()
        subtopic = a.get("subtopic")
        body = a["text"].strip()
        text = (heading + "\n" + body) if heading and not body.startswith(heading) else body
        rows.append({
            "id": f"{kb}-m{n}", "object_type": "legislation_article",
            "branch": BRANCH, "topic": topic, "subtopic": subtopic, "micro_issue": None,
            "title": f"مادة {label} — {LAW_TAG}",
            "text": text,
            "meta": _meta({"article_number": label, "chapter": chap,
                           "article_heading": heading or None})})

    for n in sorted(annexes, key=lambda x: int(x)):
        ax = annexes[n]
        title = ax.get("title", f"ملحق ({n})")
        body = ax["text"].strip()
        rows.append({
            "id": f"{kb}-annex{n}", "object_type": "legislation_article",
            "branch": BRANCH, "topic": "الملاحق", "subtopic": title, "micro_issue": None,
            "title": f"{title} — {LAW_TAG}",
            "text": body,
            "meta": _meta({"annex_number": n, "annex_title": title, "chunk": "annex"})})
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
    ap.add_argument("json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    data = json.load(open(args.json, encoding="utf-8"))
    rows = build_rows(data)

    from collections import OrderedDict
    bych = OrderedDict()
    n_annex = 0
    for r in rows:
        if r["meta"].get("chunk") == "annex":
            n_annex += 1
        else:
            bych.setdefault(r["meta"]["chapter"], []).append(r["meta"]["article_number"])
    print("== تقرير كتاب إنفاذ القانون (الكتاب الثالث) ==")
    print(f"اللائحة: {INSTRUMENT}")
    print(f"الكتاب: ({BOOK_NO}) {BOOK_TT}  | الفرع: {BRANCH}  | البادئة: {LAW_ID}-k{BOOK_NO}")
    print(f"إجمالي الكائنات: {len(rows)}  (مواد: {len(rows)-n_annex} | ملاحق: {n_annex})")
    for ch in sorted(bych, key=int):
        print(f"  فصل {ch} [{len(bych[ch])}]: {'، '.join(bych[ch])}")
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print(f"كائنات فارغة: {empty or 'لا'}")
    ids = [r["id"] for r in rows]
    dups = {i for i in ids if ids.count(i) > 1}
    print(f"معرّفات مكرّرة: {dups or 'لا'}")
    print("\n== عيّنات ==")
    for r in (rows[0], rows[len(rows)//2], rows[-1]):
        print(f"\n--- {r['id']} (topic={r['topic']}; sub={r['subtopic']}) ---")
        print(r["text"][:240])

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
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,'source_verified','source_authority',TRUE,%s)
                   ON CONFLICT (id) DO UPDATE SET
                    object_type=EXCLUDED.object_type,branch=EXCLUDED.branch,topic=EXCLUDED.topic,
                    subtopic=EXCLUDED.subtopic,micro_issue=EXCLUDED.micro_issue,title=EXCLUDED.title,
                    original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                    verification_status='source_verified',usable_as_citation=TRUE,
                    metadata=EXCLUDED.metadata,updated_at=now()""",
                (r["id"], r["object_type"], r["branch"], r["topic"], r["subtopic"], r["micro_issue"],
                 r["title"], r["text"], normalize_text(r["text"]), Jsonb(r["meta"])))
            ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل الآن: python -m engine.legalmind_engine reindex")
    return 0


if __name__ == "__main__":
    sys.exit(main())
