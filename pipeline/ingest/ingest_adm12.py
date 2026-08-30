#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل المرسوم بالقانون رقم 40 لسنة 1980 بإصدار قانون تنظيم الخبرة.
المصدر: DOCX بطبقة نصّ سليمة (استُخرج آليًا ونُظّف وروجع). 4 مواد إصدار + 54 مادة
(منها ملغاة 26 و27) + ديباجة، في فصول. الفرع «إداري».
معرّفات: legis-40-1980-m{N} و -iss{N} + preamble. (عناوين الفصول تُحفظ في الميتاداتا فقط
لأن ترقيمها في المصدر مضطرب؛ لا يعتمد عليها الاسترجاع.)"""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID   = "legis-40-1980"
LAW_NO   = 40
LAW_YEAR = 1980
LAW_TAG  = "قانون تنظيم الخبرة (40/1980)"
BRANCH   = "إداري"
INSTRUMENT = "المرسوم بالقانون رقم 40 لسنة 1980 بإصدار قانون تنظيم الخبرة"
TOPIC = "تنظيم الخبرة القضائية وأعمال الخبراء أمام المحاكم والنيابة"

PREAMBLE = (
    "المرسوم بالقانون رقم 40 لسنة 1980 بإصدار قانون تنظيم الخبرة\n"
    "ينظّم هذا القانون أعمال الخبرة أمام المحاكم والنيابة العامة والإدارة العامة للتحقيقات "
    "وهيئات التحكيم القضائي: الإدارة العامة للخبراء وتشكيلها، وخبراء الجدول ولجنتهم، وشروط "
    "التعيين والقيد واليمين والواجبات والمحظورات، وأتعاب الخبرة، وتأديب الخبراء وحصانتهم، "
    "ونظام الخبرة الإلكتروني. ويلغي المواد 23-26 من مرسوم تنظيم القضاء 19/1959 وقانون "
    "تنظيم الإدارة العامة للخبراء الصادر في 6/10/1971."
)


def _label(key):
    if key.startswith("iss"):
        return f"مادة {key[3:]} (إصدار)"
    return f"مادة {key[1:]}"


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
        body = (a["text"] if isinstance(a, dict) else a).strip()
        lab = _label(key)
        is_iss = key.startswith("iss")
        is_repealed = (body == "(ملغاة)")
        extra = {}
        if is_iss:
            extra["issuing"] = True
        else:
            extra["article_number"] = key[1:]
        if a.get("fasl"):
            extra["fasl_raw"] = a["fasl"]
        if is_repealed:
            extra["repealed"] = True
        rows.append({
            "id": f"{LAW_ID}-{key}", "object_type": "legislation_article",
            "branch": BRANCH,
            "topic": "مواد الإصدار" if is_iss else TOPIC,
            "subtopic": None, "micro_issue": None,
            "title": f"{lab} — {LAW_TAG}",
            "text": body,
            "meta": meta(extra)})
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

    print("== تقرير قانون تنظيم الخبرة (40/1980) ==")
    print(f"القانون: {INSTRUMENT}  | الفرع: {BRANCH}  | البادئة: {LAW_ID}")
    print(f"إجمالي الكائنات: {len(rows)}  (مواد: {len(rows)-1} + ديباجة)")
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print(f"كائنات فارغة: {empty or 'لا'}")
    ids = [r["id"] for r in rows]
    print(f"معرّفات مكرّرة: { {i for i in ids if ids.count(i)>1} or 'لا'}")
    repealed = [r["id"] for r in rows if r["meta"].get("repealed")]
    print(f"مواد ملغاة: {repealed}")
    for r in (rows[1], rows[6], rows[len(rows)//2], rows[-1]):
        print(f"\n--- {r['id']} ({r['title']}) ---\n{r['text'][:150]}")

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
