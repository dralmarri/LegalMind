#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1 — قمع النجاة الكامل (Survival Funnel) لكل حالة Gold Set — الطابق الأعمق الذي
gold_metrics.py (Candidate Recall فقط) لا يقيسه. يستدعي _draft_build_context مباشرة
(P1-6، `.bak_buildctx`) — نفس خط الاسترجاع الحقيقي في الإنتاج بكل قنواته الثمانية
والمرتِّب والميزانية — بلا أي نداء توليد/صياغة حقيقي إطلاقًا.

لكل must_find/must_not_miss يُحسب: هل دخل تجمّع hits (نجا من احتمالي caps_n/P0-4
dedup)؟ هل سقط بـcaps_n تحديدًا؟ هل سقط بتكرار Stage-2؟ هل سقط بالميزانية؟ هل وصل
السياق النهائي فعليًا؟ — وتصنيف فشل آلي واحد بلا تخمين، من حقول `_attr` الفعلية
(cap_dropped_ids/principle_precap_dup_dropped_ids/stage2_dup_dropped_ids/budget_dropped)
+ عضوية `hits`/`seen` المُعادتين من _draft_build_context نفسها."""
import json
import sys

sys.path.insert(0, "/opt/LegalMind")


def load_gold_set(path="/opt/LegalMind/tools/retrieval_gold_set.json"):
    return json.load(open(path, encoding="utf-8"))["cases"]


def classify(oid, hits_ids, cap_dropped, precap_dup_dropped, stage2_dup_dropped,
             budget_dropped_ids, seen_ids):
    stages = {
        "in_hits_pool": oid in hits_ids,
        "cap_dropped": oid in cap_dropped,
        "precap_dup_dropped": oid in precap_dup_dropped,
        "stage2_dup_dropped": oid in stage2_dup_dropped,
        "budget_dropped": oid in budget_dropped_ids,
        "final_context": oid in seen_ids,
    }
    if stages["final_context"]:
        fail_class = None
    elif stages["budget_dropped"]:
        fail_class = "budget"
    elif stages["cap_dropped"]:
        fail_class = "cap"
    elif stages["precap_dup_dropped"] or stages["stage2_dup_dropped"]:
        fail_class = "dedup"
    elif stages["in_hits_pool"]:
        # كان في تجمّع hits ولم يدخل السياق ولم يُسجَّل سقوطه بأي قناة معروفة —
        # الاحتمال الوحيد المتبقي وفق منطق الحلقة: فشل جلب النص (oid not in texts)
        fail_class = "unknown_pool_loss"
    else:
        fail_class = "candidate-generation"  # لم يظهر في أي من القنوات الثماني إطلاقًا
    return {"id": oid, "stages": stages, "fail_class": fail_class}


def trace_case(app, client, case):
    inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
    facts_ret = case["question"]
    ctx = app._draft_build_context(client, inp, facts_ret)
    attr = ctx["attr"]
    hits_ids = {p.get("object_id") for _l, _s, p in ctx["hits"] if p.get("object_id")}
    seen_ids = ctx["seen"]
    cap_dropped = set(attr.get("cap_dropped_ids") or [])
    precap_dup_dropped = set(attr.get("principle_precap_dup_dropped_ids") or [])
    stage2_dup_dropped = set(attr.get("stage2_dup_dropped_ids") or [])
    # P1.5 (.bak_provenance): القائمة الكاملة بلا قصّ [:60] — الاسم القديم attr["budget_dropped"]
    # (الآن attr["budget_dropped_sample"]) كان يُخفي إسقاطات حقيقية خارج أول 60 عن هذا المصنِّف
    # تحديدًا (سبب سوء تصنيف legis-38-1980-m166 في gs-0013 كـ"unknown_pool_loss" بدل "budget").
    budget_dropped_ids = {d["id"] for d in (ctx.get("budget_dropped_full") or []) if d.get("id")}
    provenance_by_id = {p["object_id"]: p for p in (ctx.get("provenance") or [])}

    def trace_one(oid):
        t = classify(oid, hits_ids, cap_dropped, precap_dup_dropped,
                      stage2_dup_dropped, budget_dropped_ids, seen_ids)
        t["provenance"] = provenance_by_id.get(oid)
        return t

    must_traces = [trace_one(m) for m in case.get("must_find", [])]
    mnm_traces = [trace_one(m) for m in case.get("must_not_miss", [])]

    return {
        "case_id": case["id"], "category": case["category"],
        "retrieval_class": case.get("retrieval_class", []),
        "attr": attr,
        "must_find_traces": must_traces,
        "must_not_miss_traces": mnm_traces,
        "final_context_count": len(seen_ids),
        "hits_pool_count": len(hits_ids),
    }


def build_funnel(all_must):
    total = len(all_must)
    in_pool = sum(1 for t in all_must if t["stages"]["in_hits_pool"])
    survived_stage2 = sum(1 for t in all_must if t["stages"]["in_hits_pool"]
                           and not t["stages"]["stage2_dup_dropped"])
    survived_budget = sum(1 for t in all_must if t["stages"]["in_hits_pool"]
                           and not t["stages"]["stage2_dup_dropped"]
                           and not t["stages"]["budget_dropped"])
    final = sum(1 for t in all_must if t["stages"]["final_context"])
    fail_classes = {}
    for t in all_must:
        if t["fail_class"]:
            fail_classes[t["fail_class"]] = fail_classes.get(t["fail_class"], 0) + 1
    return {
        "total_must_find": total,
        "in_candidate_pool_hits": in_pool,
        "survived_stage2_dedup": survived_stage2,
        "survived_budget_check": survived_budget,
        "final_context": final,
        "consistency_check_budget_eq_final": survived_budget == final,
        "must_find_recall_full_pipeline": (final / total) if total else None,
        "failure_classes": fail_classes,
    }


def main():
    import anthropic
    from admin import app

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    cases = load_gold_set()
    results = []
    for c in cases:
        print(f"... {c['id']} — {c['category']}", flush=True)
        try:
            r = trace_case(app, client, c)
        except Exception as e:
            print(f"  ERROR: {c['id']}: {repr(e)}", flush=True)
            continue
        results.append(r)
        misses = [t for t in r["must_find_traces"] if t["fail_class"]]
        flag = "✓" if not misses else "✗"
        print(f"  {flag} must_find: {len(r['must_find_traces']) - len(misses)}/{len(r['must_find_traces'])}"
              f" | hits_pool: {r['hits_pool_count']} | final_context: {r['final_context_count']}"
              + (f" | فقد: {[(t['id'], t['fail_class']) for t in misses]}" if misses else ""),
              flush=True)
        mnm_misses = [t for t in r["must_not_miss_traces"] if t["fail_class"]]
        if mnm_misses:
            print(f"  ⚠ must_not_miss فقد: {[(t['id'], t['fail_class']) for t in mnm_misses]}", flush=True)
        # P1.5: نسب كل فقد (must_find وmust_not_miss) — قناته، رتبته، درجاته عبر المراحل
        for t in misses + mnm_misses:
            p = t.get("provenance")
            if p:
                print(f"    نسب {t['id']}: source={p['source']} rank={p['rank']} "
                      f"pre_rerank={p['pre_rerank_score']} reranker_raw={p['reranker_raw']} "
                      f"final_score={p['final_score']} admitted={p['admitted']}", flush=True)
            else:
                print(f"    نسب {t['id']}: غائب تمامًا عن ordered/provenance (لم يدخل hits إطلاقًا)", flush=True)

    all_must = [t for r in results for t in r["must_find_traces"]]
    all_mnm = [t for r in results for t in r["must_not_miss_traces"]]
    funnel = build_funnel(all_must)
    mnm_funnel = build_funnel(all_mnm) if all_mnm else None

    by_class = {}
    for r in results:
        for cls in (r["retrieval_class"] or ["(untagged)"]):
            by_class.setdefault(cls, {"must_find_total": 0, "must_find_final": 0})
            by_class[cls]["must_find_total"] += len(r["must_find_traces"])
            by_class[cls]["must_find_final"] += sum(
                1 for t in r["must_find_traces"] if t["stages"]["final_context"])

    print()
    print("=" * 70)
    print("قمع النجاة الكامل (Survival Funnel) — القسمان E/F من تقرير P1 (must_find)")
    print("=" * 70)
    print(json.dumps(funnel, ensure_ascii=False, indent=2))
    if mnm_funnel:
        print()
        print("قمع النجاة (must_not_miss — إخلال إجرائي إن فشل):")
        print(json.dumps(mnm_funnel, ensure_ascii=False, indent=2))
    print()
    print("Must-Find Recall حسب retrieval_class:")
    print(json.dumps(by_class, ensure_ascii=False, indent=2))
    print()
    print("SURVIVAL_METRICS_DONE | recall_full_pipeline=%s | cases=%d/%d"
          % (funnel["must_find_recall_full_pipeline"], len(results), len(cases)))


if __name__ == "__main__":
    main()
