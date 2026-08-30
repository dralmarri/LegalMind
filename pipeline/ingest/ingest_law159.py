#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل المرسوم بقانون رقم 159 لسنة 2025 في شأن مكافحة المخدرات والمؤثرات العقلية وتنظيم استعمالها
والإتجار فيها. 84 مادة + ديباجة، الفرع «جزائي». النصّ منسوخ من الصور الرسمية النظيفة + الجريدة الرسمية
(الكويت اليوم ع1767، 30/11/2025) بديلًا عن DOCX مصاب. يُلغي 74/1983 و48/1987. الجداول المرفقة (قوائم
المواد) غير مُدرَجة هنا (نصّ المواد فقط). معرّفات: legis-159-2025-m{N} + iss1 + preamble."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-159-2025"
LAW_NO, LAW_YEAR = 159, 2025
LAW_TAG = "قانون مكافحة المخدرات (159/2025)"
BRANCH = "جزائي"
INSTRUMENT = "المرسوم بقانون رقم 159 لسنة 2025 في شأن مكافحة المخدرات والمؤثرات العقلية وتنظيم استعمالها والإتجار فيها"
TOPIC = "المخدرات والمؤثرات العقلية — الجرائم والعقوبات والعلاج"

PREAMBLE = (
    "المرسوم بقانون رقم 159 لسنة 2025 في شأن مكافحة المخدرات والمؤثرات العقلية وتنظيم استعمالها والإتجار فيها\n"
    "التشريع الجزائيّ الحاكم للمخدرات في الكويت (يلغي 74/1983 و48/1987). يعرّف المواد المخدرة والمؤثرات "
    "العقلية والسلائف الكيميائية والجلب والتهريب والترويج والحيازة والتعاطي والإدمان (م1)، وينشئ المجلس "
    "الأعلى لمكافحة المخدرات ومراكز التأهيل وعلاج الإدمان (م2-م4). ينظّم تراخيص الاستيراد/التصدير/النقل "
    "والاتجار والحيازة الطبية والوصفات والإنتاج والزراعة (م5-م41). فصل العقوبات (م42-م60): الإعدام أو "
    "المؤبد للجلب/التهريب/الإنتاج/الصنع/الزراعة بقصد الاتجار (م42) وللحيازة/الشراء/البيع/الترويج/المقايضة "
    "بقصد الاتجار (م43)، والإعدام وجوبًا عند ظرف مشدد كالعود واستغلال حدث والمكان المحظور (م44)، والإعدام "
    "للتنظيم العصابي (م45)؛ والحبس المتدرّج للحيازة المجردة (م48) والتعاطي/الاستعمال الشخصي (م49) وإدارة "
    "مكان التعاطي (م50) والدسّ (م47) والحمل بالإكراه (م46) والطبيب المخالف (م53) والشخص الاعتباري (م57). "
    "بدائل العلاج والإيداع للمدمن/المتعاطي (م59، م61-م64) بتقدّمه طوعًا أو ببلاغ القريب أو بقرار النيابة/"
    "المحكمة. المصادرة الوجوبية (م69)، وعدم انقضاء الدعوى بالتقادم في جرائم م46/م47 (م74)، واختصاص النيابة "
    "العامة ومحكمة الجنايات (م75)، والضبطية القضائية (م79). صدر في 24 نوفمبر 2025 ونُشر في 30 نوفمبر 2025 "
    "ويُعمل به بعد أسبوعين."
)


def _label(key):
    if key.startswith("iss"):
        return "الديباجة" if key == "iss1" else f"مادة {key[3:]} (إصدار)"
    m = re.match(r'm(\d+)(-mukarrar)?', key)
    return f"مادة {m.group(1)}" + (" مكرر" if m.group(2) else "")


def build_rows(data):
    arts = data["articles"]
    order = data.get("order") or list(arts.keys())
    rows = []

    def meta(extra=None):
        d = {"instrument": INSTRUMENT, "instrument_rank": "مرسوم بقانون", "law_number": LAW_NO,
             "law_year": LAW_YEAR, "upload_origin": "image_gazette_law159_transcription",
             "repeals": "legis-74-1983;legis-48-1987", "schedules_included": False}
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

    print("== تقرير قانون مكافحة المخدرات (159/2025) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print(f"فارغة: {empty or 'لا'}")
    ids = [r["id"] for r in rows]
    print(f"مكرّرة: {set(i for i in ids if ids.count(i) > 1) or 'لا'}")
    resid = [r["id"] for r in rows if "�" in r["text"]]
    print(f"محارف بديلة �: {resid or 'لا'}")
    for r in rows:
        if r["id"].endswith(("preamble", "-m1", "-m42", "-m49", "-m74", "-m84")):
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
