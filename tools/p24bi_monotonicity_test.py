#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.5 — Experiment B2-I: اختبار الصمود الحتمي الصارم (Hard Monotonicity Test) على عيّنة
واسعة (26 حالة، لا حالة الانحدار الأصلية وحدها). يفحص لكل تصميم ولكل حالة: هل
B ⊆ Combined(B, A) قبل أي ترتيب/ميزانية لاحقة؟ (`candidate_monotonicity` — منفصل تمامًا عن
صمود المرتِّب/الميزانية اللاحقين، غير المقاسين هنا عمدًا لأنهما خارج نطاق هذه التجربة).

**لا استعمال لمحرك B2-R v2 الجديد إطلاقًا** — المدخل الوحيد لرموز "A" هو
`p24b_concept_backbone.recognize()` المجمَّد من Arm B v1، تمامًا كما تنص المواصفة."""
import sys
from collections import defaultdict

sys.path.insert(0, "/home/user/LegalMind/tools")
from p24b_concept_backbone import recognize as v1_recognize, freeze_hash as v1_freeze_hash  # noqa: E402
from p24bi_fixtures import FIXTURES  # noqa: E402
from p24bi_designs import run_design  # noqa: E402

DESIGN_NAMES = ["design0_old_buggy", "design1_independent_channel",
                "design2_frozen_then_additive", "design3_provenance_union"]


def main():
    print("=" * 70)
    print("PREFLIGHT")
    print("=" * 70)
    print(f"Arm B v1 freeze_hash() = {v1_freeze_hash()}")
    print(f"عدد الحالات (عيّنة واسعة) = {len(FIXTURES)}")

    scope_by_fixture = {}
    for fx in FIXTURES:
        out = v1_recognize(fx["facts"])
        scope_by_fixture[fx["id"]] = out["scope_queries"]

    n_with_scope = sum(1 for v in scope_by_fixture.values() if v)
    print(f"حالات فعَّلت مفهومًا واحدًا على الأقل (scope_queries غير فارغة) = {n_with_scope}/{len(FIXTURES)}")

    results = defaultdict(lambda: {"violations": [], "combined_sizes": [], "elapsed": [],
                                    "n_calls": [], "dimension_losses": []})

    for fx in FIXTURES:
        scope_queries = scope_by_fixture[fx["id"]]
        for name in DESIGN_NAMES:
            r = run_design(name, fx["facts"], scope_queries, fx["chapter_index"])
            b_set, combined_set = set(r["baseline"]), set(r["combined"])
            missing = b_set - combined_set
            if missing:
                results[name]["violations"].append({"fixture": fx["id"], "missing": sorted(missing),
                                                      "baseline_size": len(b_set),
                                                      "combined_size": len(combined_set)})
            results[name]["combined_sizes"].append(len(combined_set))
            results[name]["elapsed"].append(r["elapsed_s"])
            results[name]["n_calls"].append(r["n_selector_calls"])

            # فحص انحدار على مستوى بُعد محدَّد: هل سلطة هدف كانت في B وسقطت من Combined؟
            target_arts = fx.get("target_arts", [])
            if target_arts:
                lost_targets = [a for a in target_arts if a in b_set and a not in combined_set]
                if lost_targets:
                    results[name]["dimension_losses"].append({"fixture": fx["id"], "lost": lost_targets})

    print("\n" + "=" * 70)
    print("HARD MONOTONICITY TEST RESULTS (26 حالة × 4 تصاميم)")
    print("=" * 70)
    for name in DESIGN_NAMES:
        r = results[name]
        n_viol = len(r["violations"])
        compliance = (len(FIXTURES) - n_viol) / len(FIXTURES)
        avg_combined = sum(r["combined_sizes"]) / len(r["combined_sizes"])
        avg_elapsed_ms = 1000 * sum(r["elapsed"]) / len(r["elapsed"])
        avg_calls = sum(r["n_calls"]) / len(r["n_calls"])
        print(f"\n[{name}]")
        print(f"  candidate_monotonicity_compliance = {n_viol==0} "
              f"({len(FIXTURES)-n_viol}/{len(FIXTURES)} حالة بلا انتهاك = {round(compliance*100,1)}%)")
        print(f"  انتهاكات B⊄Combined: {n_viol}")
        for v in r["violations"][:5]:
            print(f"    VIOLATION [{v['fixture']}]: missing={v['missing']} "
                  f"(|B|={v['baseline_size']} |Combined|={v['combined_size']})")
        print(f"  فقد على مستوى بُعد سلطة هادفة (target_arts): {len(r['dimension_losses'])} حالة")
        for dl in r["dimension_losses"][:5]:
            print(f"    DIMENSION_LOSS [{dl['fixture']}]: lost={dl['lost']}")
        print(f"  متوسط حجم Combined لكل حالة = {round(avg_combined, 2)}  (مؤشر بنيوي لضغط المرتِّب/الميزانية اللاحقين)")
        print(f"  متوسط عدد نداءات المُختار (selector calls) لكل حالة = {round(avg_calls, 2)}  "
              f"(مؤشر بنيوي نسبي للكلفة — لا زمنًا إنتاجيًا مطلقًا)")
        print(f"  متوسط الزمن التركيبي = {round(avg_elapsed_ms, 4)} مللي ثانية "
              f"(بيئة تركيبية صغيرة — إشارة نسبية بين التصاميم لا رقمًا إنتاجيًا)")

    print("\n" + "=" * 70)
    print("B2-I CLASSIFICATION")
    print("=" * 70)
    for name in DESIGN_NAMES:
        r = results[name]
        n_viol = len(r["violations"])
        n_dim_loss = len(r["dimension_losses"])
        if name == "design0_old_buggy":
            verdict = ("CONFIRMS_REGRESSION_MECHANISM_ON_WIDE_SAMPLE" if (n_viol > 0 or n_dim_loss > 0)
                       else "UNEXPECTED_NO_VIOLATION_CHECK_FIXTURES")
        else:
            verdict = "B2I_MONOTONICITY_PASS" if (n_viol == 0 and n_dim_loss == 0) else "B2I_MONOTONICITY_FAIL"
        print(f"  {name}: {verdict}")

    print("\nP24BI_MONOTONICITY_DONE")
    return results


if __name__ == "__main__":
    main()
