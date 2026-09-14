#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.1A — Evidence Admission Policy + Bounded Anchor Reservation، طبقًا لـ
docs/p2_architecture_design.md §5-§6. يأخذ تصنيف p2_evidence_classification ويقرِّر: من
يدخل الحجز المحدود (A1/A2/A3)، ومن يتنافس على الميزانية العادية (B/C/D)."""
from __future__ import annotations

ANCHOR_RESERVATION = {
    "تشريع": {"max_chars": 6000, "max_count": 6},
    "مبدأ قضائي": {"max_chars": 4000, "max_count": 4},
}
MAX_ANCHORS_PER_DIMENSION = 3
MAX_ANCHORS_PER_LAW_PREFIX = 5  # أول جزأين من المعرِّف (مثال legis-38-1980)


def _law_prefix(object_id):
    parts = object_id.split("-")
    return "-".join(parts[:3]) if len(parts) >= 3 else object_id


def admit(tiers, texts, dimension_ids_by_object):
    """tiers: مخرَج classify_candidates. texts: {object_id: {"text":..., "branch":...,...}}
    (لحساب الطول واستخراج label للتشريع/المبدأ). dimension_ids_by_object: {object_id:
    dimension_id} للأدلة المرتبطة ببُعد (A2/A3/B). يُعيد:
    {reserved: [...], competitive: {...}, overflow: [...], anchor_reasons: {...}}."""
    reserved, overflow, decisions = [], [], {}
    per_dim_count, per_law_count, used_chars = {}, {}, {}

    anchors = sorted(
        [(oid, t) for oid, t in tiers.items() if t["tier"] in ("A1", "A2", "A3")],
        key=lambda x: {"A1": 0, "A2": 1, "A3": 2}[x[1]["tier"]],
    )
    for oid, t in anchors:
        txt = texts.get(oid, {})
        label = txt.get("object_type_label", "تشريع")
        chars = len(txt.get("text") or "")
        dim = dimension_ids_by_object.get(oid, t["reason"].get("dimension"))
        law_pfx = _law_prefix(oid)

        cap = ANCHOR_RESERVATION.get(label, {"max_chars": 4000, "max_count": 4})
        dim_n = per_dim_count.get(dim, 0)
        law_n = per_law_count.get(law_pfx, 0)
        used = used_chars.get(label, 0)

        if dim is not None and dim_n >= MAX_ANCHORS_PER_DIMENSION:
            overflow.append({"object_id": oid, "reason": "max_anchors_per_dimension", "dimension": dim})
            decisions[oid] = {"decision": "BUMPED_TO_COMPETITIVE", "tier": t["tier"]}
            continue
        if law_n >= MAX_ANCHORS_PER_LAW_PREFIX:
            overflow.append({"object_id": oid, "reason": "max_anchors_per_law", "law_prefix": law_pfx})
            decisions[oid] = {"decision": "BUMPED_TO_COMPETITIVE", "tier": t["tier"]}
            continue
        if used + chars > cap["max_chars"] or per_dim_count.get("_total_" + label, 0) >= cap["max_count"]:
            overflow.append({"object_id": oid, "reason": "reservation_budget_exhausted", "type": label})
            decisions[oid] = {"decision": "BUMPED_TO_COMPETITIVE", "tier": t["tier"]}
            continue

        reserved.append(oid)
        decisions[oid] = {
            "decision": "ADMIT_RESERVED", "tier": t["tier"],
            "anchor_reason": {"rule_id": t["reason"].get("rule_id"), "tier": t["tier"],
                               "dimension": dim, "why": t["reason"]},
        }
        if dim is not None:
            per_dim_count[dim] = dim_n + 1
        per_law_count[law_pfx] = law_n + 1
        used_chars[label] = used + chars
        per_dim_count["_total_" + label] = per_dim_count.get("_total_" + label, 0) + 1

    # B/C/D (+ ما هُبِط من الحجز) يتنافسون عاديًا — القرار هنا تصنيفي فقط (المنافسة الفعلية
    # على الميزانية تبقى لمنطق _draft_build_context القائم، Shadow A/B تحاكيانه بترتيب مطابق)
    for oid, t in tiers.items():
        if oid in decisions:
            continue
        decisions[oid] = {"decision": "COMPETE_ON_BUDGET", "tier": t["tier"]}

    return {"reserved": reserved, "overflow": overflow, "decisions": decisions}
