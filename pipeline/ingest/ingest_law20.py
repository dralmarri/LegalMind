#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 20 لسنة 2019 بإصدار النظام الموحد لمكافحة الغش التجاري لدول مجلس التعاون الخليجي.
18 مادة (النظام المرافق) + 4 مواد إصدار + ديباجة، الفرع «جزائي» (جريمة الغش التجاري وعقوباتها). النصّ
مستخرَجٌ من DOCX ونُظّف من تلفٍ حتميّ (أقواس معكوسة الاتجاه، تشكيلٌ مضاعف، حروفٌ مكرّرة) وتُحقِّق من صور
الجريدة الرسمية. معرّفات: legis-20-2019-m{N} / -issue-{N} / -preamble."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-20-2019"
BRANCH = "جزائي"
TOPIC = "مكافحة الغش التجاري — النظام الموحد الخليجي (الجرائم والعقوبات والضبط)"
INSTRUMENT = "القانون رقم 20 لسنة 2019 بإصدار النظام الموحد لمكافحة الغش التجاري لدول مجلس التعاون لدول الخليج العربية"

PREAMBLE_SUMMARY = (
    "القانون رقم 20 لسنة 2019 بإصدار النظام (القانون) الموحد لمكافحة الغش التجاري لدول مجلس التعاون "
    "الخليجي: يحظر استيراد/تصدير/إنتاج/عرض/بيع/تخزين/نقل/ترويج/حيازة البضائع المغشوشة أو الفاسدة بقصد "
    "البيع والشروعَ في ذلك (م2)، ويُلزم المزوّد بسحبها وردّ قيمتها (م3/م5) مع افتراض علمه (م4). يمنح "
    "الموظفين صفةَ الضبطية القضائية وسلطاتِ التفتيش والضبط والتحفّظ وسحبِ العينات (م6/م7/م8)، ويجيز إغلاق "
    "المحل بقرار الوزير مع عرضه على المحكمة خلال 10 أيام (م9). العقوبات: الحبس ≤ سنتين وغرامة 5 آلاف–مليون "
    "ريال سعودي (أو ما يعادلها) لمخالفة م3/م4/م6 والبندين أ-ب من م8 (م11)، والحبس ≤ ثلاث سنوات وغرامة 100 "
    "ألف–مليون لاقتران الغش بموازين/أختام/آلات فحص مزيّفة (م12)، مع المصادرة والإتلاف ونشر الحكم والإغلاق "
    "(م13) ومسؤولية المدير الفعلي للشخص الاعتباري بالتضامن (م14) ومضاعفة العقوبة في العَود خلال خمس سنوات "
    "(م15). يحلّ محلّ قانون قمع الغش في المعاملات التجارية 62/2007 (المُلغى). يتّصل بقانون الجزاء 16/1960 "
    "وقانون التجارة 68/1980 والنظام الأساسي لمجلس التعاون 44/1981. صدر سنة 2019."
)


def build_rows(data):
    rows = []

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": 20,
             "law_year": 2019, "upload_origin": "docx_law20_gcc_gazette_verified"}
        d.update(extra); return d

    pre = PREAMBLE_SUMMARY + "\n\nـــ ديباجة القانون (سند الإصدار) ـــ\n" + (data.get("preamble_text") or "")
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — قانون مكافحة الغش التجاري (20/2019)", "text": pre,
                 "meta": meta({"chunk": "preamble"})})
    _ord = {"issue-1": "أولى", "issue-2": "ثانية", "issue-3": "ثالثة", "issue-4": "رابعة", "issue-5": "خامسة"}
    for k, txt in data.get("issuance", {}).items():
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC,
                     "title": f"مادة الإصدار {_ord.get(k, k)} — قانون مكافحة الغش التجاري (20/2019)",
                     "text": txt, "meta": meta({"chunk": "issuance"})})
    for k in data["order"]:
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC,
                     "title": f"المادة {k[1:]} — النظام الموحد لمكافحة الغش التجاري (20/2019)",
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
    print("== تقرير قانون مكافحة الغش التجاري (20/2019) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    blob = " ".join(r["text"] for r in rows)
    print("محارف بديلة �:", "نعم!" if "�" in blob else "لا")
    empty = [r["id"] for r in rows if len(r["text"]) < 10]
    print("فارغة:", empty or "لا")
    ids = [r["id"] for r in rows]; print("مكرّرة:", set(i for i in ids if ids.count(i) > 1) or "لا")
    for r in rows:
        if r["id"].endswith(("preamble", "m2", "m11", "m12")):
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
