#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محلّل المرسوم لسنة 1979 بشأن نظام الخدمة المدنية (اللائحة التنفيذية لـ15/1979).
94 مادة + عناقيد «مكرر» (م30 مكرر/مكرر1/مكرر ب/مكرر ج)، في عشرة أقسام (أولًا…عاشرًا).
تنظيف: BOM، �، أقواس مقلوبة، تعدادات، تنوين مزدوج."""
import zipfile, re, json, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "adm4.docx"
OUT = sys.argv[2] if len(sys.argv) > 2 else "adm4_parsed.json"

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

# marker: مادة/المادة N [مكرر [distinguisher]] + junk
MARK = re.compile(r'^\s*(?:ال)?مادة\s*(\d+)\s*(مكرر)?\s*([0-9أ-ي]+)?\s*[)(\-:：،.\s]*$')
SEC = re.compile(r'^\s*(أولا|ثانيا|ثالثا|رابعا|خامسا|سادسا|سابعا|ثامنا|تاسعا|عاشرا)\s*[:：]\s*(.*)$')
DIST = {"1": "1", "2": "2", "3": "3", "ب": "b", "ج": "c", "د": "d",
        "ثانيا": "2", "ثالثا": "3", "رابعا": "4"}

arts = {}
order = []
cur = None
cur_sec = None      # القسم لحظة بدء المادة (لا لحظة الإغلاق) — يمنع تسرّب عنوان القسم التالي
buf = []
sec = None

def flush():
    if cur is not None:
        arts[cur] = {"bab": cur_sec, "fasl": None,
                     "text": "\n".join(x for x in buf if x.strip()).strip()}

for t in paras:
    ms = SEC.match(t)
    if ms and len(t) < 55:
        sec = (ms.group(1) + ": " + ms.group(2)).strip().rstrip(":").strip()
        continue
    m = MARK.match(t)
    if m:
        flush()
        num = m.group(1)
        if m.group(2):                      # مكرر
            d = m.group(3)
            key = "m" + num + "mkr" + (DIST.get(d, d) if d else "")
        else:
            key = "m" + num
        cur = key
        cur_sec = sec                       # لقطة القسم عند بداية المادة
        order.append(key)
        buf = []
        continue
    if cur is not None:
        buf.append(t)
flush()

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

nums = [int(re.match(r'm(\d+)', k).group(1)) for k in arts]
print("objects:", len(arts), "| numeric max:", max(nums))
print("مكرر keys:", [k for k in arts if 'mkr' in k])
print("missing 1..max:", [n for n in range(1, max(nums) + 1) if n not in nums] or "none")
from collections import Counter
c = Counter(order)
print("dup keys:", [k for k, v in c.items() if v > 1] or "none")
print("empty:", [k for k in arts if not arts[k]["text"].strip()] or "none")
seen = []
for k in order:
    b = arts[k]["bab"]
    if b not in seen:
        seen.append(b)
print("\nالأقسام:")
for b in seen:
    ks = [k for k in order if arts[k]["bab"] == b]
    print(f"  {b} [{len(ks)}]: {ks[0]}..{ks[-1]}")
