#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل المرسوم بقانون رقم 13 لسنة 1991 بشأن الأسلحة والذخائر والأسلحة البيضاء والأسلحة الهوائية
الخطرة. 29 مادة + 3 مكرّر (21/22/24 مكرر مضافة بتعديلٍ لاحق)، الفرع «جزائي» (تجريم الحيازة/الإحراز/
الاستيراد/الاتجار بلا ترخيص، وإيقاع الروع، والعقوبات والمصادرة). النصّ منسوخ من DOCX خفيف التلف مع
تصويب آثار bidi وحروفٍ ساقطة قاطعة في مادة التعريفات؛ المحتوى العمليّ سليمٌ كما ورد. يلغي القانون
16/1961. معرّفات: legis-13-1991-m{N}[-mukarrar] + preamble."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-13-1991"
LAW_NO, LAW_YEAR = 13, 1991
LAW_TAG = "قانون الأسلحة والذخائر (13/1991)"
BRANCH = "جزائي"
INSTRUMENT = "المرسوم بقانون رقم 13 لسنة 1991 بشأن الأسلحة والذخائر والأسلحة البيضاء والأسلحة الهوائية الخطرة"
TOPIC = "الأسلحة والذخائر — الترخيص والحظر والعقوبات"

PREAMBLE = (
    "المرسوم بقانون رقم 13 لسنة 1991 بشأن الأسلحة والذخائر والأسلحة البيضاء والأسلحة الهوائية الخطرة\n"
    "ينظّم حيازة الأسلحة (البنادق والمسدسات) والذخائر والأسلحة البيضاء والأسلحة الهوائية الخطرة وإحرازها "
    "واستعمالها واستيرادها والاتجار فيها وإصلاحها ونقلها، ويشترط الترخيص من وزير الداخلية بشروطٍ في الطالب "
    "(الجنسية، السنّ 21 سنة، الأهلية، خلوّ السوابق، اللياقة). يحظر مطلقاً حيازة المدافع والمدافع الرشاشة "
    "وكاتمات الصوت، ويحدّد الأماكن المحظورة لحمل/استعمال السلاح، ويعفي أفراد الشرطة والجيش والحرس الوطني "
    "والإطفاء. يقرّر عقوبات الحبس والغرامة والمصادرة لمخالفة الحيازة/الاستيراد بلا ترخيص، ولحيازة الأسلحة "
    "البيضاء والهوائية في الأماكن المحظورة، ولجريمة «إيقاع الروع» بالسلاح في مكان عام (م22 مكرر)، مع "
    "مضاعفة العقوبة في العَود. يلغي القانون 16/1961. صدر في 28 ديسمبر 1991."
)


def _label(key):
    if key.startswith("iss"):
        return f"مادة {key[3:]} (إصدار)"
    m = re.match(r'm(\d+)(-mukarrar)?', key)
    return f"مادة {m.group(1)}" + (" مكرر" if m.group(2) else "")


def build_rows(data):
    arts = data["articles"]
    order = data.get("order") or list(arts.keys())
    rows = []

    def meta(extra=None):
        d = {"instrument": INSTRUMENT, "instrument_rank": "مرسوم بقانون", "law_number": LAW_NO,
             "law_year": LAW_YEAR, "upload_origin": "docx_law13_transcription", "repeals": "legis-16-1961"}
        if extra:
            d.update(extra)
        return d

    rows.append({
        "id": f"{LAW_ID}-preamble", "object_type": "legislation_article",
        "branch": BRANCH, "topic": "الديباجة", "subtopic": None, "micro_issue": None,
        "title": f"ديباجة — {LAW_TAG}", "text": PREAMBLE, "meta": meta({"chunk": "preamble"})})

    for key in order:
        a = arts[key]
        body = (a["text"] if isinstance(a, dict) else a).strip()
        is_iss = key.startswith("iss")
        extra = {}
        if is_iss:
            extra["issuing"] = True
        else:
            mm = re.match(r'm(\d+)(-mukarrar)?', key)
            extra["article_number"] = mm.group(1) + (" مكرر" if mm.group(2) else "")
        if isinstance(a, dict) and a.get("sec"):
            extra["fasl_raw"] = a["sec"]
        rows.append({
            "id": f"{LAW_ID}-{key}", "object_type": "legislation_article", "branch": BRANCH,
            "topic": "مواد الإصدار" if is_iss else TOPIC, "subtopic": None, "micro_issue": None,
            "title": f"{_label(key)} — {LAW_TAG}", "text": body, "meta": meta(extra)})
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

    print("== تقرير قانون الأسلحة والذخائر (13/1991) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print(f"فارغة: {empty or 'لا'}")
    ids = [r["id"] for r in rows]
    print(f"مكرّرة: {set(i for i in ids if ids.count(i) > 1) or 'لا'}")
    resid = [r["id"] for r in rows if "�" in r["text"]]
    print(f"محارف بديلة �: {resid or 'لا'}")
    for r in rows:
        if r["id"].endswith(("preamble", "-m1", "-m2", "-m21", "-m22-mukarrar", "-m28")):
            print(f"\n--- {r['id']} ({r['title']}) ---\n{r['text'][:160]}")

    if args.dry_run:
        print("\n[dry-run] لم يُدخَل شيء."); return 0

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
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل reindex.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
