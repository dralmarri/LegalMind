#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 12 لسنة 2020 في شأن حق الاطلاع على المعلومات.
18 كائنًا: ديباجة + 17 مادة في سبعة فصول. الفرع «إداري». معرّفات: legis-12-2020-m{N}.

القانونُ **نافذ**: صدر 31/8/2020 ويُعمل به بعد ستة أشهر من نشره في الجريدة الرسمية.

قيدٌ على المصدر — يُدوَّن ولا يُخفى: النصُّ منقولٌ من ملفَّين غيرِ رسميَّين (DOCX + نسخةِ محامٍ
بصيغة PDF) لا من «الكويت اليوم». وقد صُحّحت عشرةُ مواضعِ سقوطِ حروفٍ، كلُّها لا-كلماتٌ في العربية،
وستّةٌ منها مؤكَّدةٌ بنصٍّ صريحٍ في الشاهد الثاني. والتصحيحاتُ محفوظةٌ بأسانيدها في
`metadata.source_corrections` على كائن الديباجة.
"""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-12-2020"
BRANCH = "إداري"
TOPIC = ("حق الاطلاع على المعلومات — التزامُ الجهات بالإفصاح، وطلبُ المعلومة ومواعيدُه، "
         "وحالاتُ الحظر، والتظلّم، والعقوبات")
INSTRUMENT = "القانون رقم 12 لسنة 2020 في شأن حق الاطلاع على المعلومات"

PREAMBLE_SUMMARY = (
    "القانون رقم 12 لسنة 2020 في شأن حق الاطلاع على المعلومات: يقرّر لكلّ شخصٍ — طبيعيٍّ أو "
    "اعتباريٍّ له مصلحة — الحقَّ في الاطلاع على المعلومات التي في حوزة الجهات العامة والحصولِ "
    "عليها (م2)، ويقرّر معه حقًّا خاصًّا في الاطلاع على القرارات الإدارية التي تمسّ حقوقه وعلى ما "
    "يحتويه أيُّ مستندٍ يتعلق به. صدر في 31/8/2020 عن نائب الأمير، ويُعمل به بعد **ستة أشهر** من "
    "نشره في الجريدة الرسمية (م17)، وتصدر لائحتُه التنفيذية بقرارٍ من **وزير العدل** خلال ستة أشهر "
    "من صدوره (م16). "
    "نطاقُ «الجهة» واسع: الوزاراتُ والهيئاتُ والمؤسساتُ العامة وسائرُ الأشخاص الاعتبارية العامة، "
    "والشركاتُ الكويتية التي تساهم فيها الدولة أو إحداها بما يزيد على 50% من رأس المال، بل "
    "والشركاتُ والمؤسساتُ الخاصة التي تحتفظ بمعلوماتٍ أو مستنداتٍ **نيابةً عن** هذه الجهات (م1). "
    "ويُلزم الجهاتِ بتعيين موظّفٍ مختصٍّ أو أكثر (م3)، وبتنظيم معلوماتها وتصنيفها وفهرستها وتحديدِ "
    "ما يُعتبَر سرّيًّا خلال **سنتين** من العمل بالقانون (م4)، وبالنشر الاستباقيّ على موقعها "
    "الإلكترونيّ خلال **ثلاث سنوات** (م5). "
    "ثمّ ينظّم طلبَ المعلومة: الإشعارُ بالاستلام (م7)، والتجزئةُ متى دخل بعضُ المطلوب في نطاق "
    "حماية الخصوصية (م10)، وتسبيبُ الرفض كتابةً (م11). ويعدّد في م12 **عشرَ حالاتٍ يُحظَر فيها "
    "الكشف** (الأمنُ الوطنيّ، والسرّيةُ المقرّرة بالدستور أو بقانونٍ أو بقرار مجلس الوزراء، وسيرُ "
    "العدالة، والحياةُ الخاصة والطبّية والمصرفية، والسرُّ التجاريّ، والعلاقاتُ الدولية، واقتصادُ "
    "الدولة، وسلامةُ الأفراد، وقراراتُ المحكمة والنيابة والإدارة العامة للتحقيقات، ومنازعاتُ "
    "الأسرة وقضايا الأحداث والتحقيقاتُ الجزائية الجارية). "
    "★ والتظلّمُ في م13 **وجوبيٌّ سابقٌ على الدعوى**: «ولا يجوز اتخاذ إجراءات التقاضي قبل البتّ في "
    "التظلّم»، ومهلةُ الردّ ستّون يومًا، وعدمُ الردّ رفضٌ ضمنيّ. ومن رفع دعواه قبله دُفع بعدم القبول. "
    "والعقوباتُ في م14 (الحبسُ حتى سنتين وغرامةٌ حتى ثلاثة آلاف دينار)، و**تختصّ النيابةُ العامة "
    "دون غيرها** بالتحقيق والتصرّف والادّعاء في جرائمه (م15). "
    "يتّصل بقانون الجزاء 16/1960 والإجراءات الجزائية 17/1960، وبالقضاء الإداري 20/1981 "
    "(دعوى الإلغاء بعد التظلّم)، وبالخدمة المدنية 15/1979، وبحماية البيانات في التشريعات ذات الصلة."
)

SOURCE_NOTE = (
    "★ مصدرُ النصّ: ملفّان غيرُ رسميَّين (DOCX + نسخةُ محامٍ بصيغة PDF)، لا «الكويت اليوم». "
    "صُحّحت عشرةُ مواضعِ سقوطِ حروفٍ، كلُّها لا-كلماتٌ في العربية، وستّةٌ منها مؤكَّدةٌ بنصٍّ صريحٍ "
    "في الشاهد الثاني. ويُنصَح بمقابلة النصّ على الجريدة الرسمية قبل الاستشهاد به أمام القضاء."
)


def build_rows(data):
    rows = []

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": 12,
             "law_year": 2020, "issued_on": "2020-08-31",
             "in_force_rule": "بعد ستة أشهر من النشر في الجريدة الرسمية (م17)",
             "source_authority": "ملفّان غير رسميَّين (DOCX + PDF نسخة محامٍ) — لا الجريدة الرسمية",
             "needs_gazette_verification": True,
             "upload_origin": "docx_autocleaned+pdf_image_witness"}
        d.update(extra); return d

    pre = (PREAMBLE_SUMMARY + "\n\n" + SOURCE_NOTE
           + "\n\nـ__ ديباجة القانون (سند الإصدار) ـــ\n" + data["preamble_text"]
           + "\n\nـــ بيان الإصدار ـــ\n" + data["issuance"])
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — قانون حق الاطلاع على المعلومات (12/2020)",
                 "text": pre,
                 "meta": meta({"chunk": "preamble", "source_corrections": data["corrections"],
                               "chapters": data["chapters"]})})
    for k in data["order"]:
        a = data["articles"][k]
        rows.append({"id": f"{LAW_ID}-m{k}", "topic": TOPIC,
                     "title": "المادة %s — قانون حق الاطلاع على المعلومات (12/2020)" % k,
                     "text": a["text"],
                     "meta": meta({"article_number": k, "chapter": a["chapter"]})})
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
    print("== تقرير قانون حق الاطلاع على المعلومات (12/2020) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)} (متوقَّع 18)")
    assert len(rows) == 18, len(rows)
    blob = " ".join(r["text"] for r in rows)
    print("محارف تالفة �:", blob.count("�"))
    assert "�" not in blob
    for bad in ("عى ", "الأعال", "للباد", "سامته"):
        assert bad not in blob, "بقي تلف: %s" % bad
    print("لا-كلماتٌ متبقّية: لا ✓")
    short = [r["id"] for r in rows if len(r["text"].strip()) < 40]
    print("قصيرة:", short or "لا"); assert not short
    ids = [r["id"] for r in rows]
    dup = {i for i in ids if ids.count(i) > 1}; print("مكرّرة:", dup or "لا"); assert not dup
    print("تصحيحاتٌ محفوظةٌ بأسانيدها:", len(data["corrections"]))
    print("الفصول:", len(data["chapters"]))
    # قواعدُ يجب أن تكون في المتن لا في الإحالة
    for oid, needle, lbl in ((f"{LAW_ID}-m13", "ولا يجوز اتخاذ إجراءات التقاضي قبل البت في التظلم",
                              "التظلّم الوجوبيّ السابق"),
                             (f"{LAW_ID}-m15", "تختص النيابة العامة دون غيرها", "اختصاصُ النيابة"),
                             (f"{LAW_ID}-m12", "سلامته", "حالةُ الحظر الثامنة")):
        r = next(x for x in rows if x["id"] == oid)
        assert needle in r["text"], "%s: %s غيرُ موجود" % (oid, needle)
        print("   ✓", lbl)
    for r in rows:
        if r["id"].endswith(("preamble", "m13", "m14")):
            print(f"\n--- {r['id']} ---\n{r['text'][:190]}")
    if args.dry_run:
        print("\n[dry-run] لم يُدخَل شيء."); return 0

    import psycopg
    from psycopg.types.json import Jsonb
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        sys.exit("DATABASE_URL غير مضبوط — صدّر deploy/.env أوّلًا")
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
