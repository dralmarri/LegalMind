#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 61 لسنة 2007 في شأن الإعلام المرئي والمسموع. 21 مادة + ديباجة، الفرع «جزائي».
كان الأصلُ الرقميّ شديدَ التلف فرُفض، ثمّ اسْتُعيد حرفًا بحرف من صور الجريدة الرسمية. معرّفات:
legis-61-2007-m{N}. م11 منه هي المُحال إليها في م18 من القانون 8/2016 لتنظيم الإعلام الإلكتروني."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-61-2007"
BRANCH = "جزائي"
TOPIC = "الإعلام المرئي والمسموع — ترخيص البث والمدير العام والمحظورات والعقوبات والاختصاص"
INSTRUMENT = "القانون رقم 61 لسنة 2007 في شأن الإعلام المرئي والمسموع"

PREAMBLE_SUMMARY = (
    "القانون رقم 61 لسنة 2007 في شأن الإعلام المرئي والمسموع: يعرّف الإعلامَ المرئي والمسموع والبثَّ "
    "وإعادةَ البث والقناةَ والبرامجَ والترددَ وترخيصَ البث والمرخصَ له (م1). ويوجب ترخيصًا من وزارة الإعلام "
    "لممارسة أعمال البث (م2)، ويشترط في طالبه أن يكون شركةً أو مؤسسةً فرديةً كويتية لا يقلّ رأسُ مالها عن "
    "خمسمائة ألف دينار للقناة المرئية ومائتي ألف للمسموعة، وفي الشركاء الجنسيةُ الكويتية وسنُّ الثلاثين "
    "وحسنُ السيرة (م3). ويلزم تعيينُ مدير عام للقناة كويتيٍّ لا يقلّ عمره عن ثلاثين سنة حاصلٍ على شهادة "
    "جامعية وخبرةٍ خمسِ سنوات ومتفرّغٍ (م4). ويصدر الوزير قرارَه خلال تسعين يومًا وإلّا عُدّ الطلبُ مرفوضًا، "
    "ولذوي الشأن الطعنُ في قرار الرفض أمام الدائرة الإدارية وفق المرسوم بقانون 20/1981 وتعديلاته خلال ستين "
    "يومًا (م5). ومدةُ الترخيص عشر سنوات قابلة للتجديد (م5)، وتجب مباشرةُ البث خلال سنتين (م6)، وتُودَع "
    "كفالةٌ ماليةٌ مائةُ ألف دينار خلال ثلاثة أشهر (م7). ويتضمّن الترخيصُ تسعةَ شروطٍ والتزامات، منها "
    "الاحتفاظُ بسجلّ البرامج اثني عشر شهرًا وتسجيلُ البث ثلاثةَ أشهر (م8). ويقع باطلًا إيجارُ الترخيص "
    "ويبطل بيعُه بلا موافقة (م9)، ويُلغى بحكم القانون في خمس حالات (م10). ويحظر على المرخص له بثُّ أربعةَ "
    "عشرَ محظورًا: المساس بالذات الإلهية والملائكة والقرآن والأنبياء والصحابة وأمّهات المؤمنين وآل البيت "
    "(11/1)، والتحريض على قلب نظام الحكم (11/2)، والتعرّض لشخص الأمير بالنقد (11/3)، وتحقير الدستور "
    "(11/4)، وإهانة رجال القضاء والنيابة (11/5)، وخدشَ الآداب (11/6)، وإفشاءَ الأنباء السرية (11/7)، "
    "والتأثيرَ في قيمة العملة (11/8)، وإفشاءَ ما يدور في الاجتماعات الرسمية (11/9)، والمساسَ بكرامة "
    "الأشخاص (11/10)، والدعوةَ أو الحضَّ على كراهية أو ازدراء أيّ فئة من فئات المجتمع (11/11)، والمساسَ "
    "بالحياة الخاصة للموظف (11/12)، والإضرارَ بالعلاقات الكويتية (11/13)، وخروجَ القناة عن غرض الترخيص "
    "(11/14). والعقوبات: البثّ بلا ترخيص حبسٌ لا يجاوز سنةً وغرامة 5000-10000 دينار أو إحداهما مع وجوب "
    "مصادرة المعدّات (م12)؛ ومخالفةُ الحظر في 11/2 يعاقب عليها المديرُ العام ومعدُّ المادة ومقدّمها وكلُّ "
    "مسؤولٍ عن بثّها بعقوبة م29/1 من القانون 31/1970، ومخالفةُ 11/1 بالحبس سنةً وغرامة 5000-20000، وأيُّ "
    "مخالفةٍ أخرى بغرامة 3000-10000، مع جواز إلغاء الترخيص أو وقفه سنةً (م13). ويجوز بقرارٍ مسبَّبٍ من "
    "الوزير حظرُ بثّ أيّ إعلان (م14). وتختصّ النيابةُ العامة دون غيرها (م17)، ودائرةُ الجنايات بالمحكمة "
    "الكلية مع الاستئناف والتمييز استثناءً من م8 من القانون 40/1972 (م18). صدر في 16 رجب 1428هـ الموافق "
    "30 يوليو 2007م. وتُحيل إليه المادةُ 18 من القانون 8/2016 لتنظيم الإعلام الإلكتروني."
)


def build_rows(data):
    rows = []

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": 61,
             "law_year": 2007, "upload_origin": "docx_restored_from_gazette_images"}
        d.update(extra); return d

    pre = PREAMBLE_SUMMARY + "\n\nـــ ديباجة القانون (سند الإصدار) ـــ\n" + (data.get("preamble_text") or "")
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — قانون الإعلام المرئي والمسموع (61/2007)", "text": pre,
                 "meta": meta({"chunk": "preamble"})})
    secs = data.get("sections") or {}
    for k in data["order"]:
        num = re.match(r"m(\d+)", k).group(1)
        sec = secs.get(k) or ""
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC,
                     "title": f"المادة {num}{(' — ' + sec) if sec else ''} — قانون الإعلام المرئي والمسموع (61/2007)",
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
    print("== تقرير قانون الإعلام المرئي والمسموع (61/2007) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    blob = " ".join(r["text"] for r in rows)
    print("محارف بديلة �:", "نعم!" if "�" in blob else "لا", "| شرطات _:", blob.count("_"))
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print("فارغة:", empty or "لا")
    ids = [r["id"] for r in rows]; print("مكرّرة:", set(i for i in ids if ids.count(i) > 1) or "لا")
    for r in rows:
        if r["id"].endswith(("preamble", "m5", "m11", "m13")):
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
