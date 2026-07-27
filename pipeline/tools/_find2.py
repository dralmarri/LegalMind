import json
path="/root/.claude/projects/-home-user-LegalMind/51a36a7b-3508-590f-af5f-27bfda80b244.jsonl"
hits=set()
with open(path) as f:
    for line in f:
        try: o=json.loads(line)
        except: continue
        def walk(x):
            if isinstance(x,str):
                if 'qdrant_points' in x and 'points_count' in x and 'knowledge_objects' in x \
                   and '_find' not in x and 'walk(' not in x:
                    hits.add(x)
            elif isinstance(x,dict):
                for v in x.values(): walk(v)
            elif isinstance(x,list):
                for v in x: walk(v)
        walk(o)
cand=sorted(hits,key=len)
print("num:",len(cand))
if cand:
    h=cand[0]
    i=h.find('qdrant_points')
    print("=====SNIPPET=====")
    print(h[max(0,i-1300):i+400])
