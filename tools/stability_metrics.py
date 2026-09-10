#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1.6 — قياس استقرار الاسترجاع (Retrieval Stability Rate) لكل حالة Gold Set: يشغّل
_draft_build_context عدة تكرارات مستقلة (افتراضيًا 5، بنفس منهجية gs0015_stability.py
اليدوية المُعتمَدة سابقًا) على نفس السؤال، بتصفير كاش الفهرس (_draft_chap_index) بين كل
تكرار لمحاكاة طلب مستقل حقيقي — بلا أي نداء توليد. يقيس لكل must_find: ثبات الحضور،
تفاوت الرتبة، تفاوت القناة، وتفاوت عدد محاور Haiku (subqueries) كمؤشر غير مباشر على
مصدر التذبذب. لا يُغيِّر أي سلوك إنتاج — أداة قياس مستقلة فقط، بنفس نمط survival_metrics.py."""
import argparse
import json
import statistics
import sys

sys.path.insert(0, "/opt/LegalMind")


def load_gold_set(path="/opt/LegalMind/tools/retrieval_gold_set.json"):
    return json.load(open(path, encoding="utf-8"))["cases"]


def _reset_chap_cache(app):
    """يصفّر كاش _draft_chap_index (إن وُجد باسم معروف) بين التكرارات لمحاكاة عملية
    مستقلة — بنفس ما فعلته gs0015_stability.py يدويًا. فشل صامت إن تغيّر اسم الكاش
    الداخلي مستقبلًا (لا يوقف القياس، فقط يفقد ضمانة "محاكاة عملية جديدة")."""
    for name in ("_CHAP_INDEX_CACHE", "_draft_chap_index_cache", "_chap_index_cache"):
        if hasattr(app, name):
            try:
                setattr(app, name, None)
            except Exception:
                pass


def run_one(app, client, case):
    inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
    ctx = app._draft_build_context(client, inp, case["question"])
    hits_ids = {p.get("object_id") for _l, _s, p in ctx["hits"] if p.get("object_id")}
    seen_ids = ctx["seen"]
    prov_by_id = {p["object_id"]: p for p in (ctx.get("provenance") or [])}
    ordered_rank = {p["object_id"]: p["rank"] for p in (ctx.get("provenance") or [])}

    per_target = {}
    for oid in list(case.get("must_find", [])) + list(case.get("must_not_miss", [])):
        p = prov_by_id.get(oid)
        per_target[oid] = {
            "in_pool": oid in hits_ids,
            "survived": oid in seen_ids,
            "source": p["source"] if p else None,
            "rank": p["rank"] if p else None,
            "final_score": p["final_score"] if p else None,
        }
    return {
        "subqueries": ctx.get("subqueries") or [],
        "dense_union_count": (ctx.get("attr") or {}).get("dense_union_count"),
        "targets": per_target,
    }


def aggregate_case(case, runs):
    n = len(runs)
    targets = list(runs[0]["targets"].keys())
    per_target_report = {}
    for oid in targets:
        presences = [r["targets"][oid]["in_pool"] for r in runs]
        survivals = [r["targets"][oid]["survived"] for r in runs]
        ranks = [r["targets"][oid]["rank"] for r in runs if r["targets"][oid]["rank"] is not None]
        sources = {r["targets"][oid]["source"] for r in runs if r["targets"][oid]["source"]}
        survived_n = sum(survivals)
        if survived_n == n:
            label = "stable"
        elif survived_n >= n - 1:
            label = "mildly_unstable"
        else:
            label = "unstable"
        per_target_report[oid] = {
            "presence_ratio": f"{sum(presences)}/{n}",
            "survival_ratio": f"{survived_n}/{n}",
            "stability_label": label,
            "rank_min": min(ranks) if ranks else None,
            "rank_max": max(ranks) if ranks else None,
            "rank_stdev": round(statistics.pstdev(ranks), 2) if len(ranks) > 1 else 0.0,
            "distinct_sources_seen": sorted(sources),
            "channel_variance": len(sources) > 1,
        }
    subq_sets = [tuple(sorted(r["subqueries"])) for r in runs]
    subquery_variance = len(set(subq_sets)) > 1
    dense_counts = [r["dense_union_count"] for r in runs if r["dense_union_count"] is not None]
    return {
        "case_id": case["id"],
        "runs": n,
        "subquery_variance": subquery_variance,
        "distinct_subquery_sets": len(set(subq_sets)),
        "dense_union_count_range": [min(dense_counts), max(dense_counts)] if dense_counts else None,
        "targets": per_target_report,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5,
                     help="عدد التكرارات المستقلة لكل حالة (افتراضي 5، بنفس رقم gs-0015)")
    ap.add_argument("--only", type=str, default=None,
                     help="قصر القياس على معرفات حالات محددة، مفصولة بفواصل (مثال gs-0013,gs-0015)")
    args = ap.parse_args()

    import anthropic
    from admin import app

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    cases = load_gold_set()
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in wanted]

    results = []
    for c in cases:
        if not c.get("must_find") and not c.get("must_not_miss"):
            print(f"... {c['id']} — تخطٍّ (بلا must_find/must_not_miss لقياسه)", flush=True)
            continue
        print(f"... {c['id']} — {c['category']} ({args.runs} تكرارات)", flush=True)
        runs = []
        for i in range(args.runs):
            _reset_chap_cache(app)
            try:
                runs.append(run_one(app, client, c))
            except Exception as e:
                print(f"  ERROR تكرار {i+1}: {repr(e)}", flush=True)
        if not runs:
            continue
        agg = aggregate_case(c, runs)
        results.append(agg)
        for oid, t in agg["targets"].items():
            print(f"  {oid}: نجاة={t['survival_ratio']} ({t['stability_label']}) "
                  f"رتبة[{t['rank_min']}-{t['rank_max']}] قنوات={t['distinct_sources_seen']}",
                  flush=True)
        if agg["subquery_variance"]:
            print(f"  ⚠ تفاوت محاور Haiku: {agg['distinct_subquery_sets']} صيغة مختلفة عبر "
                  f"{agg['runs']} تكرارات — مؤشر مصدر تذبذب محتمل", flush=True)

    print()
    print("=" * 70)
    print("Retrieval Stability Rate — تقرير كامل")
    print("=" * 70)
    print(json.dumps(results, ensure_ascii=False, indent=2))

    all_targets = [(r["case_id"], oid, t) for r in results for oid, t in r["targets"].items()]
    stable = sum(1 for _, _, t in all_targets if t["stability_label"] == "stable")
    mild = sum(1 for _, _, t in all_targets if t["stability_label"] == "mildly_unstable")
    unstable = sum(1 for _, _, t in all_targets if t["stability_label"] == "unstable")
    print()
    print(f"ملخص: مستقر={stable} | تذبذب طفيف={mild} | غير مستقر={unstable} | "
          f"إجمالي أهداف مقيسة={len(all_targets)}")
    print("STABILITY_METRICS_DONE")


if __name__ == "__main__":
    main()
