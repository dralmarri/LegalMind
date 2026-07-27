# -*- coding: utf-8 -*-
"""Final parser v3 — level driven by heading WORD not style code."""
import zipfile, re, json
z=zipfile.ZipFile('legis.docx')
xml=z.read('word/document.xml').decode('utf-8')
paras=re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)
def text_of(p): return ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S)).strip()
def style_of(p):
    m=re.search(r'<w:pStyle w:val="([^"]+)"', p); return m.group(1) if m else ''
rows=[(style_of(p), text_of(p)) for p in paras if text_of(p)]

order=['section','book','part','chapter','mabhath']
WORD2LVL={'القسم':'section','الكتاب':'book','الباب':'part','لباب':'part',
          'الفصل':'chapter','المبحث':'mabhath'}
LABEL=re.compile(r'^(القسم|الكتاب|الباب|لباب|الفصل|المبحث)\b')
STRUCT_STYLES={'a','a0','a1','a2','a3','a4'}
HDR=re.compile(r'^\s*(?:ال)?مادة\s+(\d+)\s*(مكرر\w*)?\s*(?:\)\s*([أ-ي])\s*\()?\s*[\)\.\-]*\s*$')
def clean(t): return re.sub(r'\s+',' ',re.sub(r'[\)\(]{2,}','',t)).strip()
def hdr_num(t):
    m=HDR.match(t)
    if not m: return None
    num=m.group(1)
    if m.group(2): num+=' مكرر'
    if m.group(3): num+=' '+m.group(3)
    return num

crumb={k:None for k in order}
def clear_below(lvl):
    for l in order[order.index(lvl)+1:]: crumb[l]=None

blocks=[]; cur=None; pending=None
for s,t in rows:
    if s=='Title':
        blocks.append({'num':None,'crumb':dict(crumb),'body':[t],'kind':'title'}); cur=None; continue
    num=hdr_num(t)
    if num is not None:
        cur={'num':num,'crumb':dict(crumb),'body':[],'kind':'article'}; blocks.append(cur); continue
    mlab=LABEL.match(t)
    if mlab and s in STRUCT_STYLES:
        pending=WORD2LVL[mlab.group(1)]; cur=None; continue
    if s in STRUCT_STYLES and pending:
        crumb[pending]=t; clear_below(pending); pending=None; cur=None; continue
    if s in STRUCT_STYLES and not pending:
        # single-line heading label+name combined e.g. "الفصل الاول - الموصي له"
        m2=re.match(r'^(القسم|الكتاب|الباب|الفصل|المبحث)\s+\S+\s*[-:]\s*(.+)$', t)
        if m2:
            lvl=WORD2LVL[m2.group(1)]; crumb[lvl]=m2.group(2).strip(); clear_below(lvl); cur=None; continue
        # else treat as name at last pending-ish: skip into body
    ct=clean(t)
    if not ct: continue
    if cur is None:
        blocks.append({'num':None,'crumb':dict(crumb),'body':[ct],'kind':'orphan'}); cur=blocks[-1]
    else:
        cur['body'].append(ct)

for b in blocks: b['text']=' '.join(b['body']).strip(); del b['body']
seq_int=lambda n:int(re.match(r'(\d+)',n).group(1)) if n else None

final=[]; preamble=None
for i,b in enumerate(blocks):
    if b['kind']=='title': continue
    if b['kind']=='orphan':
        prevn=None
        for j in range(i-1,-1,-1):
            if blocks[j]['kind']=='article': prevn=seq_int(blocks[j]['num']); break
        if prevn is None: preamble=b['text']; continue
        b2=dict(b); b2['num']=str(prevn+1); b2['kind']='article'; b2['recovered']=True; final.append(b2); continue
    if b['kind']=='article': final.append(b)

# split art21 fragment from art20
for b in final:
    if b['num']=='20':
        m=re.search(r'(قبل ان ينحل زواجه.*)$', b['text'])
        if m:
            frag=b['text'][m.start():].strip(); b['text']=b['text'][:m.start()].strip()
            a21=[x for x in final if x['num']=='21']
            if a21: a21[0]['text']=frag; a21[0]['fragment_incomplete']=True
        break
# dedup
seen=set(); dd=[]
for b in final:
    k=(b['num'],b['text'][:60])
    if k in seen: continue
    seen.add(k); dd.append(b)
final=dd
final.sort(key=lambda b:(seq_int(b['num']), re.match(r'\d+(.*)',b['num']).group(1)))

ints=sorted(set(seq_int(b['num']) for b in final))
print("articles:", len(final), "| missing base:", [n for n in range(1,348) if n not in ints])
# section distribution now
from collections import Counter
sc=Counter(b['crumb'].get('section') for b in final)
print("sections:", dict(sc))
json.dump({'preamble':preamble,'articles':final}, open('legis_final.json','w'), ensure_ascii=False, indent=1)
# verify مواريث section fixed
mawarith=[b['num'] for b in final if b['crumb'].get('section')=='المواريث']
print("المواريث articles: %d (%s .. %s)" % (len(mawarith), mawarith[0], mawarith[-1]))
