#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import zipfile, re, html, json

AR2W = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
def nd(s): return s.translate(AR2W)

z = zipfile.ZipFile('lab3.docx')
xml = z.read('word/document.xml').decode('utf-8')
paras = re.split(r'</w:p>', xml)
lines = []
for p in paras:
    texts = re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S)
    line = html.unescape(''.join(texts)).strip()
    if line:
        lines.append(line)

def clean(l):
    l = re.sub(r'\)\)+', '', l); l = re.sub(r'\(\(+', '', l)
    return l.strip()

# Insert a line break before any inline "مادة <digits>" that is not "المادة"
# (article boundary markers), so they start a new line.
marker = re.compile(r'(?<!ال)(?<![^\s.،؛])?مادة\s+([0-9٠-٩]{1,3})(?=\s|$)')
proc = []
for raw in lines:
    l = clean(raw)
    # split inline markers: put newline before a bare "مادة N" if preceded by content
    l2 = re.sub(r'(.+?)(?<![ال])\bمادة\s+([0-9٠-٩]{1,3})\b',
                lambda m: m.group(1).rstrip() + "\n" + "مادة " + m.group(2)
                          if m.group(1).strip() else "مادة " + m.group(2),
                l)
    for part in l2.split("\n"):
        part=part.strip()
        if part: proc.append(part)

art_re  = re.compile(r'^(?:مادة|المادة)\s+([0-9٠-٩]+)\s*(.*)$')
bab_re  = re.compile(r'^الباب\s')
fasl_re = re.compile(r'^الفصل\s')

articles={}; order=[]; cur_bab=None; cur_fasl=None; cur=None; buf=[]
def flush():
    global cur,buf
    if cur is not None:
        articles[cur]["text"]="\n".join(x for x in buf if x).strip()
    buf=[]
for l in proc:
    ma=art_re.match(l)
    if ma:
        flush()
        num=nd(ma.group(1)); cur=num
        articles[num]={"bab":cur_bab,"fasl":cur_fasl,"text":""}
        order.append(num)
        buf=[ma.group(2).strip()] if ma.group(2).strip() else []
        continue
    if bab_re.match(l):
        flush(); cur=None; cur_bab=l; cur_fasl=None; continue
    if fasl_re.match(l):
        flush(); cur=None; cur_fasl=l; continue
    buf.append(l)
flush()

nums=sorted(int(n) for n in articles)
missing=[i for i in range(1,nums[-1]+1) if i not in nums]
print("articles:",len(articles),"| range",nums[0],"-",nums[-1],"| missing:",missing)
for n in ["8","9","10"]:
    a=articles.get(n)
    print(f"\n--- مادة {n} (bab={a['bab']}) ---\n{a['text'][:200]}" if a else f"م{n} missing")
json.dump({"articles":articles,"order":order}, open('lab3_parsed.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)

# --- post-process: normalize bullets and Arabic-Indic digits in body, tidy ---
import json as _j
data=_j.load(open('lab3_parsed.json',encoding='utf-8'))
def tidy(t):
    lines=t.split("\n")
    out=[]
    for ln in lines:
        ln=ln.strip()
        # "-1 " or "- 1 " bullet at start -> "1. "
        m=re.match(r'^-\s*([0-9٠-٩]+)\s+(.*)$', ln)
        if m: ln=f"{nd(m.group(1))}. {m.group(2)}"
        out.append(ln)
    # rejoin, then merge wrapped lines (lines not ending with . and next not a bullet) lightly
    return "\n".join(x for x in out if x)
for n,a in data["articles"].items():
    a["text"]=tidy(a["text"])
_j.dump(data, open('lab3_parsed.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print("tidied.")
print("\n=== مادة 1 ===")
print(data["articles"]["1"]["text"][:600])
print("\n=== مادة 40 ===")
print(data["articles"]["40"]["text"][:400])
empty=[n for n,a in data["articles"].items() if not a["text"].strip()]
print("\nempty:",empty or "none")
