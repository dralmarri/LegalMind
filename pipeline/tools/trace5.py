# -*- coding: utf-8 -*-
import re, zipfile
from xml.etree import ElementTree as ET
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
path = "/root/.claude/uploads/51a36a7b-3508-590f-af5f-27bfda80b244/2460e481-CMA_2_AR_2026_R80.docx"
z = zipfile.ZipFile(path)
root = ET.fromstring(z.read("word/document.xml").decode("utf-8"))
body = root.find(W+"body")
def cell_text(tc):
    return "\n".join("".join(x.text or "" for x in p.iter(W+"t")).strip()
                     for p in tc.findall(W+"p")).strip()
seq=[]
for child in body:
    if child.tag==W+"p":
        seq.append(("p","".join(x.text or "" for x in child.iter(W+"t")).strip()))
    elif child.tag==W+"tbl":
        rows=[[cell_text(tc) for tc in tr.findall(W+"tc")] for tr in child.findall(W+"tr")]
        seq.append(("tbl",rows))
ART = re.compile(r"^(?:المادة|مادة)\s+(\d+(?:-\d+)+)")
# Find ALL paragraph indices where each empty article number appears
targets = ["1-5","1-8","8-2","5-1"]
locs = {t:[] for t in targets}
for i,(k,v) in enumerate(seq):
    if k=="p":
        m=ART.match(v or "")
        if m and m.group(1) in locs:
            locs[m.group(1)].append(i)
for t,ii in locs.items():
    print(f"مادة {t}: occurrences at {ii}")
# dump context around first occurrence of 1-5
def dump(a,b):
    for i in range(a,b):
        k,v=seq[i]
        if k=="p": print(f"{i} P  {v[:75]}")
        else: print(f"{i} TBL[{len(v)}r] c0={ (v[0][0][:25] if v and v[0] else '') }")
print("\n=== around 1-5 (first occ) ===")
i0=locs["1-5"][0]; dump(i0-2,i0+12)
print("\n=== around 8-2 (first occ) ===")
i0=locs["8-2"][0]; dump(i0-2,i0+12)
