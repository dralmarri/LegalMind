#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 61 لسنة 2007 في شأن الإعلام المرئي والمسموع. 21 مادة + ديباجة، الفرع «جزائي».
كان الأصلُ الرقميّ شديدَ التلف فرُفض، ثمّ اسْتُعيد حرفًا بحرف من صور الجريدة الرسمية. معرّفات:
legis-20-2014-m{N}. م11 منه هي المُحال إليها في م18 من القانون 8/2016 لتنظيم الإعلام الإلكتروني."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-20-2014"
BRANCH = "مدني"
TOPIC = "المعاملات الإلكترونية — حجية المستند والتوقيع الإلكتروني والتصديق والدفع الإلكتروني وحماية البيانات والعقوبات"
INSTRUMENT = "القانون رقم 20 لسنة 2014 في شأن المعاملات الإلكترونية (المعدَّل بالمرسوم بقانون 148/2025)"

PREAMBLE_SUMMARY = (
    "القانون رقم 20 لسنة 2014 في شأن المعاملات الإلكترونية: يعرّف الإلكترونيَّ والكتابةَ والبياناتِ والمستندَ "
    "أو السجلَّ والرسالةَ والمنشئَ والمرسلَ إليه والمعاملةَ والنظامَ المؤتمت والتوقيعَ الإلكتروني والتوقيعَ "
    "المحميَّ وأداةَ التوقيع والموقِّعَ والدفعَ الإلكتروني والمؤسسةَ المالية والقيدَ غير المشروع ومزوِّدَ خدمات "
    "التصديق وشهادةَ التصديق وختمَ الوقت والجهةَ المختصة والتشفير (م1). "
    "**م2 وم3 مستبدَلتان بالمرسوم بقانون رقم 148 لسنة 2025** (الكويت اليوم ع1763، 2/11/2025، صدر 23 أكتوبر 2025): "
    "فصار القانون يسري — ما لم يتفق الأطراف على غيره — على السجلات والرسائل والمعاملات والمستندات والتوقيعات "
    "الإلكترونية ذات العلاقة بالمعاملات والتصرفات المدنية والتجارية والإدارية **وعلى كلّ نزاع ينشأ عن استخدامها**، "
    "مع مراعاة الأحكام الخاصة لأيٍّ منها في القوانين الأخرى، **ولا يُعتدّ لأيّ سبب بإنكار آثارها القانونية** (م2). "
    "وقد ألغى هذا الاستبدالُ قائمةَ الاستثناءات التي كانت في نصّ 2014 (الأحوال الشخصية والوقف والوصية، وسندات ملكية "
    "العقار وما ينشأ عنها من حقوق عينية، والسندات الإذنية والكمبيالات، وما يستلزم محرَّرًا رسميًّا) — فصارت داخلةً "
    "في النطاق بنصّ المذكّرة الإيضاحية. وم3 الجديدة تجعل السجلَّ والمستندَ والرسالةَ والمعاملةَ والتوقيعَ الإلكتروني "
    "منتجًا لذات آثار الورق والتوقيع الكتابي، **وتُعدّها مستوفيةً جميع الأركان المتطلَّبة لانعقاد التصرّف** أو ترتيب "
    "أيّ أثر قانوني، بما في ذلك التسجيل أو الإشهار متى أنشأت الجهةُ المناط بها ذلك سجلًّا إلكترونيًّا. "
    "ولا يُلزَم أحدٌ بقبول التعامل الإلكتروني بلا موافقته، وقبولُ الجهات الحكومية يجب أن يكون صريحًا (م4). "
    "والصورةُ المنسوخة على الورق حجّةٌ على الكافة للمستند الرسمي وعلى من نُسب إليه توقيعُه للعرفي، بشروط م19/م20 (م6)، "
    "ويُرجَع فيما لم يَرِد فيه نصٌّ إلى قانون الإثبات 39/1980 (م7). ويجوز التعاقدُ بين نظمٍ مؤتمتة بلا تدخّلٍ بشريّ "
    "(م8). وللمستند أربعةُ شروطٍ لإنتاج أثره (م9)، وقواعدُ الإسناد إلى المنشئ (م11) والإخطار بالتسلّم (م12) ووقتُ "
    "الإرسال والتسلّم ومكانُهما (م15/م16)، وحجّيةُ ختم الوقت (م17). "
    "وللتوقيع المحميّ حجّيةُ التوقيع الكتابي (م18) بأربعة شروط (م19)، وعبءُ تقديم شهادة التصديق على المتمسّك به (م20)، "
    "وواجباتُ الموقِّع الثلاثة (م21). وتنظّم الجهةُ المختصة خدماتِ التصديق وتُرخّصها وتراقبها (م22-م25) بالتنسيق مع "
    "الهيئة العامة للمعلومات المدنية (م23). وللجهات الحكومية قبولُ الإيداع والتراخيص والرسوم والعطاءات إلكترونيًّا "
    "(م26/م27). وينظّم الفصلُ السادس الدفعَ الإلكتروني: التزاماتِ المؤسسة المالية (م29)، ومسؤوليةَ العميل عن القيد "
    "غير المشروع وحدودَها (م30)، وتعليماتِ البنك المركزي وجزاءَ م85 من القانون 22/1968 (م31). "
    "ويحمي الفصلُ السابع الخصوصية: حظرُ الاطّلاع والإفشاء والنشر بلا موافقةٍ أو قرارٍ قضائيّ مسبَّب (م32)، وحقُّ الفرد "
    "في الاطّلاع على بياناته (م33)، وإجراءاتُ طلب البيانات ورفضِه خلال ثلاثين يومًا والتظلّمِ خلال ستين (م34)، "
    "والمحظوراتُ والالتزامات (م35)، وحقُّ المحو والتعديل (م36). "
    "والعقوبات: حبسٌ ≤ ثلاث سنوات وغرامة 5000-20000 دينار لستّ صورٍ منها الدخولُ غير المشروع وتعطيلُ النظام وتزويرُ "
    "التوقيع أو المستند واستعمالُه ومزاولةُ التصديق بلا ترخيص ومخالفةُ م32 وم35، مع المصادرة ونشرِ ملخّص الحكم "
    "ومضاعفةِ العقوبة في العود (م37)؛ وحبسٌ ≤ سنة وغرامة 3000-10000 لمن قدّم بياناتٍ غير صحيحة في طلب الترخيص (م38)؛ "
    "ومسؤوليةُ المسؤول عن الإدارة الفعلية وتضامنُ الشخص المعنوي (م39). وتختصّ النيابةُ العامة دون غيرها (م40)، "
    "وللموظفين المحدَّدين صفةُ الضبطية القضائية (م41)، **ويجوز الصلحُ للمرة الأولى بدفع ألف دينار قبل الإحالة "
    "فتنقضي الدعوى الجزائية وجميعُ آثارها** (م42). صدر في 11 ربيع الآخر 1435هـ الموافق 11 فبراير 2014م، ويُعمل به "
    "من تاريخ إقرار اللائحة التنفيذية (م46). تستند إليه ديباجةُ القانون 8/2016 لتنظيم الإعلام الإلكتروني."
)


def build_rows(data):
    rows = []

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": 20,
             "law_year": 2014, "upload_origin": "official_booklet_images + gazette_1763_amendment"}
        d.update(extra); return d

    pre = PREAMBLE_SUMMARY + "\n\nـــ ديباجة القانون (سند الإصدار) ـــ\n" + (data.get("preamble_text") or "")
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — قانون المعاملات الإلكترونية (20/2014)", "text": pre,
                 "meta": meta({"chunk": "preamble"})})
    secs = data.get("sections") or {}
    for k in data["order"]:
        num = re.match(r"m(\d+)", k).group(1)
        sec = secs.get(k) or ""
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC,
                     "title": f"المادة {num}{(' — ' + sec) if sec else ''} — قانون المعاملات الإلكترونية (20/2014)",
                     "text": data["articles"][k],
                     "meta": meta({"article_number": num, "section": sec})})
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
    print("== تقرير قانون المعاملات الإلكترونية (20/2014) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    blob = " ".join(r["text"] for r in rows)
    print("محارف بديلة �:", "نعم!" if "�" in blob else "لا", "| شرطات _:", blob.count("_"))
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print("فارغة:", empty or "لا")
    ids = [r["id"] for r in rows]; print("مكرّرة:", set(i for i in ids if ids.count(i) > 1) or "لا")
    for r in rows:
        if r["id"].endswith(("preamble", "m2", "m3", "m37")):
            print(f"\n--- {r['id']} ---\n{r['text'][:150]}")
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
