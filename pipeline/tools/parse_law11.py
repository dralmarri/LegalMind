#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محلّل مرسوم بقانون 11/2026 الحماية من العنف الأسري (جرائم أمن الدولة + الرشوة).
3 مواد إصدار بصيغة ترتيبية (أولى/ثانية/ثالثة) + 61 مادة (م1-61) في بابين وفصول.
يعالج صيغ الرأس المرنة، شوائب )))، ويلتقط عناوين البنية، وينظّف عناوين الأقسام الفرعية العالقة."""
import zipfile, re, json, sys
from collections import Counter

SRC = sys.argv[1] if len(sys.argv) > 1 else "law_new.docx"
OUT = sys.argv[2] if len(sys.argv) > 2 else "law11_parsed.json"

xml = zipfile.ZipFile(SRC).read("word/document.xml").decode("utf-8")
paras = []
for pm in re.finditer(r"<w:p\b.*?</w:p>", xml, re.S):
    t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", pm.group(0), re.S))
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    if t.strip():
        paras.append(t)
TR = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
paras = [p.translate(TR).replace("﻿", "").replace("‏", "").replace("‎", "")
         .replace("ی", "ي").replace("ک", "ك").replace("ھ", "ه") for p in paras]

HDR = re.compile(r'^\s*(?:ال)?م?ادة\s+(\d+)\s*(مكرر\w*)?\s*[)\(]*\s*$')
_ORD = {"اولى": 1, "أولى": 1, "ثانية": 2, "ثانيه": 2, "ثالثة": 3, "ثالثه": 3,
        "رابعة": 4, "رابعه": 4, "خامسة": 5, "خامسه": 5}
ORDHDR = re.compile(r'^\s*(?:ال)?م?ادة\s+(' + "|".join(_ORD) + r')\s*:?\s*$')
_STRUCT = re.compile(r'^\s*(الكتاب|الباب|الفصل|الفرع)\b')
TERMSET = set('.؛!؟»)')


def STRUCT_match(s):
    return _STRUCT.match(s) and len(s.strip()) < 50


bound = next(i for i, p in enumerate(paras) if HDR.match(p.strip()))

order = []
arts = {}


def add(key, sec):
    if key in arts:
        key = key + "_dup"
    order.append(key)
    arts[key] = {"text": [], "sec": sec, "mukarrar": "mukarrar" in key}
    return key


# --- مواد الإصدار الترتيبية (قبل الحدود) ---
cur = None
for i in range(bound):
    s = paras[i].strip()
    mo = ORDHDR.match(s)
    if mo:
        cur = add("iss" + str(_ORD[mo.group(1)]), None); continue
    if cur and s and not STRUCT_match(s):
        arts[cur]["text"].append(paras[i])

# --- القانون (بابان/فصول) ---
cur = None
sec = None
i = bound
while i < len(paras):
    s = paras[i].strip()
    if STRUCT_match(s):
        cur = None
        title = [s]
        j = i + 1
        while j < len(paras):
            nxt = paras[j].strip()
            if HDR.match(nxt) or STRUCT_match(nxt) or len(nxt) >= 60:
                break
            title.append(nxt); j += 1
        sec = " / ".join(title)
        i = j
        continue
    m = HDR.match(s)
    if m:
        cur = add("m" + m.group(1) + ("-mukarrar" if m.group(2) else ""), sec)
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


_SIG = re.compile(r'نائب أمير الكويت|^\s*أمير الكويت\s*$|صدر في قصر|بقصر السيف|الموافق\s+\d|جابر الأحمد الصباح')
_EXEC = re.compile(r'على رئيس مجلس الوزراء.*تنفيذ هذا القانون')


def clean(lines, is_iss=False):
    txt = "\n".join(x for x in lines if x.strip()).strip()
    txt = txt.replace("�", "")
    # اقطع كتلة التوقيع/الختام المُتسرّبة (وبند التنفيذ في غير مواد الإصدار — فهو iss3)
    ll = txt.split("\n"); cut = None
    for _i, _ln in enumerate(ll):
        if _SIG.search(_ln) or ((not is_iss) and _EXEC.search(_ln)):
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
    txt = re.sub(r'[ \t]{2,}', ' ', txt).strip()
    txt = strip_trailing_subsections(txt)
    if re.sub(r'[)\(«»\s\.]', '', txt) in ("ملغاة", "ملغاه", "ملغى", "ملغية", "ملغيه"):
        return "(ملغاة)"
    return txt


for k in list(arts):
    arts[k]["text"] = clean(arts[k]["text"], k.startswith("iss"))

json.dump({"articles": {k: arts[k] for k in order}, "order": order},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

iss = [k for k in order if k.startswith("iss")]
main = [k for k in order if k.startswith("m")]
base = sorted(int(re.match(r'm(\d+)', k).group(1)) for k in main if "mukarrar" not in k)
missing = [n for n in range(1, max(base) + 1) if n not in base]
rep = [k for k in main if arts[k]["text"] == "(ملغاة)"]
empty = [k for k in arts if not arts[k]["text"].strip()]
print("=== مرسوم بقانون 11/2026 (الحماية من العنف الأسري) ===")
print(f"إصدار: {iss} | رئيسية: {len(main)} | النطاق: {min(base)}..{max(base)} | مفقودة: {missing}")
print(f"ملغاة: {len(rep)} | فارغة: {empty or 'لا'} | تكرار: {[k for k,v in Counter(order).items() if v>1] or 'لا'}")
for k in ("m1", "m2", "m20", "m21", "m30", "m31"):
    if k in arts:
        print(f"\n--- {k} (sec={arts[k]['sec']}) ---\n{arts[k]['text'][:160]}")
