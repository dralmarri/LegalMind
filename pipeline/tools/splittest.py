# -*- coding: utf-8 -*-
import re, math, zipfile
from xml.etree import ElementTree as ET
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
def q(t): return W+t
path = "/root/.claude/uploads/51a36a7b-3508-590f-af5f-27bfda80b244/2460e481-CMA_2_AR_2026_R80.docx"
root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml").decode())
body = root.find(q("body"))
ART = re.compile(r"^(?:المادة|مادة)\s+(\d+(?:-\d+)+)\s*$")
def para_info(p):
    txt="".join(x.text or "" for x in p.iter(q("t"))).strip()
    pPr=p.find(q("pPr")); fp=pPr.find(q("framePr")) if pPr is not None else None
    st=""; 
    if pPr is not None:
        ps=pPr.find(q("pStyle")); st=ps.get(q("val"),"") if ps is not None else ""
    def gi(a):
        if fp is None: return None
        v=fp.get(q(a)); return int(v) if v and v.lstrip("-").isdigit() else None
    return {"text":txt,"style":st,"x":gi("x"),"y":gi("y"),"h":gi("h"),"w":gi("w"),
            "sect":pPr is not None and pPr.find(q("sectPr")) is not None}
pages=[]; cur=[]
for child in body:
    if child.tag==q("p"):
        pi=para_info(child); cur.append(pi)
        if pi["sect"]: pages.append(cur); cur=[]
    elif child.tag==q("tbl"): cur.append({"text":"<TBL>","style":"tbl","x":None,"y":None,"h":None,"w":None,"sect":False})
if cur: pages.append(cur)

def is_noise(t):
    if not t: return True
    if re.match(r"^\d{1,4}$",t): return True
    if re.match(r"^(يناير|فبراير|مارس|أبريل|إبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)\s*\d{4}$",t): return True
    if t=="كتاب هيئة أسواق المال": return True
    if re.match(r"^[أ-ي]$",t): return True
    if re.match(r"^(الفصل|الباب)\s",t): return True
    return False

def blocks_of(page):
    blk=[]
    for pi in page:
        if pi["style"]=="tbl": continue
        key=(pi["x"],pi["y"],pi["h"],pi["w"])
        if blk and blk[-1]["key"]==key: blk[-1]["paras"].append(pi)
        else: blk.append({"key":key,"paras":[pi],"y":pi["y"],"h":pi["h"],"w":pi["w"]})
    return blk

def CPL(w):  # chars per line from frame width (twips)
    return max(20, int((w or 9149)/120))

# For each shared frame, compute text-proportional paragraph tops and check number alignment
def analyze_page(pn):
    page=pages[pn]; blk=blocks_of(page)
    nums=sorted((b["paras"][0]["text"], b["y"]) for b in blk
                if len(b["paras"])==1 and ART.match(b["paras"][0]["text"]) and (b["h"] or 0)<1200 and (b["w"] or 0)<3000)
    nums=sorted(((y,ART.match(t).group(1)) for t,y in nums))
    for b in blk:
        paras=[p for p in b["paras"] if not is_noise(p["text"])]
        if len(paras)<1 or b["y"] is None: continue
        innums=[(y,N) for (y,N) in nums if (b["y"]-600)<=y<=(b["y"]+(b["h"] or 0)+200)]
        if len(innums)<2: continue
        # text-proportional tops
        cpl=CPL(b["w"]); lines=[max(1,math.ceil(len(p["text"])/cpl)) for p in paras]
        tot=sum(lines); cum=0; tops=[]
        for L in lines:
            tops.append(b["y"] + (b["h"] or 0)*cum/tot); cum+=L
        print(f"\n=page {pn} frame y={b['y']} h={b['h']} w={b['w']} paras={len(paras)} nums={[n for _,n in innums]}")
        # for each internal number (skip the first which = frame start), find nearest para boundary
        for (ny,N) in innums:
            # nearest para index by top
            gaps=[(abs(tops[i]-ny),i) for i in range(len(tops))]
            gaps.sort(); g,idx=gaps[0]
            approx_para_h=(b["h"] or 0)/len(paras)
            print(f"    num {N} y={ny}: nearest para#{idx} top≈{int(tops[idx])} gap={int(g)} (~{g/approx_para_h:.2f} paras)  para='{paras[idx]['text'][:40]}'")

for pn in (6,13,14,19,28,35):
    analyze_page(pn)
