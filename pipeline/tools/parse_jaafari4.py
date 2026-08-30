# -*- coding: utf-8 -*-
"""Parser v4 (final) for قانون 124/2019 الجعفري — structural styles never body."""
import zipfile, re, json
z=zipfile.ZipFile('jaafari.docx')
xml=z.read('word/document.xml').decode('utf-8')
paras=re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)
def text_of(p): return ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S)).strip()
def style_of(p):
    m=re.search(r'<w:pStyle w:val="([^"]+)"', p); return m.group(1) if m else ''
rows=[(style_of(p), text_of(p)) for p in paras if text_of(p)]

# split inline-merged headers "...آخر. المادة 15"
fixed=[]
for s,t in rows:
    t2=re.sub(r'\)\)\)',' ',t)
    m=re.search(r'^(.*\S)\s+((?:ال)?مادة\s+\d+)\s*$', t2)
    if m and s=='a4' and not re.match(r'^\s*(?:ال)?مادة\s+\d+\s*$', m.group(1)) and len(m.group(1))>=6:
        fixed.append((s,m.group(1).strip())); fixed.append((s,m.group(2).strip()))
    else:
        fixed.append((s,t2.strip()))
rows=fixed

STYLE_LVL={'a':'book','a0':'chapter','a1':'part','a3':'pillar'}
order=['book','chapter','part','pillar']
WORDS=r'كتاب|الفصل|فصل|الباب|باب|الركن|المبحث'
def wlevel(w):
    return {'كتاب':'book','الفصل':'chapter','فصل':'chapter','الباب':'part','باب':'part'}.get(w,'pillar')
ORD=r'(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|الحادي عشر|الثاني عشر|الثالث عشر)'
HDR=re.compile(r'^\s*(?:ال)?مادة\s+(\d+)\s*(مكرر\w*)?\s*[:\.\-\)]*\s*$')
def hdr_num(t):
    m=HDR.match(t)
    return (m.group(1)+(' مكرر' if m.group(2) else '')) if m else None
def clean(t): return re.sub(r'\s+',' ',re.sub(r'[\)\(]{2,}','',t)).strip()
def parse_heading(t):
    m=re.match(r'^\s*(%s)\b[^:]*:\s*(.+)$'%WORDS, t)
    if m: return ('name', wlevel(m.group(1)), m.group(2).strip())
    m=re.match(r'^\s*(%s)\b[^:]*:\s*$'%WORDS, t)
    if m: return ('pending', wlevel(m.group(1)), None)
    m=re.match(r'^\s*(%s)\s+%s\s*$'%(WORDS,ORD), t)
    if m: return ('pending', wlevel(m.group(1)), None)
    m=re.match(r'^\s*(%s)\s+(.+)$'%WORDS, t)
    if m: return ('name', wlevel(m.group(1)), m.group(2).strip())
    return None

crumb={k:None for k in order}
def clear_below(lvl):
    for l in order[order.index(lvl)+1:]: crumb[l]=None

start_idx=next(i for i,(s,t) in enumerate(rows) if re.match(r'^\s*كتاب\b',t))
head_rows=rows[:start_idx]; body_rows=rows[start_idx:]

blocks=[]; cur=None; pend=None; prev_struct=False
for s,t in body_rows:
    num=hdr_num(t)
    if num is not None:
        cur={'num':num,'crumb':dict(crumb),'body':[],'kind':'article'}; blocks.append(cur)
        pend=None; prev_struct=False; continue
    if s in STYLE_LVL:
        if t=='وفيه فصول': prev_struct=True; cur=None; continue
        ph=parse_heading(t)
        if ph and ph[0]=='name':
            crumb[ph[1]]=ph[2]; clear_below(ph[1]); pend=None
        elif ph and ph[0]=='pending':
            pend=ph[1]
        elif pend:
            crumb[pend]=t; clear_below(pend); pend=None
        else:
            lvl=STYLE_LVL[s]
            if prev_struct and crumb[lvl]:
                crumb[lvl]=crumb[lvl]+' '+t
            else:
                crumb[lvl]=t; clear_below(lvl)
        prev_struct=True; cur=None; continue
    prev_struct=False
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
seen=set(); dd=[]
for b in final:
    k=(b['num'],b['text'][:50])
    if k in seen: continue
    seen.add(k); dd.append(b)
final=dd
final.sort(key=lambda b:(seq(b['num']), b['num']))
ints=sorted(set(seq(b['num']) for b in final))
from collections import Counter
print("articles:", len(final), "| max:", max(ints), "| expected(510-13):", 510-13)
print("missing:", [n for n in range(1,max(ints)+1) if n not in ints])
print("dups:", {k:v for k,v in Counter(b['num'] for b in final).items() if v>1})
print("recovered:", [b['num'] for b in final if b.get('recovered')])
print("books:", dict(Counter(b['crumb'].get('book') for b in final)))
print("empty/short:", [b['num'] for b in final if len(b['text'])<8])
json.dump({'articles':final,'head_rows':head_rows}, open('jaafari_final.json','w'), ensure_ascii=False, indent=1)
print("saved.")
