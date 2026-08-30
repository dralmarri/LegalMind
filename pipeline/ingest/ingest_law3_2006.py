#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 3 لسنة 2006 في شأن المطبوعات والنشر. 33 مادة + ديباجة، الفرع «جزائي» (المحظورات
والعقوبات م19-م28، النيابة م23، دائرة الجنايات م24، السقوط م25). النصُّ النافذ المعدَّل، مقابَلٌ بصور
الجريدة الرسمية (الكويت اليوم ع762، 2/4/2006) وبالنسخة المجمَّعة المحدَّثة. معرّفات: legis-3-2006-m{N}.
يتّصل بـ8/2016 (م18 منه تُحيل محظوراتِ هذا القانون وعقوباتِه) وبـ20/1981 (م11 هنا تُجيز الطعنَ بالإلغاء)."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-3-2006"
BRANCH = "جزائي"
TOPIC = "المطبوعات والنشر — التراخيص والصحيفة ورئيس التحرير والمحظورات والعقوبات والاختصاص"
INSTRUMENT = "القانون رقم 3 لسنة 2006 في شأن المطبوعات والنشر"

PREAMBLE_SUMMARY = (
    "القانون رقم 3 لسنة 2006 في شأن المطبوعات والنشر: يكفل حرية الصحافة والطباعة والنشر وفق أحكامه (م1)، "
    "ويعرّف المطبوع والطابع والصحيفة ورئيس التحرير والناشر والتداول والكاتب والمحرر — وينصّ صراحةً على أنّه "
    "«يدخل في حكم المطبوع ما ينشر من خلال المواقع أو الوسائل الإعلامية الإلكترونية» (م2). يوجب ترخيصَ "
    "المطابع ومحال بيع المطبوعات ودور النشر والترجمة ومكاتب الدعاية بشروطٍ أربعة (م3-م7). ولا تخضع الصحف "
    "لرقابةٍ مسبقة (م8)، ويشترط لإصدار الصحيفة ترخيصٌ ورأسُ مالٍ لا يقلّ عن مائتين وخمسين ألف دينار "
    "لليومية (م9)، وشروطٌ في طالب الترخيص (م10). يصدر الوزير قرارَه خلال تسعين يومًا وإلّا عُدّ الطلبُ "
    "مرفوضًا، ولذوي الشأن الطعنُ بإلغاء قرار الرفض أمام الدائرة الإدارية وفق المرسوم بالقانون 20/1981 خلال "
    "ستين يومًا (م11). وتُودَع كفالةٌ ماليةٌ مائة ألف دينار لليومية وخمسة وعشرون ألفًا لغيرها خلال ثلاثة "
    "أشهر (م12)، ويبطل إيجارُ الترخيص وبيعُه بلا موافقة (م13)، وتُلغى التراخيص في أحوالٍ أربعة (م14)، ولا "
    "يُلغى ترخيصُ الصحيفة إلّا بحكمٍ نهائيّ مع جواز إيقافها مؤقتًا أسبوعين قابلة للتجديد بقرار رئيس دائرة "
    "الجنايات أو قاضي الأمور المستعجلة بطلب النيابة (م15). ويشترط في رئيس التحرير شروطٌ أربعة (م16)، "
    "وعليه تحرّي الدقة ونشرُ الردّ والتصحيح والتكذيب دون مقابل (م17)، ويلزم مراسلو الصحف الأجنبية بترخيص "
    "(م18). ويحظر المساسُ بالذات الإلهية والقرآن والأنبياء والصحابة وأمّهات المؤمنين وآل البيت (م19)، "
    "والتعرّضُ لشخص الأمير بالنقد (م20)، وأحدَ عشرَ محظورًا في النشر منها تحقير الدستور وإهانة القضاء وخدش "
    "الآداب وإثارة الفتن الطائفية والقبلية (م21). وتختصّ النيابةُ العامة دون غيرها (م23)، ودائرةُ الجنايات "
    "بالمحكمة الكلية مع الاستئناف والتمييز (م24)، وتسقط الدعوى الجزائية بثلاثة أشهر من النشر والتعويض بسنة "
    "(م25). والعقوبات: غرامة 500-1000 دينار لمخالفات الفصل الأول وتشتدّ إلى 3000-10000 مع المصادرة (م26)، "
    "وحبسٌ لا يجاوز سنةً وغرامة 5000-20000 لمخالفة م19، وغرامة 5000-20000 لمخالفة م20، و3000-10000 لمخالفة "
    "م21، و1000-3000 لسائر مخالفات الفصل الثاني، مع جواز إلغاء الترخيص أو تعطيل الصحيفة سنةً والمصادرة "
    "وإغلاق المطبعة (م27)، والتحريضُ على قلب نظام الحكم يعاقَب بعقوبة م29/1 من القانون 31/1970 (م28). "
    "صدر في 27 صفر 1427هـ الموافق 27 مارس 2006م ونُشر في الكويت اليوم ع762 بتاريخ 2/4/2006. "
    "يُلغي القانون 3/1961. ويتّصل به القانون 8/2016 لتنظيم الإعلام الإلكتروني (م18 منه تُحيل إلى محظورات "
    "هذا القانون وعقوباتها)."
)


def build_rows(data):
    rows = []

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": 3,
             "law_year": 2006, "upload_origin": "docx_verified_against_gazette_762_2006"}
        d.update(extra); return d

    pre = PREAMBLE_SUMMARY + "\n\nـــ ديباجة القانون (سند الإصدار) ـــ\n" + (data.get("preamble_text") or "")
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — قانون المطبوعات والنشر (3/2006)", "text": pre,
                 "meta": meta({"chunk": "preamble"})})
    secs = data.get("sections") or {}
    for k in data["order"]:
        num = re.match(r"m(\d+)", k).group(1)
        sec = secs.get(k) or ""
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC,
                     "title": f"المادة {num}{(' — ' + sec) if sec else ''} — قانون المطبوعات والنشر (3/2006)",
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
    print("== تقرير قانون المطبوعات والنشر (3/2006) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    blob = " ".join(r["text"] for r in rows)
    print("محارف بديلة �:", "نعم!" if "�" in blob else "لا", "| ))) :", blob.count(")))"))
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print("فارغة:", empty or "لا")
    ids = [r["id"] for r in rows]; print("مكرّرة:", set(i for i in ids if ids.count(i) > 1) or "لا")
    for r in rows:
        if r["id"].endswith(("preamble", "m2", "m11", "m27")):
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
