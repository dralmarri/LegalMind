# -*- coding: utf-8 -*-
"""Parser for قانون 51/1984 الأحوال الشخصية — hierarchical article extraction."""
import zipfile, re, json

Z='legis.docx'
z=zipfile.ZipFile(Z)
xml=z.read('word/document.xml').decode('utf-8')
paras=re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)
def text_of(p): return ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S)).strip()
def style_of(p):
    m=re.search(r'<w:pStyle w:val="([^"]+)"', p); return m.group(1) if m else ''
rows=[(style_of(p), text_of(p)) for p in paras if text_of(p)]

# hierarchy styles:
#  a  = القسم (section)   a0 = الكتاب (book)   a1 = الباب (part)
#  a2 = الفصل (chapter)   a3 = ??  a4 = المبحث (sub)   a5 = body/article
# structural heading appears as TWO consecutive lines: label then name (mostly)
LEVELS={'a':'section','a0':'book','a1':'part','a2':'chapter','a3':'sub','a4':'mabhath'}

# flexible article-header: optional ال, مادة, number, optional مكرر, optional junk ) . -
HDR=re.compile(r'^\s*(?:ال)?مادة\s+(\d+)\s*(مكرر\w*)?\s*[\)\.\-]*\s*$')
LABEL=re.compile(r'^(القسم|الكتاب|الباب|الفصل|المبحث|لباب)\b')

# Build a clean stream: classify each row
def classify(s,t):
    if s=='Title': return ('title',t)
    m=HDR.match(t)
    if m:
        num=m.group(1)+(' مكرر' if m.group(2) else '')
        return ('article_hdr', num)
    if s in LEVELS:
        # could be label line or name line
        if LABEL.match(t): return ('level_label', (s,t))
        return ('level_name', (s,t))
    return ('body', t)

stream=[classify(s,t) for s,t in rows]

# Walk and build breadcrumb + articles
crumb={'section':None,'book':None,'part':None,'chapter':None,'sub':None,'mabhath':None}
order=['section','book','part','chapter','sub','mabhath']
def clear_below(lvl):
    idx=order.index(lvl)
    for l in order[idx+1:]: crumb[l]=None

articles=[]
cur=None  # current article dict
i=0
pending_label=None  # (level, label_text) awaiting a name
while i < len(stream):
    kind,val=stream[i]
    if kind=='title':
        i+=1; continue
    if kind=='level_label':
        s,t=val; lvl=LEVELS[s]
        pending_label=(lvl,t); i+=1; continue
    if kind=='level_name':
        s,t=val; lvl=LEVELS[s]
        # a heading closes any open article
        cur=None
        name=t
        crumb[lvl]=name; clear_below(lvl)
        pending_label=None
        i+=1; continue
    if kind=='article_hdr':
        cur={'num':val,'crumb':dict(crumb),'body':[]}
        articles.append(cur); i+=1; continue
    if kind=='body':
        if cur is None:
            # orphan body (header absent) -> stash for later reconstruction
            articles.append({'num':None,'crumb':dict(crumb),'body':[val],'orphan':True})
            cur=articles[-1]
        else:
            cur['body'].append(val)
        i+=1; continue
    i+=1

# join bodies
for a in articles:
    a['text']=' '.join(a['body']).strip()
    del a['body']

print("total article-blocks:", len(articles))
orphans=[a for a in articles if a.get('orphan')]
print("orphan blocks (header absent):", len(orphans))
numbered=[a for a in articles if a['num']]
print("numbered articles:", len(numbered))
nums=[a['num'] for a in numbered]
# sequential check on pure-int nums
ints=[int(re.match(r'(\d+)',n).group(1)) for n in nums]
miss=[n for n in range(1,348) if n not in ints]
print("still-missing ints:", miss)
json.dump(articles, open('legis_articles.json','w'), ensure_ascii=False, indent=1)
print("saved legis_articles.json")
