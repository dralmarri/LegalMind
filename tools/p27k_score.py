# -*- coding: utf-8 -*-
"""P2.7-K — مُسجِّل ميكانيكي لنتائج المسارات مقابل الحزم المجمَّدة.
لا يحكم على المضمون؛ يطابق المعرّفات ويُخرج الحالة الخام لكل proposition
ليُبنى فوقها التقييم القانوني اليدوي الموثق."""
import json, os, sys

ROOT = "/home/user/LegalMind"
LANES = ["/tmp/claude-0/k_lane_A_C.json",
         "/tmp/claude-0/k_lane_B_D.json",
         "/tmp/claude-0/k_lane_E_F_G.json"]

packets = json.load(open(os.path.join(ROOT, "tools/p27k_frozen_packets.json")))["cases"]

lanes = {}
for f in LANES:
    if not os.path.exists(f):
        print("MISSING:", f); continue
    for rec in json.load(open(f)):
        lanes[rec["case_id"]] = rec

out = {}
for cid, pk in packets.items():
    rec = lanes.get(cid)
    if rec is None:
        out[cid] = {"status": "LANE_NOT_EXECUTED"}
        continue
    # خريطة: object_id -> [(role, proposition_text, fetch_failed)]
    found = {}
    roles_run = []
    for ln in rec.get("lanes", []):
        roles_run.append(ln["role"])
        for a in ln.get("authorities_found", []):
            found.setdefault(a["object_id"], []).append(
                {"role": ln["role"], "text": a.get("proposition", ""),
                 "fetch_failed": bool(a.get("fetch_failed")),
                 "type": a.get("type"), "date": a.get("date")})
    props = []
    for p in pk["propositions"]:
        hits = []
        for aid in p["authority_ids"]:
            if aid in found:
                hits.append({"id": aid, "occurrences": found[aid]})
        ids_found = [h["id"] for h in hits]
        ids_missing = [a for a in p["authority_ids"] if a not in ids_found]
        # هل وُجد في المسار المتوقَّع لدوره؟
        in_expected_role = any(o["role"] == p["authority_role"]
                               for h in hits for o in h["occurrences"])
        any_fetch_failed = any(o["fetch_failed"] for h in hits for o in h["occurrences"])
        props.append({
            "proposition": p["proposition"],
            "authority_role": p["authority_role"],
            "source_layer": p["source_layer"],
            "critical": p["critical"],
            "authority_ids": p["authority_ids"],
            "ids_found": ids_found,
            "ids_missing": ids_missing,
            "any_id_found": bool(ids_found),
            "all_ids_found": not ids_missing,
            "found_in_expected_role_lane": in_expected_role,
            "any_fetch_failed": any_fetch_failed,
            "extracted_texts": [o["text"] for h in hits for o in h["occurrences"]],
        })
    out[cid] = {
        "status": "EXECUTED",
        "expected_roles": pk["expected_roles"],
        "critical_roles": pk["critical_roles"],
        "roles_run": roles_run,
        "n_authorities_returned": len(found),
        "propositions": props,
        "conflict_findings": rec.get("conflict_findings"),
        "temporal_findings": rec.get("temporal_findings"),
    }

json.dump(out, open("/tmp/claude-0/k_mech_scores.json", "w"),
          ensure_ascii=False, indent=1)

# ملخص خام
tot = crit = hit = crithit = 0
for cid, v in out.items():
    if v["status"] != "EXECUTED":
        print(cid, v["status"]); continue
    for p in v["propositions"]:
        tot += 1
        if p["any_id_found"]: hit += 1
        if p["critical"]:
            crit += 1
            if p["any_id_found"]: crithit += 1
print("PROPOSITIONS (id-level) %d/%d" % (hit, tot))
print("CRITICAL (id-level)     %d/%d" % (crithit, crit))
