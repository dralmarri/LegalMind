import ast, json, re
src=open('/tmp/app_patched.py').read()
# extract _CMAREG3_BUNDLES literal
m=re.search(r"_CMAREG3_BUNDLES\s*=\s*(\[.*?\n\])", src, re.S)
bundles=ast.literal_eval(m.group(1))
d=json.load(open('book3_articles.json',encoding='utf-8'))
valid=set("k3-m"+k for k in d['articles']) | set("k3-annex"+n for n in d['annexes'])
print("bundles:",len(bundles))
allsfx=[]
bad=[]
for name,keys,sfx in bundles:
    allsfx+=sfx
    for s in sfx:
        if s not in valid: bad.append(s)
print("total suffixes:",len(allsfx),"| unique:",len(set(allsfx)))
print("invalid suffixes (not real objects):", bad or 'NONE')
# coverage: which articles/annexes are referenced
refart=set(s[4:] for s in allsfx if s.startswith('k3-m'))
print("distinct articles referenced:",len(refart),"of",len(d['articles']))
print("annexes referenced:", sorted(s for s in set(allsfx) if 'annex' in s))
