#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.3 §D — حقن مرشح الحقيقة الأرضية (Oracle Candidate Injection) — تشخيص offline بحت.

يُستعمَل `authority_id` من Ground Truth تشخيصيًا فقط، لفصل أربع طبقات فشل عن بعضها:
توليد المرشحين / سقف ما قبل الترتيب / المرتِّب المتقاطع / الميزانية. الحقن هنا **حيّ فعليًا
داخل `_draft_build_context` الحقيقية** عبر تصحيح مؤقت (monkey-patch try/finally، استعادة فورية،
صفر تعديل على القرص) لدالتين حقيقيتين مؤكَّد توقيعهما حيًّا (`probe_hooks.py`، 2026-09-16):

1. **`inject_post_cap_pre_reranker`** (لا يحتاج أي درجة مُفترَضة): تصحيح
   `_prin_xref(hits, texts, picked)` — آخر دالة حقيقية تُستدعى قبل نداء `_draft_rerank` مباشرة
   في `_draft_build_context` (مؤكَّد من مصدرها الحرفي، `dump_source.py`) — تُشغِّل السلوك
   الأصلي أولًا (صفر تغيير في مخرَجه)، ثم تُلحق مرشح الحقيقة الأرضية (نصه الحقيقي عبر
   `_draft_fetch_texts`) بنفس كائنات `hits`/`texts`/`picked` **بالمرجع** (تحويرها من داخل
   الدالة المصحَّحة مرئي في الدالة المستدعية لأن بايثون يمرر القوائم/المجموعات/القواميس
   بالمرجع) بدرجة ابتدائية 0.5 (وسيطة بلا أثر فعلي، لأن `_draft_rerank` الحقيقي يعيد حسابها).
   من هذه النقطة فصاعدًا **الكود الحقيقي غير المعدَّل تمامًا** (نداء المرتِّب الفعلي، دمج
   الدرجات، الترتيب، حلقة الميزانية) يعالج المرشح المحقون كأي مرشح حقيقي آخر دون أي تمييز.
2. **`inject_pre_cap`** (يحتاج درجة كثيفة حقيقية مرصودة تجريبيًا من P2.3 §A — **لا تُخمَّن
   أبدًا**؛ يُرفَض التشغيل صراحة بلا درجة حقيقية): تصحيح `_draft_search(vector, types, limit)`
   لإلحاق ضربة اصطناعية بشكل `payload`/`score` مطابق تمامًا لمخرَج الدالة الحقيقية (مؤكَّد
   حيًّا)، عند أول نداء يطابق نوع الهدف (تشريع/مبدأ قضائي) فقط، بالدرجة الكثيفة **الحقيقية**
   المرصودة فعليًا لهذا المعرِّف في إحدى تشغيلات Normal من P2.3 §A — فيخضع لقرار السقف
   الحقيقي (`caps_n`) بمنافسة حقيقية على نفس حصة نوعه.

**الحقن هنا تشخيصي بحت وممنوع منعًا مطلقًا من أي قرار إنتاج/تشغيل حي — المعرِّف المحقون لا
يدخل أي قاعدة أو بوابة أو نمط مستقبلي مهما كانت النتيجة.**"""
import json
import sys

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")


def load_gold_set(path="/opt/LegalMind/tools/retrieval_gold_set.json"):
    return {c["id"]: c for c in json.load(open(path, encoding="utf-8"))["cases"]}


def _oracle_label(oid):
    return "مبدأ قضائي" if oid.startswith("jprin-") else "تشريع"


def extract_oracle_trace(oid, ctx):
    hits = ctx["hits"]
    attr = ctx["attr"]
    seen = ctx["seen"]
    provenance_by_id = {p["object_id"]: p for p in ctx["provenance"]}
    hit_ids = {p.get("object_id") for _l, _s, p in hits if p.get("object_id")}
    cap_dropped_ids = set(attr.get("cap_dropped_ids") or [])
    prov = provenance_by_id.get(oid)
    return {
        "oracle_injected": True,
        "survives_pre_rerank_cap": oid in hit_ids,
        "explicitly_cap_dropped": oid in cap_dropped_ids,
        "reranker_present": prov is not None,
        "reranker_raw": (prov or {}).get("reranker_raw"),
        "post_rerank_rank": (prov or {}).get("rank"),
        "survives_budget": bool((prov or {}).get("admitted")),
        "final_context": oid in seen,
    }


def run_post_cap_injection(app, client, case, oracle_id):
    """§D-2: حقن بعد السقف وقبل المرتِّب — بلا حاجة لأي درجة مُفترَضة."""
    orig_prin_xref = app._prin_xref
    injected_flag = {"done": False}

    def patched_prin_xref(hits, texts, picked):
        result = orig_prin_xref(hits, texts, picked)
        if oracle_id in picked:
            return result  # موجود أصلًا (اكتُشف عضويًا هذه التشغيلة) — لا حقن، لا ازدواج
        fetched = app._draft_fetch_texts({oracle_id})
        if not fetched.get(oracle_id) or not (fetched[oracle_id].get("text") or "").strip():
            return result  # لا نص حقيقي في القاعدة — لا حقن بلا سند
        texts.update(fetched)
        picked.add(oracle_id)
        hits.append((_oracle_label(oracle_id), 0.5,
                     {"object_id": oracle_id, "_source": "oracle_injected_post_cap"}))
        injected_flag["done"] = True
        return result

    app._prin_xref = patched_prin_xref
    try:
        inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
        ctx = app._draft_build_context(client, inp, case["question"])
    finally:
        app._prin_xref = orig_prin_xref

    trace = extract_oracle_trace(oracle_id, ctx)
    trace["config"] = "inject_post_cap_pre_reranker"
    trace["injection_attempted"] = injected_flag["done"]
    trace["naturally_present_before_injection_point"] = not injected_flag["done"]
    return trace


def run_pre_cap_injection(app, client, case, oracle_id, injected_score):
    """§D-1: حقن قبل السقف — بدرجة كثيفة حقيقية مرصودة تجريبيًا من P2.3 §A فقط، لا مُختلَقة."""
    if injected_score is None:
        return {"config": "inject_pre_cap", "oracle_injected": False,
                "skipped_reason": "no_empirical_dense_score_available_in_normal5"}

    fetched = app._draft_fetch_texts({oracle_id})
    if not fetched.get(oracle_id) or not (fetched[oracle_id].get("text") or "").strip():
        return {"config": "inject_pre_cap", "oracle_injected": False,
                "skipped_reason": "no_real_text_available"}

    orig_search = app._draft_search
    target_label = _oracle_label(oracle_id)
    legislation_types = set(app._kb.LEGISLATION_TYPES)
    principle_types = set(app._kb.PRINCIPLE_TYPES)
    injected_once = {"done": False}

    def patched_search(vector, types, limit):
        raw = orig_search(vector, types, limit)
        if injected_once["done"]:
            return raw
        types_set = set(types)
        matches = (target_label == "تشريع" and types_set == legislation_types) or \
                  (target_label == "مبدأ قضائي" and types_set == principle_types)
        if matches:
            injected_once["done"] = True
            payload = {"object_id": oracle_id, "object_type": target_label}
            raw = list(raw) + [{"payload": payload, "score": injected_score}]
        return raw

    app._draft_search = patched_search
    try:
        inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
        ctx = app._draft_build_context(client, inp, case["question"])
    finally:
        app._draft_search = orig_search

    trace = extract_oracle_trace(oracle_id, ctx)
    trace["config"] = "inject_pre_cap"
    trace["injected_score_source"] = "empirical_normal5_dense_score_p23a"
    trace["injected_score"] = injected_score
    trace["injection_attempted"] = injected_once["done"]
    return trace


# case_id -> [authority_id, ...] — الأهداف التسعة عبر الإخفاقات الحرجة السبعة (P2.2 §7)
ORACLE_TARGETS = {
    "gs-0002": ["legis-38-1980-m166", "legis-38-1980-m167"],
    "gs-0009": ["regl-1-2016-m65"],
    "gs-0010": ["legis-51-1984-m299", "legis-51-1984-m300"],
    "gs-0011": ["legis-51-1984-m337", "legis-51-1984-m338"],
    "gs-0014": ["legis-20-2015-m49"],
    "gs-0017": ["legis-38-1980-m103"],
}

# يُملأ من نتائج P2.3 §A (درجة كثيفة حقيقية مرصودة في أي تشغيلة Normal اكتشفت الهدف) —
# فارغ افتراضيًا حتى تصل بيانات §A؛ أي معرِّف غائب هنا يعني inject_pre_cap يُرفَض صراحة له.
EMPIRICAL_DENSE_SCORES = {}


def main():
    import anthropic
    from admin import app

    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    gold = load_gold_set()

    args = sys.argv[1:]
    configs = args[0].split(",") if args and args[0] else ["post_cap"]
    case_ids = args[1].split(",") if len(args) > 1 and args[1] else sorted(ORACLE_TARGETS.keys())

    results = {}
    for cid in case_ids:
        case = gold[cid]
        for oid in ORACLE_TARGETS[cid]:
            key_name = f"{cid}/{oid}"
            results[key_name] = {}
            if "post_cap" in configs:
                print(f"=== {key_name} — inject_post_cap_pre_reranker ===", flush=True)
                r = run_post_cap_injection(app, client, case, oid)
                results[key_name]["post_cap"] = r
                print(f"  {json.dumps(r, ensure_ascii=False, default=str)}", flush=True)
            if "pre_cap" in configs:
                score = EMPIRICAL_DENSE_SCORES.get(oid)
                print(f"=== {key_name} — inject_pre_cap (score={score}) ===", flush=True)
                r = run_pre_cap_injection(app, client, case, oid, score)
                results[key_name]["pre_cap"] = r
                print(f"  {json.dumps(r, ensure_ascii=False, default=str)}", flush=True)

    print()
    print("=" * 70)
    print("P23_ORACLE_INJECTION_RAW_RESULTS")
    print("=" * 70)
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    print(f"\nP23_ORACLE_INJECTION_DONE | targets={len(results)}")


if __name__ == "__main__":
    main()
