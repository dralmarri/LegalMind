#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل المرسوم بقانون رقم 51 لسنة 2026 بتخصيص دوائر جزائية لنظر جرائم أمن الدولة الخارجي والداخلي وجرائم
الأعمال الإرهابية. 7 مواد + ديباجة، الفرع «جزائي» (تنظيمٌ قضائيٌّ جزائيٌّ خاصّ باختصاص نظر جرائم أمن الدولة
والإرهاب). نصٌّ مستخرَجٌ من DOCX ومُصوَّبٌ من تلفٍ حتميّ (أقواسٌ معكوسةٌ حول أرقام + حركاتٌ مضاعفة).
معرّفات: legis-51-2026-m{N}. يتّصل بـ31/1970 (جرائم أمن الدولة) و47/2026 (الإرهاب) و17/1960 (م69 الحبس الاحتياطي)."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-51-2026"
BRANCH = "جزائي"
TOPIC = "الدوائر الجزائية المتخصصة — اختصاص نظر جرائم أمن الدولة والأعمال الإرهابية"
INSTRUMENT = "المرسوم بقانون رقم 51 لسنة 2026 بتخصيص دوائر جزائية لنظر جرائم أمن الدولة الخارجي والداخلي وجرائم الأعمال الإرهابية"

PREAMBLE_SUMMARY = (
    "المرسوم بقانون رقم 51 لسنة 2026 بتخصيص دوائر جزائية لنظر جرائم أمن الدولة الخارجي والداخلي وجرائم "
    "الأعمال الإرهابية: ينشئ قضاءً جزائيًّا متخصّصًا لهذه الجرائم. تُخصَّص دائرةٌ جزائيةٌ (أو أكثر) في "
    "المحكمة الكلية برئاسة مستشارٍ وعضوية اثنين من القضاة الكويتيين، تختصّ دون غيرها بنظر الجنايات والجنح "
    "المتعلقة بجرائم أمن الدولة الخارجي والداخلي وجرائم الأعمال الإرهابية المنصوص عليها في القانون 31/1970 "
    "والمرسوم بقانون 47/2026، ولها سلطاتُ رئيس المحكمة في الحبس الاحتياطي طبقًا للمادة 69 من قانون الإجراءات "
    "17/1960 (م1). وتُخصَّص دائرةٌ جزائيةٌ نظيرةٌ في محكمة الاستئناف (برئاسة وكيل محكمة وعضوية مستشارَين) "
    "تختصّ دون غيرها بالاستئنافات، ويكون حكمها نهائيًّا لا يُطعَن فيه بأيّ طريق (م2). تفصل هذه الدوائر على "
    "وجه السرعة ولا يُقبَل أمامها الادّعاء المدني (م3)، وتُحال إليها الدعاوى المنظورة بحالتها ودون رسوم (م4). "
    "ولا تسري أحكامه على الطعون المنظورة وقت العمل به في الأحكام الصادرة في جرائم م1 (م5). يلغي كلَّ حكمٍ "
    "مخالف (م6) ويُنشَر ويُعمَل به من تاريخ نشره (م7). صدر في 30 مارس 2026. يتّصل بقانون الجزاء 16/1960 "
    "والإجراءات الجزائية 17/1960 وجرائم أمن الدولة 31/1970 وتنظيم القضاء 23/1990 ومكافحة الإرهاب 47/2026."
)


def build_rows(data):
    rows = []

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "مرسوم بقانون", "law_number": 51,
             "law_year": 2026, "upload_origin": "docx_law51_autocleaned"}
        d.update(extra); return d

    pre = PREAMBLE_SUMMARY + "\n\nـــ ديباجة/إصدار المرسوم بقانون ـــ\n" + (data.get("preamble_text") or "") + \
        (("  " + data["issue_tail"]) if data.get("issue_tail") else "")
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — تخصيص دوائر جزائية لجرائم أمن الدولة والإرهاب (51/2026)", "text": pre,
                 "meta": meta({"chunk": "preamble"})})
    for k in data["order"]:
        num = re.match(r"m(\d+)", k).group(1)
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC,
                     "title": f"المادة {num} — تخصيص دوائر جزائية لجرائم أمن الدولة والإرهاب (51/2026)",
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
    print("== تقرير مرسوم تخصيص الدوائر الجزائية (51/2026) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    blob = " ".join(r["text"] for r in rows)
    print("محارف بديلة �:", "نعم!" if "�" in blob else "لا")
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print("فارغة:", empty or "لا")
    ids = [r["id"] for r in rows]; print("مكرّرة:", set(i for i in ids if ids.count(i) > 1) or "لا")
    for r in rows:
        if r["id"].endswith(("preamble", "m1", "m2", "m5")):
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
