#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.1 — Shadow A (Admission Shadow) Offline Replay Runner، طبقًا لـ
docs/p2_1_shadow_mode_design.md §1/§5 (v2). يقرأ `current hits` من تشغيلة إنتاجية فعلية
حقيقية لـ`_draft_build_context` (بلا أي تعديل عليها) **ولا يستدعي أي نداء استرجاع جديد** —
فقط: Backbone (تحديد الأبعاد + قواعد A3 المرشَّحة، بلا تغذية قنوات) → تصنيف → حجز → قبول →
تغطية. Offline فقط (بأمر صريح) — لا يُشغَّل على حركة مرور حية، فقط Gold Set أو حركة مرور
تاريخية معاد تشغيلها من `facts_ret` محفوظ.

**تأكيد عدم مساس الإنتاج:** هذا سكربت مستقل يُشغَّل يدويًا offline، لا نقطة استدعاء واحدة من
admin/app.py الحي إليه أو منه — عزل فيزيائي تام (Section 8، P2.1 v2).

**تصحيح عزل تجريبي (2026-09-14):** التشغيلة الأولى أظهرت `legis-1-2016-m30` (Discovery
Failure تاريخيًا موثَّق — غائبة عن hits الحقيقية) ضمن must_find_rescued خطأً، بسبب حقن كان
موجودًا وقتها في `p2_evidence_classification.classify_candidates` (أُزيل الآن كليًا). النتيجة
السابقة سُجِّلت لا مُحيت (`experimental isolation bug detected before Shadow B`) — الحقن كان
يصنع مرشحًا لم يكتشفه أي استرجاع فعلي، فيُبطل تعريف Shadow A. بعد التصحيح: `main()` يتحقق
آليًا أن لا تقاطع بين `must_find_rescued` و`a3_absent_from_hits` في أي حالة."""
import json
import sys

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")


def load_gold_set(path="/opt/LegalMind/tools/retrieval_gold_set.json"):
    return json.load(open(path, encoding="utf-8"))["cases"]


def run_one(app, client, case, backbone_mod, ec_mod, ap_mod, cc_mod):
    inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
    ctx = app._draft_build_context(client, inp, case["question"])  # الإنتاج الحقيقي، بلا تعديل

    current_final = set(ctx["seen"])
    hits = ctx["hits"]

    # Backbone: تحديد الأبعاد + A1/A3 فقط (بلا تغذية أي قناة استرجاع جديدة — Shadow A تحديدًا)
    scope = backbone_mod.compute_backbone(app, case["request_type"], case["question"])

    # نصوص المرشحين الحاليين فقط (قراءة مكرَّرة لبيانات مكتشَفة أصلًا — ليست بحثًا جديدًا)
    ids = {p.get("object_id") for _l, _s, p in hits if p.get("object_id")}
    texts_raw = app._draft_fetch_texts(ids)
    texts = {oid: {"text": (t.get("text") or ""),
                   "object_type_label": t.get("branch") and "تشريع" or "تشريع"}
             for oid, t in texts_raw.items()}
    # تمييز مبسَّط للنوع (تشريع/مبدأ) من بادئة المعرِّف — كافٍ لغرض حجم الحجز فقط
    for oid in texts:
        texts[oid]["object_type_label"] = "مبدأ قضائي" if oid.startswith("jprin-") else "تشريع"

    xref_map = getattr(app, "_XREF", {})
    tiers = ec_mod.classify_candidates(hits, scope, xref_map=xref_map, texts=texts)
    dim_by_obj = {}
    for a in scope.get("anchors_a1", []) + scope.get("anchors_a3", []):
        if "dimension_id" in a:
            dim_by_obj[a["authority_id"]] = a["dimension_id"]

    # تعقّب صريح (بعد إزالة الحقن 2026-09-14): أي anchor A3 حدَّده Backbone لكن لم يظهر إطلاقًا
    # في hits الحقيقية — هذه بالضبط مادة Shadow B (تحتاج جلبًا/استرجاعًا فعليًا جديدًا)، ويجب
    # ألا تظهر أبدًا في must_find_rescued هنا. تسجيلها صراحةً يجعل التحقق من سلامة العزل مباشرًا
    # بلا اشتقاق يدوي من shadow_a_evidence_tiers.
    a3_ids_all = {a["authority_id"] for a in scope.get("anchors_a3", [])}
    a3_absent_from_hits = sorted(a3_ids_all - set(tiers.keys()))
    s_tier_ids = sorted(oid for oid, t in tiers.items() if t["tier"] == "S")

    admission = ap_mod.admit(tiers, texts, dim_by_obj)

    # محاكاة تجميع مبسَّطة: المحجوزون يدخلون دومًا (ضمن سقوفهم)؛ التنافسيون (B/C/D) نفترض أنهم
    # يحافظون على نفس مصير current (نجوا/لم ينجوا) لأن Shadow A لا يعيد حساب المرتِّب ولا
    # الميزانية العادية من الصفر — هذا تبسيط Shadow A المتعمَّد (يعزل أثر القبول على A فقط،
    # لا يعيد محاكاة كامل تنافس B/C/D، الموثَّق في تصميم P2.1 §2: "ماذا يفعل القبول الجديد
    # بنفس المرشحين الذين وجدهما الإنتاج فعليًا" — التركيز على مصير المرشحين المُرقَّين لا كل شيء).
    shadow_final = set(admission["reserved"]) | (current_final - {
        oid for oid, t in tiers.items() if t["tier"] in ("A1", "A2", "A3")
    })

    cov = cc_mod.check_coverage(scope, tiers, admission["decisions"], shadow_final)

    return {
        "case_id": case["id"],
        "current_final_context": sorted(current_final),
        "shadow_a_evidence_tiers": {k: v["tier"] for k, v in tiers.items()},
        "shadow_a_reserved_candidates": sorted(admission["reserved"]),
        "shadow_a_overflow": admission["overflow"],
        "shadow_a_coverage_state": cov,
        "shadow_a_final_context": sorted(shadow_final),
        "must_find": case.get("must_find", []),
        "must_find_rescued": sorted(set(case.get("must_find", [])) & (shadow_final - current_final)),
        "must_find_lost": sorted(set(case.get("must_find", [])) & (current_final - shadow_final)),
        "all_authorities_lost": sorted(current_final - shadow_final),
        "a3_absent_from_hits": a3_absent_from_hits,
        "s_tier_ids": s_tier_ids,
    }


def main():
    import anthropic
    from admin import app
    import p2_backbone, p2_evidence_classification, p2_admission_policy, p2_coverage_checker

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    cases = load_gold_set()

    only = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    if only:
        cases = [c for c in cases if c["id"] in only]

    results = []
    for c in cases:
        print(f"... {c['id']} — Shadow A", flush=True)
        try:
            r = run_one(app, client, c, p2_backbone, p2_evidence_classification,
                        p2_admission_policy, p2_coverage_checker)
        except Exception as e:
            print(f"  !! shadow-a-error: {e!r}", flush=True)
            continue
        results.append(r)
        print(f"  rescued={r['must_find_rescued']} lost={r['must_find_lost']} "
              f"coverage_complete={r['shadow_a_coverage_state']['coverage_complete']}", flush=True)

    print()
    print("=" * 70)
    print("SHADOW_A_RAW_RESULTS")
    print("=" * 70)
    print(json.dumps(results, ensure_ascii=False, indent=2))

    total_rescued = sum(len(r["must_find_rescued"]) for r in results)
    total_lost = sum(len(r["must_find_lost"]) for r in results)

    # بوابة عزل صريحة: لا يجوز أبدًا أن يظهر معرِّف واحد في كلٍّ من must_find_rescued
    # و a3_absent_from_hits لنفس الحالة — هذا بالضبط توقيع علة الحقن المُصلَحة. فشل هذا الفحص
    # يعني عودة الانتهاك ولا يجوز تجاهله.
    isolation_violations = []
    for r in results:
        bad = set(r["must_find_rescued"]) & set(r["a3_absent_from_hits"])
        if bad:
            isolation_violations.append((r["case_id"], sorted(bad)))
    if isolation_violations:
        print(f"\n!! SHADOW_A_ISOLATION_VIOLATION: {isolation_violations}")
    else:
        print("\nSHADOW_A_ISOLATION_OK: صفر تقاطع بين must_find_rescued وa3_absent_from_hits")

    print(f"\nSHADOW_A_DONE | cases={len(results)} | must_find_rescued_total={total_rescued} "
          f"| must_find_lost_total={total_lost}")


if __name__ == "__main__":
    main()
