#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.6 — أداة التقييم المجمَّدة. **بنية النتيجة والمقاييس هنا تُجمَّد قبل أي قياس نهائي —
تعديلها بعد التجميد يُبطل مقارنة Dev/Gold.**

منهجية المطابقة الدلالية (قرار مسجَّل): المطابقة بين نص Planner الحر ونص الحقيقة الأرضية
الكنوني تُنجَز بحكم دلالي مباشر من المشغِّل (قراءة وتصنيف يدوي منضبط بقاعدة ثابتة) لا بنداء
حكم آلي منفصل لكل زوج — قرار كلفة/اتساق واعٍ (نداء حكم آلي مستقل لكل بُعد من مئات الأبعاد يضخّم
كلفة التجربة بلا ضمان اتساق أعلى، والقاعدة الثابتة المُطبَّقة يدويًا هنا محكومة بمعيار واحد
موثَّق: هل يصف الوصفان **نفس المسألة القانونية الجوهرية** بصرف النظر عن الصياغة؟). هذا حدّ
منهجي موثَّق صراحة في التقرير النهائي، لا إخفاءً.

التصنيف الآلي الوحيد المحسوب برمجيًا بلا تدخل بشري: **التأصيل الواقعي** (`FACT_GROUNDED`/
`PARTIALLY_GROUNDED`/`UNGROUNDED`) — تراكب لفظي بين `triggering_facts` ونص السؤال الأصلي،
معيار موضوعي قابل لإعادة الإنتاج بخلاف المطابقة الدلالية."""
import re
import sys

sys.path.insert(0, "/home/user/LegalMind/tools")
from p26_schema import validate_structure, detect_id_leakage  # noqa: E402

_AR_WORD_RE = re.compile(r"[ء-ي]{2,}")
_FACT_GROUNDED_TH = 0.6
_FACT_PARTIAL_TH = 0.3


def _norm_words(text):
    return set(_AR_WORD_RE.findall(text or ""))


def classify_fact_grounding(triggering_fact, question_text):
    """تراكب لفظي بين عبارة الواقعة المزعومة ونص السؤال الأصلي — معيار موضوعي، لا حكم دلالي."""
    fw = _norm_words(triggering_fact)
    if not fw:
        return "UNGROUNDED"
    qw = _norm_words(question_text)
    overlap = len(fw & qw) / len(fw)
    if overlap >= _FACT_GROUNDED_TH:
        return "FACT_GROUNDED"
    if overlap >= _FACT_PARTIAL_TH:
        return "PARTIALLY_GROUNDED"
    return "UNGROUNDED"


def score_case(case, planner_obj, raw_json_text, manual_matches):
    """
    case: من DEV_SET/GOLD_TIER_SET (الحقيقة الأرضية).
    planner_obj: مخرج Planner بعد json.loads.
    raw_json_text: النص الخام (لكشف تسرّب المعرِّفات).
    manual_matches: قائمة أحكام دلالية يدوية بالبنية:
        [{"gt_issue_id":..., "gt_dimension_id":..., "matched": bool,
          "planner_status": "required|conditional|possible"|None}]
        كل بُعد حقيقة أرضية غير مذكور في القائمة يُعامَل matched=False تلقائيًا.
        أي بُعد Planner لم يُربَط بأي بُعد حقيقة أرضية هو "غير مسنود" (unsupported) ويُحسَب
        من `planner_obj` مباشرة (عدد أبعاد Planner الكلي - عدد المطابقات matched=True).
    """
    ok, struct_errors = validate_structure(planner_obj) if planner_obj is not None else (False, ["JSON غير قابل للتفكيك"])
    id_leaks = detect_id_leakage(raw_json_text)

    gt_dims = []
    for iss in case["ground_truth_issues"]:
        for d in iss["dimensions"]:
            gt_dims.append({**d, "issue_id": iss["issue_id"]})

    match_by_key = {(m["gt_issue_id"], m["gt_dimension_id"]): m for m in manual_matches}
    dim_results = []
    for d in gt_dims:
        key = (d["issue_id"], d["dimension_id"])
        m = match_by_key.get(key, {"matched": False, "planner_status": None})
        status_correct = (m["matched"] and m.get("planner_status") == d["status"])
        dim_results.append({**d, "matched": m["matched"], "planner_status": m.get("planner_status"),
                             "status_correct": status_correct})

    n_planner_dims = 0
    all_planner_facts = []
    if planner_obj:
        for iss in planner_obj.get("issues", []) or []:
            for d in iss.get("required_dimensions", []) or []:
                n_planner_dims += 1
                for tf in d.get("triggering_facts", []) or []:
                    all_planner_facts.append(tf)

    n_matched = sum(1 for m in manual_matches if m.get("matched"))
    n_unsupported = max(0, n_planner_dims - n_matched)

    fact_grounding = [{"fact": tf, "class": classify_fact_grounding(tf, case["question"])}
                       for tf in all_planner_facts]

    return {
        "case_id": case["id"], "complexity": case["complexity"],
        "structural_valid": ok, "structural_errors": struct_errors,
        "id_leakage": id_leaks,
        "gt_dim_count": len(gt_dims), "planner_dim_count": n_planner_dims,
        "dimension_results": dim_results,
        "n_unsupported": n_unsupported,
        "fact_grounding": fact_grounding,
    }


def aggregate(case_scores):
    """يُعيد كل المقاييس المطلوبة عبر مجموعة حالات مُقيَّمة (خرج score_case لكل حالة)."""
    total_gt = sum(cs["gt_dim_count"] for cs in case_scores)
    total_matched = sum(sum(1 for d in cs["dimension_results"] if d["matched"]) for cs in case_scores)
    total_planner = sum(cs["planner_dim_count"] for cs in case_scores)
    total_unsupported = sum(cs["n_unsupported"] for cs in case_scores)

    dim_recall = total_matched / total_gt if total_gt else None
    dim_precision = (total_planner - total_unsupported) / total_planner if total_planner else None
    unsupported_rate = total_unsupported / total_planner if total_planner else None

    crit_gt = [d for cs in case_scores for d in cs["dimension_results"] if d.get("critical")]
    crit_matched = sum(1 for d in crit_gt if d["matched"])
    critical_recall = crit_matched / len(crit_gt) if crit_gt else None

    strict_complete = sum(
        1 for cs in case_scores
        if cs["gt_dim_count"] == 0 or all(d["matched"] for d in cs["dimension_results"] if d.get("critical"))
    )
    strict_completeness = strict_complete / len(case_scores) if case_scores else None

    by_status = {"required": {"tp": 0, "fp_status": 0, "total_gt": 0},
                 "conditional": {"tp": 0, "fp_status": 0, "total_gt": 0},
                 "possible": {"tp": 0, "fp_status": 0, "total_gt": 0}}
    for cs in case_scores:
        for d in cs["dimension_results"]:
            st = d["status"]
            by_status[st]["total_gt"] += 1
            if d["matched"]:
                if d["status_correct"]:
                    by_status[st]["tp"] += 1
                else:
                    by_status[st]["fp_status"] += 1
    status_precision = {}
    for st, v in by_status.items():
        denom = v["tp"] + v["fp_status"]
        status_precision[st] = {"classification_precision": (v["tp"] / denom if denom else None),
                                 "total_gt": v["total_gt"], "matched_correct_status": v["tp"],
                                 "matched_wrong_status": v["fp_status"]}

    all_facts = [fg for cs in case_scores for fg in cs["fact_grounding"]]
    n_ungrounded = sum(1 for fg in all_facts if fg["class"] == "UNGROUNDED")
    ungrounded_rate = n_ungrounded / len(all_facts) if all_facts else None

    by_complexity = {}
    for cs in case_scores:
        by_complexity.setdefault(cs["complexity"], {"gt": 0, "matched": 0})
        by_complexity[cs["complexity"]]["gt"] += cs["gt_dim_count"]
        by_complexity[cs["complexity"]]["matched"] += sum(1 for d in cs["dimension_results"] if d["matched"])
    complexity_recall = {k: (v["matched"] / v["gt"] if v["gt"] else None) for k, v in by_complexity.items()}

    n_id_leak = sum(1 for cs in case_scores if cs["id_leakage"])
    n_structural_invalid = sum(1 for cs in case_scores if not cs["structural_valid"])

    return {
        "n_cases": len(case_scores),
        "dimension_recall": dim_recall, "dimension_precision": dim_precision,
        "critical_dimension_recall": critical_recall,
        "strict_case_completeness": strict_completeness,
        "unsupported_dimension_rate": unsupported_rate,
        "ungrounded_dimension_rate": ungrounded_rate,
        "status_classification_precision": status_precision,
        "complexity_stratified_recall": complexity_recall,
        "structural_validity_violations": n_structural_invalid,
        "id_leakage_violations": n_id_leak,
        "total_gt_dimensions": total_gt, "total_planner_dimensions": total_planner,
        "total_matched": total_matched, "total_unsupported": total_unsupported,
    }


if __name__ == "__main__":
    print("classify_fact_grounding smoke test:")
    print(classify_fact_grounding("القاضي قريب لأحد الخصوم", "تبيَّن أن القاضي قريب لأحد الخصوم في الدعوى"))
    print(classify_fact_grounding("موضوع لا علاقة له بالسؤال إطلاقًا", "تبيَّن أن القاضي قريب لأحد الخصوم في الدعوى"))
