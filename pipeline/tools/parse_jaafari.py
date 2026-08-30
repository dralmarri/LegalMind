# -*- coding: utf-8 -*-
"""Parser for قانون 124/2019 الأحوال الشخصية الجعفرية."""
import zipfile, re, json
z=zipfile.ZipFile('jaafari.docx')
xml=z.read('word/document.xml').decode('utf-8')
paras=re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)
def text_of(p): return ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S)).strip()
def style_of(p):
    m=re.search(r'<w:pStyle w:val="([^"]+)"', p); return m.group(1) if m else ''
rows=[(style_of(p), text_of(p)) for p in paras if text_of(p)]

# split inline-merged headers: "...بلفظ آخر. ))) المادة 15" -> two rows
fixed=[]
for s,t in rows:
    t=re.sub(r'\)\)\)',' ',t)
    m=re.search(r'(.+?\S)\s+((?:ال)?مادة\s+\d+)\s*$', t)
    if m and s=='a4' and len(m.group(1))>15:
        fixed.append((s,m.group(1).strip())); fixed.append((s,m.group(2).strip()))
    else:
        fixed.append((s,t.strip()))
rows=fixed

STYLE_LVL={'a':'book','a0':'chapter','a1':'part','a3':'pillar'}
order=['book','chapter','part','pillar']
# heading level from WORD
WORD_LVL=[('كتاب','book'),('الفصل','chapter'),('فصل','chapter'),
          ('الباب','part'),('باب','part'),
          ('الركن','pillar'),('المبحث','pillar')]
HDR=re.compile(r'^\s*(?:ال)?مادة\s+(\d+)\s*(مكرر\w*)?\s*[:\.\-\)]*\s*$')
def clean(t): return re.sub(r'\s+',' ',re.sub(r'[\)\(]{2,}','',t)).strip()
def hdr_num(t):
    m=HDR.match(t)
    if not m: return None
    n=m.group(1)
    if m.group(2): n+=' مكرر'
    return n
def heading_level(t):
    for w,l in WORD_LVL:
        if re.match(r'^\s*%s\b'%w, t): return l
    return None
def split_colon_heading(t):
    # "الفصل الأول: إنشاء الزواج" -> ('chapter','إنشاء الزواج'); returns (level,name) or None
    m=re.match(r'^\s*(كتاب|الفصل|فصل|الباب|باب|الركن|المبحث)\b([^:]*):\s*(.+)$', t)
    if m:
        lvl=heading_level(m.group(1))
        return lvl, m.group(3).strip()
    return None

crumb={k:None for k in order}
def clear_below(lvl):
    for l in order[order.index(lvl)+1:]: crumb[l]=None

# find where substantive law starts: first "كتاب" heading
start_idx=next(i for i,(s,t) in enumerate(rows) if re.match(r'^\s*كتاب\b',t))
head_rows=rows[:start_idx]   # title + preamble + issuing articles + signature
body_rows=rows[start_idx:]

blocks=[]; cur=None; pending_lvl=None
for s,t in body_rows:
    num=hdr_num(t)
    if num is not None:
        cur={'num':num,'crumb':dict(crumb),'body':[],'kind':'article'}; blocks.append(cur); continue
    if s in STYLE_LVL:
        sc=split_colon_heading(t)
        if sc and sc[0]:
            crumb[sc[0]]=sc[1]; clear_below(sc[0]); pending_lvl=None; cur=None; continue
        wl=heading_level(t)
        if wl and re.match(r'^\s*(كتاب|الفصل|فصل|الباب|باب|الركن|المبحث)\s*(الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|[:\d])',t) or (wl and len(t)<25):
            pending_lvl=wl; cur=None; continue
        if pending_lvl:                     # this is the NAME line
            crumb[pending_lvl]=t; clear_below(pending_lvl); pending_lvl=None; cur=None; continue
        # standalone heading word without ordinal (e.g. "كتاب الزواج")
        if wl:
            crumb[wl]=t; clear_below(wl); cur=None; continue
    ct=clean(t)
    if not ct: continue
    if cur is None:
        blocks.append({'num':None,'crumb':dict(crumb),'body':[ct],'kind':'orphan'}); cur=blocks[-1]
    else:
        cur['body'].append(ct)

for b in blocks: b['text']=' '.join(b['body']).strip(); del b['body']
seq=lambda n:int(re.match(r'(\d+)',n).group(1)) if n else None

final=[]
for i,b in enumerate(blocks):
    if b['kind']=='orphan':
        prevn=None
        for j in range(i-1,-1,-1):
            if blocks[j]['kind']=='article': prevn=seq(blocks[j]['num']); break
        if prevn is None: continue
        b2=dict(b); b2['num']=str(prevn+1); b2['kind']='article'; b2['recovered']=True; final.append(b2); continue
    final.append(b)
# dedup
seen=set(); dd=[]
for b in final:
    k=(b['num'],b['text'][:50])
    if k in seen: continue
    seen.add(k); dd.append(b)
final=dd
final.sort(key=lambda b:(seq(b['num']), b['num']))

ints=sorted(set(seq(b['num']) for b in final))
from collections import Counter
miss=[n for n in range(1,max(ints)+1) if n not in ints]
print("substantive articles:", len(final), "| max:", max(ints))
print("missing:", miss)
print("recovered:", [b['num'] for b in final if b.get('recovered')])
print("books (topic):", dict(Counter(b['crumb'].get('book') for b in final)))
empt=[b['num'] for b in final if len(b['text'])<8]
print("empty/short:", empt[:20])
json.dump({'articles':final,'head_rows':head_rows}, open('jaafari_final.json','w'), ensure_ascii=False, indent=1)
print("saved.")
