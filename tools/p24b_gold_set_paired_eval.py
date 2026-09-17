#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.4B — PHASE 1: Paired Gold Set40 Evaluation (Baseline vs Arm B).

**آلية الحقن الوحيدة المسموح بها:** `admission_policy=fixed_cap_policy` **يبقى مطابقًا
للأساس تمامًا في كلا الجانبين** — لا سقف ديناميكي، لا Arm A، لا دمج A+B. المتغير الوحيد بين
الأساس وArm B هو قائمة subqueries المُغذَّاة لنفس تسلسل `build_context_traced` (من P2.4A-DIAG،
غير معدَّل هنا) الحقيقي: الأساس يستعمل محاور Haiku المجمَّدة فقط؛ Arm B يستعمل **نفس** المحاور
+ `scope_queries` الناتجة من `p24b_concept_backbone.recognize(facts)` (طبقة حتمية مجمَّدة،
بصمة c5153b06...، غير مُعدَّلة). محاور Haiku مجمَّدة بنداء واحد لكل حالة يُعاد استعماله للجانبين
معًا (الثابت التجريبي docs/p2_4_experimental_invariant.md).

subqueries هي بالضبط القناة التي تتغذى منها bundle/direct/chapter/lexical **أيضًا** (لا الكثيف
وحده) — فحقن scope_queries فيها يختبر الفرضية المعمارية عبر كل القنوات دفعة واحدة، لا قناة
مصطنعة موازية.

Gold Set **للتقييم فقط** — `load_gold_set`/`must_find`/`must_find_any_of` تُستهلَك هنا بصفتها
الحقيقة الأرضية المستقلة الموجودة سلفًا، لا بصفتها مصدر تصميم لأي قاعدة (القواعد جُمِّدت في
PHASE 0/الالتزام السابق قبل هذا الملف بالكامل)."""
import json
import sys
import time

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")


def _covered(seen, oid):
    return oid in seen


def run_case(app, client, pipe, backbone, case):
    inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
    facts = case["question"]

    t0 = time.monotonic()
    frozen_axes = app._draft_subqueries(client, case["request_type"], facts,
                                         getattr(inp, "madhab", None), [])
    axes_s = time.monotonic() - t0

    rec = backbone.recognize(facts)  # حتمي بالكامل — صفر نداء نموذج لغوي هنا
    arm_b_subqueries = frozen_axes + rec["scope_queries"]

    must_find = case.get("must_find") or []
    must_find_any_of = case.get("must_find_any_of") or []
    all_group_ids = list(must_find) + [oid for g in must_find_any_of for oid in g]
    trace_ids = set(all_group_ids)

    from p24a_diag_provenance_trace import build_context_traced

    t0 = time.monotonic()
    baseline_res = build_context_traced(app, client, inp, facts, pipe.fixed_cap_policy,
                                         frozen_axes, trace_ids=trace_ids)
    baseline_s = time.monotonic() - t0

    t0 = time.monotonic()
    arm_b_res = build_context_traced(app, client, inp, facts, pipe.fixed_cap_policy,
                                      arm_b_subqueries, trace_ids=trace_ids)
    arm_b_s = time.monotonic() - t0

    per_authority = {}
    for oid in trace_ids:
        b_in_best = oid in baseline_res["best"]
        a_in_best = oid in arm_b_res["best"]
        b_events = baseline_res["events"].get(oid, [])
        a_events = arm_b_res["events"].get(oid, [])
        b_final = _covered(baseline_res["seen"], oid)
        a_final = _covered(arm_b_res["seen"], oid)
        _NON_DISCOVERY_CHANNELS = ("FINAL", "post_rerank", "budget")
        b_discovered = b_in_best or any(e.get("channel") not in _NON_DISCOVERY_CHANNELS for e in b_events)
        a_discovered = a_in_best or any(e.get("channel") not in _NON_DISCOVERY_CHANNELS for e in a_events)

        rescue_primary_cause = None
        if (not b_final) and a_final:
            if a_in_best and not b_in_best:
                rescue_primary_cause = "DENSE_DISCOVERY_VIA_SCOPE"
            elif a_discovered and not b_discovered:
                rescue_primary_cause = "CHANNEL_DISCOVERY_VIA_SCOPE"
            else:
                rescue_primary_cause = "OTHER_RANKING_OR_BUDGET"

        new_loss_cause = None
        if b_final and not a_final:
            new_loss_cause = "COMPETITION_OR_OTHER"  # فحص يدوي عبر events عند الحاجة

        per_authority[oid] = {
            "baseline_discovered": b_discovered, "arm_b_discovered": a_discovered,
            "baseline_in_dense_best": b_in_best, "arm_b_in_dense_best": a_in_best,
            "baseline_final": b_final, "arm_b_final": a_final,
            "rescue_primary_cause": rescue_primary_cause, "new_loss_cause": new_loss_cause,
            "baseline_events": b_events, "arm_b_events": a_events,
        }

    return {
        "case_id": case["id"], "frozen_axes": frozen_axes, "axes_s": round(axes_s, 2),
        "arm_b_recognition": rec,
        "must_find": must_find, "must_find_any_of": must_find_any_of,
        "per_authority": per_authority,
        "baseline_final_context_count": baseline_res["final_context_count"],
        "arm_b_final_context_count": arm_b_res["final_context_count"],
        "baseline_rerank_pool": baseline_res["rerank_pool_size"],
        "arm_b_rerank_pool": arm_b_res["rerank_pool_size"],
        "baseline_wall_s": round(baseline_s, 2), "arm_b_wall_s": round(arm_b_s, 2),
    }


def main():
    import anthropic
    from admin import app
    import p24_offline_pipeline as pipe
    import p24b_concept_backbone as backbone
    from p23_stable_failure_matrix import load_gold_set

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    gold = load_gold_set()

    args = sys.argv[1:]
    case_ids = args[0].split(",") if args and args[0] else sorted(gold.keys())

    results = {}
    for cid in case_ids:
        case = gold[cid]
        r = run_case(app, client, pipe, backbone, case)
        results[cid] = r
        concepts = r["arm_b_recognition"]["concepts_triggered"]
        deps = r["arm_b_recognition"]["dependencies_triggered"]
        rescues = [oid for oid, a in r["per_authority"].items() if a["rescue_primary_cause"]]
        losses = [oid for oid, a in r["per_authority"].items() if a["new_loss_cause"]]
        print(f"[{cid}] concepts={concepts} deps={deps} rescues={rescues} losses={losses} "
              f"ctx_delta={r['arm_b_final_context_count'] - r['baseline_final_context_count']}", flush=True)

    print()
    print("=" * 70)
    print("P24B_GOLDSET_PAIRED_RAW_RESULTS")
    print("=" * 70)
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    print("\nP24B_GOLDSET_PAIRED_DONE")


if __name__ == "__main__":
    main()
