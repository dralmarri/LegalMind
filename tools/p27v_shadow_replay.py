#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.7-V القسم 9 — إعادة تشغيل ظلّية على Gold Set40.

المسار: Question -> Scope Gate -> بذور Planner المجمَّدة -> الـgraph المجمَّدة (23 حافة)
         -> Applicability Gate -> التوسعة.

لا شيء في P2.7 يُمس: نفس البذور، نفس الحواف، نفس الحقيقة الأرضية، نفس مفتاح LOCO.
البوابتان طبقتا ترشيح **فوق** المخرَج لا داخله.
"""
import json, os

B = os.path.dirname(os.path.abspath(__file__))
L = lambda n: json.load(open(os.path.join(B, n), encoding="utf-8"))


def main():
    m = L("p27_graph_measurement.json")
    g = L("p27_coverage_graph.json")
    gt_all = L("p26_v_original_gold40_required_dimensions.json")
    scores = L("p26_v_scores.json")
    audit = L("p27_missed_dimension_audit.json")
    scope = {x["case_id"]: x for x in json.load(
        open("/tmp/claude-0/scope_out.json", encoding="utf-8"))}
    applic = {x["pair_id"]: x for x in json.load(
        open("/tmp/claude-0/applic_out.json", encoding="utf-8"))}

    gt_by_case = {c["case_id"]: {d["dimension_id"]: d for d in c["required_dimensions"]}
                  for c in gt_all}
    cls_of = {(a["case_id"], a["dimension_id"]): a["classification"] for a in audit["audit"]}

    # ---- تطبيق البوابتين على كل توسعة
    decided = []
    for pc in m["per_case"]:
        cid = pc["case_id"]
        st = scope[cid]["scope_status"]
        for x in pc["expansions"]:
            pid = f"{cid}|{x['edge']}"
            av = applic[pid]["verdict"]
            if st == "OUT_OF_SCOPE":
                final, why = "BLOCKED_SCOPE", "بوابة النطاق: صفر توسعة على سؤال خارج النطاق"
            elif av == "DOES_NOT_APPLY":
                final, why = "BLOCKED_APPLICABILITY", "بوابة الانطباق: شرط المصدر غير متحقق"
            elif av == "UNRESOLVED":
                final, why = "FOR_REVIEW", "غير محسوم — لا يُصنَّف REQUIRED"
            elif st in ("MIXED", "UNCERTAIN"):
                final, why = "FOR_REVIEW", "نطاق مختلط/غير مؤكد — لا يُصنَّف REQUIRED"
            else:
                final, why = "ADMITTED", "IN_SCOPE + APPLIES"
            decided.append({**x, "case_id": cid, "scope_status": st,
                            "applicability": av, "final_status": final, "why": why})

    # ADMITTED وحدها تدخل السياق. FOR_REVIEW لا تُحتسب إضافة مقبولة ولا إنقاذًا.
    adm = {(d["case_id"], d["gt_dimension_id"]) for d in decided
           if d["final_status"] == "ADMITTED" and d["gt_dimension_id"]}

    def metrics(loco_only):
        tot = crit = rec = crit_rec = 0
        n_complete = 0
        rescues, rescues_crit = [], []
        additions = additions_true = 0
        false_adds = []
        by_role = {}
        for cs in scores["case_scores"]:
            cid = cs["case_id"]
            dd = [d for d in decided if d["case_id"] == cid]
            ok = {d["gt_dimension_id"]: d for d in dd
                  if d["final_status"] == "ADMITTED" and d["gt_dimension_id"]
                  and (d["loco_admissible"] or not loco_only)}
            case_crit_all = True
            for d in cs["dimension_results"]:
                gd = gt_by_case[cid].get(d["dimension_id"], {})
                tot += 1
                role = gd.get("legal_role") or "other"
                by_role.setdefault(role, [0, 0]); by_role[role][1] += 1
                is_crit = bool(gd.get("critical"))
                crit += 1 if is_crit else 0
                hit = bool(d["matched"])
                ghit = d["dimension_id"] in ok
                if not hit and ghit:
                    rescues.append((cid, d["dimension_id"]))
                    if is_crit:
                        rescues_crit.append((cid, d["dimension_id"]))
                if hit or ghit:
                    rec += 1; by_role[role][0] += 1
                    crit_rec += 1 if is_crit else 0
                elif is_crit:
                    case_crit_all = False
            n_complete += 1 if case_crit_all else 0
            for d in dd:
                if d["final_status"] != "ADMITTED" or d["planner_already_found"]:
                    continue
                if loco_only and not d["loco_admissible"]:
                    continue
                additions += 1
                if d["gt_dimension_id"]:
                    additions_true += 1
                else:
                    false_adds.append((cid, d["edge"], d["dimension_node"]))
        return {
            "loco_clean_only": loco_only,
            "dimension_recall": round(rec / tot, 4),
            "critical_dimension_recall": round(crit_rec / crit, 4),
            "strict_case_completeness": round(n_complete / len(scores["case_scores"]), 4),
            "graph_additions_total": additions,
            "graph_additions_matching_gt": additions_true,
            "graph_addition_precision": round(additions_true / additions, 4) if additions else None,
            "false_additions": false_adds,
            "n_rescued": len(rescues), "n_rescued_critical": len(rescues_crit),
            "rescued": rescues, "rescued_critical": rescues_crit,
            "recall_by_legal_role": {k: {"hit": v[0], "total": v[1],
                                         "recall": round(v[0] / v[1], 4)}
                                     for k, v in sorted(by_role.items())},
        }

    # ---- حفظ كل إنقاذ من الاثني عشر عبر البوابتين (القسم 12)
    before = m["baseline_C_planner_plus_graph_LOCO_CLEAN"]["rescued"]
    preservation = []
    for cid, did in before:
        d = next(x for x in decided if x["case_id"] == cid and x["gt_dimension_id"] == did)
        preservation.append({
            "case_id": cid, "dimension_id": did, "edge_id": d["edge"],
            "critical": d["gt_critical"],
            "before_gate": "rescued",
            "after_scope_gate": "PASS" if d["scope_status"] not in ("OUT_OF_SCOPE",) else "BLOCKED",
            "after_applicability_gate": d["applicability"],
            "final_status": d["final_status"],
            "explanation": d["why"] if d["final_status"] != "ADMITTED" else "حُفظ",
        })

    out = {
        "_note": "P2.7-V الأقسام 9-12 — إعادة تشغيل ظلّية. صفر مساس بـP2.7: البذور والحواف "
                 "والحقيقة الأرضية ومفتاح LOCO كما هي؛ البوابتان ترشيح فوق المخرَج.",
        "freeze_ref": "tools/p27v_freeze.json",
        "scope_gate_summary": {s: sum(1 for v in scope.values() if v["scope_status"] == s)
                               for s in ("IN_SCOPE", "OUT_OF_SCOPE", "MIXED", "UNCERTAIN")},
        "applicability_summary": {v: sum(1 for a in applic.values() if a["verdict"] == v)
                                  for v in ("APPLIES", "DOES_NOT_APPLY", "UNRESOLVED")},
        "final_status_summary": {s: sum(1 for d in decided if d["final_status"] == s)
                                 for s in ("ADMITTED", "BLOCKED_SCOPE",
                                           "BLOCKED_APPLICABILITY", "FOR_REVIEW")},
        "P2_7_V_LOCO_CLEAN": metrics(True),
        "P2_7_V_WITH_LEAKAGE": metrics(False),
        "rescue_preservation": preservation,
        "decisions": decided,
    }
    json.dump(out, open(os.path.join(B, "p27v_shadow_results.json"), "w"),
              ensure_ascii=False, indent=1)

    r = out["P2_7_V_LOCO_CLEAN"]
    print("=" * 68)
    print("P2.7-V — إعادة التشغيل الظلّية (LOCO نظيف)")
    print("=" * 68)
    print("بوابة النطاق     :", out["scope_gate_summary"])
    print("بوابة الانطباق   :", out["applicability_summary"])
    print("الحالة النهائية  :", out["final_status_summary"])
    print("-" * 68)
    print("استدعاء الأبعاد   : %.4f" % r["dimension_recall"])
    print("الاستدعاء الحاكم  : %.4f" % r["critical_dimension_recall"])
    print("اكتمال صارم      : %.4f" % r["strict_case_completeness"])
    print("الإضافات         : %d   المطابق: %d   الدقة: %s"
          % (r["graph_additions_total"], r["graph_additions_matching_gt"],
             r["graph_addition_precision"]))
    print("الإنقاذ          : %d (حاكم %d)" % (r["n_rescued"], r["n_rescued_critical"]))
    print("إضافات غير مطابقة باقية:")
    for f in r["false_additions"]:
        print("   ", f)
    lost = [p for p in preservation if p["final_status"] != "ADMITTED"]
    print("إنقاذ مفقود:", lost if lost else "لا شيء — 12/12 محفوظة")


if __name__ == "__main__":
    main()
