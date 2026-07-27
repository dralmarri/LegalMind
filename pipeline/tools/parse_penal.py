#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محلّل قانون الجزاء رقم 16 لسنة 1960: مادتا إصدار + القانون المرافق (م1..286 + مكرر)
في كتب/أبواب/فصول. يعالج صيغ الرأس المرنة (مادة/المادة/ادة)، شوائب )))، المواد الملغاة،
ويلتقط عناوين البنية. المواد الفرعية («-1 ...») العالقة تُنظَّف لاحقًا بخط أنابيب التدقيق."""
import zipfile, re, json, sys
from collections import Counter

SRC = sys.argv[1] if len(sys.argv) > 1 else "newlaw.docx"
OUT = sys.argv[2] if len(sys.argv) > 2 else "penal_parsed.json"

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
_STRUCT = re.compile(r'^\s*(الكتاب|الباب|الفصل|الفرع)\b')


def STRUCT_match(s):
    # رأس بنية حقيقيّ: يبدأ بكلمة البنية وقصير (يستبعد الإحالات وسط الجملة «...في الباب الثامن، ...»)
    return _STRUCT.match(s) and len(s.strip()) < 45


def ismul(p):
    return re.sub(r'[)\(\s]', '', p) in ("ملغاة", "ملغاه", "ملغى")


bound = next(i for i, p in enumerate(paras) if p.strip().startswith("الكتاب الأول"))

order = []
arts = {}


def add(key, sec):
    if key in arts:
        key = key + "_dup"
    order.append(key)
    arts[key] = {"text": [], "sec": sec, "mukarrar": "mukarrar" in key}
    return key


# --- مواد الإصدار (قبل الحدود) ---
cur = None
for i in range(bound):
    s = paras[i].strip()
    m = HDR.match(s)
    if m and not STRUCT_match(s):
        cur = add("iss" + m.group(1), None); continue
    if cur and s:
        arts[cur]["text"].append(paras[i])

# --- القانون المرافق ---
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
        key = "m" + m.group(1) + ("-mukarrar" if m.group(2) else "")
        cur = add(key, sec)
        i += 1
        continue
    if cur:
        arts[cur]["text"].append(paras[i])
    i += 1


TERMSET = set('.؛!؟»)')


def strip_trailing_subsections(txt):
    """يزيل عناوين الأقسام الفرعية العالقة في الذيل (سطر قصير بلا ختام يعقب سطرًا منتهيًا بختام،
    وليس بندًا مرقّمًا/حرفيًّا داخل المادة)."""
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


def clean(lines):
    txt = "\n".join(x for x in lines if x.strip()).strip()
    txt = txt.replace("�", "")
    out = []
    for ln in txt.split("\n"):
        if re.match(r'^\s*[)(]{1,}\s*$', ln):        # سطر أقواس مستقلّ
            continue
        ln = re.sub(r'\s*\){2,}\s*$', '', ln)         # ))) ذيلية
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
    arts[k]["text"] = clean(arts[k]["text"])

# تقرير
iss = [k for k in order if k.startswith("iss")]
main = [k for k in order if k.startswith("m")]
base = sorted(int(re.match(r'm(\d+)', k).group(1)) for k in main if "mukarrar" not in k)
mk = [k for k in main if "mukarrar" in k]
missing = [n for n in range(1, max(base) + 1) if n not in base]
repealed = [k for k in main if arts[k]["text"] == "(ملغاة)"]
empty = [k for k in arts if not arts[k]["text"].strip()]
dup = [k for k in order if k.endswith("_dup")]

json.dump({"articles": {k: arts[k] for k in order}, "order": order},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("=== قانون الجزاء 16/1960 ===")
print(f"مواد إصدار: {iss}")
print(f"مواد رئيسية: {len(main)} (أساسية فريدة {len(base)} + مكرر {len(mk)})")
print(f"النطاق: {min(base)}..{max(base)} | مفقودة: {missing}")
print(f"مكرر: {mk}")
print(f"ملغاة: {len(repealed)}")
print(f"فارغة: {empty or 'لا'} | مفاتيح مكرّرة: {dup or 'لا'}")
c = Counter(order)
print(f"تكرار المفاتيح: {[k for k,v in c.items() if v>1] or 'لا'}")
# عيّنات
for k in ("iss1", "m1", "m18", "m57", "m164-mukarrar", "m286"):
    if k in arts:
        print(f"\n--- {k} (sec={arts[k]['sec']}) ---\n{arts[k]['text'][:180]}")
