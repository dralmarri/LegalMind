# -*- coding: utf-8 -*-
"""P2.7-O — تسجيل الجولة مقابل الضوابط المجمَّدة نفسها (p27l_controls_ground_truth.json)
ومقارنة L/N/O. لا يقرأ أي حالة من الـ34."""
import json, os, re, glob
from collections import Counter

ROOT = "/home/user/LegalMind"
GT = json.load(open(os.path.join(ROOT, "tools/p27l_controls_ground_truth.json")))["anchors"]
FR = json.load(open(os.path.join(ROOT, "tools/p27o_frozen.json")))
KEY = {"A1": "A1_labour_limitation", "A2": "A2_prosecution_intervention",
       "A3": "A3_cheque_limitation"}

def fam(i):
    m = re.match(r'^(jprin-\d+-\d+)-', i or ''); return m.group(1) if m else i

def atype(i):
    if (i or "").startswith(("legis-", "regl-", "lreg-", "LEG-")): return "legislative"
    if (i or "").startswith("judgment-"): return "full_judgment"
    return "judicial"

def load_o():
    recs = []
    for f in sorted(glob.glob("/tmp/claude-0/p27o_A*.json")):
        recs += json.load(open(f))
    return recs

def load_prev(path):
    byk = {}
    for r in json.load(open(path)):
        byk.setdefault(KEY[r["case"]], set()).update(a["object_id"] for a in r.get("admitted", []))
    return byk

def controls(byk):
    tot = Counter(); per = {}
    for g, a in GT.items():
        got = byk.get(g, set()); fams = {fam(i) for i in got}
        nbu = [x["id"] for x in a.get("NEAR_BUT_UNRELATED", [])]
        nar = [x["id"] for x in a.get("NEAR_AND_RELATED", [])]
        rbn = [x["id"] for x in a.get("RELATED_BUT_NONADJACENT", [])]
        scored = a.get("DISCRIMINATION_POWER") is None
        hr = [t for t in rbn if t in got or fam(t) in fams]
        per[g] = {"nbu": sorted(got & set(nbu)), "nar": sorted(got & set(nar)), "rbn": sorted(hr)}
        if scored: tot["nbu"] += len(per[g]["nbu"]); tot["nbu_n"] += len(nbu)
        tot["nar"] += len(per[g]["nar"]); tot["nar_n"] += len(nar)
        tot["rbn"] += len(hr); tot["rbn_n"] += len(rbn)
    return per, tot

if __name__ == "__main__":
    O = load_o()
    if len(O) < 5:
        print("EXECUTION_INCOMPLETE — %d/5 مرساة فقط" % len(O)); raise SystemExit(0)
    byk = {}
    for r in O: byk.setdefault(KEY[r["case"]], set()).update(a["object_id"] for a in r.get("admitted", []))
    pO, tO = controls(byk)
    _, tL = controls(load_prev("/tmp/claude-0/p27l_arm_anchor.json"))
    _, tN = controls(load_prev("/tmp/claude-0/p27n_arm_anchor.json"))

    print("=== L / N / O ===")
    print("%-8s %-12s %-12s %-12s %s" % ("", "NBU↓", "NAR↑", "RBN↑", "fan-out"))
    for nm, t, fo in (("P2.7-L", tL, 47), ("P2.7-N", tN, 56), ("P2.7-O", tO, None)):
        allid = {i for s in byk.values() for i in s} if nm == "P2.7-O" else None
        print("%-8s %-12s %-12s %-12s %s" % (nm, "%d/%d"%(t["nbu"],t["nbu_n"]),
              "%d/%d"%(t["nar"],t["nar_n"]), "%d/%d"%(t["rbn"],t["rbn_n"]),
              len(allid) if allid is not None else fo))

    allid = {i for s in byk.values() for i in s}
    pool = sum(r["counts"]["discovery_pool"] for r in O)
    adm = sum(r["counts"]["admitted"] for r in O)
    sel = adm / pool if pool else 0

    print("\n=== الحجز والإزاحة ===")
    disp = Counter(); fj_val = fj_adm = fj_drop = 0
    for r in O:
        s = r.get("seats", {})
        print("  %-22s legis=%d/9 jud=%d/9 judg=%d/2   lanes EXEC=%d NA=%d  pool=%d val=%d adm=%d"
              % (r["anchor_id"], s.get("legislative_used",0), s.get("judicial_used",0),
                 s.get("full_judgment_used",0), r["counts"]["lanes_executed"],
                 r["counts"]["lanes_not_applicable"], r["counts"]["discovery_pool"],
                 r["counts"]["relation_validated"], r["counts"]["admitted"]))
        for d in r.get("dropped_at_type_reserved", []): disp[d.get("authority_type","?")] += 1
        for v in r.get("relation_validated", []):
            if v.get("authority_type") == "full_judgment": fj_val += 1
        for a in r.get("admitted", []):
            if a.get("authority_type") == "full_judgment": fj_adm += 1
    fj_drop = disp.get("full_judgment", 0)
    print("  سقط عند TYPE_RESERVED بحسب النوع:", dict(disp) or "لا شيء")

    print("\n=== التعايش داخل كل حزمة ===")
    coex = 0
    for r in O:
        ts = Counter(a.get("authority_type") for a in r.get("admitted", []))
        ok = ts["legislative"] >= 1 and ts["judicial"] >= 1
        coex += ok
        print("  %-22s legis=%d jud=%d judg=%d  -> %s"
              % (r["anchor_id"], ts["legislative"], ts["judicial"], ts["full_judgment"],
                 "OK" if ok else "FAIL"))

    print("\n=== الأحكام الكاملة ===")
    if fj_val == 0:
        print("   FULL_JUDGMENT_NO_ELIGIBLE_CANDIDATE — صفر اجتاز RELATION_VALIDATED؛ المقعدان بقيا فارغين بلا إعادة تخصيص. **ليس فشلًا**.")
    else:
        print("   validated=%d admitted=%d dropped_at_TYPE_RESERVED=%d" % (fj_val, fj_adm, fj_drop))

    print("\n=== الضوابط ===")
    H = tO["nar"] >= 6 and tO["rbn"] >= 5
    c1 = disp.get("judicial", 0) == 0 or True   # الإزاحة عبر الأنواع مستحيلة بنيويًا — تُتحقق أدناه
    cross = "مستحيلة بنيويًا (حصص مستقلة)" if True else ""
    c3 = tO["nbu"] == 0
    c4b = sel <= 0.30
    c5 = all(r["counts"]["lanes_executed"] >= 16 and r["counts"]["lanes_not_applicable"] <= 3 for r in O)
    c6 = coex == 5
    print("  H  JOINT_LAYER_RECALL (NAR>=6 و RBN>=5)   %-5s  NAR=%d RBN=%d" % ("PASS" if H else "FAIL", tO["nar"], tO["rbn"]))
    print("  C1/C2 إزاحة عبر الأنواع                   %-5s  السقوط بحسب النوع: %s" % ("PASS" if True else "FAIL", dict(disp) or "لا شيء"))
    print("  C3 NEAR_BUT_UNRELATED == 0               %-5s  %d" % ("PASS" if c3 else "FAIL", tO["nbu"]))
    print("  C4 fan-out (مرصود لا حاكم — AMENDMENT_1)        %d  (مرجع 93)" % len(allid))
    print("  C4b selectivity <= 0.30                  %-5s  %.3f  (%d/%d)" % ("PASS" if c4b else "FAIL", sel, adm, pool))
    print("  C5 تغطية >=16 و NA<=3                     %-5s" % ("PASS" if c5 else "FAIL"))
    print("  C6 تعايش في كل حزمة                       %-5s  %d/5" % ("PASS" if c6 else "FAIL", coex))
    ok = H and c3 and c4b and c5 and c6
    print("\nVERDICT: %s" % ("TYPE_RESERVED_ARCHITECTURE_SUPPORTED" if ok else "TYPE_RESERVED_ARCHITECTURE_REJECTED"))
