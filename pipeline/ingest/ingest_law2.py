#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 2 لسنة 2016 بإنشاء الهيئة العامة لمكافحة الفساد (نزاهة) والأحكام الخاصة
بالكشف عن الذمة المالية. 59 مادة (+7 مكرّرات) في 7 أبواب. الفرع «جزائي» (يعرّف جرائم الفساد
ويعاقب عليها، ويحمي المبلّغين، وتُحيل إليه م59/م60 من 31/1970). النصّ نظيف؛ صُحِّح تلف ترميزيّ
لكلمة «المبلِّغ» آليًّا (de-mojibake)، وقلبُ أرقام bidi في قائمة إحالة م45 (متحقَّق بالمحتوى).
معرّفات: legis-2-2016-m{N}[-mukarrar] + preamble."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-2-2016"
LAW_NO, LAW_YEAR = 2, 2016
LAW_TAG = "مكافحة الفساد والذمة المالية (2/2016)"
BRANCH = "جزائي"
INSTRUMENT = ("القانون رقم 2 لسنة 2016 بشأن إنشاء الهيئة العامة لمكافحة الفساد "
              "والأحكام الخاصة بالكشف عن الذمة المالية")
TOPIC = "مكافحة الفساد والكشف عن الذمة المالية"

PREAMBLE = (
    "القانون رقم 2 لسنة 2016 بشأن إنشاء الهيئة العامة لمكافحة الفساد والأحكام الخاصة بالكشف "
    "عن الذمة المالية\n"
    "ينشئ الهيئة العامة لمكافحة الفساد (نزاهة) ويحدّد أهدافها واختصاصاتها ومجلس أمنائها وجهازها "
    "التنفيذي وشؤونها المالية ومشاركة المجتمع (الأبواب 1-2). ويعرّف «جرائم الفساد» بالإحالة إلى "
    "قوانين حماية المال العام والرشوة واستغلال النفوذ والاختلاس وغيرها (م22)، وينظّم إجراءات الضبط "
    "والتحقيق (الباب 3). ويُلزِم فئاتٍ محدّدة (الوزراء والنواب والقضاة وكبار الموظفين) بتقديم إقرارات "
    "الذمة المالية وفحصها وسريّتها (الباب 4). وينظّم إجراءات البلاغ عن الفساد وبرنامج حماية المبلّغين "
    "والشهود (الباب 5). ويقرّر عقوبات مخالفة أحكامه (الباب 6). صدر سنة 2016. "
    "(تُحيل إليه م59/م60 من القانون 31/1970 في تعريف جرائم الفساد ومسؤولية الشخص الاعتباري.)"
)


def _label(key):
    m = re.match(r'm(\d+)(-mukarrar)?', key)
    n = m.group(1)
    return f"مادة {n} مكرر" if m.group(2) else f"مادة {n}"


def build_rows(data):
    arts = data["articles"]
    order = data.get("order") or list(arts.keys())
    rows = []

    def meta(extra=None):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": LAW_NO,
             "law_year": LAW_YEAR, "upload_origin": "docx_law2_parser"}
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
        mm = re.match(r'm(\d+)(-mukarrar)?', key)
        extra = {"article_number": mm.group(1) + (" مكرر" if mm.group(2) else "")}
        if isinstance(a, dict) and a.get("sec"):
            extra["fasl_raw"] = a["sec"]
        if isinstance(a, dict) and a.get("source_note"):
            extra["source_note"] = a["source_note"]
        rows.append({
            "id": f"{LAW_ID}-{key}", "object_type": "legislation_article", "branch": BRANCH,
            "topic": TOPIC, "subtopic": None, "micro_issue": None,
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

    print("== تقرير القانون 2/2016 (مكافحة الفساد والذمة المالية) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print(f"فارغة: {empty or 'لا'}")
    ids = [r["id"] for r in rows]
    print(f"مكرّرة: {set(i for i in ids if ids.count(i) > 1) or 'لا'}")
    resid = [r["id"] for r in rows if "�" in r["text"]]
    print(f"محارف بديلة �: {resid or 'لا'}")
    for r in rows:
        if r["id"].endswith(("preamble", "-m22", "-m45", "-m1")):
            print(f"\n--- {r['id']} ({r['title']}) ---\n{r['text'][:180]}")

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
