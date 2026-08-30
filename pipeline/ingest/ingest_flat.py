#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل عام لتشريع مسطّح (مواد مرقّمة بلا تبويب هرمي، عناوين ترتيبية اختيارية).

يتحمّل: ترتيب المواد غير المتسلسل في المصدر، وكتلة توقيع/إصدار في وسط الملف
(تُتخطّى ولا توقف المسح). يبني legislation_preamble + legislation_article.
يطابق اصطلاحات قاعدة المعرفة: source_key=NULL, source_verified/source_authority,
usable_as_citation=TRUE. مُعامَل بالكامل عبر وسائط سطر الأوامر.
"""
from __future__ import annotations
import argparse, os, re, sys, zipfile
from collections import OrderedDict
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_DIAC = re.compile(r"[ً-ْـ]")
_INVIS = re.compile(r"[​-‏‪-‮⁦-⁩﻿]")

def _deac(s: str) -> str:
    s = _INVIS.sub("", s); s = _DIAC.sub("", s)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا")):
        s = s.replace(a, b)
    return s.strip()

_ORD = OrderedDict([
    ("اولا", 1), ("ثانيا", 2), ("ثالثا", 3), ("رابعا", 4), ("خامسا", 5),
    ("سادسا", 6), ("سابعا", 7), ("ثامنا", 8), ("تاسعا", 9), ("عاشرا", 10),
])
ORD_LINE = re.compile(r"^(" + "|".join(_ORD) + r")\s*:?\s*$")
ART = re.compile(r"^(?:المادة|المادّة|مادة)\s*(?:رقم\s*)?\(*\s*(\d+)\s*\)*(\s*مكرر)?\b(.*)$")
# كتلة التوقيع/الإصدار — تُتخطّى (قد تظهر في وسط الملف)
SIG = re.compile(r"^(أمير الكويت|صباح السالم|صدر .*قصر|صدر ب|الموافق\s*:)")

def read_paragraphs(path: str) -> list[str]:
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read("word/document.xml").decode("utf-8"))
    out = []
    for p in root.iter(W + "p"):
        txt = "".join(t.text or "" for t in p.iter(W + "t")).strip()
        if txt:
            out.append(txt)
    return out

def parse(paras, default_topic):
    first_art = next((i for i, p in enumerate(paras) if ART.match(p)), len(paras))
    preamble = "\n".join(paras[:first_art]).strip()
    articles = []
    cur_topic = default_topic
    cur = None
    i = first_art
    while i < len(paras):
        line = paras[i]; dl = _deac(line)
        if ORD_LINE.match(dl):
            title = paras[i + 1].strip() if i + 1 < len(paras) else ""
            cur_topic = re.sub(r"\s+", " ", title).strip(" :") or default_topic
            cur = None; i += 2; continue
        ma = ART.match(line)
        if ma:
            num = int(ma.group(1)); rest = (ma.group(3) or "").strip()
            cur = {"num": num, "topic": cur_topic, "body": []}
            if rest:
                cur["body"].append(rest)
            articles.append(cur); i += 1; continue
        if SIG.match(line):
            cur = None; i += 1; continue          # تخطّي التوقيع، لا توقف
        if cur is not None:
            cur["body"].append(line)
        i += 1
    for a in articles:
        txt = "\n".join(a["body"]).strip()
        txt = re.sub(r"^[\s)(﴾﴿\]\[]+", "", txt)   # شظايا أقواس مشوّهة في الصدر
        a["text"] = txt.strip()
    # ترتيب حسب رقم المادة (المصدر قد يكون غير متسلسل)
    articles.sort(key=lambda a: a["num"])
    return preamble, articles

def build_rows(preamble, articles, cfg):
    rows = []
    base = {"law_name": cfg["law_name"], "law_year": cfg["law_year"],
            "law_number": cfg["law_number"], "upload_origin": "docx_legislation_import"}
    if preamble:
        rows.append({"id": f"{cfg['law_id']}-preamble", "object_type": "legislation_preamble",
                     "branch": cfg["branch"], "topic": "ديباجة", "subtopic": None, "micro_issue": None,
                     "title": f"ديباجة — {cfg['law_short']}", "text": preamble, "meta": dict(base)})
    for a in articles:
        meta = dict(base); meta.update({"article_number": str(a["num"]),
                                        "tabweeb": {"section": a["topic"]}, "tabweeb_path": a["topic"]})
        rows.append({"id": f"{cfg['law_id']}-m{a['num']}", "object_type": "legislation_article",
                     "branch": cfg["branch"], "topic": a["topic"], "subtopic": None, "micro_issue": None,
                     "title": f"المادة {a['num']} — {cfg['law_short']}", "text": a["text"], "meta": meta})
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
    ap.add_argument("--law-number", type=int, required=True)
    ap.add_argument("--law-year", type=int, required=True)
    ap.add_argument("--law-name", required=True)
    ap.add_argument("--law-short", required=True)
    ap.add_argument("--branch", default="مدني")
    ap.add_argument("--default-topic", default="أحكام عامة")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cfg = {"law_number": args.law_number, "law_year": args.law_year,
           "law_id": f"legis-{args.law_number}-{args.law_year}",
           "law_name": args.law_name, "law_short": args.law_short, "branch": args.branch}

    paras = read_paragraphs(args.docx)
    preamble, articles = parse(paras, args.default_topic)
    rows = build_rows(preamble, articles, cfg)

    nums = [a["num"] for a in articles]
    dups = sorted({n for n in nums if nums.count(n) > 1})
    missing = sorted(set(range(min(nums), max(nums) + 1)) - set(nums)) if nums else []
    empties = [a["num"] for a in articles if not a["text"]]
    print("== تقرير السلامة ==")
    print(f"القانون: {cfg['law_name']}  [{cfg['law_id']}]  الفرع: {cfg['branch']}")
    print(f"ديباجة: {'نعم' if preamble else 'لا'}   عدد المواد: {len(articles)}   المدى: {min(nums)}–{max(nums)}")
    print(f"مكرّرات: {dups or 'لا'}   مواد ناقصة: {missing or 'لا'}   مواد فارغة النص: {empties or 'لا'}")
    print(f"إجمالي الكائنات: {len(rows)}")
    print("\n== الشجرة حسب القسم (topic) ==")
    tree = OrderedDict()
    for a in articles:
        tree.setdefault(a["topic"], []).append(a["num"])
    for tp, ns in tree.items():
        print(f"• {tp}  [{len(ns)}]  (م{ns[0]}–{ns[-1]})")

    if args.dry_run:
        print("\n[dry-run] لم يُدخَل شيء.")
        for a in articles:
            print(f"\n--- م{a['num']} ---\n{a['text'][:200]}")
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
