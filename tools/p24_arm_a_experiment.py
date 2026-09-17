#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.4 — Arm A: مقارنة مقابلة للواقع (Counterfactual) بين `fixed_cap_policy` (الأساس، يكرر
سلوك الإنتاج حرفيًا) و`dynamic_admission_policy_for_pipeline` (Arm A) — كلاهما عبر
`tools/p24_offline_pipeline.build_context_offline` نفسها، بلا أي مساس بـ`admin/app.py`.

**تشخيص بحت — DIAGNOSTIC ONLY.** لا تعديل إنتاجي، لا رفع ميزانية، لا قاعدة خاصة بحالة، ولا
تصميم مبني على معرِّف سلطة بعينه. القائمة `CRITICAL_TARGETS` مستوردة من P2.3 (بنية قائمة سلفًا
لا شيء جديد يُضاف بسبب هذه التجربة).

**مرحلتان:**
1. **تمريرة واحدة على Gold Set كاملة** (كل حالة مرة واحدة، أساس مقابل ديناميكي) — تقيس
   must_find/must_find_any_of، دلتا حجم حوض المرتِّب، دلتا زمن المرتِّب، دلتا حجم السياق
   النهائي، عبر كل الأربعين حالة.
2. **5x استقرار على حالات الإخفاقات الحرجة فقط** (`CRITICAL_TARGETS`، تشمل تحديدًا حالتَي
   `PRE_RERANK_CAP_FAILURE`/`INTERMITTENT_PRE_RERANK_CAP_FAILURE`: gs-0009/regl-1-2016-m65
   وgs-0014/legis-20-2015-m49) — أساس مقابل ديناميكي، 5 تكرارات مستقلة لكل جانب، تُبلِغ عن
   rescue_rate (كم من التكرارات أنقذ فيها Arm A هدفًا كان غائبًا في الأساس لنفس التكرار)،
   survival_rate (كم من نجاحات الأساس بقيت ناجحة في Arm A — لا فقد جديد)، وnew_loss_rate
   (كم من نجاحات الأساس فُقدت في Arm A تحديدًا).

يُطبع تقدُّم سطر-بسطر (`flush=True`) وحصيلة JSON نهائية تحت علامة `ARM_A_FULL_EXPERIMENT_DONE`.
يُنصَح بتشغيله بـ`nohup` (قد يستغرق عشرات الدقائق: ~140 نداء `build_context_offline`، كل واحد
يستدعي Haiku + تضمين + Qdrant + المرتِّب المتقاطع الحقيقي بإعادة تحميل نموذجه)."""
import json
import sys
import time

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")


def _covered(ctx, oid):
    return oid in ctx["seen"]


def _any_of_covered(ctx, group):
    return any(_covered(ctx, o) for o in group)


def _measure_one(app, client, pipe, arm_a, case):
    """يشغّل الأساس والديناميكي مرة واحدة لحالة واحدة، يُعيد قاموس مقارنة مسطَّح."""
    inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
    facts = case["question"]

    t0 = time.monotonic()
    b_ctx = pipe.build_context_offline(app, client, inp, facts, admission_policy=pipe.fixed_cap_policy)
    b_time = time.monotonic() - t0

    t0 = time.monotonic()
    d_ctx = pipe.build_context_offline(app, client, inp, facts,
                                        admission_policy=arm_a.dynamic_admission_policy_for_pipeline)
    d_time = time.monotonic() - t0

    must_find = case.get("must_find") or []
    must_find_any_of = case.get("must_find_any_of") or []

    b_must = {o: _covered(b_ctx, o) for o in must_find}
    d_must = {o: _covered(d_ctx, o) for o in must_find}
    b_anyof = [_any_of_covered(b_ctx, g) for g in must_find_any_of]
    d_anyof = [_any_of_covered(d_ctx, g) for g in must_find_any_of]

    rescued = [o for o in must_find if not b_must[o] and d_must[o]]
    lost = [o for o in must_find if b_must[o] and not d_must[o]]
    anyof_rescued = [i for i, (bv, dv) in enumerate(zip(b_anyof, d_anyof)) if not bv and dv]
    anyof_lost = [i for i, (bv, dv) in enumerate(zip(b_anyof, d_anyof)) if bv and not dv]

    return {
        "baseline_must_find": b_must, "dynamic_must_find": d_must,
        "baseline_any_of": b_anyof, "dynamic_any_of": d_anyof,
        "rescued": rescued, "lost": lost,
        "any_of_rescued_group_idx": anyof_rescued, "any_of_lost_group_idx": anyof_lost,
        "baseline_reranker_pool": b_ctx["attr"]["reranker_pool_size"],
        "dynamic_reranker_pool": d_ctx["attr"]["reranker_pool_size"],
        "reranker_pool_delta": d_ctx["attr"]["reranker_pool_size"] - b_ctx["attr"]["reranker_pool_size"],
        "baseline_rerank_s": round(b_ctx["timings"].get("rerank_s") or 0, 3),
        "dynamic_rerank_s": round(d_ctx["timings"].get("rerank_s") or 0, 3),
        "rerank_runtime_delta_s": round((d_ctx["timings"].get("rerank_s") or 0)
                                         - (b_ctx["timings"].get("rerank_s") or 0), 3),
        "baseline_context_count": b_ctx["attr"]["final_context_count"],
        "dynamic_context_count": d_ctx["attr"]["final_context_count"],
        "context_count_delta": d_ctx["attr"]["final_context_count"] - b_ctx["attr"]["final_context_count"],
        "baseline_wall_s": round(b_time, 2), "dynamic_wall_s": round(d_time, 2),
    }


def _authority_trace(app, ctx, oid):
    """إعادة استعمال منطق التتبع الحقيقي من P2.3 (trace_authority_full) — لا إعادة اختراع."""
    from p23_stable_failure_matrix import trace_authority_full
    return trace_authority_full(oid, ctx)


def phase1_full_gold_set(app, client, pipe, arm_a, gold, case_ids):
    results = {}
    for cid in case_ids:
        case = gold[cid]
        r = _measure_one(app, client, pipe, arm_a, case)
        results[cid] = r
        print(f"[P1][{cid}] rescued={r['rescued']} lost={r['lost']} "
              f"any_of_rescued_groups={r['any_of_rescued_group_idx']} "
              f"any_of_lost_groups={r['any_of_lost_group_idx']} "
              f"pool_delta={r['reranker_pool_delta']} rerank_dt={r['rerank_runtime_delta_s']}s "
              f"ctx_delta={r['context_count_delta']}", flush=True)
    return results


def phase2_stability(app, client, pipe, arm_a, gold, critical_targets, runs=5):
    """5x على حالات CRITICAL_TARGETS فقط (بنية P2.3 القائمة، لا شيء جديد بسبب هذه التجربة)."""
    all_authority_ids = sorted({oid for dims in critical_targets.values() for d in dims
                                 for oid in d["authority_ids"]})
    per_authority_runs = {oid: [] for oid in all_authority_ids}
    per_case_runs = {}

    for cid, dims in critical_targets.items():
        case = gold[cid]
        inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
        facts = case["question"]
        case_runs = []
        for i in range(runs):
            b_ctx = pipe.build_context_offline(app, client, inp, facts, admission_policy=pipe.fixed_cap_policy)
            d_ctx = pipe.build_context_offline(app, client, inp, facts,
                                                admission_policy=arm_a.dynamic_admission_policy_for_pipeline)
            run_rec = {"run": i + 1, "authorities": {}}
            for d in dims:
                for oid in d["authority_ids"]:
                    b_final = _covered(b_ctx, oid)
                    d_final = _covered(d_ctx, oid)
                    b_trace = _authority_trace(app, b_ctx, oid)
                    d_trace = _authority_trace(app, d_ctx, oid)
                    rec = {
                        "dimension_id": d["dimension_id"],
                        "baseline_final": b_final, "dynamic_final": d_final,
                        "baseline_pre_cap_present": b_trace["pre_cap_present"],
                        "baseline_post_cap_present": b_trace["post_cap_present"],
                        "dynamic_pre_cap_present": d_trace["pre_cap_present"],
                        "dynamic_post_cap_present": d_trace["post_cap_present"],
                        "outcome": (
                            "rescued" if (not b_final and d_final) else
                            "new_loss" if (b_final and not d_final) else
                            "survived_success" if (b_final and d_final) else
                            "still_failing"
                        ),
                    }
                    run_rec["authorities"][oid] = rec
                    per_authority_runs[oid].append(rec)
                    print(f"[P2][{cid}][{oid}] run {i+1}/{runs}: {rec['outcome']} "
                          f"(baseline={b_final} dynamic={d_final})", flush=True)
            case_runs.append(run_rec)
        per_case_runs[cid] = case_runs

    summary = {}
    for oid, recs in per_authority_runs.items():
        n = len(recs)
        rescued_n = sum(1 for r in recs if r["outcome"] == "rescued")
        survived_n = sum(1 for r in recs if r["outcome"] == "survived_success")
        new_loss_n = sum(1 for r in recs if r["outcome"] == "new_loss")
        still_failing_n = sum(1 for r in recs if r["outcome"] == "still_failing")
        baseline_success_n = survived_n + new_loss_n  # كان ناجحًا بالأساس (بصرف النظر عن مصيره في Arm A)
        summary[oid] = {
            "n_runs": n,
            "rescue_rate": round(rescued_n / n, 3) if n else None,
            "survival_rate": round(survived_n / baseline_success_n, 3) if baseline_success_n else None,
            "new_loss_rate": round(new_loss_n / baseline_success_n, 3) if baseline_success_n else None,
            "still_failing_rate": round(still_failing_n / n, 3) if n else None,
            "raw_counts": {"rescued": rescued_n, "survived": survived_n,
                            "new_loss": new_loss_n, "still_failing": still_failing_n},
        }
    return {"per_case_runs": per_case_runs, "per_authority_summary": summary}


def main():
    import anthropic
    from admin import app
    import p24_offline_pipeline as pipe
    import p24_arm_a_dynamic_cap as arm_a
    from p23_stable_failure_matrix import load_gold_set, CRITICAL_TARGETS

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    gold = load_gold_set()

    args = sys.argv[1:]
    phase = args[0] if args else "both"
    stability_runs = int(args[1]) if len(args) > 1 else 5

    out = {"phase1": None, "phase2": None}

    if phase in ("1", "phase1", "both"):
        print("=== PHASE 1 — Gold Set كاملة، تمريرة واحدة (أساس × ديناميكي) ===", flush=True)
        out["phase1"] = phase1_full_gold_set(app, client, pipe, arm_a, gold, sorted(gold.keys()))

    if phase in ("2", "phase2", "both"):
        print(f"\n=== PHASE 2 — استقرار {stability_runs}x على حالات CRITICAL_TARGETS ===", flush=True)
        out["phase2"] = phase2_stability(app, client, pipe, arm_a, gold, CRITICAL_TARGETS, runs=stability_runs)
        print("\n--- ملخص per_authority (rescue_rate/survival_rate/new_loss_rate) ---", flush=True)
        for oid, s in out["phase2"]["per_authority_summary"].items():
            print(f"  {oid}: {s}", flush=True)

    print()
    print("=" * 70)
    print("ARM_A_FULL_EXPERIMENT_RAW_RESULTS")
    print("=" * 70)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    print("\nARM_A_FULL_EXPERIMENT_DONE")


if __name__ == "__main__":
    main()
