#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.3 §C — اختبار Frozen Axes السببي على الأهداف التي أظهرت "discovery instability" فعليًا
في P2.3 §A (Normal×5): gs-0010/legis-51-1984-m299 وgs-0017/legis-38-1980-m103 — الوحيدان
اللذان أظهرا تذبذب اكتشاف حقيقي (لا تذبذب سقف فقط) عبر الخماسية.

لكل هدف: محوران حقيقيان مأخوذان **حرفيًا** من مخرجات §A (لا إعادة بناء، لا تخمين) —
مجموعة محاور أدَّت فعليًا إلى اكتشاف الهدف (run ناجح)، ومجموعة أخرى أدَّت فعليًا إلى عدم
اكتشافه (run فاشل) — كلٌّ منهما يُجمَّد ويُشغَّل Frozen×5 منفصلة، بإعادة استعمال
`frozen_axes_experiment.run_one` القائمة حرفيًا (تدعم `frozen_axes=[...]` صراحةً) —
صفر منطق حقن/تجميد جديد، فقط تشغيل الدالة الموجودة بمدخلات محددة.

الغاية: فصل "axis-dependent retrieval" (تجميد نفس المحاور يُعيد نفس النتيجة حتمًا في الحالتين)
عن "ANN/Qdrant/ranking nondeterminism" (حتى المحاور المجمَّدة نفسها تتذبذب). تشخيص بحت — بلا
أي تعديل على أي ملف قرار حي."""
import json
import sys

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")

# محاور حقيقية حرفية من مخرجات P23_STABLE_MATRIX_RAW_RESULTS (2026-09-16) — لا تخمين
TARGETS = {
    "gs-0010": {
        "focus_target": "legis-51-1984-m299",
        "success_axes": ["توزيع التركة بين الورثة", "حصة الزوجة من الميراث",
                          "حصة البنات من الميراث", "حصة الأخ الشقيق من التركة",
                          "ترتيب الورثة ودرجاتهم"],  # run-3 (اكتُشف فعليًا، dense)
        "fail_axes": ["توزيع التركة بين الورثة", "نصيب الزوجة من الميراث",
                      "نصيب البنات من الميراث", "نصيب الأخ الشقيق من التركة",
                      "أحكام الميراث في الشريعة الإسلامية"],  # run-2 (لم يُكتشَف)
    },
    "gs-0017": {
        "focus_target": "legis-38-1980-m103",
        "success_axes": ["تنحي القاضي لقرابة أو مصاهرة", "عدم صلاحية القاضي لنظر الدعوى",
                          "موانع سماع الدعوى من حيث القاضي",
                          "درجات القرابة والمصاهرة الموجبة للتنحي",
                          "حقوق الخصوم في طلب تنحي القاضي"],  # run-2 (اكتُشف عبر chapter)
        "fail_axes": ["عدم صلاحية القاضي لنظر الدعوى", "القرابة والصهرية كسبب لرد القاضي",
                      "موانع نظر القاضي للقضايا", "درجات القرابة المانعة من الاختصاص",
                      "واجبات القاضي في حالة القرابة والمصاهرة"],  # run-4 (لم يُكتشَف)
    },
}


def main():
    import anthropic
    from admin import app
    import kb_types
    import frozen_axes_experiment as fae

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    gold = fae.load_gold_set()

    args = sys.argv[1:]
    case_ids = args[0].split(",") if args and args[0] else sorted(TARGETS.keys())
    runs = int(args[1]) if len(args) > 1 else 5

    results = {}
    for cid in case_ids:
        spec = TARGETS[cid]
        target = spec["focus_target"]
        case = gold[cid]
        results[cid] = {"target": target}
        for label in ("success_axes", "fail_axes"):
            frozen = spec[label]
            print(f"=== {cid}/{target} — Frozen×{runs} ({label}) ===", flush=True)
            print(f"  frozen_axes = {frozen}", flush=True)
            runs_out = []
            mismatch = False
            for i in range(runs):
                fae._reset_chap_cache(app)
                r = fae.run_one(app, client, case, frozen_axes=frozen)
                r["run_id"] = f"{label}-{i + 1}"
                runs_out.append(r)
                if r["exact_axes"] != frozen:
                    mismatch = True
                    print(f"  ⚠ AXES_MISMATCH at {label}-{i + 1}: {r['exact_axes']}", flush=True)
                t = r["targets"].get(target, {})
                print(f"  {label}-{i + 1}: discovered={t.get('discovered')} "
                      f"channel={t.get('channel')} final_context={t.get('final_context')}", flush=True)
            disc = [r["targets"].get(target, {}).get("discovered") for r in runs_out]
            surv = [r["targets"].get(target, {}).get("final_context") for r in runs_out]
            results[cid][label] = {
                "frozen_axes": frozen, "runs": runs_out,
                "axes_integrity_confirmed": not mismatch,
                "discovery_summary": f"{sum(bool(x) for x in disc)}/{len(disc)}",
                "survival_summary": f"{sum(bool(x) for x in surv)}/{len(surv)}",
            }
            print(f"  => discovery={results[cid][label]['discovery_summary']} "
                  f"survival={results[cid][label]['survival_summary']} "
                  f"integrity={'OK' if not mismatch else 'MISMATCH!'}", flush=True)

    print()
    print("=" * 70)
    print("P23_FROZEN_CAUSAL_RAW_RESULTS")
    print("=" * 70)
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    print(f"\nP23_FROZEN_CAUSAL_DONE | targets={len(results)}")


if __name__ == "__main__":
    main()
