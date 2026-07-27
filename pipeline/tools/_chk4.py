import ast, json, re
src=open('/tmp/app_patched.py').read()
m=re.search(r"_CMAREG4_BUNDLES\s*=\s*(\[.*?\n\])", src, re.S)
bundles=ast.literal_eval(m.group(1))
d=json.load(open('book4_articles.json',encoding='utf-8'))
valid=set("k4-m"+k for k in d['articles']) | set("k4-annex"+n for n in d['annexes'])
allsfx=[]; bad=[]
for name,keys,sfx in bundles:
    allsfx+=sfx
    for s in sfx:
        if s not in valid: bad.append(s)
print("bundles:",len(bundles),"| total suffixes:",len(allsfx),"| unique:",len(set(allsfx)))
print("invalid suffixes:", bad or 'NONE')
print("distinct articles referenced:",len(set(s for s in allsfx if s.startswith('k4-m'))),"of",len(d['articles']))
print("annexes referenced:", sorted(s for s in set(allsfx) if 'annex' in s))
print("loop wired:", src.count("for _name, keys, sfx in _CMAREG4_BUNDLES")==1)
