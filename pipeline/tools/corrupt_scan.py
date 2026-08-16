# -*- coding: utf-8 -*-
import re, zipfile
from xml.etree import ElementTree as ET
W="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
def q(t): return W+t
path="/root/.claude/uploads/51a36a7b-3508-590f-af5f-27bfda80b244/2460e481-CMA_2_AR_2026_R80.docx"
root=ET.fromstring(zipfile.ZipFile(path).read("word/document.xml").decode())
body=root.find(q("body"))
paras=[]
for p in body.iter(q("p")):
    t="".join(x.text or "" for x in p.iter(q("t"))).strip()
    if t: paras.append(t)

ARABIC=re.compile(r"[؀-ۿ]")
LATIN=re.compile(r"[A-Za-z]")
def corrupt_score(t):
    if len(t)<8: return 0.0,{}
    words=t.split()
    ar=len(ARABIC.findall(t))
    latin=len(LATIN.findall(t))
    # single-letter arabic words (excluding و)
    singles=sum(1 for w in words if len(w)==1 and ARABIC.match(w) and w not in "وأفبلاي")
    # words containing arabic-indic digits mid-word
    digmid=sum(1 for w in words if re.search(r"[٠-٩]", w) and ARABIC.search(w))
    # punctuation-inside-word (dot/comma glued to arabic)
    glued=len(re.findall(r"[؀-ۿ][.,][؀-ۿ]", t))
    frac_single=singles/max(1,len(words))
    flags={"latin":latin,"singles":singles,"digmid":digmid,"glued":glued,"frac_single":round(frac_single,2)}
    score=0
    if latin>0: score+=2
    if frac_single>0.25: score+=2
    if digmid>0: score+=1
    if glued>=2: score+=1
    return score, flags

sus=[]
for i,t in enumerate(paras):
    s,fl=corrupt_score(t)
    if s>=2: sus.append((i,s,t,fl))
print(f"total non-empty paras: {len(paras)}")
print(f"suspicious (score>=2): {len(sus)}")
print("\n-- sample suspicious paragraphs --")
for i,s,t,fl in sus[:40]:
    print(f"[{i}] score={s} {fl}\n     {t[:90]}")
