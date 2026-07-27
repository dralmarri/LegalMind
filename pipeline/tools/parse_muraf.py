#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محلّل متين لقانون المرافعات 38/1980 من muraf.docx.
كشف بمطابقة الرقم المتوقَّع (يعالج التصاق «نصّمادة N» + الإشارات النصّية)، مع تتبّع كتاب/باب/فصل."""
import zipfile, re, json, sys
SRC = sys.argv[1] if len(sys.argv) > 1 else "muraf/muraf.docx"
OUT = sys.argv[2] if len(sys.argv) > 2 else "muraf_parsed.json"

xml = zipfile.ZipFile(SRC).read("word/document.xml").decode("utf-8")
paras = []
for pm in re.finditer(r"<w:p\b.*?</w:p>", xml, re.S):
    t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", pm.group(0), re.S))
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    if t.strip():
        paras.append(t)
TR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
paras = [p.translate(TR).replace("﻿","").replace("‏","").replace("‎","").replace("ی","ي").replace("ک","ك") for p in paras]

def h(s): return re.sub(r"[أإآ]","ا", re.sub(r"[ىی]","ي", s)).replace("ة","ه")
STRUCT = re.compile(r"^\s*(الكتاب|الباب|الفصل)\b")
# علامة مادة في أي موضع: «(ال)مادة N [مكرر]»
MADA = re.compile(r"(?:ال)?ماده\s*(\d+)\s*(مكررا?)?")

arts = {}; order = []; arts_title = {}
cur = None; buf = []; cur_ctx = {"kitab":None,"bab":None,"fasl":None}
expected = 1; last_base = 0

def flush():
    if cur is not None:
        arts[cur] = {"ctx": dict(pending_ctx[cur]),
                     "text": "\n".join(x for x in buf if x.strip()).strip()}
pending_ctx = {}
def start(key):
    global cur, buf
    flush(); cur = key; order.append(key); pending_ctx[key] = dict(cur_ctx); buf = []

i = 0
# تجاوز الديباجة حتى «المادة 1»
while i < len(paras):
    s = paras[i].strip()
    if STRUCT.match(h(s)):
        lvl = h(s).split()[0]
        title = s
        if i+1 < len(paras) and len(paras[i+1]) < 60 and not MADA.match(h(paras[i+1].strip())) and not STRUCT.match(h(paras[i+1].strip())):
            title = s + " " + paras[i+1].strip(); i += 1
        if lvl == "الكتاب": cur_ctx = {"kitab":title,"bab":None,"fasl":None}
        elif lvl == "الباب": cur_ctx = {"kitab":cur_ctx["kitab"],"bab":title,"fasl":None}
        else: cur_ctx = {"kitab":cur_ctx["kitab"],"bab":cur_ctx["bab"],"fasl":title}
        i += 1; continue
    m = None
    for mm in MADA.finditer(h(paras[i])):
        num = int(mm.group(1)); mkr = mm.group(2)
        if mkr and num == last_base: m = mm; break
        if (not mkr) and num == expected: m = mm; break
    if m:
        raw = paras[i]
        pre = raw[:m.start()].strip()
        title = None
        if pre:
            buf.append(pre)
        elif buf:
            # عنوان جانبي يسبق «المادة N»: سطر قصير بلا نهاية جملة، ويسبقه سطرٌ منتهٍ بعلامة نهاية
            # (أي أن المادة السابقة أُغلقت فعلًا) — تمييزًا له عن سطر استكمالٍ قصير للمادة السابقة.
            cand = buf[-1].strip()
            prev_closed = (len(buf) >= 2 and buf[-2].strip()[-1:] in '.؛»):!؟"')
            if prev_closed and 0 < len(cand) <= 70 and cand[-1] not in '.؛»):!؟"،' and not STRUCT.match(h(cand)):
                title = buf.pop()
        num = m.group(1); mkr = m.group(2)
        if mkr: key = "m"+num+"mkr"
        else: key = "m"+num; last_base = int(num); expected = int(num)+1
        start(key)
        arts_title[key] = title
        post = raw[m.end():].strip()
        if post: buf.append(post)
        i += 1; continue
    if cur is not None: buf.append(paras[i])
    i += 1
flush()

def clean(t):
    t = t.replace("�","")
    t = re.sub(r"\)\)\s*(.+?)\s*\(\(", r"«\1»", t, flags=re.S)
    t = re.sub(r"\)\s*([ء-ي0-9][^()]{0,200}?)\s*\(", lambda m:"("+re.sub(r"\s+"," ",m.group(1)).strip()+")", t, flags=re.S)
    out=[]
    for ln in t.split("\n"):
        if re.fullmatch(r"\s*[)(]+\s*", ln): continue
        out.append(ln)
    t="\n".join(out)
    t=t.replace(")))","").replace("(((","")
    t=re.sub(r"ًً+","ً",t)
    return re.sub(r"[ \t]{2,}"," ",t).strip()

for k in arts: arts[k]["text"]=clean(arts[k]["text"])
json.dump({"articles":{k:arts[k]["text"] for k in order},
           "titles":{k:arts_title.get(k) for k in order},
           "ctx":{k:arts[k]["ctx"] for k in order},"order":order},
          open(OUT,"w",encoding="utf-8"), ensure_ascii=False, indent=1)

nums=sorted(int(re.match(r"m(\d+)",k).group(1)) for k in order)
print("مواد:",len(order),"| المدى:",min(nums),"-",max(nums))
print("ناقص:",[n for n in range(min(nums),max(nums)+1) if n not in nums] or "لا")
print("مكرر:",[k for k in order if "mkr" in k])
# فحص الاجتزاع: مواد لا تنتهي بعلامة نهاية (عدا استثناءات)
TERM=set('.؛»):!؟"'); bad=[]
for k in order:
    t=arts[k]["text"].strip()
    if t and t[-1] not in TERM and not re.search(r"\d\s*[مه]$",t): bad.append(k)
print("مشتبه اجتزاعها:",len(bad),bad[:20])
print("\n--- عيّنات ---")
for k in ("m1","m9","m108","m123","m164","m316" if 316 in nums else order[-1]):
    if k in arts: print(f"[{k}] {arts[k]['text'][:120]}")
