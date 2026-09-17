#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.3 §D — فحص تشخيصي (قراءة فقط، بلا أي نداء حي): يسرد أسماء دوال/سمات admin.app التي
تحتوي كلمات مفتاحية مرشَّحة لمراحل السقف/المرتِّب/الميزانية (cap/rerank/budget/admit/draft_build)
مع توقيع كل دالة (inspect.signature) — الغرض حصرًا تأكيد الأسماء الحقيقية قبل بناء أي أداة حقن
(Oracle Injection)، تفاديًا للتخمين. صفر نداء شبكي، صفر نداء نموذج، صفر تعديل."""
import inspect
import sys

sys.path.insert(0, "/opt/LegalMind")
from admin import app

KEYWORDS = ["cap", "rerank", "budget", "admit", "draft_build", "draft_rerank", "_draft_"]

names = [n for n in dir(app) if any(k in n.lower() for k in KEYWORDS)]
print(f"=== {len(names)} أسماء مطابقة ===")
for n in sorted(names):
    obj = getattr(app, n)
    if callable(obj):
        try:
            sig = str(inspect.signature(obj))
        except (TypeError, ValueError):
            sig = "(؟)"
        print(f"  def {n}{sig}")
    else:
        print(f"  {n} = {type(obj).__name__} (غير قابلة للاستدعاء)")

print()
print("=== مصدر _draft_build_context (لتحديد الدوال الداخلية التي يستدعيها فعليًا) ===")
try:
    src = inspect.getsource(app._draft_build_context)
    print(f"عدد الأسطر: {len(src.splitlines())}")
    # اطبع فقط أسطر نداء الدوال الداخلية (تبدأ بمسافة ثم اسم يحوي كلمة مفتاحية أو نمط نداء دالة)
    import re
    for i, line in enumerate(src.splitlines(), 1):
        if re.search(r'\b(cap|rerank|budget|admit)\w*\s*\(', line, re.IGNORECASE):
            print(f"  L{i}: {line.strip()}")
except Exception as e:
    print(f"  !! تعذّر جلب المصدر: {e!r}")

print("PROBE_INTERNALS_DONE")
