#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل اللائحة التنفيذية للقانون 49/2016 — الصادرة بالمرسوم 30 لسنة 2017.
48 كائنًا: ديباجةُ المرسوم + 47 مادة. الفرع «إداري». معرّفات: reg-30-2017-m{N}.

وأهمُّ ما فيه حقلان في الميتاداتا:
 • `implements` — مواد القانون التي تنفّذها كلُّ مادّة، ومعها `implements_basis` (سندُ الوصل:
   إحالةٌ صريحةٌ في المتن، أو تطابقُ ترويسة). فالمستفتي يرى **لِمَ** وُصلت لا أنّها وُصلت.
 • `fills_gap`  — خمسةُ مواضعَ تُعيّن فيها اللائحةُ ما تركه القانونُ مفتوحًا («تحددها اللائحة»).
   وهي مواضعُ السؤال العمليّ: نسبةُ التأمينين، ونسبةُ أفضلية المنتج الوطني، والمواعيد.
"""
from __future__ import annotations
import argparse, json, os, re, sys

REG_ID = "reg-30-2017"
LAW_ID = "legis-49-2016"
BRANCH = "إداري"
TOPIC = ("اللائحة التنفيذية للمناقصات العامة — التصنيف والتأهيل، الطرح والعطاءات، التأمينان، "
         "الترسية، الشكوى والتظلّم، تضارب المصالح")
INSTRUMENT = "اللائحة التنفيذية للقانون رقم 49 لسنة 2016 بشأن المناقصات العامة (المرسوم 30/2017)"

PREAMBLE_SUMMARY = (
    "اللائحة التنفيذية للقانون رقم 49 لسنة 2016 بشأن المناقصات العامة، الصادرة بالمرسوم رقم 30 لسنة "
    "2017: 47 مادة، نُشرت في الكويت اليوم ع1326 بتاريخ 5/2/2017، ويُعمل بها من تاريخ النشر. صدرت "
    "بناءً على م91 من القانون التي أوجبت صدورها بمرسوم خلال ستة أشهر من نشره. "
    "تُفصّل ما أحال إليه القانونُ ولم يُعيّنه، وأخصُّ مواضعها العملية خمسة: **نسبة التأمين الأولي** "
    "لا تقلّ عن 1% ولا تجاوز 5% من القيمة التقديرية (م30)، و**نسبة التأمين النهائي** لا تقلّ عن 10% "
    "من القيمة الإجمالية للعقد (م42)، و**نسبة أفضلية المنتج الوطني** 15% (م40)، و**مدّة قبول أو "
    "استبعاد العروض الفنية** عشرة أيام تُمدّ إلى عشرين (م32)، و**ميعاد نشر جداول المناقصات** تسعون "
    "يومًا قبل الطرح (م47). "
    "وتنظّم: التعاريف ونطاق السريان والسجلات (م1-م3)، ووحدة الشراء بمؤسسة البترول الكويتية "
    "واختصاصاتها والتظلّم أمامها (م4-م7)، ونشر قرارات الجهاز والمواصفات الفنية (م8-م10)، والممارسة "
    "العامة والإلكترونية والاتفاقية الإطارية (م11-م14)، والتسجيل والتصنيف إلى أربع فئات والتظلّم منه "
    "(م15-م20)، والتأهيل المسبق والإعلان (م21-م24)، وتسليم الوثائق والرسوم والعينات (م25-م27)، "
    "والمظروفين الفني والمالي والاجتماع التمهيدي (م28-م29)، والتأمين الأولي وفتح المظاريف (م30-م33)، "
    "وكشوف التفريغ وعناصر التقييم والترسية والتسعير (م34-م37)، والأسعار المنخفضة بصورة غير طبيعية "
    "(م38)، والأفضليات (م39-م40)، والإخطار بالنتيجة والتأمين النهائي (م41-م42)، والشكوى والتظلّم "
    "(م43-م44)، وتضارب المصالح والسلوك الواجب ونشر الجداول (م45-م47). "
    "★ صدر في شأنها استدراكٌ من مجلس الوزراء صحّح م30 بند (3): خطابُ ضمان التأمين الأولي يُحرَّر "
    "**لصالح الجهاز** لا لصالح الجهة صاحبة الشأن — والتأمينُ النهائيُّ في م42 يبقى لصالح الجهة "
    "صاحبة الشأن، وهو تمييزٌ مقصود. "
    "تُقرأ مع القانون 49/2016، وقانون إنشاء القضاء الإداري 20/1981، والمرافعات 38/1980، "
    "وديوان المحاسبة 30/1964، والصندوق الوطني للمشروعات الصغيرة والمتوسطة 98/2013، وتشجيع "
    "الاستثمار المباشر 116/2013."
)


def build_rows(data):
    rows = []

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "لائحة تنفيذية",
             "issued_by": "مرسوم رقم 30 لسنة 2017", "law_number": 30, "law_year": 2017,
             "parent_law": LAW_ID,
             "gazette": "الكويت اليوم ع1326 — 5/2/2017", "in_force_from": "2017-02-05",
             "upload_origin": "gazette_images_visual_transcription"}
        d.update(extra); return d

    pre = (PREAMBLE_SUMMARY + "\n\nـــ مرسوم الإصدار ـــ\n" + data["decree_text"]
           + "\n\nـــ بيان الإصدار ـــ\n" + data["issuance"])
    rows.append({"id": f"{REG_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — اللائحة التنفيذية للمناقصات العامة (المرسوم 30/2017)",
                 "text": pre, "meta": meta({"chunk": "preamble"})})

    for k in data["order"]:
        a = data["articles"][k]
        extra = {"article_number": k,
                 "implements": [f"{LAW_ID}-{x}" for x in a["implements"]],
                 "implements_basis": a["implements_basis"]}
        if a.get("title"):
            extra["article_title"] = a["title"]
        for f in ("fills_gap", "reading_note", "source_correction"):
            if a.get(f):
                extra[f] = a[f]
        head = "المادة %s" % k + (" — %s" % a["title"] if a.get("title") else "")
        rows.append({"id": f"{REG_ID}-m{k}", "topic": TOPIC,
                     "title": f"{head} — اللائحة التنفيذية للمناقصات العامة (30/2017)",
                     "text": a["text"], "meta": meta(extra)})
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
    ap = argparse.ArgumentParser(); ap.add_argument("json"); ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    data = json.load(open(args.json, encoding="utf-8"))
    rows = build_rows(data)
    print("== تقرير اللائحة التنفيذية للمناقصات العامة (30/2017) ==")
    print(f"الفرع: {BRANCH} | البادئة: {REG_ID} | إجمالي الكائنات: {len(rows)} (متوقَّع 48)")
    assert len(rows) == 48, len(rows)
    blob = " ".join(r["text"] for r in rows)
    print("محارف بديلة �:", "نعم!" if "�" in blob else "لا",
          "| علاماتُ صفحات:", "نعم!" if "⟦" in blob else "لا")
    assert "�" not in blob and "⟦" not in blob
    short = [r["id"] for r in rows if len(r["text"].strip()) < 60]
    print("قصيرة:", short or "لا"); assert not short
    ids = [r["id"] for r in rows]
    dup = {i for i in ids if ids.count(i) > 1}; print("مكرّرة:", dup or "لا"); assert not dup

    linked = [r for r in rows[1:] if r["meta"]["implements"]]
    print("موصولةٌ بالقانون: %d/47" % len(linked))
    tgts = sorted({t for r in linked for t in r["meta"]["implements"]})
    print("موادُّ القانون المستهدَفة: %d" % len(tgts))
    gaps = [r for r in rows if "fills_gap" in r["meta"]]
    print("\nتُعيّن ما تركه القانون (%d):" % len(gaps))
    for r in gaps:
        print("   %-16s %s" % (r["id"].replace(REG_ID + "-", ""), r["meta"]["fills_gap"]))
    corr = [r["id"] for r in rows if "source_correction" in r["meta"]]
    note = [r["id"] for r in rows if "reading_note" in r["meta"]]
    print("\nتصحيحٌ رسميٌّ موثَّق:", corr or "لا")
    print("تحفّظُ قراءةٍ موسوم:", note or "لا")
    # الأثرُ العمليّ: النِّسَبُ المُعيَّنة موجودةٌ في المتن لا في الإحالة
    for oid, needle, lbl in ((f"{REG_ID}-m42", "(10%)", "التأمين النهائي 10%"),
                             (f"{REG_ID}-m40", "(15%)", "أفضلية المنتج الوطني 15%"),
                             (f"{REG_ID}-m30", "ولصالح الجهاز", "التأمين الأولي ⇐ الجهاز")):
        r = next(x for x in rows if x["id"] == oid)
        assert needle in r["text"], "%s: %s غيرُ موجود" % (oid, needle)
        print("   ✓", lbl)
    for r in rows:
        if r["id"].endswith(("preamble", "m30", "m42")):
            print(f"\n--- {r['id']} ---\n{r['text'][:180]}")
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
                   VALUES (%s,'legislation_article',%s,%s,NULL,NULL,%s,%s,%s,NULL,
                           'source_verified','source_authority',TRUE,%s)
                   ON CONFLICT (id) DO UPDATE SET
                    branch=EXCLUDED.branch,topic=EXCLUDED.topic,title=EXCLUDED.title,
                    original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                    verification_status='source_verified',usable_as_citation=TRUE,
                    metadata=EXCLUDED.metadata,updated_at=now()""",
                (r["id"], BRANCH, r["topic"], r["title"], r["text"],
                 normalize_text(r["text"]), Jsonb(r["meta"])))
            ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل reindex.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
