#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محلّل الأمر الأميري بالقانون رقم 61 لسنة 1976 بإصدار قانون التأمينات الاجتماعية.
مواد إصدار (م1-7) ثم القانون المرافق (م1-132 + مكرر) في تسعة أبواب وفصولها.
تنظيف: BOM، �، أقواس مقلوبة، تعدادات، تنوين مزدوج."""
import zipfile, re, json, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "adm5.docx"
OUT = sys.argv[2] if len(sys.argv) > 2 else "adm5_parsed.json"

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

ORD = ("الاول", "الثاني", "الثالث", "الرابع", "الخامس",
       "السادس", "السابع", "الثامن", "التاسع", "العاشر")
def _h(s):                       # تطبيع الهمزة لمطابقة «الأول/الاول»
    return re.sub(r'[أإآ]', 'ا', s)
_ORDX = "|".join(ORD)
_BAB = re.compile(r'^\s*الباب\s+(' + _ORDX + r')\s*$')
_FASL = re.compile(r'^\s*الفصل\s+(' + _ORDX + r')\s*$')
BAB = type("R", (), {"match": staticmethod(lambda s: _BAB.match(_h(s)))})
FASL = type("R", (), {"match": staticmethod(lambda s: _FASL.match(_h(s)))})
# marker: مادة/المادة N [مكرر[ا]] [(dist)] + junk
MARK = re.compile(
    r'^\s*(?:ال)?مادة\s*(\d+)\s*(مكررا?)?\s*[)(]*\s*([أ-ي0-9])?\s*[)(]*[)(\-:：،.\s]*$')
# علامة «مكرر» ساقطة كلمة «مادة»: سطر كامل = رقم + مكرر[ا] + [تمييز] + شوائب
MARK_BARE = re.compile(
    r'^\s*(\d+)\s*(مكررا?)\s*[)(]*\s*([أ-ي0-9])?\s*[)(]*[)(\-:：،.\s]*$')
DIST = {"أ": "a", "ب": "b", "ج": "c", "د": "d", "1": "1", "2": "2", "3": "3"}

# find boundary: first "الباب الأول" = start of main law; before it = issuing articles
try:
    boundary = next(i for i, t in enumerate(paras) if BAB.match(t.strip()) and "الأول" in t)
except StopIteration:
    boundary = len(paras)

arts = {}
order = []
cur = None
cur_bab = None
cur_fasl = None
bab = None
fasl = None
buf = []
last_base = None      # آخر رقم مادة أساسي — لكشف تكرار الرقم (مكرر ساقط الكلمة)

def flush(is_issuing):
    if cur is not None:
        arts[cur] = {"bab": cur_bab, "fasl": cur_fasl, "issuing": is_issuing,
                     "text": "\n".join(x for x in buf if x.strip()).strip()}

i = 0
while i < len(paras):
    t = paras[i]
    issuing = i < boundary
    if not issuing:
        mb = BAB.match(t.strip())
        mf = FASL.match(t.strip())
        if mb:
            parts = []
            j = i + 1
            while j < len(paras) and len(parts) < 2 and len(paras[j]) < 90 \
                  and not MARK.match(paras[j]) and not MARK_BARE.match(paras[j]) \
                  and not BAB.match(paras[j].strip()) and not FASL.match(paras[j].strip()):
                parts.append(paras[j].strip())
                j += 1
            bab = (t.strip() + " — " + " ".join(parts)).strip() if parts else t.strip()
            fasl = None
            i = j
            continue
        if mf:
            title = t.strip()
            if i + 1 < len(paras) and not MARK.match(paras[i + 1]) and len(paras[i + 1]) < 60 \
               and not BAB.match(paras[i + 1].strip()) and not FASL.match(paras[i + 1].strip()):
                title = title + " — " + paras[i + 1].strip()
                i += 1
            fasl = title
            i += 1
            continue
    m = MARK.match(t)
    if (not m) and (not issuing):
        mbare = MARK_BARE.match(t)
        if mbare:                          # «N مكررا» بلا كلمة «مادة»
            m = mbare
    if m:
        flush(cur is not None and cur.startswith("iss"))
        num = m.group(1)
        mkr = m.group(2)
        d = m.group(3)
        if issuing:
            key = "iss" + num
        elif mkr:
            key = "m" + num + "mkr" + (DIST.get(d, d) if d else "")
        elif int(num) == last_base:
            # تكرار الرقم الأساسي دون كلمة «مكرر» = مادة مكرر سقطت كلمتها في المصدر
            key = "m" + num + "mkr"
            n = 1
            while key in arts:
                key = "m" + num + "mkr" + str(n); n += 1
        else:
            key = "m" + num
            last_base = int(num)
        cur = key
        cur_bab = None if issuing else bab
        cur_fasl = None if issuing else fasl
        order.append(key)
        buf = []
        i += 1
        continue
    if cur is not None:
        buf.append(t)
    i += 1
flush(cur is not None and cur.startswith("iss"))

def clean(txt):
    txt = txt.replace("�", "")
    txt = re.sub(r'\)([ء-ي][^()]{0,80}?)\(', r'(\1)', txt, flags=re.S)
    out = []
    for ln in txt.split("\n"):
        ln = re.sub(r'^\s*-\s*(\d+)\s*[-–]?\s*', r'\1. ', ln)
        ln = re.sub(r'^\s*(\d+)\s*[-–]\s*', r'\1. ', ln)
        ln = re.sub(r'^\s*-\s*([أ-ي])\s*-\s*', r'\1) ', ln)
        ln = re.sub(r'^\s*([أ-ي])\s*[-–]\s+', r'\1) ', ln)
        out.append(ln)
    txt = "\n".join(out)
    txt = re.sub(r'ًً+', 'ً', txt)
    return re.sub(r'[ \t]{2,}', ' ', txt).strip()

for k in arts:
    arts[k]["text"] = clean(arts[k]["text"])

json.dump({"articles": arts, "order": order},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

iss = [k for k in order if k.startswith("iss")]
main = [k for k in order if not k.startswith("iss")]
mnums = sorted(int(re.match(r'm(\d+)', k).group(1)) for k in main)
print("total objects:", len(arts), "| issuing:", len(iss), "| main:", len(main))
print("main numeric max:", max(mnums), "| missing 1..max:",
      [n for n in range(1, max(mnums) + 1) if n not in mnums] or "none")
print("مكرر:", [k for k in main if 'mkr' in k])
from collections import Counter
c = Counter(order)
print("dup keys:", [k for k, v in c.items() if v > 1] or "none")
print("empty:", [k for k in arts if not arts[k]["text"].strip()] or "none")
seen = []
for k in order:
    b = arts[k]["bab"]
    if b not in seen:
        seen.append(b)
print("\nأبواب:")
for b in seen:
    ks = [k for k in order if arts[k]["bab"] == b]
    print(f"  {b} [{len(ks)}]: {ks[0]}..{ks[-1]}")
