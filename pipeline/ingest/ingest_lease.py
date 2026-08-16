#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل عام لتشريع مسطّح معقّد: أرقام هندية، مواد مكرّرة بحروف، مواد ملغاة،
وإحالات داخلية (المادة (س) من هذا القانون) يجب ألا تُلتقط كعناوين.

قاعدة العنوان الصارمة: سطر العنوان مجرّد علامة «المادة رقم [مكرر[ا] [حرف]]» بلا نصّ
لاحق؛ فإن تبِعه كلامٌ (مثل «من هذا القانون…») فهو إحالة داخل المتن لا عنوان.
يبني legislation_preamble + legislation_article بمعرّفات m{n}[-mukarrar][-a..].
"""
from __future__ import annotations
import argparse, os, re, sys, zipfile
from collections import OrderedDict
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_DIAC = re.compile(r"[ً-ْـ]")
_INVIS = re.compile(r"[​-‏‪-‮⁦-⁩﻿]")
_ARDIG = {ord(a): str(i) for i, a in enumerate("٠١٢٣٤٥٦٧٨٩")}
_LET = {"أ": "a", "ا": "a", "إ": "a", "ب": "b", "ج": "c", "د": "d", "ه": "e", "و": "f", "ز": "g"}
_LET_AR = {"a": "أ", "b": "ب", "c": "ج", "d": "د", "e": "هـ", "f": "و", "g": "ز"}

def _ad(s):  return s.translate(_ARDIG)          # أرقام هندية → لاتينية
def _deac(s):
    s = _INVIS.sub("", s); s = _DIAC.sub("", s)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا")):
        s = s.replace(a, b)
    return s.strip()

_ORD = OrderedDict([("اولا", 1), ("ثانيا", 2), ("ثالثا", 3), ("رابعا", 4), ("خامسا", 5),
                    ("سادسا", 6), ("سابعا", 7), ("ثامنا", 8), ("تاسعا", 9), ("عاشرا", 10)])
ORD_LINE = re.compile(r"^(" + "|".join(_ORD) + r")\s*:?\s*$")
# بادئة العنوان: المادة + أقواس/فراغات + رقم + بقيّة السطر
PREFIX = re.compile(r"^(?:المادة|المادّة|مادة)\s*[)(﴾﴿\s]*(\d+)(.*)$")
# كتلة التوقيع/الإصدار — محدّدة بدقّة كي لا تلتبس بجُمَل المتن (مثل «يستصدر بها»/«صدر بها حكم»)
SIG = re.compile(r"^(أمير الكويت|صباح السالم الصباح|عبد الله السالم|صدر (?:في|ب)?\s*قصر"
                 r"|صدر في\s+\d|صدر في\s*:|الموافق\s*[:\d])")

def classify_head(line):
    """يعيد (num, mukarrar, sub) إن كان السطر عنوان مادة صِرفًا، وإلا None.
    sub: رمز الجزء الفرعي للمادة المكرّرة — حرف (a..) أو رقم ('1'..)."""
    m = PREFIX.match(_ad(line))
    if not m:
        return None
    num = int(m.group(1)); rest = m.group(2)
    rs = re.sub(r"[\s)(﴾﴿\-–—]+", " ", rest).strip()      # إزالة أقواس/شرطات
    toks = rs.split()
    i = 0; muk = False; sub = None
    if toks and toks[0].rstrip("اًأ").startswith("مكرر"):
        muk = True; i = 1
    if muk and len(toks) > i:                               # جزء فرعي: حرف أو رقم
        t = toks[i]
        if t in _LET:
            sub = _LET[t]; i += 1
        elif t.isdigit():
            sub = t; i += 1
    if i != len(toks):
        return None                                        # بقي كلامٌ ⇒ إحالة لا عنوان
    return num, muk, sub

def read_paragraphs(path):
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read("word/document.xml").decode("utf-8"))
    out = []
    for p in root.iter(W + "p"):
        txt = "".join(t.text or "" for t in p.iter(W + "t")).strip()
        if txt:
            out.append(txt)
    return out

def _clean_body(lines):
    t = "\n".join(lines).strip()
    t = re.sub(r"^[\s)(﴾﴿\]\[]+", "", t)
    t = re.sub(r"[\s)(﴾﴿\]\[]+$", "", t)
    return t.strip()

def parse(paras, default_topic):
    first = next((i for i, p in enumerate(paras)
                  if classify_head(p) or ORD_LINE.match(_deac(p))), len(paras))
    preamble = "\n".join(paras[:first]).strip()
    articles = []; cur_topic = default_topic; cur = None
    i = first
    while i < len(paras):
        line = paras[i]
        if ORD_LINE.match(_deac(line)):
            title = paras[i + 1].strip() if i + 1 < len(paras) else ""
            cur_topic = re.sub(r"\s+", " ", title).strip(" :") or default_topic
            cur = None; i += 2; continue
        h = classify_head(line)
        if h:
            num, muk, sub = h
            cur = {"num": num, "mukarrar": muk, "sub": sub, "topic": cur_topic, "body": []}
            articles.append(cur); i += 1; continue
        if SIG.match(_ad(line)):
            cur = None; i += 1; continue
        if cur is not None:
            cur["body"].append(line)
        i += 1
    for a in articles:
        a["text"] = _clean_body(a["body"])
    def _subkey(s):                                        # None ثم أرقام ثم حروف
        if not s:
            return (0, 0, "")
        return (1, int(s), "") if s.isdigit() else (2, 0, s)
    articles.sort(key=lambda a: (a["num"], 1 if a["mukarrar"] else 0, _subkey(a["sub"])))
    return preamble, articles

def _arlabel(a):
    s = str(a["num"])
    if a["mukarrar"]:
        s += " مكرر"
    if a["sub"]:
        s += f" ({a['sub'] if a['sub'].isdigit() else _LET_AR.get(a['sub'], a['sub'])})"
    return s

def _suffix(a):
    s = ""
    if a["mukarrar"]:
        s += "-mukarrar"
    if a["sub"]:
        s += "-" + a["sub"]
    return s

def build_rows(preamble, articles, cfg):
    rows = []
    base = {"law_name": cfg["law_name"], "law_year": cfg["law_year"],
            "law_number": cfg["law_number"], "upload_origin": "docx_legislation_import"}
    if preamble:
        rows.append({"id": f"{cfg['law_id']}-preamble", "object_type": "legislation_preamble",
                     "branch": cfg["branch"], "topic": "ديباجة", "subtopic": None, "micro_issue": None,
                     "title": f"ديباجة — {cfg['law_short']}", "text": preamble, "meta": dict(base)})
    for a in articles:
        lbl = _arlabel(a); meta = dict(base)
        meta.update({"article_number": lbl, "tabweeb": {"section": a["topic"]}, "tabweeb_path": a["topic"]})
        if a["text"].replace("(", "").replace(")", "").strip().startswith("ملغا"):
            meta["repealed"] = True
        rows.append({"id": f"{cfg['law_id']}-m{a['num']}{_suffix(a)}", "object_type": "legislation_article",
                     "branch": cfg["branch"], "topic": a["topic"], "subtopic": None, "micro_issue": None,
                     "title": f"المادة {lbl} — {cfg['law_short']}", "text": a["text"], "meta": meta})
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

    nums = sorted({a["num"] for a in articles})
    missing = sorted(set(range(min(nums), max(nums) + 1)) - set(nums)) if nums else []
    empties = [_arlabel(a) for a in articles if not a["text"]]
    muk = [_arlabel(a) for a in articles if a["mukarrar"]]
    repealed = [_arlabel(a) for a in articles if a["text"].replace("(", "").replace(")", "").strip().startswith("ملغا")]
    print("== تقرير السلامة ==")
    print(f"القانون: {cfg['law_name']}  [{cfg['law_id']}]  الفرع: {cfg['branch']}")
    print(f"ديباجة: {'نعم' if preamble else 'لا'}   عدد المواد (بالمكرّر): {len(articles)}   أرقام أساسية: {min(nums)}–{max(nums)}")
    print(f"مواد ناقصة: {missing or 'لا'}   مواد فارغة: {empties or 'لا'}")
    print(f"مواد مكرّرة: {muk or 'لا'}")
    print(f"مواد ملغاة: {repealed or 'لا'}")
    print(f"إجمالي الكائنات: {len(rows)}")
    print("\n== المواد (بالترتيب) ==")
    print("  " + "، ".join("م" + _arlabel(a) for a in articles))

    if args.dry_run:
        print("\n[dry-run] لم يُدخَل شيء.")
        for a in articles:
            print(f"\n--- م{_arlabel(a)} (topic={a['topic']}) ---\n{a['text'][:220]}")
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
