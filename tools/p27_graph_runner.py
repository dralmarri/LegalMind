#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.7 — مشغّل القياس (الأقسام H/I/K/L/M/N/O).

لا يُعاد تشغيل Planner إطلاقًا: البذور تُستخرج من مخرجاته المحفوظة
(`p26_v_gold40_planner_outputs.json`) من جولة P2.6-V نفسها.

التقسيم الصارم:
  Planner  = seed (اكتشاف المفاهيم من نص السؤال)
  Graph    = expansion (توسعة بعمق 1 على حواف VERIFIED حصرًا)

ضبط التسريب (H): الحافة مقبولة عند اختبار الحالة X إذا وإذا فقط ظهر مصدرها المُسنِد
في الحقيقة الأرضية لحالة أخرى ≠ X.
"""
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    with open(os.path.join(BASE, name), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- تطبيع عربي
_DIAC = re.compile(r"[ً-ْٰـ]")


def norm(s):
    if not s:
        return ""
    s = _DIAC.sub("", str(s))
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ---------------------------------------------------------- استخراج البذور (I)
def planner_text(rec):
    """كل النص الذي أنتجه Planner لهذه الحالة — ولا شيء من نص السؤال الخام."""
    obj = rec.get("parsed_object") or {}
    parts = [obj.get("primary_issue") or ""]
    for iss in obj.get("issues") or []:
        parts.append(iss.get("issue") or "")
        parts.extend(iss.get("triggering_facts") or [])
        for d in iss.get("required_dimensions") or []:
            parts.append(d.get("dimension") or "")
            parts.append(d.get("why_required") or "")
            parts.append(d.get("condition") or "")
            parts.extend(d.get("triggering_facts") or [])
    return norm(" | ".join(p for p in parts if p))


def seed_concepts(text_norm, nodes):
    """مطابقة مفهوم = ورود أحد surface_forms مطبَّعًا داخل نص Planner."""
    hits = []
    for n in nodes:
        if n["node_type"] == "LEGAL_DIMENSION":
            continue
        for sf in n.get("surface_forms") or []:
            if norm(sf) and norm(sf) in text_norm:
                hits.append({"node": n["id"], "matched_surface_form": sf})
                break
    return hits


# ------------------------------------------------------------------ main
def main():
    graph = load("p27_coverage_graph.json")
    planner = load("p26_v_gold40_planner_outputs.json")
    gt_all = load("p26_v_original_gold40_required_dimensions.json")
    scores = load("p26_v_scores.json")
    audit = load("p27_missed_dimension_audit.json")
    thresholds = load("p27_frozen_thresholds.json")

    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = [e for e in graph["edges"] if e["status"] == "VERIFIED"]
    d2gt = {k: v for k, v in graph["edge_to_gt_dimension_map"].items()
            if not k.startswith("_")}

    gt_by_case = {c["case_id"]: c["required_dimensions"] for c in gt_all}
    matched_by_case = {}
    for cs in scores["case_scores"]:
        matched_by_case[cs["case_id"]] = {
            d["dimension_id"]: d for d in cs["dimension_results"]}

    # -------- خرائط المصدر المُسنِد → الحالات التي تذكره في حقيقتها (H)
    src_to_cases = {}
    for cid, dims in gt_by_case.items():
        for d in dims:
            for sid in d.get("ground_truth_authority_ids") or []:
                src_to_cases.setdefault(sid, set()).add(cid)

    def edge_admissible(edge, case_id):
        """مقبولة إن كان أحد مصادرها حاضرًا في حقيقة حالة أخرى غير هذه."""
        for sid in edge["provenance"]:
            other = src_to_cases.get(sid, set()) - {case_id}
            if other:
                return True, sorted(other)
        return False, []

    # -------- تشغيل التوسعة على الأربعين (I + K)
    per_case = []
    for rec in planner:
        cid = rec["case_id"]
        ptext = planner_text(rec)
        seeds = seed_concepts(ptext, graph["nodes"])
        seed_ids = {s["node"] for s in seeds}

        gt_dims = {d["dimension_id"]: d for d in gt_by_case.get(cid, [])}
        mres = matched_by_case.get(cid, {})

        expansions = []
        for e in edges:
            if e["source"] not in seed_ids:
                continue
            adm, witnesses = edge_admissible(e, cid)
            tgt = e["target"]
            gt_ids = d2gt.get(tgt, [])
            hit_gt = [g for g in gt_ids if g in gt_dims]
            if hit_gt:
                g = hit_gt[0]
                already = bool(mres.get(g, {}).get("matched"))
                verdict = "COVERED" if already else (
                    "UNRESOLVED_CONDITIONAL" if e["necessity"] == "CONDITIONAL"
                    and not gt_dims[g].get("required") else "MISSING_REQUIRED")
                expansions.append({
                    "edge": e["id"], "source_concept": e["source"],
                    "dimension_node": tgt, "necessity": e["necessity"],
                    "gt_dimension_id": g,
                    "gt_required": bool(gt_dims[g].get("required")),
                    "gt_critical": bool(gt_dims[g].get("critical")),
                    "gt_role": gt_dims[g].get("legal_role"),
                    "planner_already_found": already,
                    "verdict": verdict,
                    "loco_admissible": adm, "loco_witness_cases": witnesses,
                    "provenance": e["provenance"],
                })
            else:
                expansions.append({
                    "edge": e["id"], "source_concept": e["source"],
                    "dimension_node": tgt, "necessity": e["necessity"],
                    "gt_dimension_id": None, "gt_required": False,
                    "gt_critical": False, "gt_role": None,
                    "planner_already_found": False,
                    "verdict": "NOT_IN_GROUND_TRUTH",
                    "loco_admissible": adm, "loco_witness_cases": witnesses,
                    "provenance": e["provenance"],
                })

        per_case.append({
            "case_id": cid,
            "seeds": seeds,
            "n_gt_dimensions": len(gt_dims),
            "expansions": expansions,
        })

    # ------------------------------------------------- المقاييس (L/M/N)
    def agg(loco_only):
        tot = crit = rec = crit_rec = 0
        rescues, rescues_crit = [], []
        additions = 0          # كل ما تضيفه graph فوق Planner
        additions_true = 0     # منها ما يطابق بُعدًا حقيقيًا في حقيقة الحالة
        false_adds = []
        by_role = {}
        by_class = {}
        # الفئة من تدقيق الأخطاء
        cls_of = {(a["case_id"], a["dimension_id"]): a["classification"]
                  for a in audit["audit"]}

        n_complete = 0
        for cs in scores["case_scores"]:
            cid = cs["case_id"]
            exp = {x["gt_dimension_id"]: x for x in
                   next(p for p in per_case if p["case_id"] == cid)["expansions"]
                   if x["gt_dimension_id"]}
            case_crit_all = True
            for d in cs["dimension_results"]:
                gd = next((g for g in gt_by_case[cid]
                           if g["dimension_id"] == d["dimension_id"]), {})
                # المقام هو مقام المُقيِّم المجمَّد نفسه: كل أبعاد الحقيقة الأرضية
                # (142 بُعدًا) لا الواجبة وحدها — وإلا لم تُقارَن الأرقام بخط الأساس.
                tot += 1
                role = gd.get("legal_role") or "other"
                by_role.setdefault(role, [0, 0])
                by_role[role][1] += 1
                is_crit = bool(gd.get("critical"))
                if is_crit:
                    crit += 1
                hit = bool(d["matched"])
                x = exp.get(d["dimension_id"])
                graph_hit = bool(x) and (x["loco_admissible"] or not loco_only)
                if not hit and graph_hit:
                    rescues.append((cid, d["dimension_id"]))
                    if is_crit:
                        rescues_crit.append((cid, d["dimension_id"]))
                    k = cls_of.get((cid, d["dimension_id"]), "UNCLASSIFIED")
                    by_class.setdefault(k, [0, 0])
                    by_class[k][0] += 1
                if hit or graph_hit:
                    rec += 1
                    by_role[role][0] += 1
                    if is_crit:
                        crit_rec += 1
                elif is_crit:
                    case_crit_all = False
            n_complete += 1 if case_crit_all else 0
            # دقة الإضافة
            for x in next(p for p in per_case if p["case_id"] == cid)["expansions"]:
                if loco_only and not x["loco_admissible"]:
                    continue
                if x["planner_already_found"]:
                    continue          # ليست إضافة — Planner أصابها أصلًا
                additions += 1
                if x["gt_dimension_id"]:
                    additions_true += 1
                else:
                    false_adds.append((cid, x["edge"], x["dimension_node"]))

        # مقامات الفئات من تدقيق الأخطاء (هدف الـgraph)
        for a in audit["audit"]:
            if a.get("excluded_from_graph_target"):
                continue
            k = a["classification"]
            by_class.setdefault(k, [0, 0])
            by_class[k][1] += 1

        return {
            "loco_clean_only": loco_only,
            "gt_required_total": tot,
            "gt_critical_total": crit,
            "dimension_recall": round(rec / tot, 4) if tot else None,
            "critical_dimension_recall": round(crit_rec / crit, 4) if crit else None,
            "strict_case_completeness": round(n_complete / len(scores["case_scores"]), 4),
            "no_regression_substantive": 0,
            "_no_regression_note": "الـgraph تضيف ولا تحذف: الاتحاد مع مخرَج Planner لا يُسقط "
                                   "أي بُعد كان يصيبه، فالانحدار صفر بنيويًا لا قياسًا.",
            "n_rescued": len(rescues),
            "n_rescued_critical": len(rescues_crit),
            "rescued": rescues,
            "rescued_critical": rescues_crit,
            "graph_additions_total": additions,
            "graph_additions_matching_gt": additions_true,
            "graph_addition_precision": round(additions_true / additions, 4) if additions else None,
            "false_additions": false_adds,
            "recall_by_legal_role": {k: {"hit": v[0], "total": v[1],
                                         "recall": round(v[0] / v[1], 4) if v[1] else None}
                                     for k, v in sorted(by_role.items())},
            "rescue_by_audit_class": {k: {"rescued": v[0], "target": v[1]}
                                      for k, v in sorted(by_class.items())},
        }

    results = {
        "_note": "P2.7 الأقسام H/I/K/L/M/N/O — قياس واحد بلا أي إعادة تشغيل لـPlanner.",
        "frozen_thresholds_ref": "tools/p27_frozen_thresholds.json",
        "baseline_A_planner_alone": {
            "dimension_recall": scores["aggregate"]["dimension_recall"],
            "critical_dimension_recall": scores["aggregate"]["critical_dimension_recall"],
            "dimension_precision": scores["aggregate"]["dimension_precision"],
            "strict_case_completeness": scores["aggregate"]["strict_case_completeness"],
        },
        "baseline_C_planner_plus_graph_LOCO_CLEAN": agg(True),
        "baseline_C_planner_plus_graph_WITH_LEAKAGE": agg(False),
        "per_case": per_case,
    }

    # -------- Graph alone (B): ما تصيبه التوسعة وحدها بلا Planner
    for loco in (True, False):
        tot = hit = crit = crit_hit = 0
        for cs in scores["case_scores"]:
            cid = cs["case_id"]
            exp = {x["gt_dimension_id"] for x in
                   next(p for p in per_case if p["case_id"] == cid)["expansions"]
                   if x["gt_dimension_id"] and (x["loco_admissible"] or not loco)}
            for gd in gt_by_case[cid]:
                tot += 1
                c = bool(gd.get("critical"))
                crit += 1 if c else 0
                if gd["dimension_id"] in exp:
                    hit += 1
                    crit_hit += 1 if c else 0
        results["baseline_B_graph_alone_%s" % ("LOCO_CLEAN" if loco else "WITH_LEAKAGE")] = {
            "dimension_recall": round(hit / tot, 4),
            "critical_dimension_recall": round(crit_hit / crit, 4),
            "covered": hit, "total": tot,
        }

    # -------- الضوابط السلبية (O)
    sys.path.insert(0, BASE)
    from p26_gold_tier_set import GOLD_TIER_SET
    from p26_dev_set import DEV_SET
    neg = []
    pool = [(c["id"], c["question"], c.get("complexity") or c.get("category"))
            for c in GOLD_TIER_SET] + \
           [(c["id"], c["question"], c.get("complexity") or c.get("category"))
            for c in DEV_SET]
    for cid, q, kind in pool:
        t = norm(q)
        s = seed_concepts(t, graph["nodes"])
        fired = []
        for e in edges:
            if e["source"] in {x["node"] for x in s}:
                fired.append(e["id"])
        neg.append({"case_id": cid, "kind": kind,
                    "seeds": [x["node"] for x in s], "edges_fired": fired})
    results["negative_controls_O"] = {
        "_note": "ضابط سلبي خارج Gold Set40 كليًا: 10 حالات Gold-tier + Dev Set. البذور "
                 "تُطابَق هنا على نص السؤال مباشرة (أشدّ من الإنتاج، إذ لا مخرج Planner "
                 "محفوظ لها) فأي إطلاق هنا يُحتسب ضد الـgraph لا لها.",
        "n_cases": len(neg),
        "n_cases_with_any_firing": sum(1 for x in neg if x["edges_fired"]),
        "n_total_edges_fired": sum(len(x["edges_fired"]) for x in neg),
        "detail": neg,
    }

    # -------- سلاسل الإنقاذ: بذرة ← حافة موثَّقة ← بُعد خفي ← مطابقة الحقيقة
    chains = []
    for cid, did in results["baseline_C_planner_plus_graph_LOCO_CLEAN"]["rescued"]:
        pc = next(p for p in per_case if p["case_id"] == cid)
        x = next(e for e in pc["expansions"] if e["gt_dimension_id"] == did)
        e = next(g for g in edges if g["id"] == x["edge"])
        seed = next(s for s in pc["seeds"] if s["node"] == e["source"])
        gd = next(g for g in gt_by_case[cid] if g["dimension_id"] == did)
        chains.append({
            "case_id": cid,
            "1_seed_concept": e["source"],
            "1_seed_surface_form_in_planner_output": seed["matched_surface_form"],
            "2_verified_edge": {"id": e["id"], "relation": e["relation"],
                                "necessity": e["necessity"],
                                "provenance": e["provenance"],
                                "legal_rationale": e["legal_rationale"]},
            "3_hidden_dimension_node": x["dimension_node"],
            "4_gold_match": {"dimension_id": did, "label": gd.get("label"),
                             "critical": gd.get("critical"),
                             "legal_role": gd.get("legal_role")},
            "loco_witness_cases": x["loco_witness_cases"],
        })
    results["rescue_chains_LOCO_CLEAN"] = chains

    results["threshold_verdict"] = {}
    th = thresholds["success_thresholds_planner_plus_graph"]
    c = results["baseline_C_planner_plus_graph_LOCO_CLEAN"]
    ops = {">=": lambda a, b: a >= b, ">": lambda a, b: a > b,
           "<=": lambda a, b: a <= b, "==": lambda a, b: a == b}
    checks = {
        "verified_dimension_recall": c["dimension_recall"],
        "critical_dimension_recall": c["critical_dimension_recall"],
        "graph_addition_precision": c["graph_addition_precision"],
    }
    for k, v in checks.items():
        spec = th[k]
        results["threshold_verdict"][k] = {
            "measured": v, "threshold": spec["value"], "op": spec["op"],
            "pass": bool(v is not None and ops[spec["op"]](v, spec["value"]))}

    out = os.path.join(BASE, "p27_graph_measurement.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

    # ------------------------------------------------------------- تقرير شاشة
    print("=" * 72)
    print("P2.7 — قياس Legal Coverage Graph (depth=1، حواف VERIFIED فقط)")
    print("=" * 72)
    a = results["baseline_A_planner_alone"]
    print("A) Planner وحده      : recall=%.4f  critical=%.4f" %
          (a["dimension_recall"], a["critical_dimension_recall"]))
    b = results["baseline_B_graph_alone_LOCO_CLEAN"]
    print("B) Graph وحدها (LOCO): recall=%.4f  critical=%.4f  (%d/%d)" %
          (b["dimension_recall"], b["critical_dimension_recall"],
           b["covered"], b["total"]))
    for key in ("baseline_C_planner_plus_graph_LOCO_CLEAN",
                "baseline_C_planner_plus_graph_WITH_LEAKAGE"):
        r = results[key]
        print("C) %-28s recall=%.4f  critical=%.4f  rescued=%d (حاكم %d)"
              % ("LOCO-CLEAN" if r["loco_clean_only"] else "WITH-LEAKAGE",
                 r["dimension_recall"], r["critical_dimension_recall"],
                 r["n_rescued"], r["n_rescued_critical"]))
        print("   إضافات=%d  منها مطابق للحقيقة=%d  دقة الإضافة=%s"
              % (r["graph_additions_total"], r["graph_additions_matching_gt"],
                 r["graph_addition_precision"]))
    print("-" * 72)
    r = results["baseline_C_planner_plus_graph_LOCO_CLEAN"]
    print("الإنقاذ بفئة تدقيق الأخطاء (LOCO-clean):")
    for k, v in r["rescue_by_audit_class"].items():
        print("   %-24s %d / %d" % (k, v["rescued"], v["target"]))
    print("الاستدعاء بدور قانوني (LOCO-clean):")
    for k, v in r["recall_by_legal_role"].items():
        print("   %-28s %d/%d = %s" % (k, v["hit"], v["total"], v["recall"]))
    print("-" * 72)
    n = results["negative_controls_O"]
    print("الضوابط السلبية: %d حالة، %d منها أطلقت حافة، إجمالي الإطلاقات %d"
          % (n["n_cases"], n["n_cases_with_any_firing"], n["n_total_edges_fired"]))
    print("-" * 72)
    for k, v in results["threshold_verdict"].items():
        print("عتبة %-28s %s %s  ← المقيس %s  %s"
              % (k, v["op"], v["threshold"], v["measured"],
                 "PASS" if v["pass"] else "FAIL"))
    print("=" * 72)
    print("كُتب: %s" % out)


if __name__ == "__main__":
    main()
