#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 28 لسنة 1969 في شأن العمل في قطاع الأعمال النفطية.
المصدر: DOCX بطبقة نصّ سليمة (استُخرج آليًا ونُظّف وروجع). 24 مادة + ديباجة. الفرع «عمل».
معرّفات: legis-28-1969-m{N} + legis-28-1969-preamble."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID   = "legis-28-1969"
LAW_NO   = 28
LAW_YEAR = 1969
LAW_TAG  = "قانون العمل في قطاع الأعمال النفطية (28/1969)"
BRANCH   = "عمل"
INSTRUMENT = "القانون رقم 28 لسنة 1969 في شأن العمل في قطاع الأعمال النفطية"
TOPIC = "العمل في قطاع الأعمال النفطية"

PREAMBLE = (
    "القانون رقم 28 لسنة 1969 في شأن العمل في قطاع الأعمال النفطية\n"
    "نحن صباح السالم الصباح أمير الكويت، بعد الاطلاع على المواد 22 و65 و179 من الدستور، "
    "وعلى القانون رقم 38 لسنة 1964 في شأن العمل في القطاع الأهلي المعدل والمصحح بالقانون "
    "رقم 43 لسنة 1968، وافق مجلس الأمة على القانون الآتي نصه."
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

    print("== تقرير قانون العمل في قطاع الأعمال النفطية (28/1969) ==")
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
