# -*- coding: utf-8 -*-
"""Finalized parser for قانون 51/1984 — hierarchical articles with defect handling."""
import zipfile, re, json

z=zipfile.ZipFile('legis.docx')
xml=z.read('word/document.xml').decode('utf-8')
paras=re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)
def text_of(p): return ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S)).strip()
def style_of(p):
    m=re.search(r'<w:pStyle w:val="([^"]+)"', p); return m.group(1) if m else ''
rows=[(style_of(p), text_of(p)) for p in paras if text_of(p)]

LEVELS={'a':'section','a0':'book','a1':'part','a2':'chapter','a3':'sub','a4':'mabhath'}
order=['section','book','part','chapter','sub','mabhath']
LABEL=re.compile(r'^(القسم|الكتاب|الباب|الفصل|المبحث|لباب)\b')
# strict header: مادة N [مكرر] [(letter)] [junk]  — NO connective words after number
HDR=re.compile(r'^\s*(?:ال)?مادة\s+(\d+)\s*(مكرر\w*)?\s*(?:\)\s*([أ-ي])\s*\()?\s*[\)\.\-]*\s*$')
JUNK=re.compile(r'[\)\(]{2,}')

def clean(t):
    t=JUNK.sub('', t)
    return re.sub(r'\s+',' ',t).strip()

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

blocks=[]  # each: {num, crumb, body[], kind}
cur=None
pending=None
for s,t in rows:
    if s=='Title':
        blocks.append({'num':None,'crumb':dict(crumb),'body':[t],'kind':'title'}); cur=None; continue
    num=hdr_num(t)
    if num is not None:
        cur={'num':num,'crumb':dict(crumb),'body':[],'kind':'article'}
        blocks.append(cur); continue
    if s in LEVELS:
        lvl=LEVELS[s]
        if LABEL.match(t):
            pending=(lvl,t); continue
        else:
            crumb[lvl]=t; clear_below(lvl); pending=None; cur=None; continue
    # body
    ct=clean(t)
    if not ct: continue
    if cur is None:
        blocks.append({'num':None,'crumb':dict(crumb),'body':[ct],'kind':'orphan'}); cur=blocks[-1]
    else:
        cur['body'].append(ct)

for b in blocks: b['text']=' '.join(b['body']).strip(); del b['body']

# ---- defect handling ----
arts=[b for b in blocks if b['kind']=='article']
# assign orphan numbers by sequence position
seq_int=lambda n: int(re.match(r'(\d+)',n).group(1)) if n else None

# 1) preamble = orphan before article 1
# 2) orphan between N and N+2 -> article N+1
final=[]
preamble=None
for i,b in enumerate(blocks):
    if b['kind']=='title': continue
    if b['kind']=='orphan':
        # find prev/next article numbers
        prevn=None; nextn=None
        for j in range(i-1,-1,-1):
            if blocks[j]['kind']=='article': prevn=seq_int(blocks[j]['num']); break
        for j in range(i+1,len(blocks)):
            if blocks[j]['kind']=='article': nextn=seq_int(blocks[j]['num']); break
        if prevn is None:  # before art1 => preamble
            preamble=b['text']; continue
        assigned=prevn+1
        b2=dict(b); b2['num']=str(assigned); b2['kind']='article'; b2['recovered']=True
        final.append(b2); continue
    if b['kind']=='article':
        final.append(b)

# 3) split article 21 out of 20: art20 body currently ends with the 21-fragment
#    locate art20; its text = "لا يجوز الجمع...الأخرى. قبل ان ينحل زواجه...عدتها."
for b in final:
    if b['num']=='20':
        m=re.search(r'(قبل ان ينحل زواجه.*)$', b['text'])
        if m:
            frag=m.group(1).strip()
            b['text']=b['text'][:m.start()].strip()
            # art21 should already be recovered as orphan? check
            a21=[x for x in final if x['num']=='21']
            if a21:
                a21[0]['text']=frag; a21[0]['fragment_incomplete']=True
            else:
                final.append({'num':'21','crumb':dict(b['crumb']),'text':frag,
                              'kind':'article','recovered':True,'fragment_incomplete':True})
        break

# 4) dedup identical same-number articles (336)
seen={}
dedup=[]
for b in final:
    key=(b['num'], b['text'][:60])
    if key in seen: continue
    seen[key]=1; dedup.append(b)
final=dedup

# sort by (int, suffix)
def sortkey(b):
    m=re.match(r'(\d+)(.*)$', b['num']); return (int(m.group(1)), m.group(2))
final.sort(key=sortkey)

print("preamble captured:", bool(preamble), "| len", len(preamble or ''))
print("final articles:", len(final))
ints=sorted(set(seq_int(b['num']) for b in final))
miss=[n for n in range(1,348) if n not in ints]
print("missing base numbers:", miss)
print("recovered (header-absent):", [b['num'] for b in final if b.get('recovered')])
print("flagged incomplete fragment:", [b['num'] for b in final if b.get('fragment_incomplete')])
print("مكرر:", [b['num'] for b in final if 'مكرر' in b['num']])
# empties
empt=[b['num'] for b in final if len(b['text'])<5]
print("suspiciously empty:", empt)

json.dump({'preamble':preamble,'articles':final}, open('legis_final.json','w'), ensure_ascii=False, indent=1)
print("saved legis_final.json")
