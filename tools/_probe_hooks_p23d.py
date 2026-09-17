#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.3 §D — تحقق إضافي (نداء حي واحد رخيص للمرتِّب المحلي فقط، بلا Haiku/Anthropic) قبل بناء
أداة الحقن: تأكيد وجود الأسماء التي يعتمدها التصميم (_prin_xref/_sib_expand/_XREF) كسمات
مستوى-الوحدة القابلة للتصحيح المؤقت (monkey-patch)، وتأكيد الشكل الفعلي لمخرَج _draft_rerank."""
import inspect
import sys

sys.path.insert(0, "/opt/LegalMind")
from admin import app

for name in ("_prin_xref", "_sib_expand", "_XREF", "_kb", "_djson"):
    has = hasattr(app, name)
    print(f"{name}: exists={has}", end="")
    if has:
        obj = getattr(app, name)
        if callable(obj):
            try:
                print(f" signature={inspect.signature(obj)}")
            except Exception as e:
                print(f" (لا توقيع: {e!r})")
        else:
            print(f" type={type(obj).__name__}")
    else:
        print()

print()
print("=== نداء حي رخيص لـ_draft_rerank (مرتِّب محلي، بلا Anthropic) ===")
try:
    out = app._draft_rerank("اختبار تشخيصي", [("id1", "نص تجريبي أول عن موضوع قانوني"),
                                                ("id2", "نص تجريبي ثانٍ مختلف تمامًا")])
    print(f"type={type(out).__name__} value={out!r}")
except Exception as e:
    print(f"!! rerank-call-error: {e!r}")

print("PROBE_HOOKS_DONE")
