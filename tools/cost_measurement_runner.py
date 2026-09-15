#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.1 Closure Measurement — البند 4 (قياس زمني/تكلفة بحت، بلا تغيير سلوكي). يُشغِّل
Shadow A وShadow B الحقيقيين (بلا تعديل عليهما إطلاقًا — يُستوردان كما هما من نقطة التجميد)
على عيّنة ممثِّلة من Gold Set (لا الأربعين كلها — تخفيفًا لكلفة شبكة/Haiku متراكمة كبيرة
من جولات القياس السابقة في نفس الجلسة، إفصاح صريح لا إخفاء)، مع تغليف زمني/عدّاد حول دوال
قنوات الإنتاج الحقيقية (`cost_instrumentation.py`) لا يُغيِّر سلوكها إطلاقًا.

**اختيار العيّنة:** `gs-0013` و`gs-0036` (حالتا الفجوة الفعلية — تُظهران تكلفة
`broad_channel_search` الإضافية في Shadow B) + أربع حالات عادية متنوعة الفئة `gs-0002،
gs-0018، gs-0020، gs-0035` (بلا فجوة — تكلفة Shadow A/B الأساسية بلا بحث إضافي)."""
import json
import sys
import time

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")

from cost_instrumentation import CostCounters, instrument_app_channels, Timer

SAMPLE_CASES = ["gs-0013", "gs-0036", "gs-0002", "gs-0018", "gs-0020", "gs-0035"]


class TimedModule:
    """وسيط شفاف: يمرر كل شيء للوحدة الحقيقية، ويقيس زمن دالة واحدة محدَّدة فقط — بلا أي
    تغيير في مدخلاتها/مخرجاتها/منطقها."""

    def __init__(self, real_mod, fn_name, label, counters):
        object.__setattr__(self, "_real", real_mod)
        object.__setattr__(self, "_fn_name", fn_name)
        object.__setattr__(self, "_label", label)
        object.__setattr__(self, "_counters", counters)

    def __getattr__(self, name):
        attr = getattr(self._real, name)
        if name != self._fn_name or not callable(attr):
            return attr

        def wrapped(*a, **kw):
            with Timer(self._counters, self._label):
                return attr(*a, **kw)
        return wrapped


def load_gold_set(path="/opt/LegalMind/tools/retrieval_gold_set.json"):
    return json.load(open(path, encoding="utf-8"))["cases"]


def main():
    import anthropic
    from admin import app
    import kb_types
    import p2_backbone, p2_evidence_classification, p2_admission_policy, p2_coverage_checker
    import shadow_a_runner, shadow_b_runner

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)

    cases_all = load_gold_set()
    cases = [c for c in cases_all if c["id"] in SAMPLE_CASES]
    found_ids = {c["id"] for c in cases}
    missing = [cid for cid in SAMPLE_CASES if cid not in found_ids]
    if missing:
        print(f"!! تحذير: حالات عيّنة غير موجودة في Gold Set: {missing}", flush=True)

    counters = CostCounters()
    restore = instrument_app_channels(app, counters)

    backbone_t = TimedModule(p2_backbone, "compute_backbone", "backbone_ms", counters)
    ap_t = TimedModule(p2_admission_policy, "admit", "admission_ms", counters)
    cc_t = TimedModule(p2_coverage_checker, "check_coverage", "coverage_checker_ms", counters)

    per_case_results = []
    try:
        for c in cases:
            print(f"... {c['id']} — قياس Shadow A", flush=True)
            t0 = time.perf_counter()
            try:
                ra = shadow_a_runner.run_one(app, client, c, backbone_t,
                                              p2_evidence_classification, ap_t, cc_t)
                counters.record("shadow_a_total_ms", (time.perf_counter() - t0) * 1000)
            except Exception as e:
                print(f"  !! shadow-a-cost-error: {e!r}", flush=True)
                ra = None

            print(f"... {c['id']} — قياس Shadow B", flush=True)
            t0 = time.perf_counter()
            try:
                rb = shadow_b_runner.run_one(app, client, c, backbone_t,
                                              p2_evidence_classification, ap_t, cc_t, kb_types)
                counters.record("shadow_b_total_ms", (time.perf_counter() - t0) * 1000)
            except Exception as e:
                print(f"  !! shadow-b-cost-error: {e!r}", flush=True)
                rb = None

            per_case_results.append({
                "case_id": c["id"],
                "shadow_a_ok": ra is not None,
                "shadow_b_ok": rb is not None,
                "shadow_b_needs_broad_search": rb.get("needs_broad_search") if rb else None,
            })
    finally:
        restore()  # إعادة الدوال الأصلية داخل هذه العملية فقط — لا أثر خارجها أصلًا

    print()
    print("=" * 70)
    print("COST_MEASUREMENT_PER_CASE")
    print("=" * 70)
    print(json.dumps(per_case_results, ensure_ascii=False, indent=2))

    print()
    print("=" * 70)
    print("COST_MEASUREMENT_SUMMARY")
    print("=" * 70)
    print(json.dumps(counters.summary(), ensure_ascii=False, indent=2))
    print("\nCOST_MEASUREMENT_DONE")


if __name__ == "__main__":
    main()
