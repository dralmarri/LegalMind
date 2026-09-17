#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.4B — بروتوكول قبول القواعد: يشغّل `p24b_concept_backbone.recognize()` (حتمي بالكامل،
صفر نداء نموذج لغوي) على `p24b_dev_set.DEV_SET` (مستقل عن Gold Set)، ويحسب لكل تبعية
TP/FP/TN/FN وprecision/recall/false_activation_rate. تبعية بمعدل تفعيل كاذب خطير (هنا: عتبة
تحذيرية >10% من الأمثلة السلبية ذات الصلة) تُعلَّم `REVIEW_RECOMMENDED` لا تُرفض آليًا —
الحكم النهائي بشري كما يقتضي بروتوكول القبول."""
import json
import sys

sys.path.insert(0, "/home/user/LegalMind/tools")
from p24b_concept_backbone import DEPENDENCIES, recognize  # noqa: E402
from p24b_dev_set import DEV_SET  # noqa: E402

FALSE_ACTIVATION_WARN_THRESHOLD = 0.10


def score():
    results = {}
    per_example = []
    for ex in DEV_SET:
        out = recognize(ex["text"])
        per_example.append({"text": ex["text"], "category": ex["category"],
                             "expected": ex["expected_dependencies"],
                             "actual": out["dependencies_triggered"]})

    for dep in DEPENDENCIES:
        did = dep.dependency_id
        tp = fp = tn = fn = 0
        errors = []
        for ex in per_example:
            expected = did in ex["expected"]
            actual = did in ex["actual"]
            if expected and actual:
                tp += 1
            elif expected and not actual:
                fn += 1
                errors.append({"type": "FN", "text": ex["text"], "category": ex["category"]})
            elif not expected and actual:
                fp += 1
                errors.append({"type": "FP", "text": ex["text"], "category": ex["category"]})
            else:
                tn += 1
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        false_activation_rate = fp / (fp + tn) if (fp + tn) else None
        verdict = "OK"
        if false_activation_rate is not None and false_activation_rate > FALSE_ACTIVATION_WARN_THRESHOLD:
            verdict = "REVIEW_RECOMMENDED_HIGH_FALSE_ACTIVATION"
        results[did] = {
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": round(precision, 3) if precision is not None else None,
            "recall": round(recall, 3) if recall is not None else None,
            "false_activation_rate": round(false_activation_rate, 3) if false_activation_rate is not None else None,
            "verdict": verdict, "errors": errors,
        }
    return results, per_example


if __name__ == "__main__":
    results, per_example = score()
    print("=" * 70)
    print("P24B_ACCEPTANCE_PROTOCOL_RESULTS")
    print("=" * 70)
    for did, r in results.items():
        print(f"\n{did}: precision={r['precision']} recall={r['recall']} "
              f"false_activation_rate={r['false_activation_rate']} verdict={r['verdict']}")
        print(f"  tp={r['tp']} fp={r['fp']} tn={r['tn']} fn={r['fn']}")
        for e in r["errors"]:
            print(f"    {e['type']} [{e['category']}]: {e['text']}")
    print()
    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    print("\nP24B_ACCEPTANCE_DONE")
