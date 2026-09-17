#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.2 — تشخيص فجوة التغطية (Coverage Gap Diagnostic): تتبّع قمع النجاة (Retrieval Funnel)
لكل هدف من ضمن الـ30 معرِّف الحاكم عبر 24 بُعدًا مفقودًا في 19 حالة فريدة
(tools/coverage_gap_diagnostic_targets.json، مُشتقَّة حصرًا من required_dimensions المجمَّدة
بعد الحساب — انظر benchmark_evaluator.categorize_dimensions لنفس المصدر). تشغيل حي واحد لكل
حالة (_draft_build_context الحقيقية، بلا أي تعديل على أي ملف قرار أو قاعدة استرجاع) يلتقط
الحقول الخام المؤكَّدة حيًّا (verify_ctx_fields.py وprobe_budget.py، 2026-09-16):
  - ctx['hits']            → مجمّع المرشحين الداخل فعليًا لحوض إعادة الترتيب (كل القنوات)
  - ctx['attr']['cap_dropped_ids']  → دلاليّ اكتُشف لكن قُصّ بسقف المرحلة الأولى **قبل** الحوض
  - ctx['provenance']      → لكل مرشح دخل الحوض: pre_rerank_score/reranker_raw/final_score/
                             rank/admitted (المفتاح 'object_id'؛ لا 'id')
  - ctx['budget_dropped_full']  → مفتاح **أعلى المستوى** (لا داخل attr) — صفوف
                             {id, type, score, chars_requested, remaining_budget} (تأكَّد
                             حيًّا: المفتاح 'id' لا 'object_id' — probe_budget.py 2026-09-16)
  - ctx['seen']            → السياق النهائي الفعلي (= current_final_context في Shadow A/B)
  - ctx['attr']['stage2_dup_dropped_ids'] / ['principle_precap_dup_dropped_ids']  → أُسقط
                             بوصفه نسخة مكرِّرة لمبدأ آخر (تحقُّق تكرار لا فقد جوهري بالضرورة)

هذا تشخيص بحت: صفر تعديل على أي ملف قرار حي أو قاعدة استرجاع، وصفر استعمال لأي حقل من
required_dimensions/ground_truth_* داخل أي مسار قرار — يُقرأ بعد الحساب فقط لتحديد أي هدف
نتتبَّعه، تمامًا كما benchmark_evaluator.py (انظر tools/benchmark_isolation_test.py للتحقق
الآلي أن هذا النمط لا يُسرِّب لأي ملف قرار حي)."""
import json
import sys

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")


def load_targets(path="/opt/LegalMind/tools/coverage_gap_diagnostic_targets.json"):
    return json.load(open(path, encoding="utf-8"))


def load_gold_set(path="/opt/LegalMind/tools/retrieval_gold_set.json"):
    return json.load(open(path, encoding="utf-8"))["cases"]


def trace_authority(oid, ctx):
    """يحدِّد موضع هدف واحد في القمع بمطابقة عضوية صريحة فقط على الحقول المؤكَّدة حيًّا —
    بلا أي استنتاج لمنطق غير مُلاحَظ مباشرة في هذا التشغيل بعينه."""
    hits = ctx["hits"]
    attr = ctx["attr"]
    seen = ctx["seen"]
    provenance_by_id = {p["object_id"]: p for p in ctx["provenance"]}
    budget_dropped_full = ctx.get("budget_dropped_full") or []
    budget_dropped_by_id = {row["id"]: row for row in budget_dropped_full if "id" in row}

    hit_sources = {}
    for _l, _s, p in hits:
        the_id = p.get("object_id")
        if the_id:
            hit_sources.setdefault(the_id, set()).add(p.get("_source", "?"))
    hit_ids = set(hit_sources.keys())

    cap_dropped_ids = set(attr.get("cap_dropped_ids") or [])
    stage2_dup_dropped_ids = set(attr.get("stage2_dup_dropped_ids") or [])
    principle_precap_dup_dropped_ids = set(attr.get("principle_precap_dup_dropped_ids") or [])

    in_hits = oid in hit_ids
    in_cap_dropped = oid in cap_dropped_ids
    in_stage2_dup = oid in stage2_dup_dropped_ids
    in_precap_dup = oid in principle_precap_dup_dropped_ids
    in_provenance = oid in provenance_by_id
    in_budget_dropped = oid in budget_dropped_by_id
    in_final = oid in seen

    discovered_by_any_channel = in_hits or in_cap_dropped or in_stage2_dup or in_precap_dup

    return {
        "object_id": oid,
        "in_final_context": in_final,
        "discovered_by_any_channel": discovered_by_any_channel,
        "in_hits_pool": in_hits,
        "hit_sources": sorted(hit_sources.get(oid, ())),
        "in_cap_dropped_ids": in_cap_dropped,
        "in_stage2_dup_dropped_ids": in_stage2_dup,
        "in_principle_precap_dup_dropped_ids": in_precap_dup,
        "in_provenance": in_provenance,
        "provenance_record": provenance_by_id.get(oid),
        "in_budget_dropped_full": in_budget_dropped,
        "budget_dropped_record": budget_dropped_by_id.get(oid),
    }


def run_one(app, client, case, dims_for_case):
    inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
    ctx = app._draft_build_context(client, inp, case["question"])

    dim_traces = []
    for d in dims_for_case:
        auth_traces = {oid: trace_authority(oid, ctx) for oid in d["authority_ids"]}
        dim_traces.append({
            "dimension_id": d["dimension_id"],
            "dimension_label": d["dimension_label"],
            "critical": d["critical"],
            "legal_role": d["legal_role"],
            "dimension_satisfied_this_draw": any(
                t["in_final_context"] for t in auth_traces.values()),
            "authority_traces": auth_traces,
        })

    return {
        "case_id": case["id"],
        "subqueries": ctx.get("subqueries"),
        "attr_summary": ctx["attr"],
        "final_context_count": len(ctx["seen"]),
        "final_context_ids": sorted(ctx["seen"]),
        "dimension_traces": dim_traces,
    }


def main():
    import anthropic
    from admin import app

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)

    targets = load_targets()
    gold_cases = {c["id"]: c for c in load_gold_set()}

    args = sys.argv[1:]
    case_ids = args[0].split(",") if args else sorted(targets.keys())

    results = []
    for cid in case_ids:
        case = gold_cases.get(cid)
        dims_for_case = targets.get(cid)
        if not case or not dims_for_case:
            print(f"  !! لا توجد حالة/أهداف لـ{cid}", flush=True)
            continue
        n_auth = sum(len(d["authority_ids"]) for d in dims_for_case)
        print(f"... {cid} — تتبّع القمع ({len(dims_for_case)} بُعدًا، {n_auth} معرِّفًا)",
              flush=True)
        try:
            r = run_one(app, client, case, dims_for_case)
        except Exception as e:
            print(f"  !! coverage-gap-error: {e!r}", flush=True)
            continue
        results.append(r)
        for dt in r["dimension_traces"]:
            for oid, t in dt["authority_traces"].items():
                print(f"    [{dt['dimension_id']}] {oid}: final={t['in_final_context']} "
                      f"hits={t['in_hits_pool']}({','.join(t['hit_sources']) or '-'}) "
                      f"cap_dropped={t['in_cap_dropped_ids']} "
                      f"budget_dropped={t['in_budget_dropped_full']} "
                      f"discovered_any={t['discovered_by_any_channel']}", flush=True)

    print()
    print("=" * 70)
    print("COVERAGE_GAP_RAW_RESULTS")
    print("=" * 70)
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    print(f"\nCOVERAGE_GAP_DIAGNOSTIC_DONE | cases={len(results)}")


if __name__ == "__main__":
    main()
