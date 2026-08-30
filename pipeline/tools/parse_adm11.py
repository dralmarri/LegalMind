#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محلّل القانون رقم 42 لسنة 1964 في شأن تنظيم مهنة المحاماة أمام المحاكم.
مادتان إصداريتان (أولى/ثانية) ثم القانون المرافق: م1..م46 ببنية مسطّحة،
مع مكرر (5مكرر، 6مكررا، 11مكرر)، ومواد ملغاة (4، 5، 5مكرر، 8)، وفجوة في الترقيم (26-31).
الكشف يعتمد على أسطر العناوين المستقلّة فقط، لتفادي الإشارات النصّية («المادة 108 من قانون المرافعات»)."""
import zipfile, re, json, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "adm11.docx"
OUT = sys.argv[2] if len(sys.argv) > 2 else "adm11_parsed.json"

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

# سطر عنوان مادة مستقلّ: «(ال)مادة N [مكرر[ا]] [(حرف)]» مع تجاهل شوائب «)))» ومسافات
HDR = re.compile(
    r'^\s*(?:ال)?مادة\s+(\d+)\s*(مكررا?)?\s*'
    r'(?:[)\(]\s*([أ-ي])\s*[)\(])?\s*[)\(]*\s*$')
_LETMAP = {"أ": "a", "ا": "a", "ب": "b", "ج": "c", "د": "d"}
# مادتا الإصدار بصيغة الترتيب
ISS = re.compile(r'^\s*مادة\s+(أولى|اولى|ثانية|ثانيه)\s*[)\(]*\s*$')

# حدود القانون المرافق: أول سطر «المادة 1»
boundary = next(i for i, t in enumerate(paras) if HDR.match(t) and HDR.match(t).group(1) == "1")

order = []
arts = {}
cur = None
buf = []

def flush():
    if cur is not None:
        arts[cur] = {"issuing": str(cur).startswith("iss"),
                     "text": "\n".join(x for x in buf if x.strip()).strip()}

def start(key):
    global cur, buf
    flush()
    cur = key
    order.append(key)
    buf = []

# --- مواد الإصدار (قبل الحدود) ---
i = 0
while i < boundary:
    m = ISS.match(paras[i])
    if m:
        o = m.group(1)
        key = "issawla" if o in ("أولى", "اولى") else "issthania"
        start(key)
        i += 1
        continue
    if cur is not None:
        buf.append(paras[i])
    i += 1
flush(); cur = None; buf = []

# --- القانون المرافق ---
i = boundary
while i < len(paras):
    m = HDR.match(paras[i])
    if m:
        num, mkr, let = m.group(1), m.group(2), m.group(3)
        key = "m" + num + ("mkr" if mkr else "") + (_LETMAP.get(let, "") if let else "")
        start(key)
        i += 1
        continue
    if cur is not None:
        buf.append(paras[i])
    i += 1
flush()

def clean(txt):
    txt = txt.replace("�", "")
    # علامات اقتباس بأقواس مزدوجة معكوسة بايديًّا: «)) نص ((» → «نص» (قبل قلب الأقواس المفردة)
    txt = re.sub(r'\)\)\s*(.+?)\s*\(\(', r'«\1»', txt, flags=re.S)
    # قلب الأقواس المعكوسة بايديًّا: «) أ (» → «(أ)»، «) 14 (» → «(14)»، مع تشذيب المسافات الداخلية
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
    txt = re.sub(r'([ء-ي])\)\s*\(', r'\1 (', txt)   # قوس إغلاق شارد محشور بين كلمة وقوس فتح
    txt = re.sub(r'\)([ء-ي])', r'\1', txt)
    # مادة ملغاة: النصّ فعليًّا «)) ملغاة ((» (وقد تحوّل إلى «ملغاة» بقاعدة الاقتباس)
    if re.sub(r'[)\(«»\s]', '', txt) == "ملغاة":
        return "(ملغاة)"
    return re.sub(r'[ \t]{2,}', ' ', txt).strip()

for k in arts:
    arts[k]["text"] = clean(arts[k]["text"])

# م25: إزالة شظية يتيمة من المواد الملغاة 26-31 («المدة بكتاب موصى عليه ... مدة السقوط ...»)
if "m25" in arts:
    t = arts["m25"]["text"]
    cut = t.find("المدة بكتاب موصى")
    if cut != -1:
        arts["m25"]["text"] = t[:cut].strip()

json.dump({"articles": arts, "order": order},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

main = [k for k in order if not k.startswith("iss")]
mnums = sorted({int(re.match(r'm(\d+)', k).group(1)) for k in main})
print("objects:", len(arts), "| issuing:", [k for k in order if k.startswith("iss")], "| main:", len(main))
print("main nums:", mnums)
print("مكرر:", [k for k in main if 'mkr' in k])
print("ملغاة:", [k for k in main if arts[k]["text"] == "(ملغاة)"])
from collections import Counter
c = Counter(order)
print("dups:", [k for k, v in c.items() if v > 1] or "none")
print("empty:", [k for k in arts if not arts[k]["text"].strip()] or "none")
print("\n--- sample bodies ---")
for k in ("issawla", "issthania", "m1", "m6mkr", "m25", "m32", "m46"):
    if k in arts:
        print(f"[{k}] {arts[k]['text'][:150]}")
