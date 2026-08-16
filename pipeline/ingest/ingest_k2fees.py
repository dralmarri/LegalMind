#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل الملحق (4) «جدول رسوم خدمات الهيئة» من الكتاب الثاني للائحة التنفيذية 7/2010.

منقول بصريًا من صفحات الـPDF الرسمي. كل قسم رسوم = كائن واحد يضم بنوده حرفيًا.
معرّفات: lreg-7-2010-k2-fee{n}. النوع legislation_article، الفرع تجاري، لائحة تنفيذية دون القانون.
"""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID  = "lreg-7-2010"
BOOK_NO = 2
LAW_TAG = "لائحة أسواق المال (7/2010)"
BRANCH  = "تجاري"
PARENT  = "legis-7-2010"
INSTRUMENT = "اللائحة التنفيذية لقانون هيئة أسواق المال رقم 7 لسنة 2010"
BOOK_TT = "هيئة أسواق المال"
ANNEX   = "ملحق (4): جدول رسوم خدمات الهيئة"


def build_rows(data):
    kb = f"{LAW_ID}-k{BOOK_NO}"
    rows = []
    def meta(extra=None):
        m = {"instrument": INSTRUMENT, "instrument_rank": "لائحة تنفيذية (دون القانون)",
             "book_number": BOOK_NO, "book_title": BOOK_TT, "parent_law": PARENT,
             "annex": "الملحق (4) جدول رسوم خدمات الهيئة", "chunk": "fee_schedule",
             "upload_origin": "pdf_visual_transcription"}
        if extra:
            m.update(extra)
        return m
    for n in sorted(data["sections"], key=int):
        sec = data["sections"][n]
        text = f"جدول رسوم خدمات الهيئة — القسم ({n}) {sec['name']}:\n" + "\n".join(sec["rows"])
        rows.append({
            "id": f"{kb}-fee{n}", "object_type": "legislation_article",
            "branch": BRANCH, "topic": ANNEX, "subtopic": sec["name"], "micro_issue": None,
            "title": f"رسوم: ({n}) {sec['name']} — {LAW_TAG}",
            "text": text,
            "meta": meta({"fee_section_no": n, "fee_section": sec["name"]})})
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

    print("== تقرير الملحق (4) جدول رسوم خدمات الهيئة ==")
    print(f"الكتاب: ({BOOK_NO}) {BOOK_TT}  | الفرع: {BRANCH}  | البادئة: {LAW_ID}-k{BOOK_NO}")
    print(f"عدد أقسام الرسوم (كائنات): {len(rows)}")
    for r in rows:
        n_lines = r["text"].count("\n")
        print(f"  {r['id']}: {r['subtopic']}  ({n_lines} سطر)")
    print("\n== عيّنة ==")
    print(rows[0]["text"][:400])

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
    print(f"\n✓ أُدخل/حُدّث {ins} قسم رسوم. شغّل الآن: python -m engine.legalmind_engine reindex")
    return 0


if __name__ == "__main__":
    sys.exit(main())
