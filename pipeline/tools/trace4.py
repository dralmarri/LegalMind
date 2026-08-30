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

print("=== TOC tbl#10 ===")
for r in seq[10][1]:
    print("  ", " || ".join(c.replace("\n"," ")[:45] for c in r))
print("=== TOC tbl#15 ===")
for r in seq[15][1]:
    print("  ", " || ".join(c.replace("\n"," ")[:45] for c in r))
print("=== TOC tbl#20 ===")
for r in seq[20][1]:
    print("  ", " || ".join(c.replace("\n"," ")[:45] for c in r))
print("\n=== فee section sample tbl#758 (full) ===")
for r in seq[758][1]:
    print("  ", " || ".join((c.replace("\n"," ")[:30] for c in r)))
print("\n=== fee section-header rows (find all 'N - name:' section titles) ===")
SEC = re.compile(r"^\s*\d+\s*-\s*")
for i,(k,v) in enumerate(seq):
    if k!="tbl" or i<750: continue
    for r in v:
        if r and SEC.match(r[0] or "") and ("د.ك" not in (r[1] if len(r)>1 else "")):
            print(f"  tbl#{i}: {r[0].replace(chr(10),' ')[:50]}")
            break
