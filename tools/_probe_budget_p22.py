#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""فحص تشخيصي سريع (قراءة فقط، بلا تعديل): يشغّل _draft_build_context حيًّا مرة واحدة على
حالتين (gs-0002 وgs-0013) ويطبع البنية الخام لـctx['budget_dropped_full'] (أول 3 صفوف) +
هل أهداف هذه الحالات المفقودة (m166/m167 لـgs-0002، m297/m298/jprin لـgs-0013) تظهر فيه —
الغرض حصرًا تأكيد أسماء الحقول الفعلية قبل بناء أداة التشخيص الكاملة لـ19 حالة، تفاديًا
لأي تخمين لمنطق غير مُلاحَظ مباشرة."""
import json
import sys

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")

import anthropic
from admin import app

key = app._draft_env("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=key)


def load_gold_set(path="/opt/LegalMind/tools/retrieval_gold_set.json"):
    return json.load(open(path, encoding="utf-8"))["cases"]


gold = {c["id"]: c for c in load_gold_set()}

TARGETS = {
    "gs-0002": ["legis-38-1980-m166", "legis-38-1980-m167"],
    "gs-0013": ["legis-38-1980-m297", "legis-38-1980-m298", "jprin-1396-2005-i904-fae32f326b"],
}

for cid, target_ids in TARGETS.items():
    case = gold[cid]
    inp = app._DraftIn(request_type=case["request_type"], facts=case["question"])
    print(f"\n=== {cid} ===", flush=True)
    ctx = app._draft_build_context(client, inp, case["question"])

    bdf = ctx.get("budget_dropped_full")
    print(f"type(budget_dropped_full) = {type(bdf)}")
    print(f"len(budget_dropped_full) = {len(bdf) if bdf is not None else 'N/A'}")
    if bdf:
        print("أول 3 صفوف خام:")
        print(json.dumps(bdf[:3], ensure_ascii=False, indent=2, default=str))

    seen = ctx["seen"]
    hit_ids = {p.get("object_id") for _l, _s, p in ctx["hits"] if p.get("object_id")}
    prov_ids = {p["object_id"] for p in ctx["provenance"]}
    cap_dropped = set(ctx["attr"].get("cap_dropped_ids") or [])

    for oid in target_ids:
        in_bdf_raw = False
        bdf_match = None
        if bdf:
            for row in bdf:
                if oid in json.dumps(row, ensure_ascii=False, default=str):
                    in_bdf_raw = True
                    bdf_match = row
                    break
        print(f"  {oid}: in_final={oid in seen} in_hits={oid in hit_ids} "
              f"in_provenance={oid in prov_ids} in_cap_dropped={oid in cap_dropped} "
              f"appears_in_budget_dropped_full_raw={in_bdf_raw}")
        if bdf_match:
            print(f"    match_row={json.dumps(bdf_match, ensure_ascii=False, default=str)}")
        if oid in prov_ids:
            prow = next(p for p in ctx["provenance"] if p["object_id"] == oid)
            print(f"    provenance_record={json.dumps(prow, ensure_ascii=False, default=str)}")

print("\nPROBE_BUDGET_DONE")
