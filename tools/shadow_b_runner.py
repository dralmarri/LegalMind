#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.1 — Shadow B (Full Retrieval Shadow) Offline Replay Runner، طبقًا لـ
docs/p2_1_shadow_mode_design.md §1/§5 (v2). بخلاف Shadow A (تقرأ hits الحقيقية بلا أي بحث
جديد)، Shadow B تُجري بحثًا حقيقيًا إضافيًا عند الحاجة فقط: أي anchor A3 فعَّلته Backbone
(القاعدة أُطلقت لهذه الحالة) لكنه **غائب كليًا** عن hits الحقيقية — حالة m30 المرجعية —
تُعالَج بمسارين مفصولين صراحةً بأمر المالك:

1. **`direct_id_fetch`** (حتمي، لا بحث): المعرِّف معروف مسبقًا من القاعدة المُقنَّنة نفسها
   (`shadow_candidate_rules.json`)، فيُجلَب نصه مباشرة بـ`_draft_fetch_texts({oid})` — قراءة
   بالمعرِّف من PostgreSQL، **ليست نجاح استرجاع/بحث بأي معنى**.
2. **`broad_channel_search`** (بحث حقيقي مستقل، اختياري، لغرض القياس فقط): يُشغِّل كل قنوات
   الاسترجاع الحقيقية (كثيف/حزم/محلّ/فصول/معجمي/xref) بلا سقوف — يُستعمَل حصرًا لملء
   `also_discovered_by` (هل الكائن قابل للاكتشاف عبر بحث حقيقي مستقل، بصرف النظر عن جلبه
   المباشر؟) — **لا يُغذّي القبول أبدًا**؛ القبول يعتمد فقط على direct_id_fetch متى لزم.

**قيود التجميد (بأمر المالك 2026-09-14/15، سارية طوال هذا القياس):** لا قواعد A3 جديدة، لا
إصلاح لأي فشل Gold Set أثناء القياس، لا توسعة لقواعد الشيك (m550/m553/m532)، ولا أي تفعيل
إنتاجي أو توسعة قواعد مبنية على نتائج هذا القياس. Offline فقط — Gold Set أو حركة مرور
تاريخية معاد تشغيلها، بلا مساس بـadmin/app.py الحي (عزل فيزيائي تام، مؤكَّد بـ
import_isolation_test.py)."""
import collections
import json
import sys

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")


def load_gold_set(path="/opt/LegalMind/tools/retrieval_gold_set.json"):
    return json.load(open(path, encoding="utf-8"))["cases"]


def broad_channel_search(app, kb_types_mod, request_type, facts, subqueries):
    """يُشغّل كل قنوات الاسترجاع الحقيقية بلا caps_n/ميزانية، ويُعيد {object_id: set(channels)}.
    مطابق لمنطق tools/battery_run.py الحي (retrieve()، تحقُّق حي 2026-09-15) في القنوات
    الأساسية، مع فصل كل قناة باسمها بدل دمجها — **قياس/تشخيص فقط، لا يُستعمل لبناء السياق**."""
    found = collections.defaultdict(set)
    query = request_type + " - " + facts[:1500]
    vectors = app._draft_embed_multi([query] + subqueries)
    plans = [(vectors[0], [(list(kb_types_mod.LEGISLATION_TYPES), 10),
                            (list(kb_types_mod.PRINCIPLE_TYPES), 10),
                            (list(kb_types_mod.JUDGMENT_TYPES), 2),
                            (list(kb_types_mod.TEMPLATE_TYPES), 2)])]
    for v in vectors[1:]:
        plans.append((v, [(list(kb_types_mod.LEGISLATION_TYPES), 8),
                           (list(kb_types_mod.PRINCIPLE_TYPES), 8)]))
    for vec, buckets in plans:
        for types, lim in buckets:
            try:
                for h in app._draft_search(vec, types, lim):
                    oid = (h.get("payload") or {}).get("object_id")
                    if oid:
                        found[oid].add("dense")
            except Exception:
                pass
    try:
        for oid in app._draft_bundles(request_type, facts, subqueries, None, None):
            found[oid].add("bundle")
    except Exception:
        pass
    try:
        for oid in app._draft_direct_ids(request_type, facts, subqueries):
            found[oid].add("direct")
    except Exception:
        pass
    try:
        for oid in app._draft_chap_ids(request_type, facts, subqueries):
            found[oid].add("chapter")
    except Exception:
        pass
    try:
        for oid in app._draft_lexical(subqueries, facts):
            found[oid].add("lexical")
    except Exception:
        pass
    base_ids = list(found.keys())
    xn = 0
    for oid in base_ids:
        if xn >= 24:
            break
        for tgt in app._XREF.get(oid, ()):
            if tgt not in found and xn < 24:
                found[tgt].add("xref")
                xn += 1
    return found


def run_one(app, client, case, backbone_mod, ec_mod, ap_mod, cc_mod, kb_types_mod):
    inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
    ctx = app._draft_build_context(client, inp, case["question"])  # الإنتاج الحقيقي، بلا تعديل

    current_final = set(ctx["seen"])
    hits = list(ctx["hits"])
    # مصدر كل مرشح حاضر فعليًا في هذا التشغيل — من payload["_source"] الحقيقي، لا تخمينًا
    source_by_id = collections.defaultdict(set)
    for _l, _s, p in hits:
        oid = p.get("object_id")
        if oid:
            source_by_id[oid].add(p.get("_source", "dense"))
    hit_ids = set(source_by_id.keys())

    scope = backbone_mod.compute_backbone(app, case["request_type"], case["question"])

    # هل توجد فجوة اكتشاف فعلية (anchor A3 مُفعَّل وغائب عن hits)؟ إن لا: صفر حاجة لبحث إضافي
    # مكلف — توفير حقيقي (Shadow B لا تُثقِّل الـ38 حالة التي لا فجوة فيها).
    triggered_a3 = [a for a in scope.get("anchors_a3", [])
                    if any(d["dimension_id"] == a["dimension_id"] and d.get("required")
                           for d in scope["dimensions"])]
    needs_broad_search = any(a["authority_id"] not in hit_ids for a in triggered_a3)

    broad_found = {}
    subqueries_used = []
    if needs_broad_search:
        try:
            import anthropic
            key = app._draft_env("ANTHROPIC_API_KEY")
            client2 = anthropic.Anthropic(api_key=key)
            subqueries_used = app._draft_subqueries(client2, case["request_type"],
                                                     case["question"], None)
            broad_found = broad_channel_search(app, kb_types_mod, case["request_type"],
                                                case["question"], subqueries_used)
        except Exception as e:
            print(f"  !! broad-search-error: {e!r}", flush=True)

    injected_hits = list(hits)  # نُلحق مرشحي Shadow B الجدد هنا فقط — hits الأصلية لا تُعدَّل
    funnels = []
    for a in scope.get("anchors_a3", []):
        oid, dim_id, rule_id = a["authority_id"], a["dimension_id"], a["rule_id"]
        dim = next((d for d in scope["dimensions"] if d["dimension_id"] == dim_id), {})
        triggered = bool(dim.get("required"))

        stages = {"SCOPED": True, "A3_TRIGGERED": triggered, "CANDIDATE_GENERATED": False,
                  "RETRIEVED_OR_FETCHED": False, "GOVERNING_VERIFIED": False,
                  "RESERVED": False, "ADMITTED": False, "FINAL_CONTEXT": False}
        if not triggered:
            funnels.append({"authority_id": oid, "dimension_id": dim_id, "rule_id": rule_id,
                             "stages": stages, "note": "rule_not_triggered_for_this_case"})
            continue

        stages["CANDIDATE_GENERATED"] = True
        already_in_hits = oid in hit_ids
        channels_also = sorted(broad_found.get(oid, ()))

        if already_in_hits:
            authority_resolution_method = "already_in_production_hits"
            candidate_origin = "production_retrieval"
            retrieval_channels = sorted(source_by_id.get(oid, ()))
        else:
            authority_resolution_method = "direct_id_fetch"
            candidate_origin = "a3_curated_rule"
            retrieval_channels = []  # لم يجده أي قناة حقيقية في هذا التشغيل الفعلي — هذا هو بيت القصيد
            fetched = app._draft_fetch_texts({oid})
            if fetched.get(oid) and (fetched[oid].get("text") or "").strip():
                injected_hits.append(("تشريع", 0.0, {"object_id": oid, "_source": "a3_direct_fetch"}))
            else:
                authority_resolution_method = "not_resolvable"

        stages["RETRIEVED_OR_FETCHED"] = authority_resolution_method != "not_resolvable"

        funnels.append({
            "authority_id": oid, "dimension_id": dim_id, "rule_id": rule_id,
            "current_hit": oid in current_final,
            "in_production_hits_precap": already_in_hits,
            "candidate_origin": candidate_origin,
            "authority_resolution_method": authority_resolution_method,
            "retrieval_channels": retrieval_channels,
            "also_discovered_by": channels_also,
            "stages": stages,
        })

    all_ids = {p.get("object_id") for _l, _s, p in injected_hits if p.get("object_id")}
    texts_raw = app._draft_fetch_texts(all_ids)
    texts = {oid: {"text": (t.get("text") or "")} for oid, t in texts_raw.items()}
    for oid in texts:
        texts[oid]["object_type_label"] = "مبدأ قضائي" if oid.startswith("jprin-") else "تشريع"

    xref_map = getattr(app, "_XREF", {})
    tiers = ec_mod.classify_candidates(injected_hits, scope, xref_map=xref_map, texts=texts)
    dim_by_obj = {}
    for a in scope.get("anchors_a1", []) + scope.get("anchors_a3", []):
        if "dimension_id" in a:
            dim_by_obj[a["authority_id"]] = a["dimension_id"]

    admission = ap_mod.admit(tiers, texts, dim_by_obj)
    shadow_b_final = set(admission["reserved"]) | (current_final - {
        oid for oid, t in tiers.items() if t["tier"] in ("A1", "A2", "A3")
    })
    cov = cc_mod.check_coverage(scope, tiers, admission["decisions"], shadow_b_final)

    for f in funnels:
        oid = f["authority_id"]
        if not f["stages"].get("A3_TRIGGERED"):
            continue
        f["stages"]["GOVERNING_VERIFIED"] = tiers.get(oid, {}).get("tier") == "A3"
        f["stages"]["RESERVED"] = oid in admission["reserved"]
        f["stages"]["ADMITTED"] = oid in admission["reserved"]
        f["stages"]["FINAL_CONTEXT"] = oid in shadow_b_final

        if f["current_hit"]:
            cause = "none_needed"
        elif f["authority_resolution_method"] == "already_in_production_hits":
            cause = "admission_rescue_shadow_a"
        elif f["authority_resolution_method"] == "direct_id_fetch" and f["stages"]["FINAL_CONTEXT"]:
            cause = "A3_dependency/deterministic_backbone"
        else:
            cause = "unresolved"
        f["rescue_primary_cause"] = cause
        f["shadow_b_hit"] = oid in shadow_b_final
        f["shadow_a_hit_equivalent"] = f["current_hit"] or f["authority_resolution_method"] == "already_in_production_hits"

    context_chars_added = sum(len((texts.get(oid) or {}).get("text", ""))
                               for oid in (shadow_b_final - current_final))
    context_chars_removed = sum(len((texts.get(oid) or {}).get("text", ""))
                                 for oid in (current_final - shadow_b_final))

    return {
        "case_id": case["id"],
        "needs_broad_search": needs_broad_search,
        "current_final_context": sorted(current_final),
        "shadow_b_evidence_tiers": {k: v["tier"] for k, v in tiers.items()},
        "shadow_b_reserved_candidates": sorted(admission["reserved"]),
        "shadow_b_overflow": admission["overflow"],
        "shadow_b_coverage_state": cov,
        "shadow_b_final_context": sorted(shadow_b_final),
        "must_find": case.get("must_find", []),
        "must_find_rescued": sorted(set(case.get("must_find", [])) & (shadow_b_final - current_final)),
        "must_find_lost": sorted(set(case.get("must_find", [])) & (current_final - shadow_b_final)),
        "all_authorities_lost": sorted(current_final - shadow_b_final),
        "context_size_delta_chars": context_chars_added - context_chars_removed,
        "a3_causal_funnels": funnels,
        "subqueries_used_for_broad_search": subqueries_used,
    }


def main():
    import anthropic
    from admin import app
    import kb_types
    import p2_backbone, p2_evidence_classification, p2_admission_policy, p2_coverage_checker

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)

    args = sys.argv[1:]
    if args and args[0] == "--repeat":
        case_id, n = args[1], int(args[2])
        cases_all = load_gold_set()
        base_case = next(c for c in cases_all if c["id"] == case_id)
        cases = [dict(base_case, id=f"{case_id}#rep{i+1}") for i in range(n)]
    else:
        cases = load_gold_set()
        only = args[0].split(",") if args else None
        if only:
            cases = [c for c in cases if c["id"] in only]

    results = []
    for c in cases:
        print(f"... {c['id']} — Shadow B", flush=True)
        try:
            r = run_one(app, client, c, p2_backbone, p2_evidence_classification,
                        p2_admission_policy, p2_coverage_checker, kb_types)
        except Exception as e:
            print(f"  !! shadow-b-error: {e!r}", flush=True)
            continue
        results.append(r)
        print(f"  rescued={r['must_find_rescued']} lost={r['must_find_lost']} "
              f"coverage_complete={r['shadow_b_coverage_state']['coverage_complete']} "
              f"broad_search={r['needs_broad_search']}", flush=True)

    print()
    print("=" * 70)
    print("SHADOW_B_RAW_RESULTS")
    print("=" * 70)
    print(json.dumps(results, ensure_ascii=False, indent=2))

    total_rescued = sum(len(r["must_find_rescued"]) for r in results)
    total_lost = sum(len(r["must_find_lost"]) for r in results)

    # بوابة عزل: كل حالة يظهر فيها authority_resolution_method == direct_id_fetch لا يجوز أن
    # تُصنَّف current_hit=True في نفس الوقت (تناقض منطقي يعني علة في الكود لا في البيانات).
    contradictions = []
    for r in results:
        for f in r["a3_causal_funnels"]:
            if f.get("authority_resolution_method") == "direct_id_fetch" and f.get("current_hit"):
                contradictions.append((r["case_id"], f["authority_id"]))
    if contradictions:
        print(f"\n!! SHADOW_B_LOGIC_CONTRADICTION: {contradictions}")
    else:
        print("\nSHADOW_B_LOGIC_OK: صفر تناقض بين direct_id_fetch وcurrent_hit=True")

    print(f"\nSHADOW_B_DONE | cases={len(results)} | must_find_rescued_total={total_rescued} "
          f"| must_find_lost_total={total_lost}")


if __name__ == "__main__":
    main()
