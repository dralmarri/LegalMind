import ast,re,json
src=open('/tmp/app_patched.py').read()
m=re.search(r"_LABOR_BUNDLES\s*=\s*(\[.*?\n\])",src,re.S)
bundles=ast.literal_eval(m.group(1))
d=json.load(open('labor_parsed.json',encoding='utf-8'))
valid=set("m"+n for n in d['articles'])
allsfx=[]; bad=[]
for name,keys,sfx in bundles:
    allsfx+=sfx
    for s in sfx:
        if s not in valid: bad.append(s)
print("bundles:",len(bundles),"| suffixes:",len(allsfx),"| unique:",len(set(allsfx)))
print("invalid:",bad or 'NONE')
print("distinct articles covered:",len(set(allsfx)),"of 54")
print("labor branch block wired:", src.count('"عمل" in branch')==1)
