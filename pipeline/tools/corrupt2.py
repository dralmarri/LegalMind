# -*- coding: utf-8 -*-
import re, zipfile
from xml.etree import ElementTree as ET
W="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
def q(t): return W+t
path="/root/.claude/uploads/51a36a7b-3508-590f-af5f-27bfda80b244/2460e481-CMA_2_AR_2026_R80.docx"
root=ET.fromstring(zipfile.ZipFile(path).read("word/document.xml").decode())
body=root.find(q("body"))
ART=re.compile(r"^(?:المادة|مادة)\s+(\d+(?:-\d+)+)\s*$")
paras=[]
for p in body.iter(q("p")):
    t="".join(x.text or "" for x in p.iter(q("t"))).strip()
    paras.append(t)

ARW=re.compile(r"[؀-ۿ]")
def is_marker(t): return bool(ART.match(t))
def bad(t):
    if len(t)<10: return None
    reasons=[]
    if re.search(r"[؀-ۿ][A-Za-z]|[A-Za-z][؀-ۿ]", t): reasons.append("latin-in-word")
    if re.search(r"\b[A-Za-z]\b", t) and ARW.search(t): reasons.append("stray-latin")
    words=t.split()
    if any(len(w)>=20 and ARW.search(w) for w in words): reasons.append("glued-word")
    singles=sum(1 for w in words if len(w)==1 and ARW.match(w) and w not in "وأفبلاينمعهةتلا")
    if singles/max(1,len(words))>0.25: reasons.append("many-singles")
    if len(re.findall(r"[؀-ۿ][.،][؀-ۿ]", t))>=2: reasons.append("glued-punct")
    if len(re.findall(r"[٠-٩]", t))>=3 and len(words)<10 and ARW.search(t): reasons.append("digit-scatter")
    # diacritic/hamza scatter
    if len(re.findall(r"[ءؤئ٠]", t))>=4 and len(t)<60: reasons.append("hamza-scatter")
    return reasons or None

# attribute to current article marker (nearest preceding marker in doc order — rough)
cur=None; per_art={}; total_arts=set()
for t in paras:
    if is_marker(t):
        cur=ART.match(t).group(1); total_arts.add(cur); per_art.setdefault(cur,{"n":0,"bad":0,"ex":[]})
    elif cur and t:
        per_art[cur]["n"]+=1
        r=bad(t)
        if r:
            per_art[cur]["bad"]+=1
            if len(per_art[cur]["ex"])<1: per_art[cur]["ex"].append((t[:70],r))

badarts=[(a,d) for a,d in per_art.items() if d["bad"]>0]
print(f"distinct article numbers seen: {len(total_arts)}")
print(f"articles with >=1 corrupted paragraph: {len(badarts)}")
from collections import Counter
bychap=Counter(a.split('-')[0] for a,_ in badarts)
print("corrupted-articles by chapter:", dict(sorted(bychap.items(),key=lambda x:int(x[0]))))
print("\n-- affected articles + example --")
for a,d in sorted(badarts,key=lambda x:(int(x[0].split('-')[0]),x[0])):
    ex=d["ex"][0] if d["ex"] else ("",[])
    print(f"  م{a}: {d['bad']}/{d['n']} فقرات — {ex[1]}\n      «{ex[0]}»")
