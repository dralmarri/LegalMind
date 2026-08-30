#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بطارية قياس الاسترجاع: تجري خط الاسترجاع كاملا (محاور+متجهات+حزم+محل+معجمي) بلا نداء صياغة،
وتتحقق من حضور المصادر الواجبة. الاستهلاك: نداءات Haiku للمحاور فقط."""
import sys, json, collections
sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/admin")
from admin import app

def retrieve(rt, facts):
    import anthropic
    key = app._draft_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    subqueries = app._draft_subqueries(client, rt, facts, None)
    query = rt + " - " + facts[:1500]
    vectors = app._draft_embed_multi([query] + subqueries)
    plans = [(vectors[0], [(["legislation_article","legislation_issuing_article"],10),(["judicial_principle"],10),(["full_judgment"],2),(["judicial_template"],2)])]
    for v in vectors[1:]:
        plans.append((v, [(["legislation_article","legislation_issuing_article"],8),(["judicial_principle"],8)]))
    picked = set()
    for vec, buckets in plans:
        for types, lim in buckets:
            try:
                for h in app._draft_search(vec, types, lim):
                    oid = (h.get("payload") or {}).get("object_id")
                    if oid: picked.add(oid)
            except Exception: pass
    for oid in app._draft_bundles(rt, facts, subqueries, None, None): picked.add(oid)
    for oid in app._draft_direct_ids(rt, facts, subqueries): picked.add(oid)
    for oid in app._draft_chap_ids(rt, facts, subqueries): picked.add(oid)
    try:
        for oid in app._draft_lexical(subqueries, facts): picked.add(oid)
    except Exception: pass
    # مرآة مرحلة التوسعات في الإنتاج (كانت خارج عين البطارية منذ .bak_sibxref):
    # XREF ثم الشقيقات ثم توسعة المبادئ إلى نصوصها — بدوال الإنتاج نفسها لا نسخًا
    _xn = 0
    for oid in list(picked):
        if _xn >= 24:
            break
        for tgt in app._XREF.get(oid, ()):
            if tgt not in picked and _xn < 24:
                picked.add(tgt)
                _xn += 1
    hits = [("تشريع" if oid.startswith(("legis", "regl")) else "مبدأ قضائي", 0.5,
             {"object_id": oid}) for oid in picked]
    texts = app._draft_fetch_texts(set(picked))
    extra = app._sib_expand(hits, texts, picked) + app._prin_xref(hits, texts, picked)
    if extra:
        ex = app._draft_fetch_texts(set(extra))
        for s in extra:
            if s not in ex:
                picked.discard(s)
    return picked, subqueries

def main():
    cases = json.load(open("/opt/LegalMind/battery.json"))
    total = ok = 0
    for c in cases:
        picked, _sq = retrieve(c["rt"], c["q"])
        fails = []
        for mid in c.get("must", []):
            if mid not in picked: fails.append("must:" + mid)
        for grp in c.get("any", []):
            if isinstance(grp, str): grp = [grp]
            if grp and not any(g in picked for g in grp): fails.append("any:" + "/".join(g.rsplit("-",1)[1] for g in grp[:3]))
        for pref in c.get("must_last", []):
            import os, psycopg
            with psycopg.connect(os.environ["DATABASE_URL"]) as _c2, _c2.cursor() as _cur:
                _cur.execute("SELECT id FROM knowledge_objects WHERE id LIKE %s AND id ~ %s "
                             "ORDER BY (substring(id from 'm([0-9]+)$'))::int DESC LIMIT 1",
                             (pref + "m%", "^" + pref + "m[0-9]+$"))
                _r = _cur.fetchone()
            if _r and _r[0] not in picked:
                fails.append("last:" + _r[0])
        for pref, n in c.get("law_min", []):
            k = sum(1 for p in picked if p.startswith(pref))
            if k < n: fails.append(f"law:{pref}({k}<{n})")
        total += 1
        status = "✓" if not fails else "✗"
        if not fails: ok += 1
        print(f"{status} {c['name']} | مسترجَع: {len(picked)}" + ("" if not fails else " | فشل: " + "، ".join(fails)), flush=True)
    print(f"\nالبطاقة: {ok}/{total}", flush=True)
    print("BATTERY_PASS" if ok == total else "BATTERY_FAIL", flush=True)

if __name__ == "__main__":
    main()
