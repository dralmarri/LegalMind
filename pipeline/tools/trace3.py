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

def show_tbl(idx):
    k,v = seq[idx]
    print(f"--- tbl#{idx} ({len(v)} rows) ---")
    for r in v:
        c0 = (r[0] if len(r)>0 else "").replace("\n"," ")[:30]
        c1 = (r[1] if len(r)>1 else "").replace("\n"," ")[:60]
        print(f"   [{c0}] :: {c1}")

for idx in (283,291,398,570):
    show_tbl(idx)

# What precedes tbl#291 and tbl#570 (to resolve empty col0 continuation)
print("\n=== context before tbl#291 ===")
for i in range(276,292):
    k,v=seq[i]
    print(f"{i} {k} {'' if k=='tbl' else v[:70]}")
print("\n=== boundary: last articles -> appendix (blocks 700-725) ===")
for i in range(700,726):
    k,v=seq[i]
    if k=="p": print(f"{i} P {v[:70]}")
    else: print(f"{i} TBL[{len(v)}r]")
