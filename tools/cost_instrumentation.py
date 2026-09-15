#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.1 Closure Measurement — قياس زمني/تكلفة بحت، بلا أي تغيير سلوكي. طبقًا لأمر المالك
(البند 4، 2026-09-15): "instrumentation only ولا تغير أي candidate أو ranking أو budget".

**آلية العزل:** التغليف (wrapping) يقع **داخل عملية القياس الخاصة وحدها** — كل تشغيلة
`shadow_a_runner.py`/`shadow_b_runner.py` عملية بايثون منفصلة تمامًا عن خدمة
`legalmind-admin` الحية (نفس نمط `frozen_axes_experiment.py` المعتمد سابقًا لمونكي-باتش
`_draft_subqueries`) — لا لمس لملف admin/app.py على القرص، ولا أثر على الخدمة الحية أو
أي طلب مستخدم متزامن. الدالة المُغلَّفة تستدعي الأصلية حرفيًا بلا أي تعديل على مدخلاتها أو
مخرجاتها أو منطقها — فقط تسجّل الزمن والعدّاد كأثر جانبي صرف."""
from __future__ import annotations
import functools
import time


class CostCounters:
    """يجمع لكل تسمية (label) قائمة أزمنة بالمللي ثانية وعدّاد استدعاءات."""

    def __init__(self):
        self.durations = {}

    def record(self, label, ms):
        self.durations.setdefault(label, []).append(ms)

    def summary(self):
        out = {}
        for label, durs in self.durations.items():
            if not durs:
                continue
            s = sorted(durs)
            n = len(s)

            def pct(p, s=s, n=n):
                idx = min(n - 1, max(0, round(p * (n - 1))))
                return s[idx]

            out[label] = {
                "count": n,
                "p50_ms": round(pct(0.50), 1),
                "p95_ms": round(pct(0.95), 1),
                "max_ms": round(max(s), 1),
                "mean_ms": round(sum(s) / n, 1),
            }
        return out


def instrument_app_channels(app, counters):
    """يُلبِس دوال قنوات الاسترجاع الحية (Qdrant/PG/تضمين/Haiku) بعدّاد زمن/تكرار — بلا أي
    تغيير في السلوك (استدعاء الأصل حرفيًا، فقط قياس الزمن حوله). يُعيد دالة `restore()` تُرجع
    الدوال الأصلية (نظافة الحالة بين تشغيلات القياس المتتالية داخل نفس العملية)."""
    targets = {
        "_draft_build_context": "current_pipeline_runtime_ms",
        "_draft_search": "qdrant_search",
        "_draft_embed_multi": "embedding",
        "_draft_bundles": "bundle_query",
        "_draft_direct_ids": "direct_ids_query",
        "_draft_chap_ids": "chapter_query",
        "_draft_lexical": "lexical_query",
        "_draft_fetch_texts": "pg_fetch_texts",
        "_draft_subqueries": "haiku_subqueries",
    }
    # _draft_rerank قد لا تكون معلَّقة كدالة وحدة مستقلة الاسم — تُضاف إن وُجدت فقط
    if hasattr(app, "_draft_rerank"):
        targets["_draft_rerank"] = "reranker"

    originals = {}
    for attr, label in targets.items():
        if not hasattr(app, attr):
            continue
        orig = getattr(app, attr)
        originals[attr] = orig

        def make_wrapper(orig_fn, label):
            @functools.wraps(orig_fn)
            def wrapper(*a, **kw):
                t0 = time.perf_counter()
                try:
                    return orig_fn(*a, **kw)
                finally:
                    counters.record(label, (time.perf_counter() - t0) * 1000)
            return wrapper

        setattr(app, attr, make_wrapper(orig, label))

    def restore():
        for attr, orig in originals.items():
            setattr(app, attr, orig)
    return restore


class Timer:
    """أداة توقيت سياقية بسيطة: `with Timer(counters, "backbone_ms"): ...`"""

    def __init__(self, counters, label):
        self.counters, self.label = counters, label

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.counters.record(self.label, (time.perf_counter() - self.t0) * 1000)
        return False
