#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محلّل المرسوم بالقانون رقم 40 لسنة 1980 بإصدار قانون تنظيم الخبرة.
4 مواد إصدار (م1-4) ثم القانون المرافق (م1-54) في فصول، مع مواد ملغاة (26، 27).
يعتمد كشف العناوين على أسطر مستقلّة + مطابقة الرقم المتوقَّع (لإصلاح تشتّت الأرقام «6 2»→26)."""
import zipfile, re, json, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "adm12.docx"
OUT = sys.argv[2] if len(sys.argv) > 2 else "adm12_parsed.json"

xml = zipfile.ZipFile(SRC).read("word/document.xml").decode("utf-8")
paras = []
for pm in re.finditer(r"<w:p\b.*?</w:p>", xml, re.S):
    p = pm.group(0)
    t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    if t.strip():
        paras.append(t)

TR = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
paras = [p.translate(TR).replace("﻿", "").replace("‏", "").replace("‎", "")
         .replace("ی", "ي").replace("ک", "ك").replace("ھ", "ه") for p in paras]

# سطر عنوان مادة مستقلّ (قد يحمل أرقامًا مبعثرة بمسافات و«)))»)
HDR = re.compile(r'^\s*(?:ال)?مادة\s+([\d\s]+?)\s*[)\(]*\s*$')
FASL = re.compile(r'^\s*(الفصل|الباب)\s')

# حدود القانون المرافق: أول «الفصل الأول»
boundary = next(i for i, t in enumerate(paras) if FASL.match(t.strip()) and "الاول" in
                re.sub(r'[أإآ]', 'ا', re.sub(r'[ىی]', 'ي', t)))

order = []
arts = {}
cur = None
buf = []
cur_fasl = None

def flush():
    if cur is not None:
        arts[cur] = {"issuing": str(cur).startswith("iss"), "fasl": arts.get(cur, {}).get("fasl"),
                     "text": "\n".join(x for x in buf if x.strip()).strip()}
        arts[cur]["fasl"] = _pending_fasl.get(cur)

def start(key):
    global cur, buf
    flush()
    cur = key
    order.append(key)
    _pending_fasl[key] = cur_fasl
    buf = []

_pending_fasl = {}

def hdr_num(digits, expected):
    """يعيد رقم المادة من مجموعة أرقام قد تكون مبعثرة/معكوسة، بمطابقة المتوقَّع."""
    d = re.sub(r"\s+", "", digits)
    if not d:
        return None
    if int(d) == expected:
        return expected
    if int(d[::-1]) == expected:          # «62» ← «26»
        return expected
    return int(d)                          # احتياط: الرقم كما هو

# --- مواد الإصدار (قبل الحدود) ---
exp = 1
i = 0
while i < boundary:
    m = HDR.match(paras[i].strip())
    if m:
        n = hdr_num(m.group(1), exp)
        if n == exp:
            start("iss" + str(n)); exp += 1; i += 1; continue
    if cur is not None:
        buf.append(paras[i])
    i += 1
flush(); cur = None; buf = []

# --- القانون المرافق ---
exp = 1
i = boundary
while i < len(paras):
    s = paras[i].strip()
    if FASL.match(s):
        title = s
        if i + 1 < len(paras) and len(paras[i + 1]) < 40 and not HDR.match(paras[i + 1].strip()):
            title = s + " — " + paras[i + 1].strip(); i += 1
        cur_fasl = title
        i += 1
        continue
    m = HDR.match(s)
    if m:
        n = hdr_num(m.group(1), exp)
        if n == exp:
            start("m" + str(n)); exp += 1; i += 1; continue
    if cur is not None:
        buf.append(paras[i])
    i += 1
flush()

def clean(txt):
    txt = txt.replace("�", "")
    txt = re.sub(r'\)\)\s*(.+?)\s*\(\(', r'«\1»', txt, flags=re.S)              # اقتباس مزدوج معكوس
    txt = re.sub(r'\)\s*([ء-ي0-9][^()]{0,200}?)\s*\(',
                 lambda m: '(' + re.sub(r'\s+', ' ', m.group(1)).strip() + ')', txt, flags=re.S)
    out = []
    for ln in txt.split("\n"):
        if re.match(r'^\s*[)(]+\s*$', ln):
            continue
        ln = re.sub(r'^\s*-\s*(\d+)\s*[-–]?\s*', r'\1. ', ln)
        ln = re.sub(r'^\s*(\d+)\s*[-–]\s*', r'\1. ', ln)
        out.append(ln)
    txt = "\n".join(out)
    txt = re.sub(r'ًً+', 'ً', txt)
    txt = re.sub(r'([ء-ي])\)\s*\(', r'\1 (', txt)
    txt = re.sub(r'\)([ء-ي])', r'\1', txt)
    if re.sub(r'[)\(«»\s]', '', txt) == "ملغاة":
        return "(ملغاة)"
    return re.sub(r'[ \t]{2,}', ' ', txt).strip()

for k in arts:
    arts[k]["text"] = clean(arts[k]["text"])

json.dump({"articles": arts, "order": order},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

iss = [k for k in order if k.startswith("iss")]
main = [k for k in order if k.startswith("m")]
mnums = sorted(int(k[1:]) for k in main)
print("objects:", len(arts), "| issuing:", iss, "| main:", len(main))
print("main nums:", mnums)
print("missing:", [n for n in range(1, max(mnums) + 1) if n not in mnums] or "none")
print("ملغاة:", [k for k in main if arts[k]["text"] == "(ملغاة)"])
from collections import Counter
c = Counter(order)
print("dups:", [k for k, v in c.items() if v > 1] or "none")
print("empty:", [k for k in arts if not arts[k]["text"].strip()] or "none")
fs = []
for k in order:
    f = arts[k].get("fasl")
    if f and f not in fs:
        fs.append(f)
print("\nفصول:")
for f in fs:
    ks = [k for k in order if arts[k].get("fasl") == f]
    print(f"  {f[:55]} [{len(ks)}]: {ks[0]}..{ks[-1]}")
