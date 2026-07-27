#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل المرسوم بقانون رقم 47 لسنة 2026 في شأن مكافحة جرائم الإرهاب. 31 مادة + ديباجة، الفرع «جزائي».
النصّ مستخرَجٌ من DOCX فقرةً-فقرةً (ترويسة «مادة N»)، والتلف الوحيد حتميّ (أقواس معكوسة/تشكيل مضاعف)
صُوّب آليًّا؛ وصُحّح «تحديد⇒تهديد» في تعريف م1 بتأكيد المستخدم (حائز المصدر). معرّفات: legis-47-2026-m{N}
+ preamble. الديباجة = ملخّصٌ دلاليّ + سند الإصدار الحقيقيّ (يغذّي رسم علاقات الديباجات: 106/2013، 13/1991،
1/1993، 111/2015، 2/2016، 16/1960، 17/1960…)."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-47-2026"
LAW_NO, LAW_YEAR = 47, 2026
LAW_TAG = "المرسوم بقانون بمكافحة جرائم الإرهاب (47/2026)"
BRANCH = "جزائي"
INSTRUMENT = "المرسوم بقانون رقم 47 لسنة 2026 في شأن مكافحة جرائم الإرهاب"
TOPIC = "جرائم الإرهاب — الأعمال الإرهابية والتنظيمات والخطورة الإرهابية والتدابير الوقائية والعقوبات"

PREAMBLE = (
    "المرسوم بقانون رقم 47 لسنة 2026 في شأن مكافحة جرائم الإرهاب\n"
    "يعرّف العملَ الإرهابي (كل فعل أو تهديد يؤدي إلى وفاة/احتجاز/إيذاء أو الإضرار بالثروات والمرافق أو "
    "الأمن السيبراني، تنفيذًا لمشروع إجراميّ يهدف لبثّ الرعب أو إجبار سلطة/منظمة — م1)، والتنظيمَ الإرهابيّ "
    "والإرهابيّ والخطورةَ الإرهابية والتدابيرَ الوقائية والتسليمَ المراقب. يسري على الجرائم داخل الدولة "
    "وخارجها متى شكّلت عملًا إرهابيًّا (م2-م3)، والشروعُ كالجريمة التامة (م4)، ويعاقب على عدم الإبلاغ/إيواء "
    "الجاني (م5) مع إعفاءٍ للمبادر بالإبلاغ (م6). يستبدل بعقوبات قانون الجزاء عقوباتٍ مشدَّدة متى كانت "
    "الجريمة عملًا إرهابيًّا (الإعدام بدل المؤبد… — م7). يجرّم الاعتداء على وسائل النقل والمنشآت (م9) "
    "والبعثات الدبلوماسية (م10)، والتدريب على السلاح (م11)، وإنشاء/إدارة تنظيم إرهابي (م12)، والدعوة "
    "للانضمام والانضمام (م13)، والتخابر مع تنظيم إرهابي (م14)، والإكراه على الانضمام (م15)، ودخول الدولة "
    "لارتكاب إرهاب (م16). ينشئ مركزَ إعادة التأهيل (م17) وينظّم حالةَ الخطورة الإرهابية وإجراءاتها أمام "
    "محكمة الجنايات والتدابيرَ الوقائية (مراقبة الشرطة/حظر الارتياد/منع الاتصال — م18-م22)، ولا يعدّ الخاضع "
    "لها مجرمًا (م20)، ويستثني دون الثامنة عشرة (م23). ينشئ اللجنةَ الوطنية لمكافحة الإرهاب برئاسة وزير "
    "الداخلية وعضوية النائب العام ومحافظ البنك المركزي ورئيس وحدة التحريات المالية وغيرهم (م24-م25). يقرّر "
    "المسؤولية الجزائية للشخص الاعتباري (غرامة ≤ مليون دينار مع الحلّ/الإغلاق — م26)، ونظامَ التسليم المراقب "
    "(م27)، وعدمَ انقضاء الدعوى/العقوبة بالتقادم (م28)، واختصاصَ النيابة العامة وحدها ومحكمة الجنايات (م29). "
    "يتّصل بقانون مكافحة غسل الأموال وتمويل الإرهاب 106/2013، وقانون الأسلحة 13/1991، وحماية المال العام "
    "1/1993، وقانون الأحداث 111/2015، وهيئة مكافحة الفساد 2/2016، وقانون الجزاء 16/1960 والإجراءات 17/1960. "
    "صدر سنة 2026."
)


def _label(key):
    m = re.match(r'm(\d+)(-mukarrar)?', key)
    return f"مادة {m.group(1)}" + (" مكرر" if m.group(2) else "")


def build_rows(data):
    arts = data["articles"]
    order = data.get("order") or list(arts.keys())
    rows = []

    def meta(extra=None):
        d = {"instrument": INSTRUMENT, "instrument_rank": "مرسوم بقانون", "law_number": LAW_NO,
             "law_year": LAW_YEAR, "upload_origin": "docx_law47_paragraphs"}
        if extra:
            d.update(extra)
        return d

    _recitals = (data.get("preamble_text") or "").strip()
    _pre_text = PREAMBLE + ("\n\nـــ ديباجة المرسوم بقانون (سند الإصدار) ـــ\n" + _recitals if _recitals else "")
    rows.append({
        "id": f"{LAW_ID}-preamble", "object_type": "legislation_article",
        "branch": BRANCH, "topic": "الديباجة", "subtopic": None, "micro_issue": None,
        "title": f"ديباجة — {LAW_TAG}", "text": _pre_text, "meta": meta({"chunk": "preamble"})})

    for key in order:
        a = arts[key]
        body = (a["text"] if isinstance(a, dict) else a).strip()
        mm = re.match(r'm(\d+)(-mukarrar)?', key)
        extra = {"article_number": mm.group(1) + (" مكرر" if mm.group(2) else "")}
        if isinstance(a, dict) and a.get("sec"):
            extra["fasl_raw"] = a["sec"]
        rows.append({
            "id": f"{LAW_ID}-{key}", "object_type": "legislation_article", "branch": BRANCH,
            "topic": TOPIC, "subtopic": None, "micro_issue": None,
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

    print("== تقرير المرسوم بقانون مكافحة جرائم الإرهاب (47/2026) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print(f"فارغة: {empty or 'لا'}")
    ids = [r["id"] for r in rows]
    print(f"مكرّرة: {set(i for i in ids if ids.count(i) > 1) or 'لا'}")
    resid = [r["id"] for r in rows if "�" in r["text"]]
    print(f"محارف بديلة �: {resid or 'لا'}")
    for r in rows:
        if r["id"].endswith(("preamble", "-m1", "-m7", "-m12", "-m28")):
            print(f"\n--- {r['id']} ({r['title']}) ---\n{r['text'][:160]}")

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
