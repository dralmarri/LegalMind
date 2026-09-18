#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إغلاق Retrieval v2 — فحص موجّه ← Smoke ← Full Gate، بلصقة واحدة وبالتسلسل.

لا يبدأ Full Gate إلا إذا نجح Smoke كاملًا، فلا تُهدر أربعون دقيقة على بنية
لم تُثبت على الحالات الحاسمة أولًا.
"""
import sys, os, json, time
sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/admin")
sys.path.insert(0, "/opt/LegalMind/tools")

import retrieval_layer_validate as V     # noqa: E402 — يعيد استعمال نفس المِشجب
from retrieval.model import (LAYER_LEGISLATION as LL, LAYER_PRINCIPLE as LP,  # noqa
                             LAYER_JUDGMENT as LJ)

M146, M442 = "legis-6-2010-m146", "legis-67-1980-m442"
M166, M167 = "legis-38-1980-m166", "legis-38-1980-m167"
Q_LABOUR = ("عامل في القطاع الأهلي فصل تعسفيا دون إنذار ويطالب بمكافأة نهاية "
            "الخدمة والتعويض، وما الإجراء الواجب قبل رفع الدعوى وما مدة عدم "
            "سماعها عند الإنكار؟")
Q_CHEQUE = ("موكلي تسلم شيكين ارتدا لعدم كفاية الرصيد ويريد أمر أداء — ما ميعاد "
            "التكليف بالوفاء وما حكم تقادم دعوى الشيك؟")
Q_NASAB = ("ما الشرط الإجرائي الواجب توافره قبل قبول دعوى إثبات النسب، وما حكم "
           "رفعها على متوفى؟")
Q_DNA = ("دعوى نسب طُلب فيها فحص الحمض النووي ورفض المدعى عليه — ما أثر الرفض "
         "وهل يُقضى بالنسب استنادًا إليه؟")


def stage_of(res, oid):
    rec = res["rec"]
    if oid in {c.object_id for c in res["admitted"]}:
        return "FINAL_CONTEXT" if ('معرف="%s"' % oid) in res["context"] else "ADMITTED"
    if oid in rec.rr_out:
        return "RERANKED_NOT_ADMITTED"
    if oid in rec.rr_in:
        return "RERANKER_INPUT_ONLY"
    if oid in (rec.generated | rec.fetched):
        return "IN_POOL_ONLY"
    return "NEVER_GENERATED"


def run(q, anchors=()):
    return V.run_v2("استشارة", q, anchors_extra=anchors)


def phase_a():
    print("\n=== أ) فحص موجّه: أين تتوقف المادتان ===", flush=True)
    a = run(Q_LABOUR, ["legis-6-2010-m144"])
    b = run(Q_CHEQUE, ["legis-68-1980-m550", "legis-68-1980-m551"])
    out = {M146: stage_of(a, M146), M442: stage_of(a, M442),
           M166: stage_of(b, M166), M167: stage_of(b, M167)}
    for k, v in out.items():
        print("   %-22s %s" % (k, v), flush=True)
    return out, a, b


def phase_b(a, b):
    print("\n=== ب) Smoke: معايير الإغلاق على الحالات الحاسمة ===", flush=True)
    fails = []

    def ck(name, ok, detail=""):
        print(("   ✓ " if ok else "   ✗ ") + name + ("" if ok else "  — %s" % detail),
              flush=True)
        if not ok:
            fails.append(name)

    ck("m146 يصل FINAL_CONTEXT", stage_of(a, M146) == "FINAL_CONTEXT", stage_of(a, M146))
    ck("m442 يصل FINAL_CONTEXT", stage_of(a, M442) == "FINAL_CONTEXT", stage_of(a, M442))
    ck("m166 يصل FINAL_CONTEXT", stage_of(b, M166) == "FINAL_CONTEXT", stage_of(b, M166))
    ck("m167 يصل FINAL_CONTEXT", stage_of(b, M167) == "FINAL_CONTEXT", stage_of(b, M167))
    ck("«خمسة أيام» لا تخرج بلا تحذير زمني",
       ("خمسة أيام" not in b["context"]) or ("تحذير زمني" in b["context"]))
    for nm, r in (("العمل", a), ("الشيك", b)):
        lay = {}
        for c in r["admitted"]:
            lay[c.layer] = lay.get(c.layer, 0) + 1
        ck("قضاء في السياق (%s)" % nm, lay.get(LP, 0) + lay.get(LJ, 0) >= 1, lay)
    n = run(Q_NASAB)
    lay = {}
    for c in n["admitted"]:
        lay[c.layer] = lay.get(c.layer, 0) + 1
    ck("النسب: قاعدة قضائية في السياق", lay.get(LP, 0) + lay.get(LJ, 0) >= 1, lay)
    d = run(Q_DNA)
    bad = [x for x in (d.get("conflicts") or [])
           if x.get("resolution") and not x.get("basis_available")]
    ck("DNA: لا ترجيح بلا سند", not bad, bad)
    ck("DNA: التعارض غير ضجيجي (≤2 لكل مصدر)",
       all(len(x.get("clashes") or []) <= 2 for x in (d.get("conflicts") or [])),
       [len(x.get("clashes") or []) for x in (d.get("conflicts") or [])])
    # عينة سلطات مستقرة: حالات بطارية بواجبات must
    bat = [c for c in json.load(open("/opt/LegalMind/battery.json")) if c.get("must")][:3]
    for c in bat:
        r = run(c["q"])
        ids = {x.object_id for x in r["admitted"]}
        miss = [m for m in c["must"] if m not in ids]
        ck("سلطة مستقرة: %s" % str(c.get("name"))[:28], not miss, miss)
    nbu = ["legis-6-2010-m145", "legis-6-2010-m147", "legis-6-2010-m140",
           "legis-6-2010-m141", "legis-6-2010-m142", "legis-6-2010-m143",
           "legis-6-2010-m148"]
    got = {c.object_id for c in a["admitted"]} & set(nbu)
    ck("NEAR_BUT_UNRELATED = 0 (لا يزيد عن الأساس)", not got, sorted(got))
    return fails


def main():
    t0 = time.time()
    out, a, b = phase_a()
    fails = phase_b(a, b)
    json.dump({"stages": out, "smoke_failures": fails},
              open("/opt/LegalMind/tools/v2_close_smoke.json", "w"),
              ensure_ascii=False, indent=1)
    print("\nSMOKE: %s  (%.0f ث)" % ("PASS" if not fails else "FAIL " + str(fails),
                                      time.time() - t0), flush=True)
    if fails:
        print("لن تُشغَّل Full Gate — Smoke لم ينجح.", flush=True)
        sys.exit(1)
    print("\n=== ج) Full Regression Gate (الجولة الكاملة الأخيرة) ===", flush=True)
    V.main()


if __name__ == "__main__":
    main()
