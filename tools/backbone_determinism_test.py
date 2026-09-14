#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.1 — اختبار حتمية Backbone (شرط توقف صريح قبل أي قياس Shadow آخر، بأمر المالك).
لكل حالة اختبار: 5 تشغيلات مستقلة لـp2_backbone.compute_backbone على نفس (request_type,
facts) حرفيًا — يجب أن تُنتج بصمة canonical_hash واحدة مطابقة في الخمس جميعًا. أي اختلاف
يوقف الاعتماد فورًا (fail-fast، لا استمرار لقياس Shadow B تاليًا)."""
import json
import sys

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/tools")


def load_gold_set(path="/opt/LegalMind/tools/retrieval_gold_set.json"):
    return json.load(open(path, encoding="utf-8"))["cases"]


def main():
    import p2_backbone as pb
    from admin import app

    cases = load_gold_set()
    all_pass = True
    report = []
    for c in cases:
        hashes = []
        scopes = []
        for i in range(5):
            scope = pb.compute_backbone(app, c["request_type"], c["question"])
            h = pb.canonical_hash(scope)
            hashes.append(h)
            scopes.append(scope)
        unique = sorted(set(hashes))
        ok = len(unique) == 1
        all_pass = all_pass and ok
        report.append({
            "case_id": c["id"], "unique_hashes": len(unique), "pass": ok,
            "sample_scope": scopes[0] if ok else scopes,
        })
        flag = "✓" if ok else "✗ NONDETERMINISTIC"
        print(f"{flag} {c['id']}: 5 runs -> {len(unique)} unique hash(es)", flush=True)
        if not ok:
            print(f"  !! تفاصيل عدم الحتمية لـ{c['id']}:", flush=True)
            for i, (h, s) in enumerate(zip(hashes, scopes)):
                print(f"    run{i+1} hash={h[:16]} scope={json.dumps(s, ensure_ascii=False)[:300]}",
                      flush=True)

    print()
    print("=" * 70)
    print(f"BACKBONE_DETERMINISM_{'PASS' if all_pass else 'FAIL'} | حالات مقيسة: {len(cases)}")
    print("=" * 70)
    if not all_pass:
        print("!! شرط توقف: لا تُكمِل لقياس Shadow B قبل حل عدم الحتمية المكتشَف أعلاه.", flush=True)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
