#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.1A — تصنيف الأدلة (Evidence Classification) طبقًا لـdocs/p2_architecture_design.md §4
و§4-مكرر. يُصنِّف كل مرشح في مجموعة hits إلى A1/A2/A3/B/C/D — بلا استيراد من admin/app.py
(عزل فيزيائي تام، يقرأ `app` كوسيط مُمرَّر فقط عند الحاجة لـ_XREF).

**قرارات تشغيل صريحة (MVP، موثَّقة لا مخفاة):**
- B تُحدَّد حصرًا بمصدر 'chapter' (بوابة فصل حاكم) لأنها القناة الوحيدة المرتبطة فعليًا بنطاق
  بُعد قانوني معروف (`chapter_scopes`) في تركيبة البيانات الحالية؛ لا آلية ربط دقيقة بين نتائج
  'dense' المفردة وبُعد بعينه بعد (يحتاج تطويرًا لاحقًا لو ثبتت الحاجة قياسًا).
- C تُحدَّد لمصادر 'dense'/'bundle' (اكتشاف واسع، بعضه من محاور Haiku).
- D تُحدَّد لكل ما تبقى ('lexical'/'xref'/'sibling_xref'/'principle_xref').
- تصنيف `U` (Unverified Coverage Candidate) **لا** يقع هنا — يتطلب معرفة الأبعاد غير
  المغطاة بعد القبول، فهو مسؤولية p2_coverage_checker.py (طبقة لاحقة، §4-مكرر من P2 v2)."""
from __future__ import annotations


def classify_candidates(hits, scope, xref_map=None):
    """hits: قائمة (label, score, payload) كما تُعيدها _draft_build_context (أو Shadow A/B
    المكافئة). scope: مخرَج compute_backbone. xref_map: app._XREF أو ما يعادلها (اختياري —
    A2 تُهمَل إن غاب). يُعيد dict: {object_id: {"tier": ..., "reason": {...}}}."""
    a1_ids = {a["authority_id"] for a in scope.get("anchors_a1", [])}
    a3_by_id = {a["authority_id"]: a for a in scope.get("anchors_a3", [])}
    chapter_ids = {c["chapter_id"] for c in scope.get("chapter_scopes", [])}

    # A2: أهداف _XREF من أي مرساة A1/A3 مؤكَّدة (عمق واحد فقط، لا تعدٍّ متسلسل)
    a2_ids = {}
    if xref_map:
        for anchor_id in list(a1_ids) + list(a3_by_id.keys()):
            for target in xref_map.get(anchor_id, ()):
                if target not in a1_ids and target not in a3_by_id:
                    a2_ids.setdefault(target, anchor_id)

    result = {}
    for label, score, payload in hits:
        oid = payload.get("object_id")
        if not oid or oid in result:
            continue
        source = payload.get("_source", "dense")

        if oid in a1_ids:
            result[oid] = {"tier": "A1", "reason": {"rule_id": None, "source": "explicit_citation"}}
        elif oid in a3_by_id:
            a = a3_by_id[oid]
            result[oid] = {"tier": "A3", "reason": {"rule_id": a["rule_id"], "dimension": a["dimension_id"]}}
        elif oid in a2_ids:
            result[oid] = {"tier": "A2", "reason": {"xref_from": a2_ids[oid]}}
        elif source == "chapter" and payload.get("_chapter_id") in chapter_ids:
            result[oid] = {"tier": "B", "reason": {"chapter_id": payload.get("_chapter_id")}}
        elif source in ("dense", "bundle"):
            result[oid] = {"tier": "C", "reason": {"source": source}}
        else:
            result[oid] = {"tier": "D", "reason": {"source": source}}

    # أي anchor لم يظهر في hits أصلًا (حالة A3 حقنًا مباشرًا، مثال m30) يُضاف صراحة
    for oid, a in a3_by_id.items():
        if oid not in result:
            result[oid] = {"tier": "A3", "reason": {"rule_id": a["rule_id"], "dimension": a["dimension_id"],
                                                      "injected_directly": True}}
    for oid in a1_ids:
        if oid not in result:
            result[oid] = {"tier": "A1", "reason": {"source": "explicit_citation", "injected_directly": True}}

    return result
