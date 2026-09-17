#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.6-V Step 5/6/7/8 scoring driver.

يستدعي `p26_evaluator` المجمَّد كما هو (score_case/aggregate) بلا أي تعديل عليه.
دوره هنا: مُحوِّل بنية فقط — يبني كائنات الحالات بالشكل الذي يتوقعه المُقيِّم من
الحقيقة الأرضية الأصلية لـGold Set40، ثم يمرر أحكام المطابقة الدلالية اليدوية.

**حدّ منهجي مُعلَن:** حقيقة Gold Set40 الأصلية تحمل `required` منطقيًا (نعم/لا) ولا تحمل
التصنيف الثلاثي required/conditional/possible المستعمل في Dev26/Gold-tier10. التحويل
المعتمد هنا: required=True → "required"، required=False → "possible". أي أن الصف
CONDITIONAL في الحقيقة الأرضية **غير موجود أصلًا** في هذه المجموعة (0 من 142)، وهذا
يُعلَن صراحة في التقرير ولا يُعالَج بتعديل بيانات.
"""
import json
import sys
import collections

sys.path.insert(0, "/home/user/LegalMind/tools")
from p26_evaluator import score_case, aggregate  # noqa: E402

BASE = "/home/user/LegalMind/tools/"

gold = json.load(open(BASE + "retrieval_gold_set.json"))["cases"]
gt = {c["case_id"]: c["required_dimensions"]
      for c in json.load(open(BASE + "p26_v_original_gold40_required_dimensions.json"))}
outs = {r["case_id"]: r for r in json.load(open(BASE + "p26_v_gold40_planner_outputs.json"))}
mm = json.load(open(BASE + "p26_v_manual_matches.json"))["cases"]
meta = {c["id"]: c for c in gold}


def gt_status(dim):
    return "required" if dim["required"] else "possible"


case_scores = []
for n in range(1, 41):
    cid = f"gs-{n:04d}"
    dims = [{"dimension_id": d["dimension_id"], "status": gt_status(d),
             "critical": d["critical"], "label": d["label"],
             "legal_role": d["legal_role"]} for d in gt[cid]]
    case = {"id": cid,
            "complexity": meta[cid].get("difficulty", "unknown"),
            "question": meta[cid]["question"],
            "ground_truth_issues": [{"issue_id": cid + "-i1", "dimensions": dims}]}
    m = mm[cid]
    # المُقيِّم المجمَّد يفهرس بـ(gt_issue_id, gt_dimension_id)؛ الحقيقة الأرضية الأصلية
    # مسطّحة بلا تجميع في مسائل، فتُلف كلها في مسألة واحدة لكل حالة (محوّل بنية بحت).
    for _m in m["matches"]:
        _m["gt_issue_id"] = cid + "-i1"
    unmatched =([{"class": "reasonable_elaboration"}] * m["unmatched"]["reasonable_elaboration"] +
                 [{"class": "unsupported_risky"}] * m["unmatched"]["unsupported_risky"])
    case_scores.append(score_case(case, outs[cid]["parsed_object"],
                                  outs[cid]["raw_json_text"], m["matches"], unmatched))

agg = aggregate(case_scores)

print("=" * 78)
print("P2.6-V — GOLD SET40 (الأصلية) — مقاييس المُقيِّم المجمَّد")
print("=" * 78)
for k in ["n_cases", "total_gt_dimensions", "total_matched", "total_planner_dimensions",
          "total_unsupported_risky", "total_reasonable_elaboration",
          "dimension_recall", "dimension_precision", "critical_dimension_recall",
          "strict_case_completeness", "unsupported_dimension_rate",
          "ungrounded_dimension_rate", "structural_validity_violations",
          "id_leakage_violations"]:
    v = agg[k]
    print(f"  {k:34s} = {v:.4f}" if isinstance(v, float) else f"  {k:34s} = {v}")

print("\n--- دقة تصنيف الإلزام (Obligation Classification) حسب حالة الحقيقة الأرضية ---")
for st, v in agg["status_classification_precision"].items():
    print(f"  {st:12s} total_gt={v['total_gt']:3d}  matched_correct={v['matched_correct_status']:3d}"
          f"  matched_wrong={v['matched_wrong_status']:3d}  precision={v['classification_precision']}")

print("\n--- الاستدعاء حسب difficulty (حقل معلن في بيانات Gold Set40) ---")
for k, v in sorted(agg["complexity_stratified_recall"].items()):
    print(f"  {k:14s} = {v:.4f}" if v is not None else f"  {k:14s} = n/a")

# --- مصفوفة الارتباك 3x3 (Step 7) ---
print("\n--- مصفوفة ارتباك 3x3 (صفوف=الحقيقة الأرضية، أعمدة=تنبؤ Planner) ---")
cm = collections.Counter()
for cs in case_scores:
    for d in cs["dimension_results"]:
        if d["matched"]:
            cm[(d["status"], d["planner_status"])] += 1
cats = ["required", "conditional", "possible"]
hdr = "GT-vs-PL"
print(f"  {hdr:14s}" + "".join(f"{c:>13s}" for c in cats) + f"{'TOTAL':>9s}")
for g in cats:
    row = [cm[(g, p)] for p in cats]
    print(f"  {g:14s}" + "".join(f"{x:13d}" for x in row) + f"{sum(row):9d}")
print(f"  {'TOTAL':14s}" + "".join(f"{sum(cm[(g,p)] for g in cats):13d}" for p in cats))

# --- الاستدعاء حسب retrieval_class (حقل متعدد الوسوم معلن في البيانات) ---
print("\n--- الاستدعاء حسب retrieval_class (وسوم البيانات الأصلية، متعدد الوسوم) ---")
by_rc = collections.defaultdict(lambda: {"gt": 0, "matched": 0, "cases": 0})
for cs in case_scores:
    rcs = meta[cs["case_id"]].get("retrieval_class")
    rcs = rcs if isinstance(rcs, list) else [rcs]
    for rc in rcs:
        by_rc[rc]["gt"] += cs["gt_dim_count"]
        by_rc[rc]["matched"] += sum(1 for d in cs["dimension_results"] if d["matched"])
        by_rc[rc]["cases"] += 1
for rc, v in sorted(by_rc.items(), key=lambda kv: -kv[1]["cases"]):
    r = v["matched"] / v["gt"] if v["gt"] else None
    print(f"  {rc:28s} cases={v['cases']:2d} gt={v['gt']:3d} matched={v['matched']:3d} recall="
          + (f"{r:.4f}" if r is not None else "n/a"))

# --- الضوابط السلبية ---
print("\n--- الضوابط السلبية (case_type=negative) ---")
for cs in case_scores:
    if meta[cs["case_id"]].get("case_type") == "negative":
        nm = sum(1 for d in cs["dimension_results"] if d["matched"])
        print(f"  {cs['case_id']}: gt={cs['gt_dim_count']} matched={nm} planner_dims={cs['planner_dim_count']}")

# --- سجل التفويتات (Step 9) ---
print("\n--- كل التفويتات (False Negatives) ---")
nfn = 0
for cs in case_scores:
    for d in cs["dimension_results"]:
        if not d["matched"]:
            nfn += 1
            print(f"  {cs['case_id']:9s} [{d['dimension_id']}] critical={d['critical']} "
                  f"role={d['legal_role']} status={d['status']}")
print(f"  إجمالي التفويتات = {nfn}")

json.dump({"aggregate": agg,
           "case_scores": [{k: v for k, v in cs.items() if k != "fact_grounding"} for cs in case_scores],
           "confusion_matrix_3x3": {f"{g}->{p}": cm[(g, p)] for g in cats for p in cats},
           "retrieval_class_recall": {k: dict(v) for k, v in by_rc.items()}},
          open(BASE + "p26_v_scores.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("\nSAVED: tools/p26_v_scores.json")
