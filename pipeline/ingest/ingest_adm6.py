#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل المرسوم بقانون رقم 128 لسنة 1992 بشأن نظام التأمين التكميلي.
المصدر: DOCX بطبقة نصّ سليمة (استُخرج آليًا ونُظّف وروجع). 17 مادة + ديباجة. الفرع «عمل».
معرّفات: legis-128-1992-m{N} + legis-128-1992-preamble."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID   = "legis-128-1992"
LAW_NO   = 128
LAW_YEAR = 1992
LAW_TAG  = "قانون التأمين التكميلي (128/1992)"
BRANCH   = "إداري"
INSTRUMENT = "المرسوم بقانون رقم 128 لسنة 1992 بشأن نظام التأمين التكميلي"
TOPIC = "نظام التأمين التكميلي"

PREAMBLE = (
    "المرسوم بقانون رقم 128 لسنة 1992 بشأن نظام التأمين التكميلي\n"
    "بعد الاطلاع على الدستور، وعلى قانون العمل في القطاع الأهلي (38/1964)، وقانون العمل في "
    "قطاع الأعمال النفطية (28/1969)، والأمر الأميري بالقانون رقم 61 لسنة 1976 بإصدار قانون "
    "التأمينات الاجتماعية، والمرسوم بالقانون رقم 15 لسنة 1979 في شأن الخدمة المدنية. "
    "ينشئ هذا القانون التأمين التكميلي كمظلّة تأمينية تُكمّل التأمين الأساسي وتُطبّقه المؤسسة "
    "العامة للتأمينات الاجتماعية."
)


def build_rows(data):
    arts = data["articles"]
    order = data.get("order") or sorted(arts, key=lambda n: int(n))
    rows = []

    def meta(extra=None):
        m = {"instrument": INSTRUMENT, "instrument_rank": "قانون",
             "law_number": LAW_NO, "law_year": LAW_YEAR,
             "upload_origin": "docx_clean_textlayer"}
        if extra:
            m.update(extra)
        return m

    rows.append({
        "id": f"{LAW_ID}-preamble", "object_type": "legislation_article",
        "branch": BRANCH, "topic": "الديباجة", "subtopic": None, "micro_issue": None,
        "title": f"ديباجة — {LAW_TAG}",
        "text": PREAMBLE,
        "meta": meta({"chunk": "preamble"})})

    for n in order:
        a = arts[n]
        body = (a["text"] if isinstance(a, dict) else a).strip()
        rows.append({
            "id": f"{LAW_ID}-m{n}", "object_type": "legislation_article",
            "branch": BRANCH, "topic": TOPIC, "subtopic": None, "micro_issue": None,
            "title": f"مادة {n} — {LAW_TAG}",
            "text": body,
            "meta": meta({"article_number": n})})
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

    print("== تقرير قانون التأمين التكميلي (128/1992) ==")
    print(f"القانون: {INSTRUMENT}  | الفرع: {BRANCH}  | البادئة: {LAW_ID}")
    print(f"إجمالي الكائنات: {len(rows)}  (مواد: {len(rows)-1} + ديباجة)")
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print(f"كائنات فارغة: {empty or 'لا'}")
    ids = [r["id"] for r in rows]
    print(f"معرّفات مكرّرة: { {i for i in ids if ids.count(i)>1} or 'لا'}")
    for r in (rows[1], rows[len(rows)//2], rows[-1]):
        print(f"\n--- {r['id']} ---\n{r['text'][:180]}")

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
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل الآن: reindex")
    return 0


if __name__ == "__main__":
    sys.exit(main())
