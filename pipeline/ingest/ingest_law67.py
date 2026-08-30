#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل المرسوم بالقانون رقم 67 لسنة 1976 في شأن المرور. 59 مادة (م1-م50 + 9 مكرّرات) + ديباجة، ستّة
أبواب، الفرع «جزائي» (قانونٌ تنظيميٌّ ذو عقوباتٍ جزائيةٍ ومحكمةِ مرور). نصٌّ منقولٌ حرفًا بحرف من صور الجريدة
الرسمية النظيفة (لا من ملفّ الـOCR المتلف)، والتصويبُ الوحيد عكسُ خانتَي أرقام المواد المُحال إليها في م41/م42
(مؤكَّدٌ من النسخة الواضحة). حواشي التعديل (أغلبها المرسوم بقانون 5/2025) محفوظةٌ في الميتاداتا. معرّفات: legis-67-1976-m{N}."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-67-1976"
BRANCH = "جزائي"
TOPIC = "قانون المرور — الترخيص ورخص القيادة وقواعد المرور والعقوبات"
INSTRUMENT = "المرسوم بالقانون رقم 67 لسنة 1976 في شأن المرور"

PREAMBLE_SUMMARY = (
    "المرسوم بالقانون رقم 67 لسنة 1976 في شأن المرور: الإطار العامّ لتنظيم المرور في الكويت. يقع في ستّة "
    "أبواب: (الأول) أحكامٌ عامةٌ وتعاريف (المركبة، السيارة، الطريق، السائق، المشاة…) وأنواع المركبات "
    "(م1-م3)؛ (الثاني) ترخيص تسيير المركبات الآلية — وجوب الترخيص وتخصيص رقم، وطلب الترخيص والتأمين "
    "الإلزامي من المسئولية المدنية واللوحات ونقل الملكية والوفاة (م4-م14)؛ (الثالث) رخص القيادة — رخصة "
    "السوق واختبار القيادة ومدارس التعليم والتصاريح (م15-م24)؛ (الرابع) قواعد المرور وآدابه — قيادة "
    "آمنة والتزام الإشارات والوقوف والحوادث ومسؤولية المالك (م25-م32)؛ (الخامس) العقوبات — جداولٌ "
    "متدرّجةٌ للمخالفات (م33 حبسٌ حتى 3 أشهر/غرامة، م33مكرر حتى 3 سنوات للتهور وتجاوز الإشارة والسرعة، "
    "م34-م37 غراماتٌ متدرّجة، م36مكرر تصوير/نشر الجريمة، م37مكرر مسؤولية الشخص الاعتباري، م38 القيادة "
    "تحت تأثير المسكر/المخدر، م39/م39مكرر سحب الرخصة والعقوبات البديلة، م40 العَود، م41 الصلح، م42/م42مكرر "
    "السحب الإداري ونظام النقاط، م44 حالات القبض)؛ (السادس) أحكامٌ عامة — حجز المركبات والإشراف والمجلس "
    "الأعلى للمرور وحجية المحاضر وإلغاء مرسوم السير 13/1959 (م43-م50). عُدّل جوهريًّا بالمرسوم بقانون 5/2025 "
    "(وبالقانون 52/2001 والمرسوم بقانون 57/1980). صدر في 23 سبتمبر 1976 ويختصّ بتنفيذه وزير الداخلية."
)


def build_rows(data):
    rows = []
    secs = data.get("sections", {})
    notes = data.get("amend_notes", {})

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "مرسوم بقانون", "law_number": 67,
             "law_year": 1976, "upload_origin": "gazette_images_manual_transcription"}
        d.update(extra); return d

    pre = PREAMBLE_SUMMARY + "\n\nـــ إصدار المرسوم بقانون ـــ\n" + (data.get("preamble_text") or "") + \
        (("  " + data["issue_tail"]) if data.get("issue_tail") else "")
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — قانون المرور (67/1976)", "text": pre,
                 "meta": meta({"chunk": "preamble"})})
    for k in data["order"]:
        mm = re.match(r"m(\d+)(-mukarrar)?", k)
        label = mm.group(1) + (" مكرر" if mm.group(2) else "")
        extra = {"article_number": label, "section": secs.get(k, "")}
        if k in notes:
            extra["amend_note"] = notes[k]
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC,
                     "title": f"المادة {label} — قانون المرور (67/1976)",
                     "text": data["articles"][k], "meta": meta(extra)})
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
    print("== تقرير قانون المرور (67/1976) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    blob = " ".join(r["text"] for r in rows)
    print("محارف بديلة �:", "نعم!" if "�" in blob else "لا", "| شرطات _:", blob.count("_"))
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print("فارغة:", empty or "لا")
    ids = [r["id"] for r in rows]; print("مكرّرة:", set(i for i in ids if ids.count(i) > 1) or "لا")
    print("عدد المواد (عدا الديباجة):", len(rows) - 1, "| مكرّرات:",
          [r["meta"]["article_number"] for r in rows if "مكرر" in r["meta"].get("article_number", "")])
    for r in rows:
        if r["id"].endswith(("preamble", "m2", "m33", "m38", "m41")):
            print(f"\n--- {r['id']} (قسم={r['meta'].get('section','-')[:30]}) ---\n{r['text'][:140]}")
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
                (r["id"], BRANCH, r["topic"], r["meta"].get("section") or None, r["title"], r["text"],
                 normalize_text(r["text"]), Jsonb(r["meta"])))
            ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل reindex.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
