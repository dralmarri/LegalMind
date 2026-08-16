#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محلّل القانون رقم 6 لسنة 2010 في شأن العمل في القطاع الأهلي.
طبقة نصّ سليمة. يقسّم على «المادة N» الحقيقية فقط (لا الإشارات المرجعية)،
مع التقاط الباب والفصل، وتنظيف شوائب: BOM، أقواس مقلوبة، تعدادات، مسافات."""
import zipfile, re, json, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "lab4.docx"
OUT = sys.argv[2] if len(sys.argv) > 2 else "lab4_parsed.json"

xml = zipfile.ZipFile(SRC).read("word/document.xml").decode("utf-8")
paras = []
for pm in re.finditer(r"<w:p\b.*?</w:p>", xml, re.S):
    p = pm.group(0)
    txt = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
    txt = txt.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    if txt.strip():
        paras.append(txt)

TR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
paras = [p.translate(TR).replace("﻿", "").replace("‏", "").replace("‎", "")
         for p in paras]

ORD = ("الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس", "السابع",
       "الثامن", "التاسع", "العاشر", "الحادي عشر", "الثاني عشر", "الثالث عشر")

# marker: paragraph starting with "المادة N" whose remainder is only junk )( : - space
ART = re.compile(r'^\s*المادة\s+(\d+)\s*([)(\-:：،.\s]*)$')
# باب / فصل headings may carry a leading bullet like "3 - " ; strip it
BULLET = re.compile(r'^\s*\d+\s*[-–]\s*')
BAB = re.compile(r'^\s*الباب\s+(\S+)')
FASL = re.compile(r'^\s*الفصل\s+(\S+)')

def strip_bullet(t):
    return BULLET.sub("", t).strip()

arts = {}
order = []
cur = None
buf = []
bab = None
fasl = None
pending_heading = None  # to grab the title line following "الباب X"/"الفصل X"

def flush():
    if cur is not None:
        arts[str(cur)] = {"bab": bab, "fasl": fasl,
                          "text": "\n".join(x for x in buf if x.strip()).strip()}

i = 0
while i < len(paras):
    raw = paras[i]
    t = strip_bullet(raw)
    mb = BAB.match(t)
    mf = FASL.match(t)
    ma = ART.match(raw)
    if mb and mb.group(1) in ORD:
        # next non-heading paragraph is the title
        title = t
        if i + 1 < len(paras):
            nxt = strip_bullet(paras[i + 1])
            if not ART.match(paras[i + 1]) and not BAB.match(nxt) and not FASL.match(nxt) \
               and len(nxt) < 60:
                title = t + " — " + nxt
                i += 1
        bab = title
        fasl = None
        i += 1
        continue
    if mf and mf.group(1).split()[0] in [o.split()[0] for o in ORD]:
        title = t
        if i + 1 < len(paras):
            nxt = strip_bullet(paras[i + 1])
            if not ART.match(paras[i + 1]) and not BAB.match(nxt) and not FASL.match(nxt) \
               and len(nxt) < 60:
                title = t + " — " + nxt
                i += 1
        fasl = title
        i += 1
        continue
    if ma:
        flush()
        cur = int(ma.group(1))
        order.append(str(cur))
        buf = []
        i += 1
        continue
    buf.append(raw)
    i += 1
flush()

# ---- text cleanup ----
def clean(t):
    # bidi paren swap — genuine case only: ")نص(" where ")" is immediately followed by
    # an Arabic letter (list markers like "أ)" always have a space after ")", so are safe).
    # DOTALL to bridge a line break inside the parenthetical.
    t = re.sub(r'\)([ء-ي][^()]{0,80}?)\(', r'(\1)', t, flags=re.S)
    # bullets: "-2 " / "2 -" / "1 -الوزارة" / "-أ-" normalization at line starts
    out = []
    for ln in t.split("\n"):
        ln = re.sub(r'^\s*-\s*(\d+)\s*[-–]?\s*', r'\1. ', ln)   # "-2 نص" / "-2- نص"
        ln = re.sub(r'^\s*(\d+)\s*[-–]\s*', r'\1. ', ln)        # "2 - نص" / "1 -الوزارة"
        ln = re.sub(r'^\s*-\s*([أ-ي])\s*-\s*', r'\1) ', ln)     # "-أ- نص" -> "أ) نص"
        ln = re.sub(r'^\s*([أ-ي])\s*[-–]\s+', r'\1) ', ln)      # "ب- نص" -> "ب) نص"
        out.append(ln)
    t = "\n".join(out)
    # spacing artifacts: "يصدر ها" -> "يصدرها" (only fix "  " -> " ")
    t = re.sub(r'[ \t]{2,}', ' ', t)
    return t.strip()

for k in arts:
    arts[k]["text"] = clean(arts[k]["text"])

json.dump({"articles": arts, "order": order},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

nums = sorted(int(k) for k in arts)
print("articles:", len(arts), "| max:", max(nums))
missing = [i for i in range(1, max(nums) + 1) if i not in nums]
print("missing 1..max:", missing or "none")
from collections import Counter
c = Counter(order)
print("dup markers:", [n for n, k in c.items() if k > 1] or "none")
empty = [k for k in arts if not arts[k]["text"].strip()]
print("empty:", empty or "none")
babset = []
seen = set()
for k in order:
    b = arts[k]["bab"]
    if b not in seen:
        seen.add(b); babset.append(b)
print("\nأبواب:")
for b in babset:
    print("  ", b)
