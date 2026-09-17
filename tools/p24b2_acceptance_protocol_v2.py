#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.5 — Experiment B2-R: بروتوكول قبول v2 على `p24b2_dev_set_v2.DEV_SET_V2` — يحسب مقاييس
المفاهيم والتبعيات معًا (v2 لا تفصلهما فعليًا بعد إلا في CHEQUE_LIMITATION_CHECK) + مصفوفة
تصادم بين-مفهومي صريحة لكل الأزواج الستة."""
import json
import sys
from collections import Counter

sys.path.insert(0, "/home/user/LegalMind/tools")
from p24b2_concept_backbone_v2 import DEPENDENCIES, recognize  # noqa: E402
from p24b2_dev_set_v2 import DEV_SET_V2  # noqa: E402

FAR_WARN = 0.10


def score():
    per_example = []
    for ex in DEV_SET_V2:
        out = recognize(ex["text"])
        per_example.append({"ex": ex, "actual_deps": set(out["dependencies_triggered"]),
                             "actual_concepts": set(out["concepts_triggered"])})

    results = {}
    for dep in DEPENDENCIES:
        did = dep.dependency_id
        tp = fp = tn = fn = 0
        errors = []
        for r in per_example:
            expected = did in r["ex"]["expected_dependencies"]
            actual = did in r["actual_deps"]
            if expected and actual:
                tp += 1
            elif expected and not actual:
                fn += 1
                errors.append({"type": "FN", "text": r["ex"]["text"], "category": r["ex"]["category"]})
            elif not expected and actual:
                fp += 1
                errors.append({"type": "FP", "text": r["ex"]["text"], "category": r["ex"]["category"]})
            else:
                tn += 1
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        far = fp / (fp + tn) if (fp + tn) else None
        verdict = "REVIEW_RECOMMENDED_HIGH_FALSE_ACTIVATION" if (far is not None and far > FAR_WARN) else "OK"
        results[did] = {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
                         "precision": round(precision, 3) if precision is not None else None,
                         "recall": round(recall, 3) if recall is not None else None,
                         "false_activation_rate": round(far, 3) if far is not None else None,
                         "verdict": verdict, "errors": errors}

    # مصفوفة تصادم بين-مفهومي: لكل مثال cross_concept_pair، هل فُعِّل مفهوم غير متوقَّع؟
    cross_matrix = []
    for r in per_example:
        if r["ex"]["category"] != "cross_concept_pair":
            continue
        expected_concepts = set()
        from p24b2_concept_backbone_v2 import DEPENDENCIES_BY_CONCEPT
        dep_to_concept = {d.dependency_id: d.concept_id for d in DEPENDENCIES}
        for d in r["ex"]["expected_dependencies"]:
            expected_concepts.add(dep_to_concept[d])
        unexpected = r["actual_concepts"] - expected_concepts
        missing = expected_concepts - r["actual_concepts"]
        cross_matrix.append({"pair": r["ex"]["pair"], "text": r["ex"]["text"],
                              "expected_concepts": sorted(expected_concepts),
                              "actual_concepts": sorted(r["actual_concepts"]),
                              "unexpected_activation": sorted(unexpected), "missing": sorted(missing),
                              "clean": (not unexpected) and (not missing)})

    return results, cross_matrix, per_example


if __name__ == "__main__":
    results, cross_matrix, per_example = score()
    print("=" * 70)
    print("P24B2_ACCEPTANCE_V2_RESULTS")
    print("=" * 70)
    for did, r in results.items():
        print(f"\n{did}: precision={r['precision']} recall={r['recall']} "
              f"FAR={r['false_activation_rate']} verdict={r['verdict']}")
        print(f"  tp={r['tp']} fp={r['fp']} tn={r['tn']} fn={r['fn']}")
        for e in r["errors"]:
            print(f"    {e['type']} [{e['category']}]: {e['text']}")

    print("\n" + "=" * 70)
    print("CROSS-CONCEPT COLLISION MATRIX (6 pairs)")
    print("=" * 70)
    for row in cross_matrix:
        print(f"  [{row['pair']}] clean={row['clean']} expected={row['expected_concepts']} "
              f"actual={row['actual_concepts']} unexpected={row['unexpected_activation']} "
              f"missing={row['missing']}")
        print(f"    text: {row['text']}")

    print(f"\nAll cross-pairs clean = {all(r['clean'] for r in cross_matrix)}")
    print("\nP24B2_ACCEPTANCE_V2_DONE")
