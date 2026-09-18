# -*- coding: utf-8 -*-
"""P2.7-O part B — counterfactual admission models computed ONLY from the
existing O run + the frozen transcripts. No retrieval, no code change."""
import json, re
RAW = json.load(open("/tmp/claude-0/forensic/raw_calls.json"))
CASE = {}
for k in ("A1","A2","A3"):
    CASE[k] = json.load(open("/home/user/LegalMind/tools/p27o_run_%s.json" % k))

def famof(i):
    m = re.match(r'^(jprin-\d+-\d+)-', i or ''); return m.group(1) if m else i

# which queries belong to which anchor (exact match against the frozen lane records)
Q2A = {}
for k, recs in CASE.items():
    for r in recs:
        for l in r["lanes"]:
            for q in l["queries"]:
                Q2A[(k, q)] = r["anchor_id"]

# best observed similarity per (anchor, object_id)  -> reconstructed ranking proxy
BEST = {}
for k, calls in RAW.items():
    for c in calls:
        a = Q2A.get((k, c["query"]))
        if not a: continue
        for h in c["hits"]:
            key = (a, h["object_id"])
            if h["score"] > BEST.get(key, -1): BEST[key] = h["score"]

TARGETS_JUD = {"legis-6-2010-m144": "jprin-7-1996-e5376-66fde4a508",
               "legis-51-1984-m337": "JUR-أحوال-شخصية-مرض-الموت-PR-10-a5080271db898625"}

QUOTA = {"legislative": 9, "judicial": 9, "full_judgment": 2}
TOTAL = 20

def rows(r):
    """every relation-validated candidate with its reconstructed score"""
    out = []
    for v in r["relation_validated"]:
        oid = v["object_id"]
        out.append({"id": oid, "type": v["authority_type"],
                    "score": BEST.get((r["anchor_id"], oid), 0.0)})
    out.sort(key=lambda x: -x["score"])
    return out

def model_strict(rs):
    seats = dict(QUOTA); adm = []
    for x in rs:
        if seats.get(x["type"], 0) > 0:
            seats[x["type"]] -= 1; adm.append(x["id"])
    return adm

def model_protected(rs, mins):
    """protected minimum per type, then ALL remaining seats are a shared pool
    ranked globally. A type can never take another type's protected minimum."""
    adm, prot = [], dict(mins)
    for x in rs:                      # phase 1: fill protected minima
        if prot.get(x["type"], 0) > 0:
            prot[x["type"]] -= 1; adm.append(x["id"])
    reserved_left = sum(prot.values())          # still-owed protected seats
    shared = TOTAL - sum(mins.values())
    free = shared                                # phase 2: shared overflow
    for x in rs:
        if x["id"] in adm: continue
        if free <= 0: break
        free -= 1; adm.append(x["id"])
    return adm, reserved_left

def model_global(rs):
    return [x["id"] for x in rs[:TOTAL]]

GT = json.load(open("/home/user/LegalMind/tools/p27l_controls_ground_truth.json"))["anchors"]
KEY = {"A1":"A1_labour_limitation","A2":"A2_prosecution_intervention","A3":"A3_cheque_limitation"}

def controls(byk):
    tot = {"nbu":0,"nbu_n":0,"nar":0,"nar_n":0,"rbn":0,"rbn_n":0}
    for g,a in GT.items():
        got = byk.get(g,set()); fams = {famof(i) for i in got}
        scored = a.get("DISCRIMINATION_POWER") is None
        for cls,key in (("NEAR_BUT_UNRELATED","nbu"),("NEAR_AND_RELATED","nar"),
                        ("RELATED_BUT_NONADJACENT","rbn")):
            ids = [x["id"] for x in a.get(cls,[])]
            hits = sum(1 for t in ids if t in got or famof(t) in fams)
            if cls == "NEAR_BUT_UNRELATED" and not scored: continue
            tot[key] += hits; tot[key+"_n"] += len(ids)
    return tot

def evaluate(name, picker):
    byk, waste, dropped_val, coex, disp = {}, 0, 0, 0, 0
    detail = []
    for k, recs in CASE.items():
        for r in recs:
            rs = rows(r)
            res = picker(rs)
            adm, owed = (res if isinstance(res, tuple) else (res, 0))
            byk.setdefault(KEY[k], set()).update(adm)
            waste += TOTAL - len(adm)
            dropped_val += len(rs) - len(adm)
            ts = {}
            for x in rs:
                if x["id"] in adm: ts[x["type"]] = ts.get(x["type"],0)+1
            coex += 1 if ts.get("legislative",0) >= 1 and ts.get("judicial",0) >= 1 else 0
            detail.append((r["anchor_id"], ts, len(adm)))
    t = controls(byk)
    H = t["nar"] >= 6 and t["rbn"] >= 5
    print("\n--- %s ---" % name)
    for a, ts, n in detail:
        print("   %-22s admitted=%-3d %s" % (a, n, ts))
    print("   NAR=%d/%d  RBN=%d/%d  NBU=%d/%d  coexistence=%d/5  seats_wasted=%d  validated_dropped=%d  JOINT_LAYER_RECALL=%s"
          % (t["nar"],t["nar_n"],t["rbn"],t["rbn_n"],t["nbu"],t["nbu_n"],coex,waste,dropped_val,
             "PASS" if H else "FAIL"))
    return byk, t

print("=== نماذج القبول المضادة (حسابية بحتة على نفس التجمّع) ===")
b1,_ = evaluate("1. O_STRICT  9/9/2 بلا إعادة تخصيص", model_strict)
b3,_ = evaluate("3. GLOBAL_POOL  20 مقعدًا بلا أي حماية (تشخيصي فقط)", model_global)

print("\n=== كنس الحد الأدنى المحمي (تشريع Lmin / قضائي Jmin، والباقي مشترك) ===")
print("%-12s %-8s %-8s %-6s %-6s %-6s %-8s %s" % ("Lmin/Jmin","NAR","RBN","NBU","coex","waste","H","الهدفان القضائيان"))
for Lmin in range(0,10):
    for Jmin in (Lmin,):
        pass
best = []
for Lmin in range(0,10):
    for Jmin in range(0,10):
        if Lmin + Jmin > TOTAL: continue
        mins = {"legislative":Lmin,"judicial":Jmin,"full_judgment":0}
        byk = {}
        waste = coex = 0
        saved = []
        for k, recs in CASE.items():
            for r in recs:
                rs = rows(r)
                adm,_o = model_protected(rs, mins)
                byk.setdefault(KEY[k], set()).update(adm)
                waste += TOTAL - len(adm)
                ts = {}
                for x in rs:
                    if x["id"] in adm: ts[x["type"]] = ts.get(x["type"],0)+1
                coex += 1 if ts.get("legislative",0)>=1 and ts.get("judicial",0)>=1 else 0
                tj = TARGETS_JUD.get(r["anchor_id"])
                if tj:
                    fams = {famof(i) for i in adm}
                    if tj in adm or famof(tj) in fams: saved.append(r["anchor_id"])
        t = controls(byk)
        H = t["nar"]>=6 and t["rbn"]>=5
        best.append((Lmin,Jmin,t,coex,waste,H,saved))
for Lmin,Jmin,t,coex,waste,H,saved in best:
    if (Lmin,Jmin) in [(0,0),(3,3),(5,5),(6,6),(7,7),(8,8),(9,9),(9,0),(0,9),(6,9),(9,6),(4,4)]:
        print("%-12s %-8s %-8s %-6s %-6s %-6s %-8s %s" % (
            "%d/%d"%(Lmin,Jmin), "%d/%d"%(t["nar"],t["nar_n"]), "%d/%d"%(t["rbn"],t["rbn_n"]),
            "%d"%t["nbu"], "%d/5"%coex, waste, "PASS" if H else "FAIL", len(saved)))
mx = max(b[2]["rbn"] for b in best)
print("\nأقصى RBN عبر كل قيم الحد الأدنى:", mx, " وأقصى NAR:", max(b[2]["nar"] for b in best))
anysave = [ (L,J,s) for L,J,t,c,w,H,s in best if s ]
print("إعدادات تُنقذ هدفًا قضائيًا واحدًا على الأقل:", len(anysave), "من", len(best))
if anysave:
    print("  مثال:", anysave[0][:2], anysave[0][2])
json.dump({"best_scores_available": len(BEST)}, open("/tmp/claude-0/forensic/cf_meta.json","w"))
