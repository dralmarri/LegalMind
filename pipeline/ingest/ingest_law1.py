#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 1 لسنة 1993 بشأن حماية الأموال العامة. 32 مادة + م21 مكرر + ديباجة، الفرع
«جزائي» (جرائم المال العام: الاختلاس، الاستيلاء، الإضرار بالمصلحة، الربح غير المشروع من المقاولات،
إفشاء الأسرار، الإضرار الجسيم بالإهمال، عدم سقوط الدعوى بالتقادم، الإجراءات التحفظية، رقابة ديوان
المحاسبة). النصّ منسوخ من الصور الرسمية النظيفة التي أرسلها المستخدم (بديلًا عن DOCX مصاب بأخطاء
استخراج)؛ تصويبان محرَّران مؤكَّدان بصورٍ أوضح: م14 «إهمال»، م20 «بادر…قبل». معرّفات:
legis-1-1993-m{N}[-mukarrar] + preamble."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-1-1993"
LAW_NO, LAW_YEAR = 1, 1993
LAW_TAG = "قانون حماية الأموال العامة (1/1993)"
BRANCH = "جزائي"
INSTRUMENT = "القانون رقم 1 لسنة 1993 بشأن حماية الأموال العامة"
TOPIC = "حماية المال العام — الجرائم والعقوبات والإجراءات التحفظية"

PREAMBLE = (
    "القانون رقم 1 لسنة 1993 بشأن حماية الأموال العامة\n"
    "يجرّم الاعتداء على المال العام ويشدّد عقوباته: يعرّف «الأموال العامة» (أموال الدولة والهيئات "
    "والمؤسسات العامة والشركات التي تساهم فيها بنسبة لا تقل عن 25%)، ويعدّ في حكم الموظف العام أشخاص "
    "م43 من القانون 31/1970، ويسري على الجرائم المرتكبة خارج الكويت. يقرّر جرائم: الاختلاس (م9)، "
    "الاستيلاء بغير حق (م10)، الإضرار العمدي بمصلحة الجهة في الصفقات (م11)، الربح غير المشروع من "
    "المقاولات والتوريدات (م12)، إفشاء أسرار العمل (م13)، الإضرار الجسيم بالإهمال/التفريط (م14)، "
    "الاحتفاظ بالوثائق (م15)، مع العزل والرد وغرامة تعادل ضعف القيمة (م16). ومن أخصّ أحكامه: عدم "
    "انقضاء الدعوى الجزائية بالتقادم (م21 مكرر)، ورد الأموال والتعويض رغم انقضاء الدعوى (م22)، "
    "والإجراءات التحفظية (منع السفر والتصرف والتحفظ على الأموال داخل البلاد وخارجها — م24-م28). يُخضِع "
    "النيابةَ العامة وديوان المحاسبة لرقابة الأموال العامة والاستثمارات، ويلغي ما يعارضه من 31/1970. "
    "صدر في 7 فبراير 1993.\n"
    "الديباجة: بعد الاطلاع على الدستور، وقانون الجزاء 16/1960، وقانون الإجراءات والمحاكمات الجزائية "
    "17/1960، واللائحة الداخلية لمجلس الأمة 12/1963، وقانون ديوان المحاسبة 30/1964 المعدَّل بالمرسوم "
    "بقانون 4/1977، والقانون 31/1970، والخدمة المدنية 15/1979، وقانون المرافعات 38/1980، والقانون "
    "المدني 67/1980، وقانون الهيئة العامة للاستثمار 47/1982، وافق مجلس الأمة على القانون، وقد صدّقنا "
    "عليه وأصدرناه."
)


def _label(key):
    if key.startswith("iss"):
        return f"مادة {key[3:]} (إصدار)"
    m = re.match(r'm(\d+)(-mukarrar)?', key)
    return f"مادة {m.group(1)}" + (" مكرر" if m.group(2) else "")


def build_rows(data):
    arts = data["articles"]
    order = data.get("order") or list(arts.keys())
    rows = []

    def meta(extra=None):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": LAW_NO,
             "law_year": LAW_YEAR, "upload_origin": "image_law1_1993_transcription"}
        if extra:
            d.update(extra)
        return d

    rows.append({
        "id": f"{LAW_ID}-preamble", "object_type": "legislation_article",
        "branch": BRANCH, "topic": "الديباجة", "subtopic": None, "micro_issue": None,
        "title": f"ديباجة — {LAW_TAG}", "text": PREAMBLE, "meta": meta({"chunk": "preamble"})})

    for key in order:
        a = arts[key]
        body = (a["text"] if isinstance(a, dict) else a).strip()
        is_iss = key.startswith("iss")
        extra = {}
        if is_iss:
            extra["issuing"] = True
        else:
            mm = re.match(r'm(\d+)(-mukarrar)?', key)
            extra["article_number"] = mm.group(1) + (" مكرر" if mm.group(2) else "")
        if isinstance(a, dict) and a.get("sec"):
            extra["fasl_raw"] = a["sec"]
        rows.append({
            "id": f"{LAW_ID}-{key}", "object_type": "legislation_article", "branch": BRANCH,
            "topic": "مواد الإصدار" if is_iss else TOPIC, "subtopic": None, "micro_issue": None,
            "title": f"{_label(key)} — {LAW_TAG}", "text": body, "meta": meta(extra)})
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
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    data = json.load(open(args.json, encoding="utf-8"))
    rows = build_rows(data)

    print("== تقرير قانون حماية الأموال العامة (1/1993) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print(f"فارغة: {empty or 'لا'}")
    ids = [r["id"] for r in rows]
    print(f"مكرّرة: {set(i for i in ids if ids.count(i) > 1) or 'لا'}")
    resid = [r["id"] for r in rows if "�" in r["text"]]
    print(f"محارف بديلة �: {resid or 'لا'}")
    if data.get("editorial_notes"):
        print(f"تصويبات محرَّرة موثَّقة: {list(data['editorial_notes'].keys())}")
    for r in rows:
        if r["id"].endswith(("preamble", "-m9", "-m14", "-m16", "-m21-mukarrar", "-m32")):
            print(f"\n--- {r['id']} ({r['title']}) ---\n{r['text'][:170]}")

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
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,'source_verified','source_authority',TRUE,%s)
                   ON CONFLICT (id) DO UPDATE SET
                    object_type=EXCLUDED.object_type,branch=EXCLUDED.branch,topic=EXCLUDED.topic,
                    subtopic=EXCLUDED.subtopic,micro_issue=EXCLUDED.micro_issue,title=EXCLUDED.title,
                    original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                    verification_status='source_verified',usable_as_citation=TRUE,
                    metadata=EXCLUDED.metadata,updated_at=now()""",
                (r["id"], r["object_type"], r["branch"], r["topic"], r["subtopic"], r["micro_issue"],
                 r["title"], r["text"], normalize_text(r["text"]), Jsonb(r["meta"])))
            ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل reindex.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
