#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.3 §A — 5x مصفوفة القمع الكامل لكل معرِّف من الإخفاقات الحرجة السبعة (P2.2 §7).

تشخيص بحت — DIAGNOSTIC ONLY: 5 نداءات حية مستقلة لـ`_draft_build_context` (نفس دالة الإنتاج
الحقيقية، بلا أي تعديل) لكل حالة من الحالات الست الفريدة، بمحاور Haiku جديدة كل مرة (Normal
mode — لا تجميد محاور هنا؛ ذلك تجربة منفصلة، §C، حصريًا لأهداف تُظهر عدم استقرار اكتشاف في
هذه الخماسية). ممنوع صراحة في هذه الأداة وفي أي استعمال لمخرجاتها: أي تعديل إنتاجي، تغيير
caps/ميزانية/مرتِّب، قاعدة A3/بوابة جديدة، مرادف، تعديل استعلام، أو تعديل Gold Set بسبب النتائج.

يلتقط لكل هدف (authority_id) في كل تشغيلة، بمطابقة عضوية صريحة فقط على حقول `ctx` المؤكَّدة
حيًّا سابقًا (`verify_ctx_fields.py`، `probe_budget.py`، ومطابقة `frozen_axes_experiment.py`
القائمة لدلالة `provenance`/`admitted`):
  - discovered_by_any_channel : وُجد بأي قناة (كثيف قبل/بعد السقف، أو أي قناة أخرى)
  - pre_cap_present           : وُجد بالقناة الكثيفة تحديدًا قبل قرار السقف (إما بقي في
                                 `cap_dropped_ids` وإما نجا فدخل hits بمصدر `dense`) — القنوات
                                 الأخرى (فصل/حزمة/معجمي/مباشر/xref/شقيقات) لا يمسها السقف أصلًا
  - post_cap_present          : دخل حوض الترتيب فعليًا (`ctx['hits']`)، أي قناة
  - reranker_present          : له سجل في `ctx['provenance']` (خضع لحساب الدرجة/الرتبة)
  - reranker_raw / post_rerank_rank : من `provenance` مباشرة
  - budget_admitted           : `provenance['admitted']` (= قبول الميزانية، مطابق `seen`)
  - final_context             : `oid in ctx['seen']`
`DIMENSION_RECOGNIZED` **لا** يُحسَب آليًا هنا — يُترك لحكم بشري لاحق على نص `exact_axes`
المسجَّل لكل تشغيلة (نفس منهجية P2.2 §5)، لأنه حكم دلالي لا معيار نصي موثوق.

الحالات الست وأبعادها الحرجة (من P2.2 §7 حرفيًا، بلا أي إضافة أو حذف):"""
import json
import sys

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")

CRITICAL_TARGETS = {
    "gs-0002": [
        {"dimension_id": "civil_claim_route_amr_alada",
         "authority_ids": ["legis-38-1980-m166", "legis-38-1980-m167"]},
    ],
    "gs-0009": [
        {"dimension_id": "manager_refusal_to_convene_assembly",
         "authority_ids": ["regl-1-2016-m65"]},
    ],
    "gs-0010": [
        {"dimension_id": "wife_share_with_descendant",
         "authority_ids": ["legis-51-1984-m299"]},
        {"dimension_id": "daughters_share_two_thirds",
         "authority_ids": ["legis-51-1984-m300"]},
    ],
    "gs-0011": [
        {"dimension_id": "tadakhkhul_alniyaba_alamma_wujubi",
         "authority_ids": ["legis-51-1984-m337", "legis-51-1984-m338"]},
    ],
    "gs-0014": [
        {"dimension_id": "sarayan_alqararat_alaskariya_ala_almujannadin",
         "authority_ids": ["legis-20-2015-m49"]},
    ],
    "gs-0017": [
        {"dimension_id": "nullity_effect_of_disqualified_judge",
         "authority_ids": ["legis-38-1980-m103"]},
    ],
}


def load_gold_set(path="/opt/LegalMind/tools/retrieval_gold_set.json"):
    return {c["id"]: c for c in json.load(open(path, encoding="utf-8"))["cases"]}


def trace_authority_full(oid, ctx):
    hits = ctx["hits"]
    attr = ctx["attr"]
    seen = ctx["seen"]
    provenance_by_id = {p["object_id"]: p for p in ctx["provenance"]}
    hit_sources = {}
    for _l, _s, p in hits:
        the_id = p.get("object_id")
        if the_id:
            hit_sources.setdefault(the_id, set()).add(p.get("_source", "?"))
    hit_ids = set(hit_sources.keys())
    cap_dropped_ids = set(attr.get("cap_dropped_ids") or [])

    in_hits = oid in hit_ids
    in_cap_dropped = oid in cap_dropped_ids
    sources = hit_sources.get(oid, set())
    pre_cap_present = in_cap_dropped or ("dense" in sources)
    prov = provenance_by_id.get(oid)

    channels = sorted(sources)
    if in_cap_dropped and "dense" not in channels:
        channels.append("dense(cap_dropped)")

    return {
        "object_id": oid,
        "discovered_by_any_channel": in_hits or in_cap_dropped,
        "discovery_channels": channels,
        "pre_cap_present": pre_cap_present,
        "post_cap_present": in_hits,
        "reranker_present": prov is not None,
        "reranker_raw": (prov or {}).get("reranker_raw"),
        "post_rerank_rank": (prov or {}).get("rank"),
        "budget_admitted": bool((prov or {}).get("admitted")),
        "final_context": oid in seen,
    }


def run_one(app, client, case, dims_for_case):
    inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
    ctx = app._draft_build_context(client, inp, case["question"])
    dim_traces = []
    for d in dims_for_case:
        dim_traces.append({
            "dimension_id": d["dimension_id"],
            "authority_traces": {oid: trace_authority_full(oid, ctx) for oid in d["authority_ids"]},
        })
    return {"exact_axes": list(ctx.get("subqueries") or []), "dimension_traces": dim_traces}


def main():
    import anthropic
    from admin import app

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    gold = load_gold_set()

    args = sys.argv[1:]
    case_ids = args[0].split(",") if args and args[0] else sorted(CRITICAL_TARGETS.keys())
    runs = int(args[1]) if len(args) > 1 else 5

    results = {}
    for cid in case_ids:
        print(f"=== {cid} — {runs} تشغيلات مستقلة ===", flush=True)
        case_runs = []
        for i in range(runs):
            r = run_one(app, client, gold[cid], CRITICAL_TARGETS[cid])
            r["run_id"] = f"run-{i + 1}"
            case_runs.append(r)
            print(f"  run-{i + 1}: axes={r['exact_axes']}", flush=True)
            for dt in r["dimension_traces"]:
                for oid, t in dt["authority_traces"].items():
                    print(f"    [{dt['dimension_id']}] {oid}: disc={t['discovered_by_any_channel']} "
                          f"pre_cap={t['pre_cap_present']} post_cap={t['post_cap_present']} "
                          f"rerank_present={t['reranker_present']} rerank_raw={t['reranker_raw']} "
                          f"rank={t['post_rerank_rank']} budget_admitted={t['budget_admitted']} "
                          f"final={t['final_context']} channels={t['discovery_channels']}", flush=True)
        results[cid] = case_runs

    print()
    print("=" * 70)
    print("P23_STABLE_MATRIX_RAW_RESULTS")
    print("=" * 70)
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    print(f"\nP23_STABLE_MATRIX_DONE | cases={len(results)}")


if __name__ == "__main__":
    main()
