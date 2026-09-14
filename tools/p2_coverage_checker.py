#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.1A — Coverage Checker، طبقًا لـdocs/p2_architecture_design.md §7 (مُعدَّل v2). يبني
حالة كل بُعد قانوني من مخرَجات Backbone + Classification + Admission، بآلة الحالة المُصحَّحة
(GOVERNING_VERIFIED مقابل SUPPORTING_FOUND منفصلتين، لا 'ANCHORED' واحدة)."""
from __future__ import annotations


def check_coverage(scope, tiers, admission_decisions, admitted_ids):
    """admitted_ids: مجموعة object_id التي وصلت فعليًا للسياق النهائي (reserved المقبولة +
    ما فاز بالمنافسة العادية — يُمرَّر من المستدعي بعد محاكاة/تنفيذ التجميع الكامل).

    تنويه (2026-09-14): `related_a`/`related_b` أدناه يقتصران على tier في ("A1","A2","A3")
    و("B",) على التوالي — طبقة S (Structural/Enactment) مستبعدة عمدًا من كليهما فلا تُحتسب
    سندًا حاكمًا ولا داعمًا لأي بُعد، حتى لو أُدرجت في السياق النهائي عبر المنافسة العادية.
    نقطة توسعة موثقة لا مُفعَّلة: لو استُحدثت مستقبلًا قاعدة بُعد صريحة عن النفاذ/السريان/
    الإلغاء/الانتقال الزمني، ترقية S إلى سند لذلك البُعد تحديدًا تحتاج كودًا جديدًا هنا — لا
    تُخمَّن الآن بلا قاعدة تستدعيها."""
    dims_report = {}
    for dim in scope.get("dimensions", []):
        did = dim["dimension_id"]
        required = dim.get("required", False)
        requires_governing = dim.get("requires_governing", True)

        # المرشحون المرتبطون بهذا البُعد تحديدًا (عبر anchors_a3 أو classification reason)
        related_a = [oid for oid, t in tiers.items()
                     if t["tier"] in ("A1", "A2", "A3") and t["reason"].get("dimension") == did]
        related_b = [oid for oid, t in tiers.items()
                     if t["tier"] == "B" and t["reason"].get("dimension") == did]

        governing_found = len(related_a) > 0
        governing_admitted = any(oid in admitted_ids for oid in related_a)
        supporting_found = len(related_b) > 0
        supporting_admitted = any(oid in admitted_ids for oid in related_b)

        if governing_admitted:
            authority_sufficient = True
        elif (not requires_governing) and supporting_admitted:
            authority_sufficient = True
        else:
            authority_sufficient = False

        if not required:
            state = "UNKNOWN"
        elif governing_admitted:
            state = "ADMITTED_GOVERNING"
        elif governing_found:
            state = "GOVERNING_VERIFIED"
        elif supporting_admitted:
            state = "ADMITTED_SUPPORTING"
        elif supporting_found:
            state = "SUPPORTING_FOUND"
        elif related_a or related_b:
            state = "CANDIDATE_FOUND"
        else:
            state = "SCOPED"  # طُلِب لكن لا مرشح إطلاقًا — DEAD_END يُقرَّره Search Exhaustion لا هنا

        dims_report[did] = {
            "label": dim.get("label"), "required": required, "requires_governing": requires_governing,
            "retrieval_complete": True,  # Shadow لا يشغّل CoverageRepairRequest فعليًا (تصميم P2.1، محاكاة فقط)
            "governing_authority_found": governing_found,
            "governing_authority_admitted": governing_admitted,
            "supporting_authority_found": supporting_found,
            "supporting_authority_admitted": supporting_admitted,
            "authority_sufficient": authority_sufficient,
            "temporal_resolved": False,  # لا آلية زمنية بعد (§11 من P2 — خارج نطاق P2.1 الحالي)
            "state": state,
        }

    required_dims = [d for d in dims_report.values() if d["required"]]
    coverage_complete = all(d["authority_sufficient"] for d in required_dims) if required_dims else True

    return {"dimensions": dims_report, "coverage_complete": coverage_complete,
            "required_count": len(required_dims),
            "sufficient_count": sum(1 for d in required_dims if d["authority_sufficient"])}
