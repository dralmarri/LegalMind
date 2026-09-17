#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.4B — PHASE 3: Paired Frozen Stability & Causal Confirmation (gs-0002 ×5) + replay
determinism check (gs-0011/gs-0013/gs-0017/gs-0033، recognize() فقط، بلا تشغيل باهظ).

**صفر تعديل على Arm B المجمَّدة (بصمة c5153b06...).** هذه أداة قياس بحتة تعيد بناء تسلسل
`_draft_chap_ids` **حرفيًا** (نُسخ من `inspect.getsource` الحقيقي المؤكَّد، لا تخمينًا) مع
تعليمات إضافية فقط (لا تغيير منطقي): تسجيل ترتيب المجموعات بعد الفرز، موضع كل معرِّف مستهدَف
داخل مجموعته قبل/بعد القص الثاني، ونقطة القطع الفعلية عند بلوغ السقف العام (30)."""
import json
import re
import sys
import time

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")

TARGET_IDS = ["legis-68-1980-m510", "legis-68-1980-m511",
              "legis-68-1980-m512", "legis-68-1980-m513"]

# نفس _QSTOP الحرفي من المصدر المؤكَّد
_QSTOP = {"علي", "الي", "عن", "في", "من", "ما", "لا", "او", "اذا", "كان", "كانت",
          "كل", "بين", "بعد", "قبل", "غير", "ذلك", "هذا", "هذه", "وهو", "وهي", "حتي",
          "لدي", "له", "لها", "منه", "عليه", "فيه", "وقد", "ثم", "بها", "به", "انه"}

REPLAY_CASES = ["gs-0011", "gs-0013", "gs-0017", "gs-0033"]
# القيم المسجَّلة فعليًا في PHASE 2 (من نتائج حية سابقة) — للمقارنة الحتمية هنا فقط، لا تُشتق
# من أي شيء جديد.
PHASE2_RECORDED = {
    "gs-0011": {"concepts": sorted(["LINEAGE_ESTABLISHMENT", "MARITAL_STATUS_DENIAL"]),
                "deps": sorted(["LINEAGE_COMMITTEE_MANDATORY_REVIEW",
                                 "MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"])},
    "gs-0013": {"concepts": sorted(["CHEQUE_PAYMENT_CLAIM"]),
                "deps": sorted(["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"])},
    "gs-0017": {"concepts": sorted(["JUDICIAL_DISQUALIFICATION"]),
                "deps": sorted(["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"])},
    "gs-0033": {"concepts": sorted(["LINEAGE_ESTABLISHMENT"]),
                "deps": sorted(["LINEAGE_COMMITTEE_MANDATORY_REVIEW"])},
}


def draft_chap_ids_traced(app, request_type, facts, subqueries, target_ids):
    """إعادة بناء حرفية للتسلسل الحقيقي في _draft_chap_ids (مؤكَّد بـinspect.getsource حيًّا)
    حتى نقطة السقف العام (30) — بلا تطبيق _GATES عمدًا (m510-513 ليست ضمن أي بوابة مُرمَّزة،
    مؤكَّد من نفس المصدر) فتبقى الأداة مركَّزة على آلية الفصول العامة تحديدًا."""
    _draft_norm_ar = app._draft_norm_ar
    _chap_tok = app._chap_tok
    _chap_skel = app._chap_skel
    _chap_stem = app._chap_stem
    _CHAP_SYN = app._CHAP_SYN
    _CHAP_WEAK = app._CHAP_WEAK
    _draft_chap_index = app._draft_chap_index

    blob = _draft_norm_ar((request_type or "") + " " + (facts or "") + " " + " ".join(subqueries or []))
    btoks, bskels, bstems = set(), set(), set()
    for w in re.split(r"[^0-9a-zء-ي]+", blob):
        w = _chap_tok(w)
        if len(w) >= 3 and not w.isdigit() and w not in _QSTOP:
            btoks.add(w)
            bskels.add(_chap_skel(w))
            bstems.add(_chap_stem(w))
            if w.startswith("ت") and len(w) >= 5:
                bskels.add(_chap_skel(w[1:]))
    for _base, _syns in _CHAP_SYN.items():
        _fam = (_base,) + tuple(_syns)
        if any(x in btoks or _chap_stem(x) in bstems for x in _fam):
            for x in _fam:
                btoks.add(x)
                bskels.add(_chap_skel(x))
                bstems.add(_chap_stem(x))

    def _hit(t, sub_ok=True):
        if t in btoks or _chap_skel(t) in bskels or _chap_stem(t) in bstems:
            return True
        if t.startswith("ت") and len(t) >= 5 and _chap_skel(t[1:]) in bskels:
            return True
        return sub_ok and any(t in k or k in t for k in btoks)

    scored = []
    for toks, rare, mid, arts in _draft_chap_index():
        hits = [t for t in toks if _hit(t, sub_ok=len(toks) > 1)]
        strong = [t for t in hits if t not in _CHAP_WEAK]
        if not strong:
            continue
        m, n = len(hits), len(toks)
        full = (m == n) and (n >= 2 or (n == 1 and toks[0] in mid))
        partial = (m >= 2 and m * 2 >= n and any(t in rare for t in strong))
        hitset = set(hits)
        fullw = (m < n and all((t in hitset) or (t in _CHAP_WEAK) for t in toks)
                 and any(t in rare or t in mid for t in strong))
        if full or partial or fullw:
            scored.append((len(strong), m / n, toks, arts))

    scored.sort(reverse=True, key=lambda x: (x[0], x[1]))

    trimmed = []
    for _s, _r, toks, arts in scored:
        total_before_2nd_trim = len(arts)
        small = len(arts) <= 6
        arts2 = list(arts)
        if len(arts2) > 8:
            arts2 = arts2[:6] + arts2[-2:]
        trimmed.append({"strong": _s, "ratio": round(_r, 3), "toks": toks,
                         "arts_before_2nd_trim": list(arts), "total_before_2nd_trim": total_before_2nd_trim,
                         "arts_after_2nd_trim": arts2, "small": small})

    out = []
    fill_log = []
    for gi, rec in enumerate(trimmed):
        pool = rec["arts_after_2nd_trim"] if rec["small"] else rec["arts_after_2nd_trim"][:3]
        added = [oid for oid in pool if oid not in out and len(out) < 30]
        out.extend(added)
        if added:
            fill_log.append({"phase": "pass1", "group_idx": gi, "toks": rec["toks"], "added": added})
    for gi, rec in enumerate(trimmed):
        added = [oid for oid in rec["arts_after_2nd_trim"] if oid not in out and len(out) < 30]
        out.extend(added)
        if added:
            fill_log.append({"phase": "pass2", "group_idx": gi, "toks": rec["toks"], "added": added})

    target_trace = {}
    for tid in target_ids:
        info = {"in_final_out": tid in out, "position_in_final_out": out.index(tid) if tid in out else None,
                "group_idx": None, "group_toks": None,
                "position_in_group_before_2nd_trim": None, "position_in_group_after_2nd_trim": None,
                "in_pass1_slice": None, "group_small": None, "group_total_before_2nd_trim": None,
                "total_groups_matched": len(trimmed)}
        for gi, rec in enumerate(trimmed):
            if tid in rec["arts_before_2nd_trim"]:
                info["group_idx"] = gi
                info["group_toks"] = rec["toks"]
                info["group_small"] = rec["small"]
                info["group_total_before_2nd_trim"] = rec["total_before_2nd_trim"]
                info["position_in_group_before_2nd_trim"] = rec["arts_before_2nd_trim"].index(tid)
                pool = rec["arts_after_2nd_trim"] if rec["small"] else rec["arts_after_2nd_trim"][:3]
                info["in_pass1_slice"] = tid in pool
                if tid in rec["arts_after_2nd_trim"]:
                    info["position_in_group_after_2nd_trim"] = rec["arts_after_2nd_trim"].index(tid)
        target_trace[tid] = info

    return {"out": out, "out_len": len(out), "n_groups_matched": len(trimmed),
            "target_trace": target_trace, "fill_log": fill_log}


def run_gs0002_5x(app, client, pipe, backbone, gold):
    import p24_offline_pipeline as offline_pipe
    from p24a_diag_provenance_trace import build_context_traced

    case = gold["gs-0002"]
    inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
    facts = case["question"]

    t0 = time.monotonic()
    frozen_axes = app._draft_subqueries(client, case["request_type"], facts, None, [])
    print(f"frozen_axes ({time.monotonic()-t0:.1f}s): {frozen_axes}", flush=True)

    runs = []
    concept_dep_scope_5x = []
    for i in range(5):
        rec = backbone.recognize(facts)
        concept_dep_scope_5x.append({
            "concepts": sorted(rec["concepts_triggered"]),
            "deps": sorted(rec["dependencies_triggered"]),
            "scope": sorted(rec["scope_queries"]),
        })
        arm_b_subqueries = frozen_axes + rec["scope_queries"]

        chap_baseline = draft_chap_ids_traced(app, case["request_type"], facts, frozen_axes, TARGET_IDS)
        chap_armb = draft_chap_ids_traced(app, case["request_type"], facts, arm_b_subqueries, TARGET_IDS)

        full_baseline = build_context_traced(app, client, inp, facts, offline_pipe.fixed_cap_policy,
                                              frozen_axes, trace_ids=set(TARGET_IDS))
        full_armb = build_context_traced(app, client, inp, facts, offline_pipe.fixed_cap_policy,
                                          arm_b_subqueries, trace_ids=set(TARGET_IDS))

        run_rec = {"run": i + 1, "chap_baseline": chap_baseline, "chap_armb": chap_armb,
                   "full_baseline_seen": {t: (t in full_baseline["seen"]) for t in TARGET_IDS},
                   "full_armb_seen": {t: (t in full_armb["seen"]) for t in TARGET_IDS},
                   "full_baseline_events": {t: full_baseline["events"].get(t, []) for t in TARGET_IDS},
                   "full_armb_events": {t: full_armb["events"].get(t, []) for t in TARGET_IDS}}
        runs.append(run_rec)

        b_set, a_set = set(chap_baseline["out"]), set(chap_armb["out"])
        inter = b_set & a_set
        jaccard = len(inter) / len(b_set | a_set) if (b_set | a_set) else None
        removed = b_set - a_set
        print(f"[run {i+1}] concepts={concept_dep_scope_5x[-1]['concepts']} "
              f"m510-513_baseline_chap={[t in chap_baseline['out'] for t in TARGET_IDS]} "
              f"m510-513_armb_chap={[t in chap_armb['out'] for t in TARGET_IDS]} "
              f"m510-513_baseline_final={[full_baseline['seen'].__contains__(t) for t in TARGET_IDS]} "
              f"m510-513_armb_final={[full_armb['seen'].__contains__(t) for t in TARGET_IDS]} "
              f"jaccard={jaccard:.3f} baseline_only_removed={sorted(removed)}", flush=True)

    return {"frozen_axes": frozen_axes, "concept_dep_scope_5x": concept_dep_scope_5x, "runs": runs}


def run_replay_checks(app, client, backbone, gold):
    out = {}
    for cid in REPLAY_CASES:
        case = gold[cid]
        rec = backbone.recognize(case["question"])
        actual = {"concepts": sorted(rec["concepts_triggered"]), "deps": sorted(rec["dependencies_triggered"])}
        expected = PHASE2_RECORDED[cid]
        match = actual["concepts"] == expected["concepts"] and actual["deps"] == expected["deps"]
        out[cid] = {"expected": expected, "actual": actual, "match": match}
        print(f"[replay] {cid}: match={match} expected={expected} actual={actual}", flush=True)
    return out


def main():
    import anthropic
    from admin import app
    import p24b_concept_backbone as backbone
    from p23_stable_failure_matrix import load_gold_set

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    gold = load_gold_set()

    print("=== REPLAY DETERMINISM CHECK (gs-0011/13/17/33 — recognize() فقط) ===", flush=True)
    replay = run_replay_checks(app, client, backbone, gold)

    print("\n=== gs-0002 x5 PAIRED FROZEN STABILITY ===", flush=True)
    import p24_offline_pipeline as pipe
    gs0002 = run_gs0002_5x(app, client, pipe, backbone, gold)

    result = {"replay": replay, "gs0002": gs0002}
    print()
    print("=" * 70)
    print("P24B_PHASE3_RAW_RESULTS")
    print("=" * 70)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print("\nP24B_PHASE3_DONE")


if __name__ == "__main__":
    main()
