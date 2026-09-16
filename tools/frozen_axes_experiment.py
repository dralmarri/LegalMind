#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1.8 — تجربة السببية المضبوطة (Frozen Axes Controlled Experiment). هدفها اختبار السببية
لا تحسين النتائج: هل عشوائية تفكيك Haiku لمحاور البحث (subqueries) هي المتغيّر المسؤول عن
"Discovery Instability" الموثَّقة في docs/retrieval_evaluation_consolidated_report.md؟

المتغيّر الوحيد المعزول: محاور الاستعلام (query axes). كل شيء آخر ثابت: نفس اللقطة الزمنية
للمتن (corpus snapshot)، نفس مجموعة Qdrant، نفس التضمين، نفس المرتِّب، نفس الميزانيات، نفس
البوابات، نفس قنوات التوسعة، نفس التزام الكود — لا نداء `_draft_build_context` إلا بمعامل
واحد مُتحكَّم به (تفكيك Haiku الحقيقي مقابل قائمة محاور مجمَّدة حرفيًا).

آلية التجميد: مونكي-باتش مؤقت لـ`app._draft_subqueries` (استبدال المرجع في نطاق الوحدة أثناء
تنفيذ هذا السكربت فقط، لا تعديل على أي ملف على القرص) يُعيد قائمة المحاور المجمَّدة حرفيًا
دون أي نداء شبكي — الاستعادة فورية بعد كل نداء عبر try/finally. **صفر تغيير في سلوك الإنتاج.**

حالات الاختبار:
- أربع حالات "Discovery Instability" (الاختبار السببي الأساسي): gs-0015، gs-0036/regl-1-2016-m65،
  gs-0001/legis-38-1980-m298، gs-0035/legis-6-2010-m50.
- حالة واحدة "Negative Causal Control": gs-0013/legis-38-1980-m167 — Evidence Admission
  Failure مؤكَّدة سابقًا (اكتشاف 5/5 بصرف النظر عن المحاور)؛ التوقّع الصريح: لا تغيّر تحت
  التجميد (اكتشاف يبقى 5/5، نجاة تبقى منخفضة في كلا النمطين) — إن تغيّرت النجاة تغيّرًا
  كبيرًا تحت التجميد، فهذا يُفنِّد تصنيف Evidence Admission الحالي ويستدعي تحقيقًا، لا تبريرًا.

لكل حالة: 5 تشغيلات Normal (تفكيك Haiku جديد كل مرة) ثم 5 تشغيلات Frozen (محاور مجمَّدة من
أول تشغيلة Normal، مُعاد استعمالها حرفيًا، بلا أي نداء Haiku جديد — تحقَّق آليًا بتأكيد أن
`exact_axes` المُعادة من كل تشغيلة Frozen مطابقة حرفيًا للمجمَّدة). يُخزَّن لكل هدف/تشغيلة:
discovered, channel, pre_rerank_rank, pre_rerank_score, reranker_raw, final_score, final_rank,
admitted (=budget admission), final_context (مرادف تام لـadmitted في هذه البنية — موثَّق).
Complete-Run Recall (Discovery وSurvival) يُحسَب لكل تشغيلة عبر كل عناصر must_find للحالة،
فيتيح لأول مرة min/max/mean/stdev حقيقية لكل نمط."""
import argparse
import json
import statistics
import sys

sys.path.insert(0, "/opt/LegalMind")

PRIMARY_CASES = ["gs-0015", "gs-0036", "gs-0001", "gs-0035", "gs-0038"]
NEGATIVE_CONTROL_CASE = "gs-0013"
FOCUS_TARGET = {
    "gs-0015": "LEG-UNKNOWN-P1-art2-3-6144aa963fc48469",
    "gs-0036": "regl-1-2016-m65",
    "gs-0001": "legis-38-1980-m298",
    "gs-0035": "legis-6-2010-m50",
    "gs-0013": "legis-38-1980-m167",
    # P2.2 §9 — gs-0038: أظهر 0/5 اكتشاف تمامًا في Baseline20 (docs/p2_1_closure_measurement_
    # report.md §1.3) رغم تحقُّق "Pass A" التاريخي (فحص وجود مزدوج search_legal←get_object،
    # لا تشغيلة frozen-axes ناجحة محفوظة) — لا يوجد "Frozen-success-axis" قابل للاسترجاع لهذه
    # الحالة أصلًا (Pass A لم يكن تجربة محاور مجمَّدة، فلا شيء يُستعاد)؛ يُشغَّل هنا Normal×5 +
    # Frozen-current-axis×5 فقط، بنفس منهجية كل حالة أخرى في هذه الأداة، بلا أي تخمين لمحاور
    # "ناجحة" غير موجودة أصلًا في أي سجل.
    "gs-0038": "jprin-101-1995-f1574-ce8b49f13f",
}


def load_gold_set(path="/opt/LegalMind/tools/retrieval_gold_set.json"):
    return {c["id"]: c for c in json.load(open(path, encoding="utf-8"))["cases"]}


def _reset_chap_cache(app):
    for name in ("_CHAP_INDEX_CACHE", "_draft_chap_index_cache", "_chap_index_cache"):
        if hasattr(app, name):
            try:
                setattr(app, name, None)
            except Exception:
                pass


def run_one(app, client, case, frozen_axes=None):
    """تشغيلة واحدة. frozen_axes=None => Normal (Haiku حقيقي). frozen_axes=[...] => Frozen
    (استبدال مؤقت لـ_draft_subqueries، استعادة فورية في finally، صفر نداء شبكي)."""
    inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
    mode = "normal" if frozen_axes is None else "frozen"
    orig_subq = app._draft_subqueries
    if frozen_axes is not None:
        frozen_copy = list(frozen_axes)

        def _frozen_subqueries(*_a, **_k):
            return list(frozen_copy)

        app._draft_subqueries = _frozen_subqueries
    try:
        ctx = app._draft_build_context(client, inp, case["question"])
    finally:
        app._draft_subqueries = orig_subq

    hits = ctx["hits"]
    hits_ids = {p.get("object_id") for _l, _s, p in hits if p.get("object_id")}
    seen_ids = ctx["seen"]
    prov_by_id = {p["object_id"]: p for p in (ctx.get("provenance") or [])}

    # رتبة ما قبل المرتِّب المتقاطع: تُحسَب هنا بترتيب _pre_rerank_score تنازليًا (غير مخزَّنة
    # كرتبة صريحة في provenance الإنتاجية — فقط الدرجة، لا الموضع).
    pre_rerank_scored = sorted(
        ((p.get("object_id"), p.get("_pre_rerank_score")) for _l, _s, p in hits if p.get("object_id")),
        key=lambda x: -(x[1] if x[1] is not None else -1.0),
    )
    pre_rerank_rank = {oid: i for i, (oid, _sc) in enumerate(pre_rerank_scored)}

    channel_by_id = {}
    for _l, _s, p in hits:
        oid = p.get("object_id")
        if oid and oid not in channel_by_id:
            channel_by_id[oid] = p.get("_source", "dense")

    must = list(case.get("must_find", []))
    targets = {}
    for oid in must:
        p = prov_by_id.get(oid)
        targets[oid] = {
            "discovered": oid in hits_ids,
            "channel": channel_by_id.get(oid),
            "pre_rerank_rank": pre_rerank_rank.get(oid),
            "pre_rerank_score": (p or {}).get("pre_rerank_score"),
            "reranker_raw": (p or {}).get("reranker_raw"),
            "final_score": (p or {}).get("final_score"),
            "final_rank": (p or {}).get("rank"),
            "admitted": oid in seen_ids,       # = budget admission
            "final_context": oid in seen_ids,  # مرادف تام لـ admitted في هذه البنية (موثَّق)
        }

    disc_recall = (sum(1 for oid in must if oid in hits_ids) / len(must)) if must else None
    surv_recall = (sum(1 for oid in must if oid in seen_ids) / len(must)) if must else None

    return {
        "mode": mode,
        "exact_axes": list(ctx.get("subqueries") or []),
        "targets": targets,
        "discovery_complete_run_recall": disc_recall,
        "survival_complete_run_recall": surv_recall,
    }


def run_case(app, client, case, runs=5):
    print(f"=== {case['id']} — Normal Mode ({runs} تشغيلات، Haiku جديد كل مرة) ===", flush=True)
    normal_runs = []
    for i in range(runs):
        _reset_chap_cache(app)
        r = run_one(app, client, case, frozen_axes=None)
        r["run_id"] = f"normal-{i + 1}"
        normal_runs.append(r)
        print(f"  normal-{i + 1}: axes={r['exact_axes']}", flush=True)

    frozen_axes = normal_runs[0]["exact_axes"]
    print(f"=== {case['id']} — Frozen Mode (محاور مجمَّدة من normal-1) ===", flush=True)
    print(f"  frozen_axes = {frozen_axes}", flush=True)
    frozen_runs = []
    mismatch = False
    for i in range(runs):
        _reset_chap_cache(app)
        r = run_one(app, client, case, frozen_axes=frozen_axes)
        r["run_id"] = f"frozen-{i + 1}"
        frozen_runs.append(r)
        if r["exact_axes"] != frozen_axes:
            mismatch = True
            print(f"  ⚠ AXES_MISMATCH_IN_FROZEN_MODE at frozen-{i + 1}: {r['exact_axes']}", flush=True)
        else:
            print(f"  frozen-{i + 1}: axes مطابقة حرفيًا (لا نداء Haiku) ✓", flush=True)

    print(f"  {'✗ فشل تأكيد التجميد!' if mismatch else '✓ تأكيد: صفر نداء Haiku في كل تشغيلات Frozen الخمس'}",
          flush=True)
    return {
        "normal": normal_runs, "frozen": frozen_runs,
        "frozen_axes_source": "normal-1", "frozen_axes": frozen_axes,
        "axes_integrity_confirmed": not mismatch,
    }


def _stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {
        "min": round(min(vals), 4), "max": round(max(vals), 4),
        "mean": round(statistics.mean(vals), 4),
        "stdev": round(statistics.pstdev(vals), 4) if len(vals) > 1 else 0.0,
        "n": len(vals),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--only", type=str, default=None,
                     help="قصر التجربة على معرفات حالات محددة مفصولة بفواصل")
    args = ap.parse_args()

    import anthropic
    from admin import app

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    gold = load_gold_set()

    case_ids = PRIMARY_CASES + [NEGATIVE_CONTROL_CASE]
    if args.only:
        wanted = set(args.only.split(","))
        case_ids = [c for c in case_ids if c in wanted]

    results = {}
    for cid in case_ids:
        results[cid] = run_case(app, client, gold[cid], runs=args.runs)

    print()
    print("=" * 70)
    print("FROZEN_AXES_RAW_MATRIX (كامل — لكل تشغيلة/هدف)")
    print("=" * 70)
    print(json.dumps(results, ensure_ascii=False, indent=2))

    print()
    print("=" * 70)
    print("ملخص السببية — الهدف البؤري لكل حالة، Normal مقابل Frozen")
    print("=" * 70)
    causal_summary = {}
    for cid in case_ids:
        target = FOCUS_TARGET[cid]
        row = {}
        for mode_name in ("normal", "frozen"):
            runs = results[cid][mode_name]
            disc = [r["targets"].get(target, {}).get("discovered") for r in runs]
            surv = [r["targets"].get(target, {}).get("final_context") for r in runs]
            row[mode_name] = {
                "discovery": f"{sum(bool(x) for x in disc)}/{len(disc)}",
                "survival": f"{sum(bool(x) for x in surv)}/{len(surv)}",
            }
        causal_summary[cid] = {"target": target, **row}
        print(f"{cid} / {target}:")
        print(f"  Normal: discovery={row['normal']['discovery']} survival={row['normal']['survival']}")
        print(f"  Frozen: discovery={row['frozen']['discovery']} survival={row['frozen']['survival']}")

    print()
    print("=" * 70)
    print("Complete-Run Recall statistics (Discovery وSurvival) — لكل حالة/نمط")
    print("=" * 70)
    complete_run_stats = {}
    for cid in case_ids:
        complete_run_stats[cid] = {}
        for mode_name in ("normal", "frozen"):
            runs = results[cid][mode_name]
            d_stats = _stats([r["discovery_complete_run_recall"] for r in runs])
            s_stats = _stats([r["survival_complete_run_recall"] for r in runs])
            complete_run_stats[cid][mode_name] = {"discovery": d_stats, "survival": s_stats}
            print(f"{cid} [{mode_name}] discovery: {d_stats}")
            print(f"{cid} [{mode_name}] survival:  {s_stats}")

    print()
    print(json.dumps({"causal_summary": causal_summary, "complete_run_stats": complete_run_stats},
                      ensure_ascii=False, indent=2))
    print("FROZEN_AXES_EXPERIMENT_DONE", flush=True)


if __name__ == "__main__":
    main()
