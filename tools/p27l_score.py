# -*- coding: utf-8 -*-
"""P2.7-L — مُسجِّل الأذرع الثلاثة مقابل الضوابط المجمَّدة.
ARM_ADJACENT يُحتسب هنا ميكانيكيًا (±3 في القانون نفسه) — لا يحتاج نموذجًا.
لا يقرأ أي حالة من الـ34."""
import json, os, re, sys

ROOT = "/home/user/LegalMind"
GT = json.load(open(os.path.join(ROOT, "tools/p27l_controls_ground_truth.json")))
NEIGH = {r["object_id"]: r for r in json.load(open("/tmp/claude-0/p27l_neighbourhood.json")) if r.get("found")}

ADJ_WINDOW = 3   # مُعلَن في التصميم السببي قبل التشغيل

def art_num(oid):
    m = re.match(r"^(legis-\d+-\d+)-m(\d+)$", oid or "")
    return (m.group(1), int(m.group(2))) if m else (None, None)

def arm_adjacent():
    """كل مادة في القانون نفسه ضمن ±3 من رقم المرساة، **إن كانت موجودة في القاعدة**."""
    out = {}
    for key, a in GT["anchors"].items():
        got = set()
        for anc in a["anchor_ids"]:
            law, n = art_num(anc)
            if law is None:
                continue
            for d in range(-ADJ_WINDOW, ADJ_WINDOW + 1):
                if d == 0:
                    continue
                cand = "%s-m%d" % (law, n + d)
                if cand in a["anchor_ids"]:
                    continue
                # الوجود يُتحقق من الجرد المفحوص + الأهداف المعروفة الموجودة
                if cand in NEIGH or cand in KNOWN_EXISTING:
                    got.add(cand)
        out[key] = sorted(got)
    return out

KNOWN_EXISTING = {"legis-51-1984-m340", "legis-68-1980-m553"}  # فُحص وجودهما حيًّا

def sets_for(key):
    a = GT["anchors"][key]
    nbu = [x["id"] for x in a.get("NEAR_BUT_UNRELATED", [])]
    nar = [x["id"] for x in a.get("NEAR_AND_RELATED", [])]
    rbn = [x["id"] for x in a.get("RELATED_BUT_NONADJACENT", [])]
    scored_nbu = a.get("DISCRIMINATION_POWER") != "LOW — **مُعلَن قبل التشغيل ومستبعَد من مقياس NEAR_BUT_UNRELATED**"
    return nbu, nar, rbn, scored_nbu

def score(arm_name, per_anchor_ids):
    rows = []
    tot = {"nbu_admitted": 0, "nbu_total": 0, "nar_hit": 0, "nar_total": 0,
           "rbn_hit": 0, "rbn_total": 0}
    for key in GT["anchors"]:
        nbu, nar, rbn, scored = sets_for(key)
        got = set(per_anchor_ids.get(key, []))
        r = {"anchor_group": key,
             "admitted_n": len(got),
             "NEAR_BUT_UNRELATED_admitted": sorted(got & set(nbu)),
             "NEAR_AND_RELATED_hit": sorted(got & set(nar)),
             "RELATED_BUT_NONADJACENT_hit": sorted(got & set(rbn)),
             "nbu_scored": scored}
        rows.append(r)
        if scored:
            tot["nbu_admitted"] += len(r["NEAR_BUT_UNRELATED_admitted"]); tot["nbu_total"] += len(nbu)
        tot["nar_hit"] += len(r["NEAR_AND_RELATED_hit"]); tot["nar_total"] += len(nar)
        tot["rbn_hit"] += len(r["RELATED_BUT_NONADJACENT_hit"]); tot["rbn_total"] += len(rbn)
    return {"arm": arm_name, "per_anchor": rows, "totals": tot}

if __name__ == "__main__":
    res = {}
    adj = arm_adjacent()
    res["ARM_ADJACENT"] = score("ARM_ADJACENT", adj)
    res["ARM_ADJACENT"]["expanded_to"] = adj

    p = "/tmp/claude-0/p27l_arm_anchor.json"
    if os.path.exists(p):
        byk = {}
        for rec in json.load(open(p)):
            key = {"A1": "A1_labour_limitation", "A2": "A2_prosecution_intervention",
                   "A3": "A3_cheque_limitation"}[rec["case"]]
            byk.setdefault(key, []).extend(a["object_id"] for a in rec.get("admitted", []))
        res["ARM_ANCHOR"] = score("ARM_ANCHOR", byk)
        res["ARM_ANCHOR"]["expanded_to"] = {k: sorted(set(v)) for k, v in byk.items()}

    p = "/tmp/claude-0/p27l_arm_topical.json"
    if os.path.exists(p):
        byk = {}
        for rec in json.load(open(p)):
            key = {"A1": "A1_labour_limitation", "A2": "A2_prosecution_intervention",
                   "A3": "A3_cheque_limitation"}[rec["case"]]
            byk.setdefault(key, []).extend(a["object_id"] for a in rec.get("retrieved", []))
        res["ARM_TOPICAL"] = score("ARM_TOPICAL", byk)

    json.dump(res, open("/tmp/claude-0/p27l_scores.json", "w"), ensure_ascii=False, indent=1)
    for arm, v in res.items():
        t = v["totals"]
        print("%-14s  NEAR_BUT_UNRELATED %d/%d | NEAR_AND_RELATED %d/%d | RELATED_BUT_NONADJACENT %d/%d"
              % (arm, t["nbu_admitted"], t["nbu_total"], t["nar_hit"], t["nar_total"],
                 t["rbn_hit"], t["rbn_total"]))
