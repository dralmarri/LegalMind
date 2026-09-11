#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1 — مقاييس Gold Set الاسترجاعية (بلا نداء صياغة/توليد أبدًا).

نطاق هذا الإصدار محدود بصراحة: يعيد استعمال retrieve() من tools/battery_run.py —
وهي دالة تجمع نتائج كل قنوات الاسترجاع (محاور/متجهات/حزم/محلّ/فصول/معجمي/XREF/
شقيقات/prin-xref) **بلا** أي سقف نوع (caps_n) ولا مرتِّب متقاطع ولا ميزانية أحرف.
لذلك ما يقيسه هذا السكربت هو **Candidate Recall فقط** — "هل تصل أي قناة إلى
هذا المصدر أصلًا؟" — وهو الطابق الأول من قمع النجاة (survival funnel) لا كله.

الطوابق الأعمق (Recall@K بعد الترتيب، الوصول الفعلي للسياق النهائي بعد caps_n/
المرتِّب/الميزانية، وتصنيف الفشل بمرحلته الدقيقة) تتطلب تشغيل _draft_run نفسها
(نداء توليد حقيقي) أو تنفيذ مقترح فصل البحث عن التوليد الموثق في
docs/p1_retrieval_evaluation_framework.md §H — كلاهما غير منفَّذ في هذه الجولة
بأمر صريح من المالك. القسمان أدناه (الطابق الأول فقط) صادقان بحدودهما، لا أكثر.
"""
import json
import sys

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")


def load_gold_set(path="/opt/LegalMind/tools/retrieval_gold_set.json"):
    return json.load(open(path, encoding="utf-8"))["cases"]


def _last_article_id(pref):
    import os
    import psycopg
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM knowledge_objects WHERE id LIKE %s AND id ~ %s "
            "ORDER BY (substring(id from 'm([0-9]+)$'))::int DESC LIMIT 1",
            (pref + "m%", "^" + pref + "m[0-9]+$"))
        row = cur.fetchone()
    return row[0] if row else None


def evaluate_case(retrieve_fn, case):
    picked, _sq = retrieve_fn(case["request_type"], case["question"])

    must = case.get("must_find", [])
    must_hit = [m for m in must if m in picked]
    must_miss = [m for m in must if m not in picked]

    any_groups = case.get("must_find_any_of", [])
    any_results = []
    for grp in any_groups:
        satisfied = any(g in picked for g in grp)
        any_results.append({"group": grp, "satisfied": satisfied,
                             "hit": [g for g in grp if g in picked]})

    mnm = case.get("must_not_miss", [])
    mnm_hit = [m for m in mnm if m in picked]
    mnm_miss = [m for m in mnm if m not in picked]

    law_min_results = []
    for pref, n in case.get("law_min", []):
        k = sum(1 for p in picked if p.startswith(pref))
        law_min_results.append({"prefix": pref, "required": n, "found": k,
                                 "satisfied": k >= n})

    must_last_results = []
    for pref in case.get("must_last", []):
        target = _last_article_id(pref)
        must_last_results.append({"prefix": pref, "target": target,
                                   "satisfied": bool(target) and target in picked})

    case_pass = (
        not must_miss
        and all(r["satisfied"] for r in any_results)
        and not mnm_miss
        and all(r["satisfied"] for r in law_min_results)
        and all(r["satisfied"] for r in must_last_results)
    )

    return {
        "id": case["id"], "category": case["category"],
        "retrieval_class": case.get("retrieval_class", []),
        "candidate_count": len(picked),
        "must_find_total": len(must), "must_find_hit": len(must_hit),
        "must_find_miss_ids": must_miss,
        "any_of": any_results,
        "must_not_miss_total": len(mnm), "must_not_miss_hit": len(mnm_hit),
        "must_not_miss_miss_ids": mnm_miss,
        "law_min": law_min_results,
        "must_last": must_last_results,
        "case_pass": case_pass,
    }


def aggregate(results):
    total_must = sum(r["must_find_total"] for r in results)
    hit_must = sum(r["must_find_hit"] for r in results)
    must_recall = (hit_must / total_must) if total_must else None

    mnm_cases = [r for r in results if r["must_not_miss_total"] > 0]
    mnm_fail_cases = [r for r in mnm_cases if r["must_not_miss_miss_ids"]]
    mnm_failure_rate = (len(mnm_fail_cases) / len(mnm_cases)) if mnm_cases else None

    by_class = {}
    for r in results:
        for cls in (r["retrieval_class"] or ["(untagged)"]):
            by_class.setdefault(cls, {"cases": 0, "passed": 0})
            by_class[cls]["cases"] += 1
            if r["case_pass"]:
                by_class[cls]["passed"] += 1

    overall_pass = sum(1 for r in results if r["case_pass"])

    return {
        "candidate_must_find_recall": must_recall,
        "must_find_hit_total": hit_must, "must_find_total": total_must,
        "must_not_miss_failure_rate": mnm_failure_rate,
        "must_not_miss_failing_cases": [r["id"] for r in mnm_fail_cases],
        "by_retrieval_class": by_class,
        "overall_pass": overall_pass, "overall_total": len(results),
    }


def main():
    import battery_run  # noqa: يستورد retrieve() الحية من tools/battery_run.py على الخادم

    cases = load_gold_set()
    results = []
    for c in cases:
        print(f"... {c['id']} — {c['category']}", flush=True)
        r = evaluate_case(battery_run.retrieve, c)
        results.append(r)
        flag = "✓" if r["case_pass"] else "✗"
        print(f"  {flag} مرشحون: {r['candidate_count']} | "
              f"must_find: {r['must_find_hit']}/{r['must_find_total']}"
              + (f" | فقد: {r['must_find_miss_ids']}" if r["must_find_miss_ids"] else "")
              + (f" | must_not_miss فقد: {r['must_not_miss_miss_ids']}"
                 if r["must_not_miss_miss_ids"] else ""),
              flush=True)

    agg = aggregate(results)
    print()
    print("=" * 70)
    print("ملخص القسمين C/D من تقرير P1 — Candidate Recall (الطابق الأول فقط)")
    print("=" * 70)
    print(json.dumps(agg, ensure_ascii=False, indent=2))
    print()
    print(f"GOLD_METRICS_DONE | overall {agg['overall_pass']}/{agg['overall_total']} "
          f"| candidate_must_find_recall={agg['candidate_must_find_recall']}")


if __name__ == "__main__":
    main()
