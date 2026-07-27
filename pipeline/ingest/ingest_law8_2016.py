#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 8 لسنة 2016 بتنظيم الإعلام الإلكتروني. 27 مادة + ديباجة، الفرع «جزائي» (اختصاصٌ جزائيّ:
النيابة العامة م21، دائرة الجنايات م22، الحجب والعقوبات م19). نصٌّ منقولٌ حرفًا بحرف من صور الجريدة الرسمية.
معرّفات: legis-8-2016-m{N}. يتّصل بالمطبوعات 3/2006 والإعلام المرئي 61/2007 (م18 يُحيل محظوراتِهما وعقوباتِهما)."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-8-2016"
BRANCH = "جزائي"
TOPIC = "تنظيم الإعلام الإلكتروني — الترخيص والمدير المسؤول والحجب والعقوبات والاختصاص الجزائي"
INSTRUMENT = "القانون رقم 8 لسنة 2016 بتنظيم الإعلام الإلكتروني"

PREAMBLE_SUMMARY = (
    "القانون رقم 8 لسنة 2016 بتنظيم الإعلام الإلكتروني: ينظّم المواقعَ والوسائلَ الإعلامية الإلكترونية "
    "(دور النشر والصحافة ووكالات الأنباء والخدمات الإخبارية والإعلانية التجارية ومواقع الصحف والقنوات) "
    "ويستثني الحساب الشخصي غير المهنيّ (م1-م5). يوجب الترخيصَ من وزارة الإعلام لمدة عشر سنوات (م6)، ويكتفي "
    "بالإخطار لجهات الدولة والنفع العام (م7)، ويحدّد شروطَ طالب الترخيص والمدير المسؤول والكفالة المالية "
    "(500 دينار) وأحوالَ إلغاء الترخيص ونقله (م8-م16). يُلزم المديرَ المسؤولَ بتحرّي الدقة ونشر الرد والتصحيح "
    "والتكذيب مجانًا (م17). يحظر نشرَ المحظورات المبيّنة في قانون المطبوعات والنشر 3/2006 (م19/20/21) وقانون "
    "الإعلام المرئي والمسموع 61/2007 (م11) وتوقَّع عقوباتُهما (م18). ويعاقب بغرامة 500-5000 دينار مع جواز "
    "الحجب النهائي من يمارس نشاطًا بلا ترخيص أو يخالف القانون، ولرئيس دائرة الجنايات الحجبُ المؤقت أثناء "
    "التحقيق/المحاكمة (م19). تختصّ النيابةُ العامة دون غيرها بالتحقيق والادعاء (م21)، ودائرةُ الجنايات "
    "بالمحكمة الكلية بالمحاكمة مع الطعن بالتمييز (م22)، وتسقط الدعوى الجزائية بعدم الإبلاغ خلال ثلاثة أشهر "
    "ودعوى التعويض خلال سنة (م23). صدر مستنِدًا إلى الجزاء 16/1960 والإجراءات 17/1960 والمعاملات الإلكترونية "
    "20/2014 وهيئة الاتصالات 37/2014 وجرائم تقنية المعلومات 63/2015 والوحدة الوطنية 19/2012 وغيرها. صدر 2016."
)


def build_rows(data):
    rows = []

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": 8,
             "law_year": 2016, "upload_origin": "gazette_images_manual_transcription"}
        d.update(extra); return d

    pre = PREAMBLE_SUMMARY + "\n\nـــ ديباجة القانون (سند الإصدار) ـــ\n" + (data.get("preamble_text") or "") + \
        (("  " + data["issue_tail"]) if data.get("issue_tail") else "")
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — قانون تنظيم الإعلام الإلكتروني (8/2016)", "text": pre,
                 "meta": meta({"chunk": "preamble"})})
    for k in data["order"]:
        num = re.match(r"m(\d+)", k).group(1)
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC,
                     "title": f"المادة {num} — قانون تنظيم الإعلام الإلكتروني (8/2016)",
                     "text": data["articles"][k], "meta": meta({"article_number": num})})
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
    print("== تقرير قانون تنظيم الإعلام الإلكتروني (8/2016) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    blob = " ".join(r["text"] for r in rows)
    print("محارف بديلة �:", "نعم!" if "�" in blob else "لا", "| شرطات _:", blob.count("_"))
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print("فارغة:", empty or "لا")
    ids = [r["id"] for r in rows]; print("مكرّرة:", set(i for i in ids if ids.count(i) > 1) or "لا")
    for r in rows:
        if r["id"].endswith(("preamble", "m1", "m18", "m19")):
            print(f"\n--- {r['id']} ---\n{r['text'][:140]}")
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
