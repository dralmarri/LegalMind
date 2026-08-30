# -*- coding: utf-8 -*-
import re, zipfile
from xml.etree import ElementTree as ET
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
def q(t): return W+t
path = "/root/.claude/uploads/51a36a7b-3508-590f-af5f-27bfda80b244/2460e481-CMA_2_AR_2026_R80.docx"
root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml").decode())
body = root.find(q("body"))
ART = re.compile(r"^(?:المادة|مادة)\s+(\d+(?:-\d+)+)\s*$")

def para_info(p):
    txt = "".join(x.text or "" for x in p.iter(q("t"))).strip()
    pPr = p.find(q("pPr"))
    fp = pPr.find(q("framePr")) if pPr is not None else None
    st = ""
    if pPr is not None:
        ps = pPr.find(q("pStyle"))
        if ps is not None: st = ps.get(q("val"),"")
    def gi(a):
        if fp is None: return None
        v = fp.get(q(a))
        return int(v) if v and v.lstrip("-").isdigit() else None
    x = gi("x"); y = gi("y"); h = gi("h"); w = gi("w")
    has_sect = pPr is not None and pPr.find(q("sectPr")) is not None
    return {"text":txt,"style":st,"x":x,"y":y,"h":h,"w":w,"sect":has_sect}

# Segment into pages by sectPr
pages=[]; cur=[]
for child in body:
    if child.tag==q("p"):
        pi=para_info(child)
        cur.append(pi)
        if pi["sect"]:
            pages.append(cur); cur=[]
    elif child.tag==q("tbl"):
        cur.append({"text":"<TBL>","style":"tbl","x":None,"y":None,"h":None,"w":None,"sect":False,"tbl":child})
if cur: pages.append(cur)
print(f"pages(sections)={len(pages)}")

# For a given page, reconstruct reading order:
def reconstruct(page):
    # group consecutive paras sharing identical frame (x,y,h,w) into blocks
    blocks=[]; 
    for pi in page:
        if pi["style"]=="tbl":
            blocks.append({"kind":"tbl","paras":[pi],"y":10**9}); continue
        key=(pi["x"],pi["y"],pi["h"],pi["w"])
        if blocks and blocks[-1].get("key")==key and blocks[-1]["kind"]!="tbl":
            blocks[-1]["paras"].append(pi)
        else:
            blocks.append({"key":key,"kind":"blk","paras":[pi],"y":pi["y"] if pi["y"] is not None else 10**9,"h":pi["h"]})
    # classify: number frame = single para matching ART & narrow width
    nums=[]; bodies=[]
    for b in blocks:
        if b["kind"]=="tbl": bodies.append(b); continue
        joined=" ".join(p["text"] for p in b["paras"])
        m=ART.match(b["paras"][0]["text"]) if len(b["paras"])==1 else None
        if m and (b.get("h") or 0) < 1200 and (b["key"][3] or 0) < 3000:
            nums.append((b["y"], m.group(1), b))
        else:
            bodies.append(b)
    return nums, bodies, blocks

# Count numbers per page and check pairing on pages containing ch1 content
tot_nums=0
for pi,page in enumerate(pages):
    nums,bodies,blocks=reconstruct(page)
    tot_nums+=len(nums)
print("total number-frames across pages:",tot_nums)

# Show pages 4..7 detail (early content)
for pi in range(3,8):
    page=pages[pi]; nums,bodies,blocks=reconstruct(page)
    print(f"\n===== PAGE {pi} : {len(nums)} numbers, {len(bodies)} body-blocks =====")
    print("  numbers:", [(y,n) for y,n,_ in sorted(nums)])
    for b in bodies:
        if b["kind"]=="tbl": 
            print(f"   BODY y=TBL <table>"); continue
        txt=" / ".join(p["text"] for p in b["paras"] if p["text"])[:80]
        print(f"   BODY y={b['y']} h={b.get('h')} np={len(b['paras'])}: {txt}")

print("\n\n########## FRAME-LEVEL PAIRING AUDIT ##########")
import re as _re
def is_noise(t):
    if not t: return True
    if _re.match(r"^\d{1,4}$", t): return True
    if _re.match(r"^(يناير|فبراير|مارس|أبريل|إبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)\s*\d{4}$", t): return True
    if t=="كتاب هيئة أسواق المال": return True
    if _re.match(r"^[أ-ي]$", t): return True
    if _re.match(r"^(الفصل|الباب)\s", t): return True
    return False

one2one=0; shared=[]; orphan_nums=[]; empty_frames=0
seen=set()
FASL=_re.compile(r"^(الفصل|الباب)\s")
for pi,page in enumerate(pages):
    nums,bodies,blocks=reconstruct(page)
    if not nums: continue
    # real body frames (filter noise-only blocks, tables handled elsewhere)
    bframes=[]
    for b in bodies:
        if b["kind"]=="tbl": continue
        paras=[p for p in b["paras"] if not is_noise(p["text"])]
        if not paras: continue
        if b["y"] is None or b["y"]>=10**9: continue
        bframes.append({"y":b["y"],"h":b.get("h") or 0,"paras":paras})
    numlist=sorted(nums)  # (y,N,block)
    # assign numbers to frames: a number belongs to frame if frame.y-500 <= num.y <= frame.y+frame.h
    for f in bframes:
        f["nums"]=[N for (y,N,_) in numlist if (f["y"]-600) <= y <= (f["y"]+f["h"]+200)]
    # orphan numbers: not in any frame
    assigned=set()
    for f in bframes:
        for N in f["nums"]: assigned.add(N)
    for (y,N,_) in numlist:
        if N in seen: continue  # running-header dup counts as seen already? track separately
    for f in bframes:
        if len(f["nums"])==0: empty_frames+=1
        elif len(f["nums"])==1: one2one+=1
        else: shared.append((pi,f["nums"],f["y"],len(f["paras"])))
    for (y,N,_) in numlist:
        if N not in assigned:
            orphan_nums.append((pi,N,y))

print(f"1:1 frames (one article)      : {one2one}")
print(f"shared frames (>=2 articles)  : {len(shared)}")
print(f"empty/noise frames            : {empty_frames}")
print(f"orphan numbers (no body frame): {len(orphan_nums)}")
print("\n-- shared frames detail --")
for pi,ns,y,npar in shared:
    print(f"  page {pi}: numbers {ns}  (y={y}, {npar} paras)")
print("\n-- orphan numbers (likely running-header dups or table arts) --")
from collections import Counter
oc=Counter(N for _,N,_ in orphan_nums)
print("  ", dict(oc))
