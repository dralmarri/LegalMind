#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 91 لسنة 2013 في شأن مكافحة الاتجار بالأشخاص وتهريب المهاجرين. 14 مادة + ديباجة،
الفرع «جزائي». نصٌّ مستخرَجٌ من DOCX ومُتحقَّقٌ من صور الجريدة الرسمية؛ التلف الحتميّ محدودٌ صُحّح. تُحفَظ
في م13 ملاحظةُ عدم دستورية فقرةٍ (المحكمة الدستورية — الطعن 7/2018). معرّفات: legis-91-2013-m{N} + preamble."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-91-2013"
BRANCH = "جزائي"
TOPIC = "مكافحة الاتجار بالأشخاص وتهريب المهاجرين — الجرائم والعقوبات وحماية المجني عليهم"
INSTRUMENT = "القانون رقم 91 لسنة 2013 في شأن مكافحة الاتجار بالأشخاص وتهريب المهاجرين"

PREAMBLE_SUMMARY = (
    "القانون رقم 91 لسنة 2013 في شأن مكافحة الاتجار بالأشخاص وتهريب المهاجرين: يعرّف الجريمةَ عبر الوطنية "
    "والجماعةَ الإجرامية المنظمة والاتجارَ بالأشخاص (تجنيد/نقل/إيواء/استقبال بالإكراه أو الخداع أو "
    "استغلال السلطة بغرض الاستغلال — الجنسي/السخرة/الاسترقاق/نزع الأعضاء) وتهريبَ المهاجرين والدخولَ غير "
    "المشروع (م1). العقوبات: الاتجار بالأشخاص الحبس 15 سنة، والمؤبد بظروفٍ مشدّدة، والإعدام إذا كان المجني "
    "عليه طفلاً أو أنثى أو من ذوي الاحتياجات الخاصة أو ترتّبت الوفاة (م2)؛ تهريب المهاجرين ≤10 سنوات وغرامة "
    "3-10 آلاف دينار، و≤15 سنة بظروفٍ مشدّدة (م3)؛ الإخفاء (م4)؛ المصادرة الوجوبية للعائدات والوسائل (م5)؛ "
    "مسؤولية الشخص الاعتباري وحلّه (م6)؛ عدم الإبلاغ ≤3 سنوات (م7)؛ الاعتداء على القائمين على التنفيذ ≤15 "
    "سنة والإعدام عند الوفاة (م8)؛ حمل الشهود على شهادة الزور ≤5 سنوات (م9)؛ الإعفاء بالإبلاغ (م10). تختصّ "
    "النيابة العامة وحدها (م11)، وتُقرَّر حمايةُ المجني عليهم بالعلاج ودور الرعاية ومراكز الإيواء (م12)، ولا "
    "يجوز النزول عن العقوبات ولا وقفُ تنفيذها (م13 — قضت المحكمة الدستورية بعدم دستورية جزءٍ من فقرتها "
    "الثانية بشأن الامتناع عن النطق بالعقاب، الطعن 7/2018). عائداتُ الاتجار من الجرائم الأصلية لغسل الأموال "
    "(106/2013). يتّصل بقانون الجزاء 16/1960 والأحداث 3/1983 وإقامة الأجانب 17/1959. صدر سنة 2013."
)


def build_rows(data):
    rows = []

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": 91,
             "law_year": 2013, "upload_origin": "docx_law91_gazette_verified"}
        d.update(extra); return d

    pre = PREAMBLE_SUMMARY + "\n\nـــ ديباجة القانون (سند الإصدار) ـــ\n" + (data.get("preamble_text") or "")
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — قانون مكافحة الاتجار بالأشخاص وتهريب المهاجرين (91/2013)",
                 "text": pre, "meta": meta({"chunk": "preamble"})})
    for k in data["order"]:
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC,
                     "title": f"المادة {k[1:]} — مكافحة الاتجار بالأشخاص وتهريب المهاجرين (91/2013)",
                     "text": data["articles"][k], "meta": meta({"article_number": k[1:]})})
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
    print("== تقرير قانون مكافحة الاتجار بالأشخاص (91/2013) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    blob = " ".join(r["text"] for r in rows)
    print("محارف بديلة �:", "نعم!" if "�" in blob else "لا")
    empty = [r["id"] for r in rows if len(r["text"]) < 10]
    print("فارغة:", empty or "لا")
    ids = [r["id"] for r in rows]; print("مكرّرة:", set(i for i in ids if ids.count(i) > 1) or "لا")
    for r in rows:
        if r["id"].endswith(("preamble", "m2", "m5", "m13")):
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
