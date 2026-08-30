# -*- coding: utf-8 -*-
import re, zipfile
from xml.etree import ElementTree as ET
W="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
def q(t): return W+t
path="/root/.claude/uploads/51a36a7b-3508-590f-af5f-27bfda80b244/2460e481-CMA_2_AR_2026_R80.docx"
z=zipfile.ZipFile(path)
root=ET.fromstring(z.read("word/document.xml").decode())
body=root.find(q("body"))
def font_of(p):
    fonts=set()
    for r in p.iter(q("r")):
        rPr=r.find(q("rPr"))
        if rPr is not None:
            rf=rPr.find(q("rFonts"))
            if rf is not None:
                for a in ("ascii","cs","hAnsi"):
                    v=rf.get(q(a))
                    if v: fonts.add(v)
    return fonts
# find the scrambled 8-7 para and a clean one; compare fonts
target_bad="تكه.سة"
target_clean="تعمل الهيئة على انتظام"
for p in body.iter(q("p")):
    t="".join(x.text or "" for x in p.iter(q("t"))).strip()
    if t.startswith(target_bad):
        print("BAD para text:", t[:80])
        print("BAD fonts    :", font_of(p))
        # raw runs
        runs=["".join(x.text or "" for x in r.iter(q("t"))) for r in p.iter(q("r"))]
        print("BAD runs     :", [r for r in runs if r][:8])
    if t.startswith(target_clean):
        print("\nCLEAN para text:", t[:80])
        print("CLEAN fonts    :", font_of(p))
# list all embedded fonts in the package
print("\nembedded font files:", [n for n in z.namelist() if n.startswith("word/fonts") or n.endswith(".odttf") or n.endswith(".ttf")])
# fontTable
try:
    ft=z.read("word/fontTable.xml").decode()
    embeds=re.findall(r'w:name="([^"]+)"', ft)
    print("fontTable names:", embeds[:20])
    print("has embedded (odttf refs):", ft.count("embed"))
except Exception as e:
    print("no fontTable", e)
