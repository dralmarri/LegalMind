#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محلّل المرسوم بالقانون رقم 23 لسنة 1990 بشأن تنظيم القضاء.
مواد إصدار (م1-5) ثم القانون المرافق (م1-74 + مكرر) في ستة أبواب وفصولها.
يعالج العلامات المدمجة داخل الفقرة («…رئيسمادة 14») بالتحقق من الرقم المتوقَّع."""
import zipfile, re, json, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "adm8.docx"
OUT = sys.argv[2] if len(sys.argv) > 2 else "adm8_parsed.json"

xml = zipfile.ZipFile(SRC).read("word/document.xml").decode("utf-8")
paras = []
for pm in re.finditer(r"<w:p\b.*?</w:p>", xml, re.S):
    p = pm.group(0)
    t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    if t.strip():
        paras.append(t)

TR = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
paras = [p.translate(TR).replace("﻿", "").replace("‏", "").replace("‎", "") for p in paras]

ORD = ("الاول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس",
       "السابع", "الثامن", "التاسع", "العاشر")
def _h(s):
    return re.sub(r'[أإآ]', 'ا', re.sub(r'[ىی]', 'ي', s))
_ORDX = "|".join(ORD)
BAB = re.compile(r'^\s*الباب\s+(' + _ORDX + r')\b\s*[:：]?\s*(.*)$')
FASL = re.compile(r'^\s*الفصل\s+(' + _ORDX + r')\b\s*[:：]?\s*(.*)$')
# any "مادة N [مكرر]" occurrence
MADA = re.compile(r'(?:ال)?مادة\s*(\d+)\s*(مكررا?)?')

# boundary: first "الباب الأول"
boundary = next((i for i, t in enumerate(paras) if BAB.match(_h(t.strip())) and "الاول" in _h(t)),
                len(paras))

arts = {}
order = []
cur = None
cur_bab = None
cur_fasl = None
bab = None
fasl = None
buf = []
last_base = 0
expected = 1

def flush():
    if cur is not None:
        arts[cur] = {"bab": cur_bab, "fasl": cur_fasl, "issuing": str(cur).startswith("iss"),
                     "text": "\n".join(x for x in buf if x.strip()).strip()}

def start(key, is_iss):
    global cur, cur_bab, cur_fasl, buf
    flush()
    cur = key
    cur_bab = None if is_iss else bab
    cur_fasl = None if is_iss else fasl
    order.append(key)
    buf = []

i = 0
_reset_done = False
while i < len(paras):
    t = paras[i]
    issuing = i < boundary
    if (not issuing) and (not _reset_done):
        expected = 1; last_base = 0; _reset_done = True   # القانون المرافق يبدأ ترقيمه من 1
    _ = None
    if not issuing:
        hb = _h(t.strip()); mb = BAB.match(hb); mf = FASL.match(hb)
        if mb or mf:
            # title: inline after ':' if present, else next short line
            raw = t.strip()
            m2 = re.match(r'^\s*ال(?:باب|فصل)\s+\S+\b\s*[:：]?\s*(.*)$', raw)
            title = raw
            inline = (m2.group(1).strip() if m2 else "")
            if inline:
                title = raw
            elif i + 1 < len(paras) and len(paras[i + 1]) < 55 \
                 and not MADA.search(paras[i + 1]) \
                 and not BAB.match(_h(paras[i + 1].strip())) and not FASL.match(_h(paras[i + 1].strip())):
                title = raw + ": " + paras[i + 1].strip()
                i += 1
            if mb:
                bab = title; fasl = None
            else:
                fasl = title
            i += 1
            continue
    # scan for a marker whose number matches expected (normal) or last_base (مكرر)
    m = None
    for mm in MADA.finditer(t):
        num = int(mm.group(1)); mkr = mm.group(2)
        if issuing:
            if num == expected and not mkr:
                m = mm; break
        else:
            if mkr and num == last_base:
                m = mm; break
            if (not mkr) and num == expected:
                m = mm; break
    if m:
        pre = t[:m.start()].strip()
        if pre:
            buf.append(pre)
        num = m.group(1); mkr = m.group(2)
        if issuing:
            key = "iss" + num; expected += 1
        elif mkr:
            key = "m" + num + "mkr"
        else:
            key = "m" + num; last_base = int(num); expected = int(num) + 1
        start(key, issuing)
        post = t[m.end():].strip()
        if post:
            buf.append(post)
        i += 1
        continue
    if cur is not None:
        buf.append(t)
    i += 1
flush()

def clean(txt):
    txt = txt.replace("�", "")
    txt = re.sub(r'\)([ء-ي][^()]{0,160}?)\(', r'(\1)', txt, flags=re.S)   # قلب قوس بايدي
    out = []
    for ln in txt.split("\n"):
        if re.match(r'^\s*[)(]+\s*$', ln):        # سطر شوائب أقواس فقط (بقايا العلامة)
            continue
        ln = re.sub(r'^\s*-\s*(\d+)\s*[-–]?\s*', r'\1. ', ln)
        ln = re.sub(r'^\s*(\d+)\s*[-–]\s*', r'\1. ', ln)
        out.append(ln)
    txt = "\n".join(out); txt = re.sub(r'ًً+', 'ً', txt)
    txt = re.sub(r'\)([ء-ي])', r'\1', txt)   # قوس شارد ملتصق بحرف بعد قلب الأقواس المطابقة
    return re.sub(r'[ \t]{2,}', ' ', txt).strip()

for k in arts:
    arts[k]["text"] = clean(arts[k]["text"])

json.dump({"articles": arts, "order": order},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

iss = [k for k in order if k.startswith("iss")]
main = [k for k in order if not k.startswith("iss")]
mnums = sorted(int(re.match(r'm(\d+)', k).group(1)) for k in main)
print("objects:", len(arts), "| issuing:", len(iss), "| main:", len(main))
print("main max:", max(mnums), "| missing:", [n for n in range(1, max(mnums) + 1) if n not in mnums] or "none")
print("مكرر:", [k for k in main if 'mkr' in k])
from collections import Counter
c = Counter(order)
print("dups:", [k for k, v in c.items() if v > 1] or "none")
print("empty:", [k for k in arts if not arts[k]["text"].strip()] or "none")
seen = []
for k in order:
    b = arts[k]["bab"]
    if b not in seen:
        seen.append(b)
print("\nأبواب:")
for b in seen:
    ks = [k for k in order if arts[k]["bab"] == b]
    print(f"  {str(b)[:55]} [{len(ks)}]: {ks[0]}..{ks[-1]}")
