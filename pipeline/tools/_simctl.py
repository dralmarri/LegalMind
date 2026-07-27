import re,importlib.util
exec(open('_simdraft.py').read().split('facts=')[0])
db=ns["_draft_bundles"]
# commercial query, no domestic-labor terms
ids=db("استشارة","نزاع تجاري حول عقد بيع بضائع وفسخه بين شركتين",[],None,"تجاري")
print("تجاري نقي -> labor core:", [x for x in ids if 'legis-68-2015' in x], "| n=",len(ids))
