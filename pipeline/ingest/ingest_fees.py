#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل قانون الرسوم القضائية (17/1973) — تبويب مسطّح بعناوين ترتيبية (أولًا…سابعًا).

يبني كائنات: legislation_preamble (الديباجة) + legislation_article (م1..24).
كل مادة تُنسب إلى قسمها (topic) حسب العنوان الترتيبي الذي تندرج تحته.
يطابق تمامًا اصطلاحات قاعدة المعرفة: source_key=NULL, source_verified/source_authority,
usable_as_citation=TRUE, ومعرّفات legis-17-1973-m{n}.
"""
from __future__ import annotations
import argparse, os, re, sys, zipfile
from collections import OrderedDict
from xml.etree import ElementTree as ET

LAW_NUMBER = 17
LAW_YEAR   = 1973
LAW_ID     = "legis-17-1973"
LAW_NAME   = "قانون رقم 17 لسنة 1973 في الرسوم القضائية"
LAW_SHORT  = "قانون الرسوم القضائية"
BRANCH     = "مدني"

# ── التعديل بالمرسوم بقانون رقم 78 لسنة 2025 (الكويت اليوم) ──
# النص المُدخَل هو النص المُوحَّد النافذ بعد هذا التعديل.
AMEND_REF   = "مرسوم بقانون رقم 78 لسنة 2025"
AMEND_YEAR  = 2025
CONSOLIDATION = "نص موحَّد نافذ بعد التعديل بالمرسوم بقانون رقم 78 لسنة 2025"
# مواد استُبدل نصّها بالكامل بموجب المادة الأولى من المرسوم
AMEND_REPLACED   = {2, 5, 6, 7, 9, 10, 15, 16, 17, 19, 22, 23}
# مواد استُبدلت فقرتها الأولى فقط
AMEND_FIRST_PARA = {8, 18}
# المادة 4 أُضيف إليها البندان (و) و(ز) بموجب المادة الثانية من المرسوم
AMEND_ADDED      = {4}

def _amend_note(num):
    if num in AMEND_ADDED:
        return "أُضيف البندان (و) و(ز) بموجب المادة الثانية من " + AMEND_REF
    if num in AMEND_FIRST_PARA:
        return "استُبدلت الفقرة الأولى بموجب المادة الأولى من " + AMEND_REF
    if num in AMEND_REPLACED:
        return "استُبدل نصّه بالكامل بموجب المادة الأولى من " + AMEND_REF
    return None

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_DIAC = re.compile(r"[ً-ْـ]")          # تشكيل + تطويل
_INVIS = re.compile(r"[​-‏‪-‮⁦-⁩﻿]")

def _deac(s: str) -> str:
    s = _INVIS.sub("", s)
    s = _DIAC.sub("", s)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا")):
        s = s.replace(a, b)
    return s.strip()

# العناوين الترتيبية للأقسام (بعد تجريد التشكيل)
_ORD = OrderedDict([
    ("اولا", 1), ("ثانيا", 2), ("ثالثا", 3), ("رابعا", 4),
    ("خامسا", 5), ("سادسا", 6), ("سابعا", 7), ("ثامنا", 8), ("تاسعا", 9), ("عاشرا", 10),
])
ORD_LINE = re.compile(r"^(" + "|".join(_ORD) + r")\s*:?\s*$")
ART = re.compile(r"^(?:المادة|المادّة|مادة)\s*(?:رقم\s*)?\(*\s*(\d+)\s*\)*(\s*مكرر)?\b(.*)$")
# نهاية النص: كتلة التوقيع/الإصدار
SIG = re.compile(r"^(أمير الكويت|صباح السالم|صدر في قصر السيف|في\s*:|الموافق\s*:)")

def read_paragraphs(path: str) -> list[str]:
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read("word/document.xml").decode("utf-8"))
    out = []
    for p in root.iter(W + "p"):
        txt = "".join(t.text or "" for t in p.iter(W + "t")).strip()
        if txt:
            out.append(txt)
    return out

def parse(paras: list[str]):
    # 1) الديباجة = كل ما قبل أول عنوان ترتيبي
    first_sec = next((i for i, p in enumerate(paras) if ORD_LINE.match(_deac(p))), len(paras))
    preamble = "\n".join(paras[:first_sec]).strip()

    # 2) المرور على بقية الفقرات: أقسام (topic) + مواد
    articles = []               # {num, topic, body[]}
    cur_topic = None
    cur = None
    i = first_sec
    stop = False
    while i < len(paras):
        line = paras[i]
        dl = _deac(line)
        if ORD_LINE.match(dl):
            # العنوان الترتيبي؛ عنوان القسم في السطر التالي
            title = paras[i + 1].strip() if i + 1 < len(paras) else ""
            cur_topic = re.sub(r"\s+", " ", title).strip(" :")
            cur = None
            i += 2
            continue
        ma = ART.match(line)
        if ma:
            num = int(ma.group(1))
            rest = (ma.group(3) or "").strip()
            cur = {"num": num, "topic": cur_topic or "أحكام عامة", "body": []}
            if rest:
                cur["body"].append(rest)
            articles.append(cur)
            i += 1
            continue
        if SIG.match(line) and cur is not None:
            # بلغنا كتلة التوقيع — نُنهي جمع النص
            stop = True
            break
        if cur is not None:
            cur["body"].append(line)
        i += 1
    for a in articles:
        txt = "\n".join(a["body"]).strip()
        # إزالة شظايا الأقواس المشوّهة في صدر النص (مثل «)))» من «(23)» المتضرّرة)
        txt = re.sub(r"^[\s)(﴾﴿\]\[]+", "", txt)
        a["text"] = txt.strip()
    return preamble, articles

# نصّ المرسوم المعدِّل ومذكرته الإيضاحية — سياق تشريعي (المذكرة استئناسية تفسيرية)
AMEND_CONTEXT = (
    "المرسوم بقانون رقم 78 لسنة 2025 بتعديل بعض أحكام القانون رقم 17 لسنة 1973 في شأن الرسوم القضائية.\n"
    "الغرض: الحدّ من تنامي عدد القضايا الكيدية، وكفالة جدية حق التقاضي، وتعزيز الوسائل البديلة "
    "لتسوية المنازعات عن طريق التحكيم أو الصلح.\n"
    "المادة الأولى: استبدال نصوص المواد (2، 5، 6، 7، 8/فقرة أولى، 9، 10، 15، 16، 17، 18/فقرة أولى، 19، 22، 23).\n"
    "المادة الثانية: إضافة البندين (و) و(ز) إلى المادة (4).\n"
    "من المذكرة الإيضاحية (استئناس تفسيري لا نصّ ملزم): مضى على القانون 17/1973 ما يربو على خمسين عامًا "
    "دون تعديل رغم التغيّرات الاقتصادية والاجتماعية وارتفاع معدل التضخم، وازدياد أعداد القضايا المرفوعة على "
    "نحو مضطرد؛ ولمّا كانت الرسوم القضائية مقابل الاستفادة من خدمات مرفق القضاء، فإن إعادة النظر فيها بما "
    "يتناسب مع تلك التغيّرات يحدّ من القضايا الكيدية ويكفل جدية حق التقاضي ويعزّز التحكيم والصلح، دونما إخلال "
    "بالتوازن المطلوب بين كفالة حق التقاضي وحسن سير مرفق القضاء بانتظام واطّراد."
)

def build_rows(preamble, articles):
    rows = []
    base_meta = {"law_name": LAW_NAME, "law_year": LAW_YEAR, "law_number": LAW_NUMBER,
                 "upload_origin": "docx_legislation_import", "consolidation": CONSOLIDATION,
                 "amended_by": AMEND_REF}
    if preamble:
        rows.append({"id": f"{LAW_ID}-preamble", "object_type": "legislation_preamble",
                     "branch": BRANCH, "topic": "ديباجة", "subtopic": None, "micro_issue": None,
                     "title": f"ديباجة — {LAW_SHORT}", "text": preamble,
                     "meta": dict(base_meta)})
    # كائن سياق التعديل (المرسوم 78/2025 + المذكرة الإيضاحية)
    rows.append({"id": f"{LAW_ID}-amend-78-2025", "object_type": "legislation_issuing_article",
                 "branch": BRANCH, "topic": "التعديلات — المرسوم بقانون 78/2025",
                 "subtopic": None, "micro_issue": None,
                 "title": f"المرسوم بقانون رقم 78 لسنة 2025 (المعدِّل) — الغرض والمذكرة الإيضاحية — {LAW_SHORT}",
                 "text": AMEND_CONTEXT,
                 "meta": {"law_name": LAW_NAME, "law_year": LAW_YEAR, "law_number": LAW_NUMBER,
                          "upload_origin": "docx_legislation_import",
                          "instrument": AMEND_REF, "instrument_year": AMEND_YEAR,
                          "note_type": "مرسوم معدِّل + مذكرة إيضاحية (المذكرة استئناسية تفسيرية غير ملزمة)"}})
    for a in articles:
        meta = dict(base_meta)
        meta.update({"article_number": str(a["num"]),
                     "tabweeb": {"section": a["topic"]}, "tabweeb_path": a["topic"]})
        note = _amend_note(a["num"])
        if note:
            meta["amended"] = True
            meta["amendment_note"] = note
        rows.append({"id": f"{LAW_ID}-m{a['num']}", "object_type": "legislation_article",
                     "branch": BRANCH, "topic": a["topic"], "subtopic": None, "micro_issue": None,
                     "title": f"المادة {a['num']} — {LAW_SHORT}", "text": a["text"], "meta": meta})
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
    ap.add_argument("docx")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    paras = read_paragraphs(args.docx)
    preamble, articles = parse(paras)
    rows = build_rows(preamble, articles)

    nums = [a["num"] for a in articles]
    dups = sorted({n for n in nums if nums.count(n) > 1})
    rng = set(range(min(nums), max(nums) + 1)) if nums else set()
    missing = sorted(rng - set(nums))
    empties = [a["num"] for a in articles if not a["text"]]

    print("== تقرير السلامة ==")
    print(f"القانون: {LAW_NAME}  [{LAW_ID}]  الفرع: {BRANCH}")
    print(f"ديباجة: {'نعم' if preamble else 'لا'}   عدد المواد: {len(articles)}   المدى: {min(nums)}–{max(nums)}")
    print(f"مكرّرات: {dups or 'لا'}   مواد ناقصة في المدى: {missing or 'لا'}   مواد فارغة النص: {empties or 'لا'}")
    amended = sorted(AMEND_REPLACED | AMEND_FIRST_PARA | AMEND_ADDED)
    print(f"إجمالي الكائنات (ديباجة + كائن تعديل + مواد): {len(rows)}")
    print(f"التعديل: {AMEND_REF}")
    print(f"  مواد استُبدل نصّها بالكامل: {sorted(AMEND_REPLACED)}")
    print(f"  مواد استُبدلت فقرتها الأولى: {sorted(AMEND_FIRST_PARA)}")
    print(f"  مواد أُضيف إليها بنود: {sorted(AMEND_ADDED)}  (البندان و/ز)")
    print(f"  إجمالي المواد المتأثرة: {len(amended)} من {len(articles)}")
    print("\n== الشجرة حسب القسم (topic) ==")
    tree = OrderedDict()
    for a in articles:
        tree.setdefault(a["topic"], []).append(a["num"])
    for tp, ns in tree.items():
        print(f"• {tp}  [{len(ns)}]  (م{ns[0]}–{ns[-1]})")

    if args.dry_run:
        print("\n[dry-run] لم يُدخَل شيء.")
        # عيّنة
        print("\n== عيّنة نص (م1) ==")
        print(next(r['text'] for r in rows if r['id'] == f'{LAW_ID}-m1')[:300])
        return 0

    import psycopg
    from psycopg.types.json import Jsonb
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    ins = 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
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
                        metadata=EXCLUDED.metadata,updated_at=now()""",
                    (r["id"], r["object_type"], r["branch"], r["topic"], r["subtopic"], r["micro_issue"],
                     r["title"], r["text"], normalize_text(r["text"]), Jsonb(r["meta"])))
                ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل الآن: python -m engine.legalmind_engine reindex")
    return 0

if __name__ == "__main__":
    sys.exit(main())
