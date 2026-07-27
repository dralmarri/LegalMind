#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل كتاب هيئة أسواق المال (الكتاب الثاني من اللائحة التنفيذية 7/2010).

المصدر: نصٌّ منقول يدويًا من الصفحات المُصوَّرة للـPDF الرسمي (طبقتا النصّ في
DOCX/PDF تالفتان: تشويش ترميز الخط + خلط ترتيب الإطارات) ⇒ النقل البصري هو
المصدر الوحيد الدقيق. 106 مواد في 9 فصول، بلا تلف ولا نقص.
معرّفات: lreg-7-2010-k2-m{X-Y}  — النوع legislation_article ليُسترجَع في الصياغة.
يوسَم «لائحة تنفيذية (دون القانون)»، الفرع «تجاري».
"""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID   = "lreg-7-2010"
BOOK_NO  = 2
LAW_TAG  = "لائحة أسواق المال (7/2010)"
BRANCH   = "تجاري"
PARENT   = "legis-7-2010"
INSTRUMENT = "اللائحة التنفيذية لقانون هيئة أسواق المال رقم 7 لسنة 2010"
BOOK_TT  = "هيئة أسواق المال"


def build_rows(data):
    chapters = data["chapters"]
    arts = data["articles"]
    kb = f"{LAW_ID}-k{BOOK_NO}"
    rows = []

    def _meta(extra=None):
        m = {"instrument": INSTRUMENT, "instrument_rank": "لائحة تنفيذية (دون القانون)",
             "book_number": BOOK_NO, "book_title": BOOK_TT, "parent_law": PARENT,
             "upload_origin": "pdf_visual_transcription"}
        if extra:
            m.update(extra)
        return m

    def _key(n):
        return tuple(int(x) for x in n.split("-"))

    for n in sorted(arts, key=_key):
        a = arts[n]
        chap = n.split("-")[0]
        topic = chapters.get(chap, "أحكام عامة")
        heading = a.get("heading", "").strip()
        subtopic = a.get("subtopic")
        body = a["text"].strip()
        # النصّ = العنوان الوصفي للمادة (إن وُجد) ثم متنها — مطابقةً لتخطيط المصدر
        text = (heading + "\n" + body) if heading and not body.startswith(heading) else body
        rows.append({
            "id": f"{kb}-m{n}", "object_type": "legislation_article",
            "branch": BRANCH, "topic": topic, "subtopic": subtopic, "micro_issue": None,
            "title": f"مادة {n} — {LAW_TAG}",
            "text": text,
            "meta": _meta({"article_number": n, "chapter": chap,
                           "article_heading": heading or None})})
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
    for r in rows:
        bych.setdefault(r["meta"]["chapter"], []).append(r["meta"]["article_number"])
    print("== تقرير كتاب هيئة أسواق المال (الكتاب الثاني) ==")
    print(f"اللائحة: {INSTRUMENT}")
    print(f"الكتاب: ({BOOK_NO}) {BOOK_TT}  | الفرع: {BRANCH}  | البادئة: {LAW_ID}-k{BOOK_NO}")
    print(f"إجمالي المواد: {len(rows)}")
    for ch in sorted(bych, key=int):
        print(f"  فصل {ch} [{len(bych[ch])}]: {'، '.join(bych[ch])}")
    empty = [r["meta"]["article_number"] for r in rows if not r["text"].strip()]
    print(f"مواد فارغة: {empty or 'لا'}")
    print("\n== عيّنات ==")
    for r in (rows[0], rows[18], rows[-1]):
        print(f"\n--- {r['id']} (topic={r['topic']}; sub={r['subtopic']}) ---")
        print(r["text"][:260])

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
    print(f"\n✓ أُدخل/حُدّث {ins} مادةً. شغّل الآن: python -m engine.legalmind_engine reindex")
    return 0


if __name__ == "__main__":
    sys.exit(main())
