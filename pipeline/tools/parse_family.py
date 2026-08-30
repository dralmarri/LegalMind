# -*- coding: utf-8 -*-
"""Parser for قانون 12/2015 محكمة الأسرة — flat structure."""
import zipfile, re, json
z=zipfile.ZipFile('family.docx')
xml=z.read('word/document.xml').decode('utf-8')
paras=re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)
def text_of(p): return ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S)).strip()
def style_of(p):
    m=re.search(r'<w:pStyle w:val="([^"]+)"', p); return m.group(1) if m else ''
rows=[(style_of(p), text_of(p)) for p in paras if text_of(p)]

HDR=re.compile(r'^\s*(?:ال)?مادة\s+(\d+)\s*[\)\.\-\(]*\s*$')
def clean(t): return re.sub(r'\s+',' ',re.sub(r'[\)\(]{3,}','',t)).replace('__','').strip()

htext=[t for s,t in rows if s!='Title']
# issuing section: from start until "المادة 1"
first_sub=next(i for i,t in enumerate(htext) if HDR.match(t) and int(HDR.match(t).group(1))==1)
head=htext[:first_sub]; body=htext[first_sub:]
issue_idx=next(i for i,t in enumerate(head) if t.strip()=='المادة الأولى')
preamble=' '.join(head[:issue_idx]).strip()
stop_idx=next((i for i,t in enumerate(head) if t.strip().startswith('أمير الكويت')), len(head))
enact=' | '.join(head[stop_idx:])
ORD=['الأولى','الثانية','الثالثة','الرابعة','الخامسة']
issuing=[]; cur=None
for t in head[issue_idx:stop_idx]:
    ts=t.strip()
    if ts.startswith('المادة ') and ts.replace('المادة ','') in ORD:
        cur={'ord':ts.replace('المادة ','').strip(),'body':[]}; issuing.append(cur)
    elif cur: cur['body'].append(ts)
for it in issuing: it['text']=re.sub(r'\s+',' ',' '.join(it['body'])).strip()

# substantive articles
arts=[]; cur=None
for t in body:
    m=HDR.match(t)
    if m:
        cur={'num':m.group(1),'body':[]}; arts.append(cur); continue
    if cur: cur['body'].append(clean(t))
for a in arts: a['text']=re.sub(r'\s+',' ',' '.join(a['body'])).strip(); del a['body']

print("issuing:", len(issuing), [i['ord'] for i in issuing])
print("substantive:", len(arts), "nums:", [a['num'] for a in arts])
print("preamble len:", len(preamble), "| enact:", enact[:60])
for a in arts: print("  م%-3s len=%d" % (a['num'], len(a['text'])))
json.dump({'preamble':preamble,'enact':enact,'issuing':issuing,'articles':arts},
          open('family_final.json','w'), ensure_ascii=False, indent=1)
print("saved family_final.json")
