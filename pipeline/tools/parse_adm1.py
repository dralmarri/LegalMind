#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محلّل القانون رقم 8 لسنة 2010 بشأن حقوق الأشخاص ذوي الإعاقة.
طبقة نصّ سليمة. علامات المواد مختلطة: «مادة N» (1–36 و72) و«المادة N» (37–71)،
مع «المادة 42 مكرر». 72 مادة + (42 مكرر) في عشرة فصول. تنظيف: BOM، �، أقواس، تعدادات."""
import zipfile, re, json, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "adm1.docx"
OUT = sys.argv[2] if len(sys.argv) > 2 else "adm1_parsed.json"

xml = zipfile.ZipFile(SRC).read("word/document.xml").decode("utf-8")
paras = []
for pm in re.finditer(r"<w:p\b.*?</w:p>", xml, re.S):
    p = pm.group(0)
    t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    if t.strip():
        paras.append(t)

TR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
paras = [p.translate(TR).replace("﻿", "").replace("‏", "").replace("‎", "") for p in paras]

ORD = ("الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس",
       "السابع", "الثامن", "التاسع", "العاشر")
FASL = re.compile(r'^\s*الفصل\s+(' + "|".join(ORD) + r')\b')
# marker: whole line is "مادة/المادة N [مكرر]" + optional junk )( : - .
MARK = re.compile(r'^\s*(?:ال)?مادة\s+(\d+)(\s*مكرر)?\s*[)(\-:：،.\s]*$')

arts = {}          # key -> {"fasl":..,"text":..}
order = []
cur = None
buf = []
fasl = None

def flush():
    if cur is not None:
        arts[cur] = {"bab": None, "fasl": fasl,
                     "text": "\n".join(x for x in buf if x.strip()).strip()}

i = 0
while i < len(paras):
    t = paras[i]
    mf = FASL.match(t)
    if mf:
        title = t.strip()
        if i + 1 < len(paras) and not MARK.match(paras[i + 1]) \
           and not FASL.match(paras[i + 1]) and len(paras[i + 1]) < 60:
            title = title + " — " + paras[i + 1].strip()
            i += 1
        fasl = title
        i += 1
        continue
    mm = MARK.match(t)
    if mm:
        flush()
        num = mm.group(1)
        key = ("m" + num + "mkr") if mm.group(2) else ("m" + num)
        cur = key
        order.append(key)
        buf = []
        i += 1
        continue
    buf.append(t)
    i += 1
flush()

def clean(txt):
    txt = txt.replace("�", "")                                  # � replacement char
    # تصحيح ترقيم مصدري ساقط الرقم: البند 11 في تعريفات م1 ورد «1 مجلس الإدارة»
    txt = txt.replace("\n1 مجلس الإدارة:", "\n11. مجلس الإدارة:")
    txt = re.sub(r'\)([ء-ي][^()]{0,80}?)\(', r'(\1)', txt, flags=re.S)  # bidi paren swap )نص(
    out = []
    for ln in txt.split("\n"):
        ln = re.sub(r'^\s*-\s*(\d+)\s*[-–]?\s*', r'\1. ', ln)
        ln = re.sub(r'^\s*(\d+)\s*[-–]\s*', r'\1. ', ln)
        ln = re.sub(r'^\s*-\s*([أ-ي])\s*-\s*', r'\1) ', ln)
        ln = re.sub(r'^\s*([أ-ي])\s*[-–]\s+', r'\1) ', ln)
        out.append(ln)
    txt = "\n".join(out)
    txt = re.sub(r'ًً+', 'ً', txt)                                    # double tanwin artifact
    return re.sub(r'[ \t]{2,}', ' ', txt).strip()

for k in arts:
    arts[k]["text"] = clean(arts[k]["text"])

json.dump({"articles": arts, "order": order},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

nums = [int(re.match(r'm(\d+)', k).group(1)) for k in arts]
print("article objects:", len(arts), "| numeric max:", max(nums))
print("has 42 مكرر:", "m42mkr" in arts)
missing = [n for n in range(1, max(nums) + 1) if n not in nums]
print("missing 1..max:", missing or "none")
from collections import Counter
c = Counter(order)
print("dup keys:", [k for k, v in c.items() if v > 1] or "none")
print("empty:", [k for k in arts if not arts[k]["text"].strip()] or "none")
seen = []
for k in order:
    f = arts[k]["fasl"]
    if f not in seen:
        seen.append(f)
print("\nفصول:")
for f in seen:
    ks = [k for k in order if arts[k]["fasl"] == f]
    print(f"  {f} [{len(ks)}]: {ks[0]}..{ks[-1]}")
