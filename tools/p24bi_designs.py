#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.5 — Experiment B2-I: أربعة تصاميم دمج (Design 0 القديم المعطوب كضابط تحكُّم يثبت أن
العيّنة حقيقية، ثم Designs I/II/III المقترحة في المواصفة). كل تصميم يُعيد
(baseline_B: list[str], combined: list[str], provenance: dict, n_selector_calls: int)."""
import time
import sys

sys.path.insert(0, "/home/user/LegalMind/tools")
from p24bi_chap_selector import select_chapters, tok, CAP  # noqa: E402


def baseline_only(facts_text, chapter_index):
    """الأساس الحقيقي — تُستدعى مرة واحدة، ولا تتأثر بأي تصميم لاحق (تُستعمل كمرجع B الثابت
    لحساب معيار الصمود في كل التصاميم)."""
    qt = tok(facts_text)
    out, prov = select_chapters(qt, chapter_index)
    return out, prov


def design0_old_buggy(facts_text, scope_queries, chapter_index):
    """**التصميم القديم المعطوب (Arm B v1) — لغرض الضبط فقط، لإثبات أن العيّنة تُنتج انحدارًا
    حقيقيًا قابلًا للقياس قبل أي إصلاح.** يحقن رموز النطاق مباشرة في استعلام الفصل الواحد
    ويعيد تصنيف/ترتيب/سقف كل شيء دفعة واحدة — بالضبط الآلية الموثَّقة كسبب جذري للانحدار."""
    qt = tok(facts_text) | tok(" ".join(scope_queries))
    out, prov = select_chapters(qt, chapter_index)
    return out, prov, 1


def design1_independent_channel(facts_text, scope_queries, chapter_index):
    """Design I: قناة مستقلة تمامًا — نداءان منفصلان بسقف مستقل لكل منهما، يُوحَّدان بلا أي
    مساس بنتيجة الأساس."""
    b_out, b_prov = baseline_only(facts_text, chapter_index)
    if scope_queries:
        a_qt = tok(" ".join(scope_queries))
        a_out, a_prov = select_chapters(a_qt, chapter_index)
    else:
        a_out, a_prov = [], {}
    combined = list(dict.fromkeys(b_out + a_out))  # اتحاد يحافظ على ترتيب b أولًا
    prov = {a: {**p, "source": "dense"} for a, p in b_prov.items()}
    for a, p in a_prov.items():
        if a not in prov:
            prov[a] = {**p, "source": "backbone_dependency"}
    return b_out, combined, prov, 2


def design2_frozen_then_additive(facts_text, scope_queries, chapter_index):
    """Design II: تُجمَّد نتيجة الأساس أولًا (سقف كامل)، ثم تُبنى تعبئة إضافية على الفهرس
    **بعد استبعاد كل ما دخل الأساس فعليًا** (فلا يمكن للإضافة أن تكرر أو تزيح عضوًا من B)،
    بسقف إضافي أصغر مخصَّص للتكميل لا للمنافسة الكاملة."""
    b_out, b_prov = baseline_only(facts_text, chapter_index)
    b_set = set(b_out)
    if not scope_queries:
        return b_out, list(b_out), {a: {**p, "source": "dense"} for a, p in b_prov.items()}, 1

    remaining_index = []
    for g in chapter_index:
        rem_arts = [a for a in g["arts"] if a not in b_set]
        if rem_arts:
            remaining_index.append({**g, "arts": rem_arts})

    a_qt = tok(facts_text) | tok(" ".join(scope_queries))
    ADDITIVE_CAP = 10
    a_out, a_prov = select_chapters(a_qt, remaining_index, cap=ADDITIVE_CAP)
    combined = list(b_out) + [a for a in a_out if a not in b_set]
    prov = {a: {**p, "source": "dense"} for a, p in b_prov.items()}
    for a, p in a_prov.items():
        if a not in prov:
            prov[a] = {**p, "source": "backbone_dependency"}
    return b_out, combined, prov, 2


def design3_provenance_union(facts_text, scope_queries, chapter_index):
    """Design III: اتحاد واعٍ بالمصدر — تُحسَب نتيجة الأساس المجمَّدة، وتُحسَب **مستقلًا**
    نتيجة إعادة الحساب الكاملة بالنطاق المحقون (نفس آلية Design 0 حرفيًا في حسابها الداخلي)،
    ثم يُتَّحدان بلا أي تقليم لاحق على الاتحاد نفسه — فتبقى B محفوظة عضويًا في الاتحاد مهما
    أسقطتها إعادة الحساب الداخلية للنطاق المحقون بمفردها."""
    b_out, b_prov = baseline_only(facts_text, chapter_index)
    if not scope_queries:
        return b_out, list(b_out), {a: {**p, "source": "dense"} for a, p in b_prov.items()}, 1

    scope_recompute_out, scope_recompute_prov, _ = design0_old_buggy(facts_text, scope_queries, chapter_index)
    combined = list(dict.fromkeys(b_out + scope_recompute_out))
    prov = {a: {**p, "source": "dense"} for a, p in b_prov.items()}
    for a, p in scope_recompute_prov.items():
        if a not in prov:
            prov[a] = {**p, "source": "backbone_dependency"}
    return b_out, combined, prov, 2


DESIGNS = {
    "design0_old_buggy": design0_old_buggy,
    "design1_independent_channel": design1_independent_channel,
    "design2_frozen_then_additive": design2_frozen_then_additive,
    "design3_provenance_union": design3_provenance_union,
}


def run_design(name, facts_text, scope_queries, chapter_index):
    if name == "design0_old_buggy":
        # b_out يُحسَب هنا فقط كمرجع خارجي للمقارنة (Design 0 نفسه في الإنتاج لا يحسب B
        # إطلاقًا — هذا بالضبط جوهر عيبه) — فلا يدخل زمنه المقاس.
        b_out, _ = baseline_only(facts_text, chapter_index)
        t0 = time.perf_counter()
        combined, prov, n_calls = design0_old_buggy(facts_text, scope_queries, chapter_index)
        elapsed = time.perf_counter() - t0
    else:
        t0 = time.perf_counter()
        b_out, combined, prov, n_calls = DESIGNS[name](facts_text, scope_queries, chapter_index)
        elapsed = time.perf_counter() - t0
    return {"baseline": b_out, "combined": combined, "provenance": prov,
            "n_selector_calls": n_calls, "elapsed_s": elapsed}
