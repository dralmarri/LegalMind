#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 35 لسنة 1985 بشأن جرائم المفرقعات. 11 مادة + ديباجة (العنوان)، الفرع «جزائي».
نصٌّ مستخرَجٌ من DOCX ومُصوَّبٌ من 5 أخطاء OCR حتميّة (حرفٌ ساقطٌ/مضاعَف). معرّفات: legis-35-1985-m{N}.
جرائمُ إرهابيّةُ الطابع (م1: إشاعة الذعر/تخريب المرافق ⇒ الإعدام/المؤبد) تختصّ بها محكمةُ أمن الدولة (م9)."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-35-1985"
BRANCH = "جزائي"
TOPIC = "جرائم المفرقعات — الاستعمال والإحراز والتدريب والعقوبات والاختصاص"
INSTRUMENT = "القانون رقم 35 لسنة 1985 بشأن جرائم المفرقعات"

PREAMBLE_SUMMARY = (
    "القانون رقم 35 لسنة 1985 بشأن جرائم المفرقعات: يجرّم استعمال المفرقعات (المتفجّرات) والشروع فيه "
    "وإحرازها وحيازتها وصنعها وجلبها والاتّجار فيها والتدريب عليها، ويغلّظ عقوباتها. يعاقب بالإعدام أو "
    "الحبس المؤبّد من استعمل مفرقعات بقصد القتل أو إشاعة الذعر أو تخريب المباني والمرافق العامة ودور "
    "العبادة والأماكن المأهولة، وتكون العقوبة الإعدام إن نتج عنها موتٌ (م1). ويعاقب بالحبس المؤقّت "
    "(تتدرّج مدّته من ثلاث إلى عشر سنوات فالمؤبّد بحسب الضرر والإصابة والوفاة) من عرّض بالمفرقعات حياة "
    "الناس أو أموالهم للخطر (م2). ويجرّم الإحراز والصنع والاتّجار بغير ترخيص من وزير الداخلية، ويعرّف "
    "المفرقعات (القنابل والديناميت والبارود) ويأمر بمصادرتها (م3)، والتدريب على صنعها لغرضٍ غير مشروع "
    "(م4)، وعدمَ الإبلاغ وإخفاءَ الجناة والأدلّة (م5)، ومخالفةَ شروط الترخيص (م6). ويقرّر إعفاء المبادِر "
    "بالإبلاغ (م7)، ويمنع النزول بعقوبة الإعدام/المؤبّد ووقفَ التنفيذ استثناءً من م83 جزاء (م8)، ويعقد "
    "الاختصاص لمحكمة أمن الدولة (م9)، ويلغي م32 من مرسوم 31/1970 (م10). يتّصل بقانون الجزاء 16/1960 "
    "وقانون أمن الدولة/31/1970 وقانون مكافحة الإرهاب 47/2026 (المفرقعات وسيلةٌ إرهابيّة). صدر سنة 1985."
)


def build_rows(data):
    rows = []

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": 35,
             "law_year": 1985, "upload_origin": "docx_law35_autocleaned"}
        d.update(extra); return d

    pre = PREAMBLE_SUMMARY + "\n\nـــ ديباجة/إصدار القانون ـــ\n" + (data.get("preamble_text") or "") + \
        (("  " + data["issue_tail"]) if data.get("issue_tail") else "")
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — قانون جرائم المفرقعات (35/1985)", "text": pre,
                 "meta": meta({"chunk": "preamble"})})
    for k in data["order"]:
        body = data["articles"][k]
        num = re.match(r"m(\d+)", k).group(1)
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC,
                     "title": f"المادة {num} — قانون جرائم المفرقعات (35/1985)",
                     "text": body, "meta": meta({"article_number": num})})
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
    print("== تقرير قانون جرائم المفرقعات (35/1985) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    blob = " ".join(r["text"] for r in rows)
    print("محارف بديلة �:", "نعم!" if "�" in blob else "لا")
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print("فارغة:", empty or "لا")
    ids = [r["id"] for r in rows]; print("مكرّرة:", set(i for i in ids if ids.count(i) > 1) or "لا")
    for r in rows:
        if r["id"].endswith(("preamble", "m1", "m3", "m9")):
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
