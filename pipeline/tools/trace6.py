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
        # also grab paragraph style
        pPr = child.find(W+"pPr")
        st=""
        if pPr is not None:
            ps=pPr.find(W+"pStyle")
            if ps is not None: st=ps.get(W+"val","")
        seq.append(("p","".join(x.text or "" for x in child.iter(W+"t")).strip(),st))
    elif child.tag==W+"tbl":
        rows=[[cell_text(tc) for tc in tr.findall(W+"tc")] for tr in child.findall(W+"tr")]
        seq.append(("tbl",rows,""))
print("=== blocks 55-95 (with style) ===")
for i in range(55,96):
    e=seq[i]
    if e[0]=="p": print(f"{i} P[{e[2][:10]}]  {e[1][:72]}")
    else: print(f"{i} TBL")
