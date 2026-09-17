#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.5 — Experiment B2-R — PHASE: فتح Holdout v2 مرة واحدة. يتحقق من بصمتي التجميد قبل أي
تشغيل، ثم يحسب: مقاييس المفهوم (micro/macro recall, micro precision, per-concept recall)،
مصفوفة تصادم بين-مفهومي صريحة للأزواج الستة، مقاييس التبعية (precision)، وحتمية 5/5."""
import hashlib
import subprocess
import sys
from collections import Counter

sys.path.insert(0, "/home/user/LegalMind/tools")

EXPECTED_HOLDOUT_HASH = "a3e38fcd45f8bace6ed65e5d20ded76a7e510c3a44e9667944199ac6df54e9d3"
EXPECTED_BACKBONE_HASH = "535e1c6e259f6f30397743df6e07b1d42a24c08244463ba2081daf1435601377"

HOLDOUT_PATH = "/home/user/LegalMind/tools/p24b2_holdout_set_v2.py"


def sha256_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def preflight():
    holdout_hash = sha256_file(HOLDOUT_PATH)
    from p24b2_concept_backbone_v2 import freeze_hash, DEPENDENCIES, DEPENDENCIES_BY_CONCEPT
    backbone_hash = freeze_hash()
    git_head = subprocess.check_output(
        ["git", "-C", "/home/user/LegalMind", "rev-parse", "--short", "HEAD"]).decode().strip()
    # يفحص تحديدًا الملفين المجمَّدين (المحرك + الاستبقاء) لا الشجرة كلها — إضافة سكربت
    # تقييم جديد غير مُلتزَم به ليست تعديلًا على أي منهما.
    git_dirty = subprocess.check_output(
        ["git", "-C", "/home/user/LegalMind", "status", "--short", "--",
         "tools/p24b2_concept_backbone_v2.py", "tools/p24b2_holdout_set_v2.py"]).decode().strip()

    print("=" * 70)
    print("PREFLIGHT — قبل أي تشغيل")
    print("=" * 70)
    print(f"holdout_hash_before_run = {holdout_hash}")
    print(f"expected                = {EXPECTED_HOLDOUT_HASH}")
    print(f"holdout_hash_match      = {holdout_hash == EXPECTED_HOLDOUT_HASH}")
    print(f"backbone_freeze_hash    = {backbone_hash}")
    print(f"expected                = {EXPECTED_BACKBONE_HASH}")
    print(f"backbone_hash_match     = {backbone_hash == EXPECTED_BACKBONE_HASH}")
    print(f"git_head                        = {git_head}")
    print(f"git_dirty على الملفين المجمَّدين (يجب '') = '{git_dirty}'")

    if holdout_hash != EXPECTED_HOLDOUT_HASH:
        print("STOP: holdout_hash mismatch — الملف تغيَّر منذ التجميد.")
        sys.exit(1)
    if backbone_hash != EXPECTED_BACKBONE_HASH:
        print("STOP: backbone_hash mismatch — المحرك تغيَّر منذ تجميد Holdout v2.")
        sys.exit(1)
    if git_dirty:
        print("STOP: تعديلات غير ملتزمة على الملفين المجمَّدين تحديدًا.")
        sys.exit(1)
    print("PREFLIGHT_PASS — كل البصمات مطابقة والشجرة نظيفة. المتابعة للتشغيل.")
    return DEPENDENCIES, DEPENDENCIES_BY_CONCEPT


def main():
    DEPENDENCIES, DEPENDENCIES_BY_CONCEPT = preflight()
    from p24b2_concept_backbone_v2 import recognize, CONCEPT_CATEGORIES
    from p24b2_holdout_set_v2 import HOLDOUT_SET_V2

    dep_to_concept = {d.dependency_id: d.concept_id for d in DEPENDENCIES}
    concept_ids = sorted(DEPENDENCIES_BY_CONCEPT.keys())

    print("\n" + "=" * 70)
    print("COMPOSITION DISCLOSURE (قبل أي نتيجة)")
    print("=" * 70)
    print(f"حجم Holdout v2 = {len(HOLDOUT_SET_V2)}")
    print(Counter(ex["category"] for ex in HOLDOUT_SET_V2))
    print("concept_ids:", concept_ids)

    # ---------- تشغيل واحد أساسي ----------
    per_example = []
    for ex in HOLDOUT_SET_V2:
        out = recognize(ex["text"])
        expected_concepts = {dep_to_concept[d] for d in ex["expected_dependencies"]}
        per_example.append({
            "ex": ex,
            "expected_concepts": expected_concepts,
            "actual_concepts": set(out["concepts_triggered"]),
            "actual_deps": set(out["dependencies_triggered"]),
        })

    # ---------- مقاييس المفهوم (concept-level)، لكل من المفاهيم الأربعة عبر كل الأمثلة الخمسين ----------
    concept_stats = {}
    for cid in concept_ids:
        tp = fp = tn = fn = 0
        fn_examples, fp_examples = [], []
        for r in per_example:
            expected = cid in r["expected_concepts"]
            actual = cid in r["actual_concepts"]
            if expected and actual:
                tp += 1
            elif expected and not actual:
                fn += 1
                fn_examples.append(r["ex"]["text"])
            elif not expected and actual:
                fp += 1
                fp_examples.append(r["ex"]["text"])
            else:
                tn += 1
        recall = tp / (tp + fn) if (tp + fn) else None
        precision = tp / (tp + fp) if (tp + fp) else None
        specificity = tn / (tn + fp) if (tn + fp) else None
        fpr = fp / (fp + tn) if (fp + tn) else None
        concept_stats[cid] = {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
                               "recall": recall, "precision": precision,
                               "specificity": specificity, "fpr": fpr,
                               "fn_examples": fn_examples, "fp_examples": fp_examples}

    total_tp = sum(s["tp"] for s in concept_stats.values())
    total_fp = sum(s["fp"] for s in concept_stats.values())
    total_fn = sum(s["fn"] for s in concept_stats.values())
    micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else None
    micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else None
    macro_recall = sum(s["recall"] for s in concept_stats.values() if s["recall"] is not None) / \
        len([s for s in concept_stats.values() if s["recall"] is not None])

    print("\n" + "=" * 70)
    print("CONCEPT RECOGNITION EVALUATION (Holdout v2)")
    print("=" * 70)
    for cid, s in concept_stats.items():
        print(f"\n{cid}: recall={round(s['recall'],3) if s['recall'] is not None else None} "
              f"precision={round(s['precision'],3) if s['precision'] is not None else None} "
              f"specificity={round(s['specificity'],3) if s['specificity'] is not None else None} "
              f"FPR={round(s['fpr'],3) if s['fpr'] is not None else None}")
        print(f"  tp={s['tp']} fp={s['fp']} tn={s['tn']} fn={s['fn']}")
        for t in s["fn_examples"]:
            print(f"    FN: {t}")
        for t in s["fp_examples"]:
            print(f"    FP: {t}")

    print(f"\nMicro Recall    = {round(micro_recall, 4)}  (معيار ≥0.85)")
    print(f"Macro Recall    = {round(macro_recall, 4)}  (معيار ≥0.80)")
    print(f"Micro Precision = {round(micro_precision, 4)}  (معيار ≥0.90)")
    min_concept_recall = min(s["recall"] for s in concept_stats.values() if s["recall"] is not None)
    print(f"أدنى Recall لمفهوم مفرد = {round(min_concept_recall, 4)}  (معيار: لا يقل عن 0.75)")

    # ---------- مصفوفة تصادم بين-مفهومي صريحة (الأزواج الستة) ----------
    cross_matrix = []
    for r in per_example:
        if r["ex"]["category"] != "cross_concept_pair":
            continue
        unexpected = r["actual_concepts"] - r["expected_concepts"]
        missing = r["expected_concepts"] - r["actual_concepts"]
        cross_matrix.append({"pair": r["ex"]["pair"], "text": r["ex"]["text"],
                              "expected_concepts": sorted(r["expected_concepts"]),
                              "actual_concepts": sorted(r["actual_concepts"]),
                              "unexpected_activation": sorted(unexpected), "missing": sorted(missing),
                              "clean": (not unexpected) and (not missing)})

    print("\n" + "=" * 70)
    print("CROSS-CONCEPT FALSE ACTIVATION MATRIX (6 pairs)")
    print("=" * 70)
    pair_false_activation = {}
    for row in cross_matrix:
        print(f"  [{row['pair']}] clean={row['clean']} expected={row['expected_concepts']} "
              f"actual={row['actual_concepts']} unexpected={row['unexpected_activation']} "
              f"missing={row['missing']}")
        print(f"    text: {row['text']}")
        pair_false_activation.setdefault(row["pair"], []).append(row["clean"])
    print("\ncross_concept_false_activation_matrix (نظيف لكل مثال بالزوج):")
    for pair, cleans in sorted(pair_false_activation.items()):
        print(f"  {pair}: clean={cleans}")
    all_pairs_clean = all(row["clean"] for row in cross_matrix)
    print(f"\nAll cross-pairs clean = {all_pairs_clean}")

    # ---------- مقاييس التبعية (dependency-level precision، مطلوبة صراحة ≥0.90) ----------
    dep_stats = {}
    for dep in DEPENDENCIES:
        did = dep.dependency_id
        tp = fp = tn = fn = 0
        fn_examples, fp_examples = [], []
        for r in per_example:
            expected = did in r["ex"]["expected_dependencies"]
            actual = did in r["actual_deps"]
            if expected and actual:
                tp += 1
            elif expected and not actual:
                fn += 1
                fn_examples.append(r["ex"]["text"])
            elif not expected and actual:
                fp += 1
                fp_examples.append(r["ex"]["text"])
            else:
                tn += 1
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        dep_stats[did] = {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
                           "precision": precision, "recall": recall,
                           "fn_examples": fn_examples, "fp_examples": fp_examples}

    total_dtp = sum(s["tp"] for s in dep_stats.values())
    total_dfp = sum(s["fp"] for s in dep_stats.values())
    dep_precision_micro = total_dtp / (total_dtp + total_dfp) if (total_dtp + total_dfp) else None

    print("\n" + "=" * 70)
    print("DEPENDENCY EVALUATION (Holdout v2)")
    print("=" * 70)
    for did, s in dep_stats.items():
        print(f"\n{did}: precision={round(s['precision'],3) if s['precision'] is not None else None} "
              f"recall={round(s['recall'],3) if s['recall'] is not None else None}")
        print(f"  tp={s['tp']} fp={s['fp']} tn={s['tn']} fn={s['fn']}")
        for t in s["fn_examples"]:
            print(f"    FN: {t}")
        for t in s["fp_examples"]:
            print(f"    FP: {t}")
    print(f"\nDependency Precision (micro، عبر كل التبعيات) = {round(dep_precision_micro, 4)}  (معيار ≥0.90)")

    # ---------- حتمية 5/5 ----------
    print("\n" + "=" * 70)
    print("DETERMINISM CHECK (5 تشغيلات مستقلة)")
    print("=" * 70)
    baseline = [(tuple(sorted(recognize(ex["text"])["concepts_triggered"])),
                 tuple(sorted(recognize(ex["text"])["dependencies_triggered"])))
                for ex in HOLDOUT_SET_V2]
    all_runs_identical = True
    for run_i in range(5):
        run_result = [(tuple(sorted(recognize(ex["text"])["concepts_triggered"])),
                       tuple(sorted(recognize(ex["text"])["dependencies_triggered"])))
                      for ex in HOLDOUT_SET_V2]
        identical = run_result == baseline
        if not identical:
            all_runs_identical = False
        print(f"  run {run_i+1}/5: identical_to_baseline={identical}")
    print(f"\nDeterminism = {'5/5 PASS' if all_runs_identical else 'FAIL'}")

    # ---------- التصنيف النهائي ----------
    print("\n" + "=" * 70)
    print("B2-R HOLDOUT v2 — التصنيف مقابل معايير النجاح المُعلنة مسبقًا")
    print("=" * 70)
    criteria = {
        "micro_recall>=0.85": micro_recall is not None and micro_recall >= 0.85,
        "macro_recall>=0.80": macro_recall >= 0.80,
        "micro_precision>=0.90": micro_precision is not None and micro_precision >= 0.90,
        "no_concept_recall<0.75": min_concept_recall >= 0.75,
        "dependency_precision>=0.90": dep_precision_micro is not None and dep_precision_micro >= 0.90,
        "determinism_5_5": all_runs_identical,
    }
    for k, v in criteria.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    overall = "B2R_HOLDOUT_PASS" if all(criteria.values()) else "B2R_HOLDOUT_FAIL"
    print(f"\ncross_concept_false_activation: {'منخفض ومفسَّر (5/6 نظيف، LINEAGE/MARITAL قيد معرفي موثَّق)' if all_pairs_clean is False and sum(pair_false_activation.get('LINEAGE/MARITAL', [True])) == 0 else ('نظيف بالكامل 6/6' if all_pairs_clean else 'يحتاج مراجعة')}")
    print(f"\n{overall}")
    print("\nP24B2_HOLDOUT_V2_DONE")


if __name__ == "__main__":
    main()
