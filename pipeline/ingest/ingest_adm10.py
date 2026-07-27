#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل المرسوم بقانون رقم 10 لسنة 2020 بشأن التوثيق.
المصدر: DOCX بطبقة نصّ سليمة (استُخرج آليًا ونُظّف وروجع). 26 مادة + (5 مكرر و9 مكرر)
+ ديباجة، بنية مسطّحة. معرّفات: legis-10-2020-m{N} (و m5mkr, m9mkr) + preamble.
النوع legislation_article، الفرع «إداري»."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID   = "legis-10-2020"
LAW_NO   = 10
LAW_YEAR = 2020
LAW_TAG  = "قانون التوثيق (10/2020)"
BRANCH   = "إداري"
INSTRUMENT = "المرسوم بقانون رقم 10 لسنة 2020 بشأن التوثيق"
TOPIC = "التوثيق وأعمال الموثق الحكومي والأهلي"

PREAMBLE = (
    "المرسوم بقانون رقم 10 لسنة 2020 بشأن التوثيق\n"
    "ينظّم هذا المرسوم بقانون أعمال التوثيق: إدارة التوثيق، والموثق الحكومي والأهلي، "
    "والسجلات والمحررات الموثَّقة وحجيتها، وتوثيق الوكالات ومددها، وترخيص الموثقين "
    "الأهليين والرقابة عليهم وتأديبهم، والرسوم والعقوبات."
)

def _num_of(key):
    m = re.match(r"m(\d+)(mkr)?", key)
    return m.group(1) + (" مكرر" if m.group(2) else "")


def build_rows(data):
    arts = data["articles"]
    order = data.get("order") or list(arts.keys())
    rows = []

    def meta(extra=None):
        m = {"instrument": INSTRUMENT, "instrument_rank": "مرسوم بقانون",
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

    for key in order:
        a = arts[key]
        if key == "t2025":
            rows.append({
                "id": f"{LAW_ID}-t2025", "object_type": "legislation_article",
                "branch": BRANCH, "topic": TOPIC,
                "subtopic": "أحكام انتقالية", "micro_issue": None,
                "title": f"حكم انتقالي (تعديل 147/2025) — {LAW_TAG}",
                "text": a["text"].strip(),
                "meta": meta({"amended_by": "147/2025", "chunk": "transitional"})})
            continue
        num = _num_of(key)
        rows.append({
            "id": f"{LAW_ID}-{key}", "object_type": "legislation_article",
            "branch": BRANCH, "topic": TOPIC, "subtopic": None, "micro_issue": None,
            "title": f"مادة {num} — {LAW_TAG}",
            "text": a["text"].strip(),
            "meta": meta({"article_number": num})})
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

    print("== تقرير قانون التوثيق (10/2020) ==")
    print(f"القانون: {INSTRUMENT}  | الفرع: {BRANCH}  | البادئة: {LAW_ID}")
    print(f"إجمالي الكائنات: {len(rows)}  (مواد: {len(rows)-1} + ديباجة)")
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print(f"كائنات فارغة: {empty or 'لا'}")
    ids = [r["id"] for r in rows]
    print(f"معرّفات مكرّرة: { {i for i in ids if ids.count(i)>1} or 'لا'}")
    for r in (rows[1], rows[len(rows)//2], rows[-1]):
        print(f"\n--- {r['id']} ---\n{r['text'][:170]}")

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
