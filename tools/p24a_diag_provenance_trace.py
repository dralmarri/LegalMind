#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.4A-DIAG — Channel Preemption / Evidence Provenance Trace.

تشخيص سببي بحت — DIAGNOSTIC ONLY. صفر تعديل على: dynamic policy، caps، merge logic، ترتيب
القنوات، المرتِّب، الميزانية، Gold Set. لا بوابات/A3/BM25/Hybrid جديدة. لا إصلاح — هذه أداة
قياس فقط، تُبنى فوق نفس دوال الإنتاج الحقيقية غير المعدَّلة (عبر admin.app) تمامًا كما فعلت
p24_offline_pipeline.py، مع فارقين اثنين متعمَّدين لهذه الجولة التشخيصية تحديدًا:

1. **محاور مجمَّدة (Frozen Subqueries):** نداء Haiku واحد فقط لكل حالة، يُعاد استعماله حرفيًا
   للأساس (fixed_cap_policy) وArm A (dynamic_admission_policy_for_pipeline) معًا — يعزل
   المتغير الوحيد إلى سياسة القبول ذاتها، بعد أن كشف صاحب المشروع أن أداة القياس السابقة
   (p24_arm_a_experiment.py) كانت تستدعي Haiku مستقلًا لكل جانب (مقارنة غير مزدوجة الأزواج).
2. **سجل أحداث صريح (Event Trace):** بدل الاكتفاء بالنتيجة النهائية (`seen`)، تُسجَّل كل لمسة
   قناة لكل معرِّف عبر التسلسل: القناة، ترتيبها الزمني، الدرجة الخام، ما كان موجودًا قبلها
   (المصدر/الدرجة)، وإجراء الدمج الفعلي المأخوذ **من نفس سطور الكود القائم حرفيًا** (لا تخمينًا
   من أسماء الدوال) — إما `INSERT` (لم يكن موجودًا فأُضيف) أو `SKIP_EXISTING` (كان موجودًا
   فتُخُطِّي تمامًا كما يفعل `if oid in picked: continue` الحقيقي، بلا مقارنة درجات وبلا ترقية).

**عدسة العزل السببي (Oracle Provenance):** لكل معرِّف يظهر عليه نمط PREEMPTION_REGRESSION في
Arm A (أي دخل مبكرًا بقناة أضعف من قناة كانت ستمنحه الأساس)، يُعاد بناء `hits` بديلة تستبدل
مُدخَل ذلك المعرِّف فقط بمصدر/درجة الأساس الأقوى، ثم يُعاد تشغيل مرحلتَي الترتيب والميزانية
**بلا أي تغيير آخر** (نفس النص، نفس بقية hits) للتحقق: هل كان سينجو لو احتفظ بمصدره الأقوى؟
هذا اختبار مقابل للواقع تشخيصي بحت — لا يُطبَّق على أي مسار إنتاجي."""
import json
import sys
import time

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")

TARGET_CASES = {
    "gs-0017": [("legis-38-1980-m103",
                 "P2.3 MIXED_FAILURE — ليست هدف Arm A، لكن 3/3 نجاحات أساس تحوَّلت new_loss")],
    "gs-0009": [("regl-1-2016-m65", "حالة CRITICAL_TARGETS الرسمية لـm65 (هدف Arm A الأول)")],
    "gs-0014": [("legis-20-2015-m49", "حالة CRITICAL_TARGETS الرسمية لـm49 (هدف Arm A الثاني)")],
    "gs-0012": [("legis-68-1980-m36", "phase1 new_loss")],
    "gs-0013": [("legis-68-1980-m553", "phase1 new_loss")],
    "gs-0035": [("legis-6-2010-m50", "phase1 new_loss")],
    "gs-0036": [("regl-1-2016-m65", "phase1 new_loss — حالة مختلفة عن gs-0009 لنفس السلطة m65")],
    "gs-0038": [("jprin-101-1995-f1574-ce8b49f13f", "phase1 new_loss")],
}


def dump_merge_semantics_sources(app):
    """يطبع المصدر الحرفي لدوال الدمج التي لا نملك نصها المؤكَّد بعد (_sib_expand/_prin_xref) —
    بلا أي تخمين من الاسم، كما طلب صراحة."""
    import inspect
    print("=" * 70)
    print("MERGE_SEMANTICS_SOURCE_DUMP")
    print("=" * 70)
    for name in ("_sib_expand", "_prin_xref"):
        fn = getattr(app, name, None)
        print(f"\n--- {name} ---")
        if fn is None:
            print("(غير موجودة على admin.app)")
            continue
        try:
            print(inspect.getsource(fn))
        except Exception as e:
            print(f"(تعذّر استخراج المصدر: {e})")


def _channel_pass(name, candidates_with_scores, hits, picked, trace_ids, events, order_counter):
    """يطابق حرفيًا نمط `if oid in picked: continue` القائم في bundle/direct/chapter/lexical/
    xref — صفر تغيير في القرار نفسه، فقط تسجيل الحدث."""
    added = []
    for oid, sc in candidates_with_scores:
        if not oid:
            continue
        existing = None
        if oid in picked:
            for lb, s, p in hits:
                if p.get("object_id") == oid:
                    existing = (p.get("_source", "?"), s)
                    break
        if trace_ids is None or oid in trace_ids:
            order_counter[0] += 1
            events.setdefault(oid, []).append({
                "channel": name, "channel_order": order_counter[0], "raw_channel_score": sc,
                "existing_before": existing is not None,
                "existing_provenance_before": existing[0] if existing else None,
                "existing_score_before": existing[1] if existing else None,
                "merge_action": "SKIP_EXISTING" if existing is not None else "INSERT",
                "score_after": existing[1] if existing is not None else sc,
                "provenance_after": existing[0] if existing is not None else name,
            })
        if oid in picked:
            continue
        picked.add(oid)
        hits.append(("تشريع", sc, {"object_id": oid, "_source": name}))
        added.append(oid)
    return added


def build_context_traced(app, client, inp, facts, admission_policy, frozen_subqueries, trace_ids=None):
    """إعادة بناء offline مطابقة حرفيًا لتسلسل p24_offline_pipeline.build_context_offline
    (والدوال الحقيقية التي يستدعيها)، بفارقين وحيدين: محاور مجمَّدة، وسجل أحداث. trace_ids=None
    يعني: سجّل لكل معرِّف يمر بالتسلسل (لا تكلفة إضافية — عمليات قاموس بايثون فقط)."""
    events = {}
    order_counter = [0]

    query = inp.request_type + " - " + facts[:1500]
    if getattr(inp, "madhab", None):
        query += " (مذهب " + inp.madhab + ")"
    subqueries = frozen_subqueries

    vectors = app._draft_embed_multi([query] + subqueries)
    plans = [(vectors[0], [
        (list(app._kb.LEGISLATION_TYPES), 10, "تشريع"),
        (list(app._kb.PRINCIPLE_TYPES), 10, "مبدأ قضائي"),
        (list(app._kb.JUDGMENT_TYPES), 2, "حكم كامل"),
        (list(app._kb.TEMPLATE_TYPES), 2, "نموذج صياغة"),
    ])]
    for v in vectors[1:]:
        plans.append((v, [
            (list(app._kb.LEGISLATION_TYPES), 8, "تشريع"),
            (list(app._kb.PRINCIPLE_TYPES), 8, "مبدأ قضائي"),
        ]))

    best = {}
    for vec, buckets in plans:
        for types, lim, label in buckets:
            try:
                for h in app._draft_search(vec, types, lim):
                    p = h.get("payload") or {}
                    oid = p.get("object_id")
                    if not oid:
                        continue
                    sc = h.get("score", 0)
                    if oid not in best or sc > best[oid][1]:
                        best[oid] = (label, sc, p)
            except Exception:
                continue

    _prin_oids_precap = [oid for oid, (lb, _sc, _p) in best.items() if lb == "مبدأ قضائي"]
    if _prin_oids_precap:
        try:
            _precap_texts_cache = app._draft_fetch_texts(_prin_oids_precap)
        except Exception:
            _precap_texts_cache = {}
        _seen_fp = {}
        for oid in sorted(_prin_oids_precap, key=lambda o: -best[o][1]):
            _t = _precap_texts_cache.get(oid)
            _fp = app._draft_norm_ar((_t or {}).get("text") or "")[:120] if _t else None
            if _fp and _fp in _seen_fp:
                if trace_ids is None or oid in trace_ids:
                    events.setdefault(oid, []).append({
                        "channel": "p0_4_dedup", "merge_action": "DROP_DUP_PRINCIPLE",
                        "raw_channel_score": best[oid][1],
                    })
                del best[oid]
                continue
            if _fp:
                _seen_fp[_fp] = oid

    grouped = {}
    for oid, (label, sc, p) in best.items():
        grouped.setdefault(label, []).append((sc, label, p))

    admitted_by_label, cap_dropped_ids = admission_policy(grouped)
    hits = []
    for label, items in admitted_by_label.items():
        for sc, lb, p in items:
            hits.append((lb, sc, dict(p, _source="dense")))

    cap_dropped_set = set(cap_dropped_ids)
    for oid, (label, sc, p) in best.items():
        if trace_ids is None or oid in trace_ids:
            admitted = oid not in cap_dropped_set
            order_counter[0] += 1
            events.setdefault(oid, []).append({
                "channel": "cap_decision", "channel_order": order_counter[0],
                "raw_channel_score": sc, "existing_before": False,
                "existing_provenance_before": None, "existing_score_before": None,
                "merge_action": "INSERT" if admitted else "OTHER(cap_rejected)",
                "score_after": sc if admitted else None,
                "provenance_after": "dense" if admitted else None,
            })

    picked = {p.get("object_id") for _l, _s, p in hits}

    bundle_ids = list(app._draft_bundles(inp.request_type, facts, subqueries,
                                          getattr(inp, "madhab", None), getattr(inp, "branch", None)))
    bundle_scored = [(oid, 0.85 if i < 18 else 0.0) for i, oid in enumerate(bundle_ids)]
    _channel_pass("bundle", bundle_scored, hits, picked, trace_ids, events, order_counter)

    _docrefs = app._draft_doc_refs(client, []) if hasattr(app, "_draft_doc_refs") else []
    direct_ids = app._draft_direct_ids(inp.request_type, facts, subqueries) + (_docrefs or [])
    _channel_pass("direct", [(oid, 0.99) for oid in direct_ids], hits, picked, trace_ids, events, order_counter)

    chap_ids = app._draft_chap_ids(inp.request_type, facts, subqueries)
    _channel_pass("chapter", [(oid, 0.99) for oid in chap_ids], hits, picked, trace_ids, events, order_counter)

    lex_ids = list(app._draft_lexical(subqueries, facts))[:16]
    _channel_pass("lexical", [(oid, 0.0) for oid in lex_ids], hits, picked, trace_ids, events, order_counter)

    xref_candidates = []
    for oid in list(picked):
        for tgt in app._XREF.get(oid, ()):
            xref_candidates.append(tgt)
    xref_candidates = xref_candidates[:24]
    _channel_pass("xref", [(oid, 0.05) for oid in xref_candidates], hits, picked, trace_ids, events, order_counter)

    ids = {p.get("object_id") for _l, _s, p in hits if p.get("object_id")}
    texts = app._draft_fetch_texts(ids)
    _sib = app._sib_expand(hits, texts, picked) if hasattr(app, "_sib_expand") else []
    if _sib:
        texts.update(app._draft_fetch_texts(_sib))
        for s in _sib:
            if s in texts:
                if trace_ids is None or s in trace_ids:
                    order_counter[0] += 1
                    events.setdefault(s, []).append({
                        "channel": "sibling_xref", "channel_order": order_counter[0],
                        "raw_channel_score": 0.55, "existing_before": s in picked,
                        "merge_action": "APPEND_DUPLICATE_ENTRY" if s in picked else "INSERT",
                        "score_after": 0.55, "provenance_after": "sibling_xref",
                    })
                hits.append(("تشريع", 0.55, {"object_id": s, "_source": "sibling_xref"}))
    _pxr = app._prin_xref(hits, texts, picked) if hasattr(app, "_prin_xref") else []
    if _pxr:
        texts.update(app._draft_fetch_texts(_pxr))
        for s in _pxr:
            if s in texts:
                if trace_ids is None or s in trace_ids:
                    order_counter[0] += 1
                    events.setdefault(s, []).append({
                        "channel": "principle_xref", "channel_order": order_counter[0],
                        "raw_channel_score": 0.55, "existing_before": s in picked,
                        "merge_action": "APPEND_DUPLICATE_ENTRY" if s in picked else "INSERT",
                        "score_after": 0.55, "provenance_after": "principle_xref",
                    })
                hits.append(("تشريع", 0.55, {"object_id": s, "_source": "principle_xref"}))

    result = _finish_pipeline(app, query, hits, texts, trace_ids, events, order_counter)
    result["raw_hits"] = hits
    result["texts"] = texts
    result["query"] = query
    result["best"] = best
    result["cap_dropped_ids"] = cap_dropped_set
    return result


def _finish_pipeline(app, query, hits, texts, trace_ids, events, order_counter):
    """المرحلتان الأخيرتان (المرتِّب + الميزانية) — معزولتان في دالة مستقلة لإعادة استعمالهما
    حرفيًا على hits بديلة (oracle) بلا أي تغيير في منطقهما."""
    import p24_offline_pipeline as pipe

    rerank_ids = {p.get("object_id") for lb, sc, p in hits if lb in ("تشريع", "مبدأ قضائي") and sc < 0.99}
    rerank_input = [(o, texts[o]["text"]) for o in rerank_ids if o in texts]
    _rr = app._draft_rerank(query, rerank_input)

    hits2 = [(lb, (0.5 * sc + 0.5 * _rr[p.get("object_id")])
              if (_rr and sc < 0.99 and p.get("object_id") in _rr) else sc,
              dict(p, _pre_rerank_score=sc, _reranker_raw=(_rr.get(p.get("object_id")) if _rr else None)))
             for lb, sc, p in hits]

    ordered = sorted(hits2, key=lambda h: (pipe.PRIO.get(h[0], 9), -(h[1] or 0.0)))
    parts, seen, lbl_used = [], set(), {}
    for rank, (label, score, p) in enumerate(ordered):
        oid = p.get("object_id")
        if oid and (trace_ids is None or oid in trace_ids):
            events.setdefault(oid, []).append({
                "channel": "post_rerank", "pre_rerank_score": p.get("_pre_rerank_score"),
                "reranker_raw": p.get("_reranker_raw"),
                "final_score": round(float(score or 0), 4), "final_rank": rank,
            })
        if not oid or oid in seen or oid not in texts:
            continue
        t = texts[oid]
        _txt = t["text"] or ""
        _cap = pipe.BUDGET_CAPS.get(label, 2000)
        if len(_txt) > _cap:
            _tail = _txt.rstrip().rsplit("\n", 1)[-1]
            _keep = ("\n[…]\n" + _tail) if (("الطعن" in _tail or "جلسة" in _tail) and len(_tail) < 400) else ""
            _cut = _txt[:_cap]
            _dot = max(_cut.rfind("."), _cut.rfind("؟"), _cut.rfind("!"))
            if _dot > int(_cap * 0.6):
                _cut = _cut[:_dot + 1]
            _txt = _cut + ("" if _keep else "\n[…]") + _keep
        _pub = (t.get("publication") or "").replace('"', "'").strip()
        if not _pub and label in ("مبدأ قضائي", "حكم كامل"):
            _snd = (t["text"] or "").rstrip().rsplit("\n", 1)[-1].strip()
            if ("الطعن" in _snd or "جلسة" in _snd) and len(_snd) < 400:
                _pub = _snd.replace('"', "'")
        block = ('<مصدر نوع="' + label + '" معرف="' + oid + '" فرع="' + (t.get("branch") or "")
                 + '" موضوع="' + (t.get("topic") or "") + '" عنوان="' + (t.get("title") or "")
                 + ('" النشر="' + _pub if _pub else "") + '">\n' + _txt + "\n</مصدر>")
        if lbl_used.get(label, 0) + len(block) > pipe.LBL_BUDGET.get(label, 4000):
            if trace_ids is None or oid in trace_ids:
                events.setdefault(oid, []).append({"channel": "budget", "merge_action": "BUDGET_DROPPED"})
            continue
        seen.add(oid)
        lbl_used[label] = lbl_used.get(label, 0) + len(block)
        parts.append(block)
        if trace_ids is None or oid in trace_ids:
            events.setdefault(oid, []).append({"channel": "budget", "merge_action": "BUDGET_ADMITTED"})

    if trace_ids:
        for oid in trace_ids:
            events.setdefault(oid, []).append({"channel": "FINAL", "final_context": oid in seen})

    return {"seen": seen, "hits": hits2, "events": events, "rerank_pool_size": len(rerank_input),
            "final_context_count": len(parts)}


def classify_loss(target_oid, baseline_res, arma_res):
    """يصنّف الفقد وفق الفئات الأربع المطلوبة، من الأحداث الفعلية لا من افتراض مسبق."""
    b_events = baseline_res["events"].get(target_oid, [])
    a_events = arma_res["events"].get(target_oid, [])
    b_final = target_oid in baseline_res["seen"]
    a_final = target_oid in arma_res["seen"]

    if not (b_final and not a_final):
        return "NOT_A_LOSS", "الهدف لم يفقد فعليًا في هذه المقارنة المزدوجة (paired)"

    a_touch_events = [e for e in a_events if e.get("channel") not in ("post_rerank", "budget", "FINAL")]
    a_first_touch = min(a_touch_events, key=lambda e: e.get("channel_order", 10**9)) if a_touch_events else None
    a_skip_events = [e for e in a_events if e.get("merge_action") == "SKIP_EXISTING"]

    b_touch_events = [e for e in b_events if e.get("channel") not in ("post_rerank", "budget", "FINAL")]
    b_winning_touch = next((e for e in b_touch_events if e.get("merge_action") == "INSERT"), None)

    if a_first_touch and a_first_touch.get("channel") == "cap_decision" and a_skip_events:
        stronger = a_skip_events[0]
        return "PREEMPTION_REGRESSION", (
            f"دخل Arm A عبر dense (درجة خام {a_first_touch.get('raw_channel_score')}) "
            f"ثم تخطّت قناة أقوى ({stronger.get('channel')}) لاحقًا لأنه كان 'موجودًا سلفًا' "
            f"— لم تُرقَّ الدرجة/المصدر إطلاقًا (SKIP_EXISTING حرفيًا).")

    if a_final is False and (a_first_touch is None or a_touch_events == b_touch_events):
        return "COMPETITION_REGRESSION", (
            "نفس نمط الاكتشاف/القناة تقريبًا بين الأساس وArm A، لكن حوض الترتيب/الميزانية "
            "الأوسع في Arm A أخرج الهدف من المرحلة النهائية (رتبة/ميزانية).")

    return "OTHER", "لم تُطابق أي نمط من الأنماط الثلاثة المحدَّدة بوضوح — يحتاج فحصًا يدويًا للسجل الكامل."


def build_oracle_hits(arma_raw_hits, baseline_raw_hits, target_oid):
    """يستبدل مُدخَل target_oid في hits الخاصة بـArm A بمُدخَل الأساس (الأقوى)، ويُبقي كل شيء
    آخر كما هو حرفيًا — عدسة عزل سببي، لا رقعة."""
    oracle = [h for h in arma_raw_hits if h[2].get("object_id") != target_oid]
    baseline_entry = next((h for h in baseline_raw_hits if h[2].get("object_id") == target_oid), None)
    if baseline_entry:
        oracle.append(baseline_entry)
    return oracle, baseline_entry is not None


def main():
    import anthropic
    from admin import app

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)

    dump_merge_semantics_sources(app)

    import p24_offline_pipeline as pipe
    import p24_arm_a_dynamic_cap as arm_a
    from p23_stable_failure_matrix import load_gold_set
    gold = load_gold_set()

    report = {}
    for cid, targets in TARGET_CASES.items():
        case = gold[cid]
        target_oid = targets[0][0]
        note = targets[0][1]
        print(f"\n{'=' * 70}\n{cid} — target={target_oid}\nملاحظة: {note}\n{'=' * 70}", flush=True)

        inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
        facts = case["question"]

        t0 = time.monotonic()
        frozen_subqueries = app._draft_subqueries(client, case["request_type"], facts,
                                                    getattr(inp, "madhab", None), [])
        print(f"  frozen_subqueries ({time.monotonic()-t0:.1f}s): {frozen_subqueries}", flush=True)

        baseline_res = build_context_traced(app, client, inp, facts, pipe.fixed_cap_policy,
                                             frozen_subqueries, trace_ids=None)
        print(f"  [baseline] final_context={target_oid in baseline_res['seen']} "
              f"pool={baseline_res['rerank_pool_size']} ctx_n={baseline_res['final_context_count']}", flush=True)
        for e in baseline_res["events"].get(target_oid, []):
            print(f"    [baseline][{target_oid}] {e}", flush=True)

        arma_res = build_context_traced(app, client, inp, facts, arm_a.dynamic_admission_policy_for_pipeline,
                                         frozen_subqueries, trace_ids=None)
        print(f"  [arm_a]    final_context={target_oid in arma_res['seen']} "
              f"pool={arma_res['rerank_pool_size']} ctx_n={arma_res['final_context_count']}", flush=True)
        for e in arma_res["events"].get(target_oid, []):
            print(f"    [arm_a][{target_oid}] {e}", flush=True)

        verdict, reason = classify_loss(target_oid, baseline_res, arma_res)
        print(f"  CLASSIFICATION: {verdict} — {reason}", flush=True)

        oracle_result = None
        if verdict == "PREEMPTION_REGRESSION":
            oracle_hits, had_baseline_entry = build_oracle_hits(
                arma_res["raw_hits"], baseline_res["raw_hits"], target_oid)
            if had_baseline_entry:
                oracle_run = _finish_pipeline(app, arma_res["query"], oracle_hits, arma_res["texts"],
                                               {target_oid}, {}, [0])
                oracle_result = {
                    "target_survives_with_baseline_provenance": target_oid in oracle_run["seen"],
                    "oracle_final_context_count": oracle_run["final_context_count"],
                }
                print(f"  ORACLE_PROVENANCE: يحل مكانه مصدر الأساس -> "
                      f"final_context={oracle_result['target_survives_with_baseline_provenance']} "
                      f"(ctx_n={oracle_result['oracle_final_context_count']} مقابل arm_a={arma_res['final_context_count']} "
                      f"وbaseline={baseline_res['final_context_count']})", flush=True)
            else:
                print("  ORACLE_PROVENANCE: تعذّر — لم يظهر الهدف إطلاقًا في raw_hits الخاصة بالأساس.", flush=True)

        # قسم 7 — تفسير context_count_delta: باستعمال المصدر النهائي المسجَّل لكل معرِّف مشترك
        b_seen, a_seen = baseline_res["seen"], arma_res["seen"]
        baseline_only = sorted(b_seen - a_seen)
        armA_only = sorted(a_seen - b_seen)
        baseline_only_status = {}
        for oid in baseline_only:
            if oid in arma_res["cap_dropped_ids"]:
                status = "cap"
            elif oid not in arma_res["best"] and not any(
                    p.get("object_id") == oid for _l, _s, p in arma_res["raw_hits"]):
                status = "not_discovered"
            else:
                a_src = next((p.get("_source") for _l, _s, p in arma_res["raw_hits"] if p.get("object_id") == oid), None)
                b_src = next((p.get("_source") for _l, _s, p in baseline_res["raw_hits"] if p.get("object_id") == oid), None)
                if a_src == "dense" and b_src and b_src != "dense":
                    status = "preempted"
                else:
                    status = "budget_or_rerank"
            baseline_only_status[oid] = status
        print(f"  context_delta_explain: baseline_only={len(baseline_only)} armA_only={len(armA_only)} "
              f"intersection={len(b_seen & a_seen)}", flush=True)
        print(f"    baseline_only_status: {baseline_only_status}", flush=True)

        report[cid] = {
            "target_oid": target_oid, "note": note,
            "baseline_final": target_oid in baseline_res["seen"],
            "arma_final": target_oid in arma_res["seen"],
            "baseline_events": baseline_res["events"].get(target_oid, []),
            "arma_events": arma_res["events"].get(target_oid, []),
            "classification": {"verdict": verdict, "reason": reason},
            "oracle": oracle_result,
            "context_delta": {
                "baseline_context_count": baseline_res["final_context_count"],
                "arma_context_count": arma_res["final_context_count"],
                "baseline_only_ids": baseline_only, "armA_only_ids": armA_only,
                "baseline_only_status": baseline_only_status,
            },
        }

    print()
    print("=" * 70)
    print("P24A_DIAG_RAW_RESULTS")
    print("=" * 70)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print("\nP24A_DIAG_DONE")


if __name__ == "__main__":
    main()
