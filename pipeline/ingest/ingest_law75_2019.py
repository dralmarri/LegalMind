#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 75 لسنة 2019 في شأن حقوق المؤلف والحقوق المجاورة.
52 كائنًا: ديباجة + 51 مادة في ثلاثة أبواب وسبعة فصول. الفرع «تجاري». معرّفات: legis-75-2019-m{N}.

قيدٌ على المصدر يُدوَّن ولا يُخفى: أصلُ النصّ ملفُّ DOCX غيرُ رسميّ. وصُحّحت ستّةُ مواضعِ تلفٍ
منمَّطة، كلُّها كلماتٌ **معرَّفةٌ في المادة نفسِها** فالسياقُ يحسمها.

ثمّ قُوبل النصُّ على **صورِ صفحاتٍ من «الكويت اليوم» ع1455** (الديباجة، وص أ16، والصفحةُ الأخيرة
م43–م51 وبيانُ الإصدار)، فأفادت ثلاثًا: استُكمل التاريخُ الميلاديُّ «الموافق 23 يوليو 2019 م»
موسومًا بمصدره؛ وطابقت م49 حرفًا بحرف؛ وتبيّن أنّ ترويسة «أحكام ختامية» تسبق م48 وقد التصقت
في الملفّ بذيل م47 — ففُصلت، فصارت العقوباتُ م41–م47 لا م41–م48. وما اختلف فيه الشاهدان ولم يكن
لا-كلمةً سُجّل في `metadata.gazette_divergences` ولم يُغيَّر.
"""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-75-2019"
BRANCH = "تجاري"
TOPIC = ("حقوق المؤلف والحقوق المجاورة — المصنَّفات والحقوق الأدبية والمالية، ومدةُ الحماية، "
         "والقيودُ والاستثناءات، والإدارةُ الجماعية والإجراءاتُ التحفظية والعقوبات")
INSTRUMENT = "القانون رقم 75 لسنة 2019 في شأن حقوق المؤلف والحقوق المجاورة"

PREAMBLE_SUMMARY = (
    "القانون رقم 75 لسنة 2019 في شأن حقوق المؤلف والحقوق المجاورة: الشريعةُ العامة لحماية "
    "الملكية الأدبية والفنية في الكويت. 51 مادة في ثلاثة أبواب. صدر بقصر السيف في 20 ذي القعدة "
    "1440هـ الموافق 23 يوليو 2019م عن أمير الكويت صباح الأحمد الجابر الصباح، ونُشر في «الكويت "
    "اليوم» العدد 1455 السنة الخامسة والستون. "
    "**الباب الأول (م1-م5)** التعاريف ونطاق الحماية: يعرّف المصنَّف والابتكار والمؤلَّف والمصنَّف "
    "المشتق وسائرَ المصطلحات، ويرسم نطاقَ ما يُحمى وما لا يُحمى. "
    "**الباب الثاني (م6-م33)** الحقوق: الفصلُ الأول في حقوق المؤلف — الأدبيةِ منها والمالية "
    "(م6-م15)، والفصلُ الثاني في **الحقوق المجاورة** لفناني الأداء ومنتجي التسجيلات وهيئات "
    "البث (م16-م21)، والفصلُ الثالث في **مدة الحماية** (م22-م24)، والفصلُ الرابع في أحكامٍ خاصةٍ "
    "ببعض المصنفات (م25-م30)، والفصلُ الخامس في **القيود والاستثناءات** على حقوق المؤلف والحقوق "
    "المجاورة (م31-م33) — وهو مفتاحُ الجواب في كلّ سؤالٍ عن الاستعمال المشروع بلا إذن: النسخُ "
    "للاستعمال الشخصيّ، والاقتباسُ، والاستعمالُ التعليميّ، وغيرُها بشرط ألّا يتعارض مع الاستغلال "
    "العادي للمصنف ولا يلحق ضررًا غير مبرر بمصالح صاحب الحق، مع ذكر المصدر واسم المؤلف. "
    "**الباب الثالث (م34-م51)**: الإدارةُ الجماعية لاقتضاء الحقوق والإجراءاتُ التحفظية (م34-م40) — "
    "ومنها الحجزُ والتحفّظُ ووقفُ النشر، ثمّ **العقوبات (م41-م47)** وهي حبسٌ وغرامة: م43 اعتداءٌ "
    "على حقٍّ أدبيٍّ أو ماليّ (حبسٌ 6 أشهر–سنتين وغرامة 500–50,000 د.ك)، وم44 التحايلُ على تدابير "
    "الحماية التكنولوجية (حبسٌ 6 أشهر–سنتين وغرامة 1,000–100,000 د.ك)، وم45 المصادرةُ والإتلافُ "
    "وإغلاقُ المنشأة، وم46 **العودُ خلال خمس سنوات يزيد الحدَّ الأقصى بمقدار النصف**، وم47 عرقلةُ "
    "موظّفي م36. و**م41 تُصرّح** بأنّ عقوباتِ هذا الفصل تُطبَّق «دون الإخلال بالاستثناءات الواردة "
    "بالمادتين 31 و32» — فمن أفتى بالعقوبة قبل أن يفحص الاستثناءَ جرّم مباحًا. "
    "و**الأحكامُ الختامية (م48-م51)**: م49 **تلغي القانون 22/2016 (حقوق المؤلف) والقانون 64/1999 "
    "(حقوق الملكية الفكرية)** وكلَّ نصٍّ يخالف؛ وم50 اللائحةُ التنفيذية يصدرها الوزير المختص خلال "
    "سنة من العمل بالقانون. "
    "يتّصل بقانون الجزاء 16/1960 والإجراءات الجزائية 17/1960، وبالمرافعات 38/1980، وبالقانون "
    "المدني 67/1980، وبقانون العلاقات القانونية ذات العنصر الأجنبي 5/1961، وبمرسوم بقانون "
    "التجارة الرقمية 10/2026 (م5 منه تُخضِع العلاماتِ والموادَّ المستخدمة في التسويق الرقميّ "
    "لهذا القانون)."
)

SOURCE_NOTE = (
    "★ مصدرُ النصّ: أصلُه ملفُّ DOCX غيرُ رسميّ. صُحّحت ستّةُ مواضعِ تلفٍ منمَّطة "
    "(«المصنَّف»، «المؤلَّف»، «المصنَّف المشتق»، «بُثَّ»، «المبتكِر»، «أصله») وكلُّها كلماتٌ "
    "معرَّفةٌ في المادة نفسِها فالسياقُ يحسمها، وأُسانيدها محفوظة. "
    "★★ ثمّ قُوبل على **صورِ صفحاتٍ من «الكويت اليوم» ع1455 السنة الخامسة والستون**: الصفحةِ "
    "الأولى من الديباجة، وص أ16، والصفحةِ الأخيرة (م43–م51 وبيانِ الإصدار). فاستُكمل التاريخُ "
    "الميلاديُّ «الموافق 23 يوليو 2019 م» موسومًا بمصدره (ولم يكن في الملفّ)، وطابقت م49 حرفًا "
    "بحرف، وفُصلت ترويسةُ «أحكام ختامية» عن ذيل م47 وأُثبتت قسمًا يسبق م48 — فالعقوباتُ م41–م47 "
    "لا م41–م48. "
    "⚠️ وما بقي من المواد (م1–م42) **لم يُقابَل على الجريدة**، فيُنصَح بمقابلته قبل الاستشهاد به "
    "أمام القضاء. وموضعان اختلف فيهما الشاهدان ولم يكونا لا-كلمةً فسُجِّلا ولم يُغيَّرا: خاتمةُ "
    "الديباجة (لفظُ «الآتي نصه» في الملفّ مقابلَ «التالي نصه، وقد صدقنا عليه وأصدرناه» في الصورة)، "
    "ولفظُ «القانون المرافق» في م48 وم50 مع أنّ القانون يبدأ بالباب الأول بعد الديباجة مباشرةً "
    "بلا مواد إصدارٍ في الصدر."
)


def build_rows(data):
    rows = []

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": 75,
             "law_year": 2019, "issued_hijri": "20 ذو القعدة 1440",
             "issued_gregorian": "2019-07-23",
             "gazette": data["gazette"]["citation"],
             "repeals": ["القانون 22 لسنة 2016 في شأن حقوق المؤلف والحقوق المجاورة",
                         "القانون 64 لسنة 1999 في شأن حقوق الملكية الفكرية"],
             "source_authority": "ملفّ DOCX غير رسميّ + مقابلةٌ جزئية على صور «الكويت اليوم» ع1455",
             "gazette_verified_parts": data["gazette"]["verified_pages"],
             "needs_gazette_verification": True,   # م1–م42 لم تُقابَل بعد
             "upload_origin": "docx_autocleaned+gazette_image_partial"}
        d.update(extra); return d

    pre = (PREAMBLE_SUMMARY + "\n\n" + SOURCE_NOTE
           + "\n\nـــ ديباجة القانون (سند الإصدار) ـــ\n" + data["preamble_text"]
           + "\n\nـــ بيان الإصدار ـــ\n" + data["issuance"])
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — قانون حقوق المؤلف والحقوق المجاورة (75/2019)",
                 "text": pre,
                 "meta": meta({"chunk": "preamble", "source_corrections": data["corrections"],
                               "structural_splits": data["structural_splits"],
                               "gazette_divergences": data["gazette_divergences"],
                               "structure": data["structure"]})})
    for k in data["order"]:
        a = data["articles"][k]
        extra = {"article_number": k, "bab": a["bab"], "fasl": a["fasl"],
                 "subhead": a.get("subhead")}
        if 41 <= int(k) <= 47:                       # العقوبات — لا تمتدّ إلى م48 (أحكام ختامية)
            extra["penal"] = True
        rows.append({"id": f"{LAW_ID}-m{k}", "topic": TOPIC,
                     "title": "المادة %s — قانون حقوق المؤلف والحقوق المجاورة (75/2019)" % k,
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
    print("== تقرير قانون حقوق المؤلف والحقوق المجاورة (75/2019) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)} (متوقَّع 52)")
    assert len(rows) == 52, len(rows)
    blob = " ".join(r["text"] for r in rows)
    print("محارف تالفة �:", blob.count("�"))
    assert "�" not in blob and not re.findall(r"([ً-ْ])\1", blob)
    short = [r["id"] for r in rows if len(r["text"].strip()) < 40]
    print("قصيرة:", short or "لا"); assert not short
    ids = [r["id"] for r in rows]
    dup = {i for i in ids if ids.count(i) > 1}; print("مكرّرة:", dup or "لا"); assert not dup
    print("تصحيحاتٌ محفوظةٌ بأسانيدها:", len(data["corrections"]))
    print("فصولٌ بنيويّة:", len(data["structural_splits"]),
          "| عناوينُ فرعيةٌ انتُزعت:", len(data["subheadings"]),
          "| خلافُ الشاهدين (سُجّل ولم يُغيَّر):", len(data["gazette_divergences"]))
    # ذيلُ مادةٍ لا يكون عنوانًا — ستّةُ مواضعَ تسرّبت فيها ترويسةٌ فرعيةٌ إلى المتن السابق
    for n in (5, 8, 15, 16, 21, 22):
        t = next(x for x in rows if x["id"] == f"{LAW_ID}-m%d" % n)["text"].rstrip()
        assert not t.endswith(("الحقوق الأدبية", "الحقوق المالية")), \
            "م%d ذيلُها عنوانٌ: %r" % (n, t[-40:])
    print("   ✓ ذيولُ م5 وم8 وم15 وم16 وم21 وم22 خالصةٌ من العناوين الفرعية")
    pen = [r["id"] for r in rows if r["meta"].get("penal")]
    print("موادُّ العقوبات الموسومة:", len(pen), "→ م41–م47")
    assert pen == [f"{LAW_ID}-m%d" % n for n in range(41, 48)], pen
    for oid, needle, lbl in ((f"{LAW_ID}-m41", "دون الإخلال بالاستثناءات الواردة بالمادتين",
                              "ربطُ العقوبة بالاستثناءات"),
                             (f"{LAW_ID}-m31", "الاستغلال العادي للمصنف", "معيارُ الاستعمال المشروع"),
                             (f"{LAW_ID}-m1", "المصنَّف", "التعريف"),
                             (f"{LAW_ID}-m49", "يُلغى القانون رقم 22 لسنة 2016", "الإلغاء (مطابقٌ للجريدة)"),
                             (f"{LAW_ID}-m46", "خلال خمس سنوات", "العود"),
                             (f"{LAW_ID}-preamble", "الموافق 23 يوليو 2019 م", "التاريخُ الميلاديّ"),
                             (f"{LAW_ID}-preamble", "الكويت اليوم", "بيانُ الجريدة"),
                             (f"{LAW_ID}-preamble", "لم يُقابَل على الجريدة", "التنبيهُ في المتن")):
        r = next(x for x in rows if x["id"] == oid)
        assert needle in r["text"], "%s: %s غيرُ موجود" % (oid, needle)
        print("   ✓", lbl)
    # الترويسةُ لا تكون متنًا، والأحكامُ الختامية قسمٌ قائمٌ بذاته
    m47 = next(x for x in rows if x["id"] == f"{LAW_ID}-m47")
    assert "أحكام ختامية" not in m47["text"], "ترويسةٌ باقيةٌ في متن م47"
    for n in (48, 49, 50, 51):
        assert next(x for x in rows if x["id"] == f"{LAW_ID}-m%d" % n)["meta"]["fasl"] == "أحكام ختامية"
    print("   ✓ م48–م51 أحكامٌ ختامية · م47 خالصةٌ من الترويسة")
    for r in rows:
        if r["id"].endswith(("preamble", "m31", "m41")):
            print(f"\n--- {r['id']} ---\n{r['text'][:180]}")
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
