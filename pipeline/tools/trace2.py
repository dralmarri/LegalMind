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
# Find the tables that contain articles and the fee tables. Print table index, rows, cols, first-row content
print("=== ALL TABLES ===")
for i,(k,v) in enumerate(seq):
    if k!="tbl": continue
    ncol = max(len(r) for r in v) if v else 0
    has_art = any(r and ART.match(r[0] or "") for r in v)
    hdr = " | ".join((c[:20].replace("\n"," ") for c in v[0])) if v else ""
    print(f"tbl#{i} rows={len(v)} cols={ncol} art={has_art} :: {hdr[:90]}")
