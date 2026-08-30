#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 88 لسنة 1995 في شأن محاكمة الوزراء. 16 مادة + ديباجة، الفرع «جزائي» (اختصاصٌ جزائيٌّ
خاصٌّ بجرائم الوزراء وإجراءات محاكمتهم). نصٌّ مستخرَجٌ من DOCX ونُظّف من تلفٍ حتميّ (6 محارف � + تشوّه
ترتيب «ُيُ» + مسافاتٌ دخيلة) بإحلالٍ مستهدَفٍ لعباراتٍ قانونيةٍ ثابتة. م14 «ملغاة». معرّفات: legis-88-1995-m{N}."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-88-1995"
BRANCH = "جزائي"
TOPIC = "محاكمة الوزراء — الجرائم واختصاص التحقيق والمحكمة والإجراءات"
INSTRUMENT = "القانون رقم 88 لسنة 1995 في شأن محاكمة الوزراء"

PREAMBLE_SUMMARY = (
    "القانون رقم 88 لسنة 1995 في شأن محاكمة الوزراء: ينظّم مساءلةَ الوزراء جزائيًّا عن الجرائم التي تقع "
    "منهم في تأدية أعمال وظائفهم ومحاكمتَهم. يسري على كل وزيرٍ عضوٍ في مجلس الوزراء ولو ترك منصبه بعد وقوع "
    "الجريمة (م1). يعدّد الجرائم: أمن الدولة الخارجي والداخلي، وجرائم الموظفين والمكلّفين بخدمة عامة "
    "(المشار إليها في قانون الجزاء ومرسوم 31/1970)، وجرائم الأموال العامة والفساد (م2). ينشئ لجنةَ تحقيقٍ "
    "من ثلاثة مستشارين بمحكمة الاستئناف تختص دون غيرها بفحص البلاغات والتحقيق ولها اختصاصات سلطات التحقيق "
    "(م3-م4)، مع إجازةٍ حتميةٍ للوزير بمرتبٍ كامل عند الاتهام (م5)، وإجراءات الاتهام والإعلان (م6-م7). "
    "يشكّل محكمةً خاصةً لمحاكمة الوزراء، أحكامُها لا تُطعَن إلا بالتمييز (والمعارضة في الغيابي) (م8-م12)، "
    "مع إحالة الدعاوى المنظورة إليها (م13). (م14 ملغاة.) يتّصل بقانون الجزاء 16/1960 والإجراءات الجزائية "
    "17/1960 وجرائم الوظيفة العامة 31/1970 وهيئة مكافحة الفساد 2/2016 وغسل الأموال 106/2013. صدر سنة 1995."
)


def build_rows(data):
    rows = []

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": 88,
             "law_year": 1995, "upload_origin": "docx_law88_autocleaned"}
        d.update(extra); return d

    pre = PREAMBLE_SUMMARY + "\n\nـــ ديباجة القانون (سند الإصدار) ـــ\n" + (data.get("preamble_text") or "")
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — قانون محاكمة الوزراء (88/1995)", "text": pre,
                 "meta": meta({"chunk": "preamble"})})
    for k in data["order"]:
        body = data["articles"][k]
        mm = re.match(r"m(\d+)(-mukarrar)?", k)
        label = mm.group(1) + (" مكرر" if mm.group(2) else "")
        extra = {"article_number": label}
        if body.strip() == "ملغاة":
            extra["status"] = "ملغاة"
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC,
                     "title": f"المادة {label} — قانون محاكمة الوزراء (88/1995)",
                     "text": body, "meta": meta(extra)})
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
    print("== تقرير قانون محاكمة الوزراء (88/1995) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    blob = " ".join(r["text"] for r in rows)
    print("محارف بديلة �:", "نعم!" if "�" in blob else "لا")
    print("ملغاة:", [r["id"] for r in rows if r["text"].strip() == "ملغاة"])
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print("فارغة:", empty or "لا")
    ids = [r["id"] for r in rows]; print("مكرّرة:", set(i for i in ids if ids.count(i) > 1) or "لا")
    for r in rows:
        if r["id"].endswith(("preamble", "m2", "m3", "m11")):
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
