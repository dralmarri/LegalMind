#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.4 — البنية التحتية المشتركة: إعادة بناء offline أمينة لـ`_draft_build_context` الحقيقية
(نُقلت حرفيًا من مصدرها المؤكَّد حيًّا في P2.3، `dump_source.py`، 2026-09-16) بفارق واحد
متعمَّد: **خطوة السقف الثابت (`caps_n`) وحدها** استُبدلت بدالة سياسة قبول قابلة للتوصيل
(`admission_policy_fn`). كل شيء آخر — التضمين، القنوات السبع (bundle/direct/chapter/lexical/
xref/sibling/prin_xref)، المرتِّب الحقيقي `_draft_rerank`، حلقة الميزانية — **الدوال الحقيقية
نفسها بلا أي تغيير**، مستوردة من `admin.app` واستُدعيت كما تُستدعى في الإنتاج تمامًا.

**لماذا إعادة بناء لا تصحيح مؤقت (monkey-patch):** خطوة السقف مضمَّنة (inline) داخل الدالة
الحقيقية — لا دالة منفصلة قابلة للتصحيح المؤقت عليها (مؤكَّد من قراءة المصدر الكامل). الحل
الوحيد الأمين هو نسخ التسلسل حرفيًا مع إبقاء نقطة تدخل واحدة صريحة.

**سياسة القبول (`AdmissionPolicy`):** دالة تأخذ `grouped` (قاموس {label: [(score, label,
payload), ...]}) وتُعيد نفس البنية *مُصفَّاة* (المقبول فقط) — بلا أي اطلاع على `case_id` أو
`must_find` أو `required_dimensions` أو معرِّفات الكائنات المستهدَفة؛ فقط خصائص إحصائية من
`grouped` نفسه (كثافة، توزيع درجات، فجوة القطع، تنوع topic/subtopic، تنوع القانون المصدر).

**الأساس (baseline)** = `fixed_cap_policy` (تكرار حرفي لسلوك الإنتاج: `caps_n` ثابتة لكل
تسمية) — يُستعمَل للتحقق من التطابق التام مع الإنتاج الحقيقي قبل أي تجربة (بوابة صحة إلزامية)."""
import time

CAPS_N_PRODUCTION = {"تشريع": 20, "مبدأ قضائي": 32, "حكم كامل": 3, "نموذج صياغة": 3}
LBL_BUDGET = {"تشريع": 48000, "مبدأ قضائي": 24000, "حكم كامل": 8000, "نموذج صياغة": 5000}
BUDGET_CAPS = {"تشريع": 2200, "مبدأ قضائي": 1400, "حكم كامل": 3500, "نموذج صياغة": 3500}
PRIO = {"تشريع": 0, "مبدأ قضائي": 1, "حكم كامل": 2, "نموذج صياغة": 3}


def fixed_cap_policy(grouped, caps_n=None):
    """الأساس — يكرر سلوك الإنتاج الحقيقي حرفيًا (caps_n ثابتة لكل تسمية)."""
    caps_n = caps_n or CAPS_N_PRODUCTION
    admitted, cut_ids = {}, []
    for label, items in grouped.items():
        items_sorted = sorted(items, reverse=True, key=lambda x: x[0])
        n = caps_n.get(label, 20)
        admitted[label] = items_sorted[:n]
        cut_ids += [p.get("object_id") for _sc, _lb, p in items_sorted[n:]]
    return admitted, cut_ids


def build_context_offline(app, client, inp, facts_ret, admission_policy=fixed_cap_policy,
                           policy_kwargs=None):
    """نسخة offline من _draft_build_context — الدوال الحقيقية نفسها، نقطة تدخل واحدة (السقف).
    تُعيد نفس بنية ctx الإنتاجية + حقول تشخيصية إضافية (زمن كل مرحلة، حجم حوض المرتِّب)."""
    policy_kwargs = policy_kwargs or {}
    timings = {}

    t0 = time.monotonic()
    query = inp.request_type + " - " + facts_ret[:1500]
    if getattr(inp, "madhab", None):
        query += " (مذهب " + inp.madhab + ")"
    _early_media = []
    for _a in ([inp.attachment] if getattr(inp, "attachment", None) else []) + list(getattr(inp, "attachments", None) or []):
        _k = getattr(_a, "kind", None) or (isinstance(_a, dict) and _a.get("kind"))
        _d = getattr(_a, "data", None) or (isinstance(_a, dict) and _a.get("data"))
        if _k in ("image", "pdf") and _d:
            _early_media.append(_a)
    subqueries = app._draft_subqueries(client, inp.request_type, facts_ret, getattr(inp, "madhab", None), _early_media)
    timings["subqueries_s"] = time.monotonic() - t0

    t0 = time.monotonic()
    vectors = app._draft_embed_multi([query] + subqueries)
    timings["embed_s"] = time.monotonic() - t0

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

    t0 = time.monotonic()
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
    timings["dense_search_s"] = time.monotonic() - t0
    dense_union_count = len(best)

    # P0-4: إزالة تكرار المبادئ قبل السقف (حرفيًا كما في الإنتاج)
    _prin_oids_precap = [oid for oid, (lb, _sc, _p) in best.items() if lb == "مبدأ قضائي"]
    _dup_dropped_ids = []
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
                _dup_dropped_ids.append(oid)
                del best[oid]
                continue
            if _fp:
                _seen_fp[_fp] = oid

    # === نقطة التدخل الوحيدة: السقف قابل للاستبدال بسياسة قبول ===
    grouped = {}
    for oid, (label, sc, p) in best.items():
        grouped.setdefault(label, []).append((sc, label, p))
    pre_cap_by_label = {lb: len(v) for lb, v in grouped.items()}

    admitted_by_label, cap_dropped_ids = admission_policy(grouped, **policy_kwargs)
    hits = []
    for label, items in admitted_by_label.items():
        for sc, lb, p in items:
            hits.append((lb, sc, dict(p, _source="dense")))
    # ================================================================

    picked = {p.get("object_id") for _l, _s, p in hits}
    bundle_added = []
    for _bi, oid in enumerate(app._draft_bundles(inp.request_type, facts_ret, subqueries, getattr(inp, "madhab", None), getattr(inp, "branch", None))):
        if oid in picked:
            continue
        picked.add(oid)
        _bscore = 0.85 if _bi < 18 else 0.0
        hits.append(("تشريع", _bscore, {"object_id": oid, "_source": "bundle"}))
        bundle_added.append(oid)

    direct_added = []
    _docrefs = app._draft_doc_refs(client, _early_media) if hasattr(app, "_draft_doc_refs") else []
    for oid in (app._draft_direct_ids(inp.request_type, facts_ret, subqueries) + (_docrefs or [])):
        if oid in picked:
            continue
        picked.add(oid)
        hits.append(("تشريع", 0.99, {"object_id": oid, "_source": "direct"}))
        direct_added.append(oid)

    chap_added = []
    for oid in app._draft_chap_ids(inp.request_type, facts_ret, subqueries):
        if oid in picked:
            continue
        picked.add(oid)
        hits.append(("تشريع", 0.99, {"object_id": oid, "_source": "chapter"}))
        chap_added.append(oid)

    lex_added = []
    for oid in app._draft_lexical(subqueries, facts_ret):
        if oid in picked or len(lex_added) >= 16:
            continue
        picked.add(oid)
        hits.append(("تشريع", 0.0, {"object_id": oid, "_source": "lexical"}))
        lex_added.append(oid)

    xref_added = []
    for oid in list(picked):
        for tgt in app._XREF.get(oid, ()):
            if tgt in picked or len(xref_added) >= 24:
                continue
            picked.add(tgt)
            hits.append(("تشريع", 0.05, {"object_id": tgt, "_source": "xref"}))
            xref_added.append(tgt)

    ids = {p.get("object_id") for _l, _s, p in hits if p.get("object_id")}
    texts = app._draft_fetch_texts(ids)
    _sib = app._sib_expand(hits, texts, picked) if hasattr(app, "_sib_expand") else []
    if _sib:
        texts.update(app._draft_fetch_texts(_sib))
        hits += [("تشريع", 0.55, {"object_id": s, "_source": "sibling_xref"}) for s in _sib if s in texts]
    _pxr = app._prin_xref(hits, texts, picked) if hasattr(app, "_prin_xref") else []
    if _pxr:
        texts.update(app._draft_fetch_texts(_pxr))
        hits += [("تشريع", 0.55, {"object_id": s, "_source": "principle_xref"}) for s in _pxr if s in texts]

    t0 = time.monotonic()
    rerank_ids = {p.get("object_id") for lb, sc, p in hits if lb in ("تشريع", "مبدأ قضائي") and sc < 0.99}
    rerank_input = [(o, texts[o]["text"]) for o in rerank_ids if o in texts]
    _rr = app._draft_rerank(query, rerank_input)
    timings["rerank_s"] = time.monotonic() - t0
    reranker_pool_size = len(rerank_input)

    hits = [(lb, (0.5 * sc + 0.5 * _rr[p.get("object_id")])
             if (_rr and sc < 0.99 and p.get("object_id") in _rr) else sc,
             dict(p, _pre_rerank_score=sc, _reranker_raw=(_rr.get(p.get("object_id")) if _rr else None)))
            for lb, sc, p in hits]

    ordered = sorted(hits, key=lambda h: (PRIO.get(h[0], 9), -(h[1] or 0.0)))
    parts, seen, lbl_used = [], set(), {}
    budget_dropped = []
    for label, score, p in ordered:
        oid = p.get("object_id")
        if not oid or oid in seen or oid not in texts:
            continue
        t = texts[oid]
        _txt = t["text"] or ""
        _cap = BUDGET_CAPS.get(label, 2000)
        if len(_txt) > _cap:
            _txt = _txt[:_cap]
        block = _txt
        if lbl_used.get(label, 0) + len(block) > LBL_BUDGET.get(label, 4000):
            budget_dropped.append({"id": oid, "type": label, "score": round(float(score or 0), 4)})
            continue
        seen.add(oid)
        lbl_used[label] = lbl_used.get(label, 0) + len(block)
        parts.append(block)

    provenance = []
    for rank, (lb, sc, p) in enumerate(ordered):
        oid = p.get("object_id")
        if not oid:
            continue
        provenance.append({
            "object_id": oid, "object_type": lb, "source": p.get("_source", "dense"),
            "pre_rerank_score": p.get("_pre_rerank_score"), "reranker_raw": p.get("_reranker_raw"),
            "final_score": round(float(sc or 0), 4), "rank": rank, "admitted": oid in seen,
        })

    return {
        "context": "\n\n".join(parts), "seen": seen, "hits": hits, "subqueries": subqueries,
        "provenance": provenance, "budget_dropped_full": budget_dropped,
        "attr": {
            "dense_union_count": dense_union_count, "pre_cap_by_label": pre_cap_by_label,
            "cap_dropped_ids": cap_dropped_ids, "principle_precap_dup_dropped_ids": _dup_dropped_ids,
            "bundle_added": bundle_added, "direct_added": direct_added, "chap_added": chap_added,
            "lexical_added": lex_added, "xref_added": xref_added,
            "reranker_pool_size": reranker_pool_size, "final_context_count": len(parts),
        },
        "timings": timings,
    }
