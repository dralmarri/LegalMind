#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محلّل القانون رقم 21 لسنة 2015 في شأن حقوق الطفل. 97 مادة (م1-97) بلا مكرّر، بنيةٌ مسطّحة
(عناوين الأبواب/الفصول غير مستقلّة كفقرات في هذا الملفّ). الملف نظيف عدا:
- تلف ترميزيّ لكلمة واحدة «أجَّر» ظهرت «أ ج� َر» (فراغ دخيل + محرف بديل حلّ محلّ الشدّة) — مؤكَّدة
  بالسياق («المكان المخصص للتأجير» مرّتين في م90) — تُصحَّح آليًّا.
- أقواس منقلبة اتجاهيًّا حول الأرقام «) 16 (» → «(16)» — تُطبَّع للقراءة (الأرقام سليمة غير معكوسة)."""
import zipfile, re, json, sys
from collections import Counter

SRC = sys.argv[1] if len(sys.argv) > 1 else "new_law3.docx"
OUT = sys.argv[2] if len(sys.argv) > 2 else "law3_parsed.json"

xml = zipfile.ZipFile(SRC).read("word/document.xml").decode("utf-8")
paras = []
for pm in re.finditer(r"<w:p\b.*?</w:p>", xml, re.S):
    t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", pm.group(0), re.S))
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    if t.strip():
        paras.append(t)
TR = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def demojibake(s):
    # تلف محصور: «أجَّر» تسرّبت «أ ج� َر» (شدّة مفقودة). مؤكَّدة بسياق التأجير في م90.
    s = s.replace("أ ج� َر", "أجَّر").replace("ج� َر", "جَّر")
    s = s.replace("�", "")  # أيّ محرف بديل متبقٍّ (لا يوجد غيره)
    return s


def fix_parens(s):
    # الأقواس المنقلبة حول رقمٍ: «) 16 (» → «(16)»، و«) 3(» → «(3)» (الأرقام نفسها سليمة)
    s = re.sub(r"\)\s*(\d+(?:\s*[،,]\s*\d+)*)\s*\(", r"(\1)", s)
    return s


paras = [fix_parens(demojibake(p)).translate(TR).replace("﻿", "").replace("‏", "").replace("‎", "")
         .replace("ی", "ي").replace("ک", "ك").replace("ھ", "ه") for p in paras]

HDR = re.compile(r'^\s*(?:ال)?م?ادة\s+(\d+)\s*(مكرر\w*)?\s*[)\(]*\s*$')
TERMSET = set('.؛!؟»)')

bound = next(i for i, p in enumerate(paras) if HDR.match(p.strip()))
order = []
arts = {}


def add(key):
    if key in arts:
        key = key + "_dup"
    order.append(key)
    arts[key] = {"text": [], "sec": None, "mukarrar": "mukarrar" in key}
    return key


cur = None
i = bound
while i < len(paras):
    s = paras[i].strip()
    m = HDR.match(s)
    if m:
        cur = add("m" + m.group(1) + ("-mukarrar" if m.group(2) else ""))
        i += 1
        continue
    if cur:
        arts[cur]["text"].append(paras[i])
    i += 1


def strip_trailing_subsections(txt):
    lines = txt.split("\n")
    while True:
        idx = [i for i, l in enumerate(lines) if l.strip()]
        if len(idx) < 2:
            break
        last = lines[idx[-1]].strip(); prev = lines[idx[-2]].strip()
        prev_ok = prev[-1] in TERMSET or re.sub(r'[)\(\s]', '', prev) in ("ملغاة", "ملغاه", "ملغى", "ملغية", "ملغيه")
        if (len(last) <= 42 and last[-1] not in TERMSET and prev_ok
                and not re.match(r'^[\d\-•أ-ي]\s*[-.)]', last)):
            del lines[idx[-1]:]
        else:
            break
    return "\n".join(lines).rstrip()


_SIG = re.compile(r'أمير الكويت\s*$|صدر بقصر|بقصر السيف|صباح الأحمد الصباح|نائب أمير الكويت')


def clean(lines):
    txt = "\n".join(x for x in lines if x.strip()).strip()
    txt = txt.replace("�", "")
    ll = txt.split("\n"); cut = None
    for _i, _ln in enumerate(ll):
        if _SIG.search(_ln):
            cut = _i; break
    if cut is not None:
        txt = "\n".join(ll[:cut]).strip()
    out = []
    for ln in txt.split("\n"):
        if re.match(r'^\s*[)(]{1,}\s*$', ln):
            continue
        ln = re.sub(r'\s*\){2,}\s*$', '', ln)
        ln = re.sub(r'^\s*[)(]{2,}\s*', '', ln)
        out.append(ln)
    txt = "\n".join(out)
    txt = re.sub(r'ًً+', 'ً', txt).replace("اًً", "اً")
    txt = re.sub(r'ّّ+', 'ّ', txt)
    txt = re.sub(r'[ \t]{2,}', ' ', txt).strip()
    txt = strip_trailing_subsections(txt)
    if re.sub(r'[)\(«»\s\.]', '', txt) in ("ملغاة", "ملغاه", "ملغى", "ملغية", "ملغيه"):
        return "(ملغاة)"
    return txt


for k in list(arts):
    arts[k]["text"] = clean(arts[k]["text"])

json.dump({"articles": {k: arts[k] for k in order}, "order": order},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

base = sorted(int(re.match(r'm(\d+)', k).group(1)) for k in order if "mukarrar" not in k)
missing = [n for n in range(1, max(base) + 1) if n not in base]
empty = [k for k in arts if not arts[k]["text"].strip()]
resid = [k for k in arts if "�" in arts[k]["text"]]
print("=== القانون 21/2015 (حقوق الطفل) ===")
print(f"مواد: {len(order)} | النطاق: {min(base)}..{max(base)} | مفقودة: {missing or 'لا'}")
print(f"فارغة: {empty or 'لا'} | محارف بديلة �: {resid or 'لا — نُظِّفت'} | تكرار: {[k for k,v in Counter(order).items() if v>1] or 'لا'}")
for k in ("m1", "m3", "m90", "m97"):
    if k in arts:
        print(f"\n--- {k} ---\n{arts[k]['text'][:220]}")
