#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.4-Infra — بوابة صحة إلزامية: يشغّل _draft_build_context الحقيقية ونسخة p24_offline_
pipeline.build_context_offline (بسياسة fixed_cap_policy، أي محاكاة الأساس الإنتاجي حرفيًا)
على نفس الحالة بمحاور مجمَّدة (frozen، صفر نداء Haiku، صفر تذبذب) — ويقارن ctx['seen'] بدقة
تامة. أي فارق يعني خطأً في إعادة البناء يجب إصلاحه قبل أي تجربة Arm A حقيقية."""
import sys

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")


def main():
    import anthropic
    from admin import app
    import frozen_axes_experiment as fae
    import p24_offline_pipeline as p24pipe

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    gold = fae.load_gold_set()
    case = gold["gs-0010"]
    frozen = ["توزيع التركة بين الورثة", "حصة الزوجة من الميراث", "حصة البنات من الميراث",
              "حصة الأخ الشقيق من التركة", "ترتيب الورثة ودرجاتهم"]  # نفس محاور P2.3 §4 الناجحة

    orig_subq = app._draft_subqueries

    def frozen_subq(*_a, **_k):
        return list(frozen)

    inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])

    app._draft_subqueries = frozen_subq
    try:
        real_ctx = app._draft_build_context(client, inp, case["question"])
    finally:
        app._draft_subqueries = orig_subq

    app._draft_subqueries = frozen_subq
    try:
        offline_ctx = p24pipe.build_context_offline(app, client, inp, case["question"],
                                                      admission_policy=p24pipe.fixed_cap_policy)
    finally:
        app._draft_subqueries = orig_subq

    real_seen = set(real_ctx["seen"])
    offline_seen = set(offline_ctx["seen"])

    print(f"real_seen_count={len(real_seen)} offline_seen_count={len(offline_seen)}")
    only_real = real_seen - offline_seen
    only_offline = offline_seen - real_seen
    print(f"only_in_real={len(only_real)}: {sorted(only_real)[:20]}")
    print(f"only_in_offline={len(only_offline)}: {sorted(only_offline)[:20]}")

    real_cap_dropped = set(real_ctx["attr"].get("cap_dropped_ids") or [])
    offline_cap_dropped = set(offline_ctx["attr"].get("cap_dropped_ids") or [])
    print(f"real_cap_dropped_count={len(real_cap_dropped)} offline_cap_dropped_count={len(offline_cap_dropped)}")
    print(f"cap_dropped_diff: {sorted(real_cap_dropped.symmetric_difference(offline_cap_dropped))[:20]}")

    if real_seen == offline_seen:
        print("OFFLINE_PIPELINE_VALIDATION_PASS")
    else:
        print("OFFLINE_PIPELINE_VALIDATION_FAIL")


if __name__ == "__main__":
    main()
