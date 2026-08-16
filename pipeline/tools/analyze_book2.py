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

ART = re.compile(r"^(?:المادة|مادة)\s+(\d+(?:-\d+)+)")
FASL = re.compile(r"^(الفصل|الباب)\s+")
# Walk in document order
seq = []
for child in body:
    if child.tag == W+"p":
        t = "".join(x.text or "" for x in child.iter(W+"t")).strip()
        seq.append(("p", t))
    elif child.tag == W+"tbl":
        rows = []
        for tr in child.findall(W+"tr"):
            cells = [cell_text(tc) for tc in tr.findall(W+"tc")]
            rows.append(cells)
        seq.append(("tbl", rows))

npar = sum(1 for k,_ in seq if k=="p")
ntbl = sum(1 for k,_ in seq if k=="tbl")
print(f"paragraphs(top-level)={npar}  tables={ntbl}  total_blocks={len(seq)}")

# Article markers in paragraphs
p_arts = [t for k,t in seq if k=="p" and ART.match(t or "")]
print(f"\nparagraph article markers: {len(p_arts)}")
for a in p_arts[:15]:
    print("  P:", a[:70])

# Article markers in table cells (first cell)
tbl_arts = []
for k,payload in seq:
    if k!="tbl": continue
    for row in payload:
        if row and ART.match((row[0] or "")):
            tbl_arts.append(row[0].split("\n")[0])
print(f"\ntable-row article markers: {len(tbl_arts)}")
for a in tbl_arts[:15]:
    print("  T:", a[:70])

# Collect ALL article numbers with source
allnums = []
for k,payload in seq:
    if k=="p":
        m=ART.match(payload or "")
        if m: allnums.append(("p",m.group(1)))
    else:
        for row in payload:
            if row:
                m=ART.match((row[0] or ""))
                if m: allnums.append(("t",m.group(1)))
print(f"\nTOTAL article markers (p+t): {len(allnums)}")
# chapter distribution
from collections import Counter
chap = Counter(n.split("-")[0] for _,n in allnums)
print("by chapter (first segment):", dict(sorted(chap.items(), key=lambda x:int(x[0]))))
# three-level ones
threelev=[n for _,n in allnums if n.count("-")>=2]
print(f"3-level markers: {len(threelev)} e.g. {threelev[:10]}")
