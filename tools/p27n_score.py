# -*- coding: utf-8 -*-
"""P2.7-N — تسجيل الجولة المكتملة مقابل الضوابط المجمَّدة نفسها، ومقارنتها بـP2.7-L.
لا يقرأ أي حالة من الـ34."""
import json, os
from collections import Counter

ROOT = "/home/user/LegalMind"
GT = json.load(open(os.path.join(ROOT, "tools/p27l_controls_ground_truth.json")))["anchors"]
TH = json.load(open(os.path.join(ROOT, "tools/p27n_frozen_thresholds.json")))

KEY = {"A1": "A1_labour_limitation", "A2": "A2_prosecution_intervention",
       "A3": "A3_cheque_limitation"}

def fam(i):
    import re
    m = re.match(r'^(jprin-\d+-\d+)-', i or '')
    return m.group(1) if m else i

def load(path, key):
    """يعيد {anchor_group: set(ids)} و{anchor_id: record}"""
    byk, byanchor = {}, {}
    for r in json.load(open(path)):
        g = KEY[r["case"]]
        byanchor[r["anchor_id"]] = r
        for a in r.get(key, []):
            byk.setdefault(g, set()).add(a["object_id"])
    return byk, byanchor

def controls(byk):
    tot = {"nbu": 0, "nbu_n": 0, "nar": 0, "nar_n": 0, "rbn": 0, "rbn_n": 0}
    per = {}
    for g, a in GT.items():
        got = byk.get(g, set())
        fams = {fam(i) for i in got}
        nbu = [x["id"] for x in a.get("NEAR_BUT_UNRELATED", [])]
        nar = [x["id"] for x in a.get("NEAR_AND_RELATED", [])]
        rbn = [x["id"] for x in a.get("RELATED_BUT_NONADJACENT", [])]
        scored = a.get("DISCRIMINATION_POWER") is None
        hit_rbn = [t for t in rbn if t in got or fam(t) in fams]
        per[g] = {"nbu_admitted": sorted(got & set(nbu)),
                  "nar_hit": sorted(got & set(nar)),
                  "rbn_hit": sorted(hit_rbn), "nbu_scored": scored}
        if scored:
            tot["nbu"] += len(per[g]["nbu_admitted"]); tot["nbu_n"] += len(nbu)
        tot["nar"] += len(per[g]["nar_hit"]); tot["nar_n"] += len(nar)
        tot["rbn"] += len(hit_rbn); tot["rbn_n"] += len(rbn)
    return per, tot

if __name__ == "__main__":
    L, _ = load("/tmp/claude-0/p27l_arm_anchor.json", "admitted")
    pL, tL = controls(L)
    Lall = {i for s in L.values() for i in s}

    pN = tN = None
    if os.path.exists("/tmp/claude-0/p27n_arm_anchor.json"):
        N, Nrec = load("/tmp/claude-0/p27n_arm_anchor.json", "admitted")
        pN, tN = controls(N)
        Nall = {i for s in N.values() for i in s}
    else:
        print("P2.7-N output not present yet."); raise SystemExit(0)

    print("%-12s %-22s %-22s %s" % ("", "NEAR_BUT_UNRELATED↓", "NEAR_AND_RELATED↑", "RELATED_BUT_NONADJ↑"))
    for nm, t in (("P2.7-L", tL), ("P2.7-N", tN)):
        print("%-12s %-22s %-22s %s" % (nm, "%d/%d" % (t["nbu"], t["nbu_n"]),
              "%d/%d" % (t["nar"], t["nar_n"]), "%d/%d" % (t["rbn"], t["rbn_n"])))
    print("\nfan-out (admitted distinct):  L=%d   N=%d   (سقف مجمَّد %d)"
          % (len(Lall), len(Nall), TH["CAUSAL_CONTROLS_any_failure_ends_the_round"]["C4_fan_out"]["value"]))

    print("\n=== الإنقاذ: الإخفاقات الستة (implementation gap) ===")
    resc = TH["rescue_target"]["ids"]
    got = {i for s in N.values() for i in s}; fams = {fam(i) for i in got}
    n_r = 0
    for t in resc:
        ok = t in got or fam(t) in fams
        n_r += ok
        print("   %-24s %s" % (t, "RESCUED" if ok else "still missing"))
    print("   => %d/6   (العتبة >= 4)" % n_r)

    print("\n=== الانحدار: هل فُقدت إصابة من P2.7-L؟ ===")
    lost = sorted(Lall - got)
    prev_ctrl = set()
    for g in GT:
        prev_ctrl |= set(pL[g]["nar_hit"]) | set(pL[g]["rbn_hit"])
    lost_ctrl = sorted(x for x in prev_ctrl if x not in got and fam(x) not in fams)
    print("   إصابات ضابطة مفقودة:", lost_ctrl or "لا شيء")
    print("   (سلطات أخرى لم تتكرر: %d — خارج الضوابط، لا تُحتسب انحدارًا)" % len(lost))

    print("\n=== fan-out لكل علاقة (P2.7-N) ===")
    c = Counter()
    for r in json.load(open("/tmp/claude-0/p27n_arm_anchor.json")):
        for a in r.get("admitted", []): c[a["relation_type"]] += 1
    for k, v in c.most_common(): print("   %-30s %d" % (k, v))

    print("\n=== الضوابط الأربعة ===")
    C = TH["CAUSAL_CONTROLS_any_failure_ends_the_round"]
    r1 = tN["nbu"] == 0
    r2 = tN["rbn"] >= C["C2_related_but_nonadjacent"]["value"]
    r3 = not lost_ctrl
    r4 = len(Nall) <= C["C4_fan_out"]["value"]
    for nm, ok, d in (("C1 near_but_unrelated==0", r1, "%d" % tN["nbu"]),
                      ("C2 related_nonadj>=5", r2, "%d" % tN["rbn"]),
                      ("C3 no regression", r3, str(lost_ctrl or "clean")),
                      ("C4 fan-out<=70", r4, "%d" % len(Nall))):
        print("   %-26s %-5s %s" % (nm, "PASS" if ok else "FAIL", d))
    print("\nRESCUE>=4: %s" % ("PASS" if n_r >= 4 else "FAIL"))
    print("VERDICT: %s" % ("MECHANISM_COMPLETION_PASS" if (r1 and r2 and r3 and r4 and n_r >= 4)
                           else "MECHANISM_COMPLETION_FAIL"))
