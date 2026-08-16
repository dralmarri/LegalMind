# -*- coding: utf-8 -*-
import re, zipfile
from xml.etree import ElementTree as ET
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
path = "/root/.claude/uploads/51a36a7b-3508-590f-af5f-27bfda80b244/2460e481-CMA_2_AR_2026_R80.docx"
z = zipfile.ZipFile(path)
xml = z.read("word/document.xml").decode("utf-8")
root = ET.fromstring(xml)
body = root.find(W+"body")
# only direct children paragraphs; inspect pPr details for blocks 55-73
def ptext(p): return "".join(x.text or "" for x in p.iter(W+"t")).strip()
paras=[c for c in body if c.tag==W+"p"]
# map: rebuild seq index -> element for paragraphs only around our target
# We'll iterate direct children to keep same indexing as before
seq=[]
for child in body:
    if child.tag in (W+"p", W+"tbl"):
        seq.append(child)
for i in range(55,74):
    el=seq[i]
    if el.tag!=W+"p":
        print(i,"TBL"); continue
    pPr=el.find(W+"pPr")
    info=[]
    if pPr is not None:
        if pPr.find(W+"framePr") is not None:
            fp=pPr.find(W+"framePr")
            info.append("FRAME("+",".join(f"{k.split('}')[-1]}={v}" for k,v in fp.attrib.items())+")")
        if pPr.find(W+"numPr") is not None: info.append("NUMPR")
        ps=pPr.find(W+"pStyle")
        if ps is not None: info.append("style="+ps.get(W+"val",""))
        jc=pPr.find(W+"jc")
        if jc is not None: info.append("jc="+jc.get(W+"val",""))
    print(f"{i} P {ptext(el)[:30]!r:34} {' '.join(info)}")
