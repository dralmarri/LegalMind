# -*- coding: utf-8 -*-
"""Final parser v4 = v2 logic + word-derived level for label/name pairs."""
import zipfile, re, json
z=zipfile.ZipFile('legis.docx')
xml=z.read('word/document.xml').decode('utf-8')
paras=re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)
def text_of(p): return ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S)).strip()
def style_of(p):
    m=re.search(r'<w:pStyle w:val="([^"]+)"', p); return m.group(1) if m else ''
rows=[(style_of(p), text_of(p)) for p in paras if text_of(p)]

STYLE_LVL={'a':'section','a0':'book','a1':'part','a2':'chapter','a3':'sub','a4':'mabhath'}
order=['section','book','part','chapter','sub','mabhath']
WORD_LVL={'القسم':'section','الكتاب':'book','الباب':'part','لباب':'part',
          'الفصل':'chapter','المبحث':'mabhath'}
LABEL=re.compile(r'^(القسم|الكتاب|الباب|لباب|الفصل|المبحث)\b')
HDR=re.compile(r'^\s*(?:ال)?مادة\s+(\d+)\s*(مكرر\w*)?\s*(?:\)\s*([أ-ي])\s*\()?\s*[\)\.\-]*\s*$')
def clean(t): return re.sub(r'\s+',' ',re.sub(r'[\)\(]{2,}','',t)).strip()
def hdr_num(t):
    m=HDR.match(t)
    if not m: return None
    n=m.group(1)
    if m.group(2): n+=' مكرر'
    if m.group(3): n+=' '+m.group(3)
    return n

crumb={k:None for k in order}
def clear_below(lvl):
    for l in order[order.index(lvl)+1:]: crumb[l]=None

blocks=[]; cur=None; pending_lvl=None
for s,t in rows:
    if s=='Title':
        blocks.append({'num':None,'crumb':dict(crumb),'body':[t],'kind':'title'}); cur=None; continue
    num=hdr_num(t)
    if num is not None:
        cur={'num':num,'crumb':dict(crumb),'body':[],'kind':'article'}; blocks.append(cur); continue
    if s in STYLE_LVL:
        m=LABEL.match(t)
        if m:                                   # label line -> level from WORD
            pending_lvl=WORD_LVL[m.group(1)]; cur=None; continue
        # name line
        lvl=pending_lvl if pending_lvl else STYLE_LVL[s]
        crumb[lvl]=t; clear_below(lvl); pending_lvl=None; cur=None; continue
    ct=clean(t)
    if not ct: continue
    if cur is None:
        blocks.append({'num':None,'crumb':dict(crumb),'body':[ct],'kind':'orphan'}); cur=blocks[-1]
    else:
        cur['body'].append(ct)

for b in blocks: b['text']=' '.join(b['body']).strip(); del b['body']
seq=lambda n:int(re.match(r'(\d+)',n).group(1)) if n else None

final=[]; preamble=None
for i,b in enumerate(blocks):
    if b['kind']=='title': continue
    if b['kind']=='orphan':
        prevn=None
        for j in range(i-1,-1,-1):
            if blocks[j]['kind']=='article': prevn=seq(blocks[j]['num']); break
        if prevn is None: preamble=b['text']; continue
        b2=dict(b); b2['num']=str(prevn+1); b2['kind']='article'; b2['recovered']=True; final.append(b2); continue
    final.append(b)

for b in final:
    if b['num']=='20':
        m=re.search(r'(قبل ان ينحل زواجه.*)$', b['text'])
        if m:
            frag=b['text'][m.start():].strip(); b['text']=b['text'][:m.start()].strip()
            a=[x for x in final if x['num']=='21']
            if a:
                a[0]['text']=frag; a[0]['fragment_incomplete']=True
            else:
                final.append({'num':'21','crumb':dict(b['crumb']),'text':frag,
                              'kind':'article','recovered':True,'fragment_incomplete':True})
        break
seen=set(); dd=[]
for b in final:
    k=(b['num'],b['text'][:60])
    if k in seen: continue
    seen.add(k); dd.append(b)
final=dd
final.sort(key=lambda b:(seq(b['num']), re.match(r'\d+(.*)',b['num']).group(1)))

ints=sorted(set(seq(b['num']) for b in final))
from collections import Counter
print("articles:", len(final), "| missing base:", [n for n in range(1,348) if n not in ints])
print("recovered:", [b['num'] for b in final if b.get('recovered')])
print("fragment:", [b['num'] for b in final if b.get('fragment_incomplete')])
print("مكرر:", [b['num'] for b in final if 'مكرر' in b['num']])
print("sections:", dict(Counter(b['crumb'].get('section') for b in final)))
maw=[b['num'] for b in final if b['crumb'].get('section')=='المواريث']
print("المواريث: %d articles (%s..%s)" % (len(maw), maw[0], maw[-1]))
empt=[b['num'] for b in final if len(b['text'])<5]
print("empty:", empt)
json.dump({'preamble':preamble,'articles':final,
           'law':{'name':'قانون في شأن الأحوال الشخصية','number':51,'year':1984}},
          open('legis_final.json','w'), ensure_ascii=False, indent=1)
print("saved.")
