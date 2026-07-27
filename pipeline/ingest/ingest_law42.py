#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 42 لسنة 2014 بشأن حماية البيئة. 181 مادة + م143مكرر (=182) + ديباجةٌ غنيّةٌ بالإحالات،
تسعةُ أبوابٍ وبابٌ تمهيديّ. الفرع «إداري» (تنظيمٌ بيئيٌّ تديره الهيئة العامة للبيئة، مع بابِ عقوباتٍ ومسؤوليةٍ
مدنية). النصّ منقولٌ برمجيًّا من DOCX نظيفٍ ومُصوَّبٍ من تلفٍ حتميّ (أقواسٌ معكوسةٌ حول أرقام + تشكيلٌ مضاعف +
علاماتُ «__»/«) ))» دخيلة). معرّفات: legis-42-2014-m{N}. الأقسام (الباب/الفصل/الفرعيّ) محفوظةٌ في subtopic."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-42-2014"
BRANCH = "إداري"
TOPIC = "حماية البيئة — الإدارة البيئية والتنمية وحماية عناصر البيئة والعقوبات والمسؤولية"
INSTRUMENT = "القانون رقم 42 لسنة 2014 بشأن حماية البيئة"

PREAMBLE_SUMMARY = (
    "القانون رقم 42 لسنة 2014 بشأن حماية البيئة: القانون الإطاريّ لحماية البيئة في الكويت (181 مادة + مكرر، "
    "تسعة أبواب). يبدأ بأحكامٍ عامةٍ وتعاريف ونطاقٍ وأهداف (الباب التمهيدي)، وينظّم إدارةَ شؤون البيئة عبر "
    "المجلس الأعلى للبيئة والهيئة العامة للبيئة وصندوق حماية البيئة (م4-م15)، ثم التنميةَ والبيئة وتقييمَ "
    "المردود البيئي (الباب الأول)، وحمايةَ البيئة الأرضية من التلوث وإدارةَ المواد الكيميائية والنفايات "
    "الخطرة والطبية (الباب الثاني)، وحمايةَ الهواء الخارجي (الثالث)، والبيئةَ المائية والساحلية والبحرية "
    "ومياهَ الشرب (الرابع)، والتنوعَ البيولوجي والكائناتِ الفطرية المهددة والمحمياتِ الطبيعية وجونَ الكويت "
    "(الخامس)، والإدارةَ البيئية والاستراتيجياتِ وشرطةَ البيئة والأزماتِ والكوارثِ والإعلامَ والتوعية "
    "(السادس)، ثم العقوباتِ (الباب السابع، م128 فما بعد — غراماتٌ تصاعديةٌ وعقوباتٌ عن مخالفات التلوث "
    "والنفايات والصيد والإضرار بالبيئة)، والمسؤوليةَ المدنية والتعويضَ عن الأضرار البيئية (الثامن)، "
    "وأحكامًا ختامية (التاسع). صدر مستنِدًا إلى الدستور وقانون الجزاء 16/1960 والإجراءات 17/1960 وقوانينَ "
    "بيئيةٍ وإداريةٍ عديدة (منها 21/1995 المُنشِئ للهيئة، و28/1969 و15/1979 و6/2010). صدر سنة 2014."
)


def build_rows(data):
    rows = []
    secs = data.get("sections", {})

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": 42,
             "law_year": 2014, "upload_origin": "docx_law42_autocleaned"}
        d.update(extra); return d

    pre = PREAMBLE_SUMMARY + "\n\nـــ ديباجة القانون (سند الإصدار) ـــ\n" + (data.get("preamble_text") or "")
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة", "sub": None,
                 "title": "ديباجة — قانون حماية البيئة (42/2014)", "text": pre,
                 "meta": meta({"chunk": "preamble"})})
    for k in data["order"]:
        mm = re.match(r"m(\d+)(-mukarrar)?", k)
        label = mm.group(1) + (" مكرر" if mm.group(2) else "")
        sec = secs.get(k, "") or None
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC, "sub": sec,
                     "title": f"المادة {label} — قانون حماية البيئة (42/2014)"
                              + (f" [{sec}]" if sec else ""),
                     "text": data["articles"][k], "meta": meta({"article_number": label, "section": sec or ""})})
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
    print("== تقرير قانون حماية البيئة (42/2014) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    blob = " ".join(r["text"] for r in rows)
    print("محارف بديلة �:", "نعم!" if "�" in blob else "لا", "| شرطات _:", blob.count("_"))
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print("فارغة:", empty or "لا")
    ids = [r["id"] for r in rows]; print("مكرّرة:", set(i for i in ids if ids.count(i) > 1) or "لا")
    print("مواد بأقسام:", sum(1 for r in rows if r["sub"]), "| أقسام فريدة:", len(set(r["sub"] for r in rows if r["sub"])))
    for r in rows:
        if r["id"].endswith(("preamble", "m1", "m143", "m158")):
            print(f"\n--- {r['id']} (قسم={r['sub']}) ---\n{r['text'][:130]}")
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
                   VALUES (%s,'legislation_article',%s,%s,%s,NULL,%s,%s,%s,NULL,
                           'source_verified','source_authority',TRUE,%s)
                   ON CONFLICT (id) DO UPDATE SET
                    branch=EXCLUDED.branch,topic=EXCLUDED.topic,subtopic=EXCLUDED.subtopic,title=EXCLUDED.title,
                    original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                    verification_status='source_verified',usable_as_citation=TRUE,
                    metadata=EXCLUDED.metadata,updated_at=now()""",
                (r["id"], BRANCH, r["topic"], r["sub"], r["title"], r["text"],
                 normalize_text(r["text"]), Jsonb(r["meta"])))
            ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل reindex.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
