import json,re
path="/root/.claude/projects/-home-user-LegalMind/51a36a7b-3508-590f-af5f-27bfda80b244.jsonl"
pats=['deploy/.env','EnvironmentFile','DATABASE_URL=','set -a','QDRANT_URL','/opt/LegalMind/deploy','legalmind-admin.service','source ','systemctl cat']
found={}
with open(path) as f:
    for line in f:
        try:o=json.loads(line)
        except:continue
        def walk(x):
            if isinstance(x,str):
                for p in pats:
                    if p in x and 'DATABASE_URL is not set' not in x and '_envsearch' not in x:
                        # capture a short window
                        for m in re.finditer(re.escape(p),x):
                            snip=x[max(0,m.start()-60):m.start()+90]
                            found.setdefault(p,set()).add(snip.replace('\n','\\n'))
            elif isinstance(x,dict):
                [walk(v) for v in x.values()]
            elif isinstance(x,list):
                [walk(v) for v in x]
        walk(o)
for p in pats:
    if p in found:
        print("==== ",p," ====")
        for s in list(found[p])[:4]:
            print("   ",s)
