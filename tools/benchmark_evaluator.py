#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.1 Closure — مُقيِّم Benchmark: يقرأ `required_dimensions` (الحقيقة الأرضية المستقلة،
المجمَّدة بعد التأليف الأعمى + التحقق عبر MCP) **بعد الحساب فقط** — لا يُستورَد من أي ملف
قرار حي (p2_backbone.py/p2_evidence_classification.py/p2_admission_policy.py/
p2_coverage_checker.py) ولا من مُشغِّلَي Shadow (shadow_a_runner.py/shadow_b_runner.py)؛
انظر tools/benchmark_isolation_test.py للتحقق الآلي من ذلك.

يحسب: Verified Dimension-Level Micro Recall، Case-Level Strict Scope Completeness،
Critical-Dimension Recall، Critical Case Failure Count، Unresolved Ground-Truth Dimensions
(مُستبعَدة من كل مقام)، وتوزيعات حسب legal_role/difficulty/retrieval_class — على ثلاث طبقات
مقارنة: الإنتاج الحالي (current_final_context)، Shadow A، Shadow B — بقراءة نتائج خام
محفوظة فعليًا (shadow_a2.log وshadow_b.log)، بلا أي تشغيل جديد."""
import json
from collections import defaultdict


def load_gold_set(path="/opt/LegalMind/tools/retrieval_gold_set.json"):
    return json.load(open(path, encoding="utf-8"))


def extract_raw_results(log_path, marker, index=0):
    log = open(log_path, encoding="utf-8", errors="replace").read()
    idx = 0
    blocks = []
    while True:
        s = log.find(marker, idx)
        if s == -1:
            break
        after = log[s:]
        lines = after.split("\n")
        json_start = next(i for i, ln in enumerate(lines) if ln.strip().startswith("["))
        json_lines = []
        for ln in lines[json_start:]:
            json_lines.append(ln)
            if ln == "]":
                break
        blocks.append(json.loads("\n".join(json_lines)))
        idx = s + len(marker)
    return blocks[index]


def categorize_dimensions(cases):
    """يفصل الأبعاد إلى ثلاث فئات — الحاسمة لصحة كل مقياس لاحق:
    - positive: لها سند (verified/partially_verified) وقائمة معرفات غير فارغة — تدخل الـRecall.
    - confirmed_absent: verified لكن بلا سند (ضوابط سلبية مؤكَّدة الغياب) — لا تدخل مقام الـRecall
      (لا شيء يُطلَب اكتشافه)، تُحصى منفصلة.
    - unresolved: لم يُحسَم (لا سند كافٍ وُجد) — تُستبعَد من كل مقام نهائي وتُعرَض منفصلة، كما
      أمر المالك صراحة."""
    positive, confirmed_absent, unresolved = [], [], []
    for c in cases:
        for d in c.get("required_dimensions", []):
            entry = (c["id"], d)
            status = d.get("ground_truth_status")
            ids = d.get("ground_truth_authority_ids") or []
            if status == "unresolved":
                unresolved.append(entry)
            elif status in ("verified", "partially_verified") and ids:
                positive.append(entry)
            elif status == "verified" and not ids:
                confirmed_absent.append(entry)
            else:
                unresolved.append(entry)
    return positive, confirmed_absent, unresolved


def dimension_satisfied(dim, final_context_ids):
    return any(aid in final_context_ids for aid in (dim.get("ground_truth_authority_ids") or []))


def compute_metrics(cases, final_context_by_case, label):
    positive, confirmed_absent, unresolved = categorize_dimensions(cases)
    case_by_id = {c["id"]: c for c in cases}

    def fc(cid):
        return set(final_context_by_case.get(cid, []))

    hits = [dimension_satisfied(d, fc(cid)) for cid, d in positive]
    micro_recall = round(sum(hits) / len(hits), 4) if hits else None

    crit_pairs = [(cid, d) for cid, d in positive if d.get("critical")]
    crit_hits = [dimension_satisfied(d, fc(cid)) for cid, d in crit_pairs]
    critical_recall = round(sum(crit_hits) / len(crit_hits), 4) if crit_hits else None

    by_case_required = defaultdict(list)
    for cid, d in positive:
        if d.get("required"):
            by_case_required[cid].append(d)
    case_pass = {cid: all(dimension_satisfied(d, fc(cid)) for d in dims)
                 for cid, dims in by_case_required.items()}
    strict_completeness = round(sum(case_pass.values()) / len(case_pass), 4) if case_pass else None

    by_case_critical = defaultdict(list)
    for cid, d in positive:
        if d.get("critical"):
            by_case_critical[cid].append(d)
    critical_case_pass = {cid: all(dimension_satisfied(d, fc(cid)) for d in dims)
                           for cid, dims in by_case_critical.items()}
    critical_failures = sorted(cid for cid, ok in critical_case_pass.items() if not ok)

    def _hashable(key):
        # بعض حقول Gold Set (retrieval_class تحديدًا) قوائم لا قيمًا مفردة لبعض الحالات —
        # تُحوَّل لـtuple مرتَّب لتصلح مفتاحًا، بلا تغيير في المعنى (نفس المجموعة = نفس الدلو)
        if isinstance(key, list):
            return tuple(sorted(key))
        return key

    def recall_by(keyfn):
        buckets = defaultdict(lambda: [0, 0])
        for cid, d in positive:
            key = _hashable(keyfn(cid, d))
            buckets[key][0] += int(dimension_satisfied(d, fc(cid)))
            buckets[key][1] += 1
        return {str(k): {"hit": v[0], "total": v[1],
                          "recall": round(v[0] / v[1], 4) if v[1] else None}
                for k, v in sorted(buckets.items(), key=lambda kv: str(kv[0]))}

    return {
        "label": label,
        "positive_dimensions_total": len(positive),
        "confirmed_absent_dimensions_total": len(confirmed_absent),
        "unresolved_dimensions_total": len(unresolved),
        "unresolved_dimensions": [{"case_id": cid, "dimension_id": d["dimension_id"]}
                                   for cid, d in unresolved],
        "verified_dimension_level_micro_recall": micro_recall,
        "critical_dimension_recall": critical_recall,
        "case_level_strict_scope_completeness": strict_completeness,
        "case_level_strict_scope_completeness_pass": sum(case_pass.values()),
        "case_level_strict_scope_completeness_total": len(case_pass),
        "critical_case_failure_count": len(critical_failures),
        "critical_case_failures": critical_failures,
        "recall_by_legal_role": recall_by(lambda cid, d: d.get("legal_role")),
        "recall_by_difficulty": recall_by(lambda cid, d: case_by_id[cid].get("difficulty")),
        "recall_by_retrieval_class": recall_by(lambda cid, d: case_by_id[cid].get("retrieval_class")),
    }


def main():
    gold = load_gold_set()
    cases = gold["cases"]
    missing = [c["id"] for c in cases if "required_dimensions" not in c]
    if missing:
        print(f"!! الملف غير مجمَّد بعد — حالات بلا required_dimensions: {missing}")
        raise SystemExit(1)

    shadow_a = extract_raw_results("/tmp/shadow_a2.log", "SHADOW_A_RAW_RESULTS")
    shadow_b = extract_raw_results("/tmp/shadow_b.log", "SHADOW_B_RAW_RESULTS", index=0)

    current_fc = {r["case_id"]: r["current_final_context"] for r in shadow_a}
    shadow_a_fc = {r["case_id"]: r["shadow_a_final_context"] for r in shadow_a}
    shadow_b_fc = {r["case_id"]: r["shadow_b_final_context"] for r in shadow_b}

    results = {
        "gold_set_frozen_at": gold.get("_required_dimensions_frozen_at"),
        "baseline_current_production": compute_metrics(cases, current_fc, "current_production"),
        "shadow_a": compute_metrics(cases, shadow_a_fc, "shadow_a"),
        "shadow_b": compute_metrics(cases, shadow_b_fc, "shadow_b"),
    }
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("\nBENCHMARK_EVALUATOR_DONE")


if __name__ == "__main__":
    main()
