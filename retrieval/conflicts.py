# -*- coding: utf-8 -*-
"""كشف التعارض بين السلطات — **رصدٌ ووسمٌ بلا حسم آلي**.

القاعدة الحاكمة (البند 9): لا يُحسم تعارضٌ آليًا ما لم يوجد في البيانات سندٌ
يسمح بالحسم. وما لا سند له يخرج بوسم `POTENTIAL_AUTHORITY_CONFLICT` ومعه
طرفاه كاملين، فيقرر المحامي — ولا يُخترع ترجيح.

ثلاثة محاور:
  statute ↔ judicial      مبدأ يقتبس مدةً تخالف نص المادة النافذ.
  judicial ↔ judicial     مبدآن يفسّران المادة نفسها بمدتين مختلفتين.
  current ↔ superseded    سلطة موسومة ملغاة تتعايش مع أخرى نافذة على المحل نفسه.
"""
import re
from .temporal import periods, CONFLICT_DETECTED, SUPERSEDED, TRANSITION_VERIFIED
from .model import LAYER_LEGISLATION, LAYER_PRINCIPLE, LAYER_JUDGMENT

FLAG = "POTENTIAL_AUTHORITY_CONFLICT"
_ART_IN_TEXT = re.compile(r"الماد[ةه]\s*\(?\s*(\d{1,4})")


def _cited_articles(text, limit=6):
    return [m.group(1) for m in _ART_IN_TEXT.finditer(text or "")][:limit]


def detect(admitted, text_of, row_of):
    """يعيد قائمة تعارضات موسومة، بلا أي ترجيح."""
    out = []
    jud = [c for c in admitted if c.layer in (LAYER_PRINCIPLE, LAYER_JUDGMENT)]
    leg = [c for c in admitted if c.layer == LAYER_LEGISLATION]

    # 1) statute ↔ judicial — مرصود أصلًا في الطبقة الزمنية، يُرفع هنا وسمًا صريحًا
    for c in jud:
        cf = getattr(c, "temporal_conflict", None)
        if c.temporal_status == CONFLICT_DETECTED and cf:
            out.append({
                "flag": FLAG, "axis": "statute_vs_judicial",
                "judicial": c.object_id, "statute": cf.get("article_id"),
                "clashes": cf.get("clashes"),
                "resolution": None, "basis_available": False,
                "note": "المبدأ يقتبس مدةً تخالف النص النافذ — يبقى صالحًا فيما "
                        "عدا هذه النقطة، ولا يُقدَّم تفصيله القديم بوصفه النافذ.",
            })

    # 2) judicial ↔ judicial — مبدآن على المادة نفسها بمدتين مختلفتين
    by_art = {}
    for c in jud:
        t = text_of(c.object_id) or ""
        ps = periods(t)
        for a in _cited_articles(t):
            by_art.setdefault(a, []).append((c.object_id, ps))
    for art, items in by_art.items():
        if len(items) < 2:
            continue
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a_id, a_p = items[i]
                b_id, b_p = items[j]
                units = {u for _n, u in a_p} & {u for _n, u in b_p}
                clash = []
                for u in units:
                    av = {n for n, uu in a_p if uu == u}
                    bv = {n for n, uu in b_p if uu == u}
                    if av and bv and not (av & bv):
                        clash.append({"unit": u, "a": sorted(av), "b": sorted(bv)})
                if clash:
                    out.append({
                        "flag": FLAG, "axis": "judicial_vs_judicial",
                        "article": art, "a": a_id, "b": b_id, "clashes": clash,
                        "resolution": None, "basis_available": False,
                        "note": "سلطتان قضائيتان تذكران مدتين مختلفتين للمادة "
                                "نفسها — قد يكون أحدهما سابقًا لتعديل. لا ترجيح "
                                "بلا سند.",
                    })

    # 3) current ↔ superseded — الملغى يتعايش مع النافذ على المحل نفسه
    sup = [c for c in admitted if c.temporal_status in (SUPERSEDED, TRANSITION_VERIFIED)]
    for c in sup:
        md = (row_of(c.object_id) or {}).get("metadata") or {}
        if isinstance(md, str):
            try:
                import json as _j
                md = _j.loads(md)
            except Exception:
                md = {}
        by = md.get("repealed_by")
        peers = [x.object_id for x in leg
                 if x.object_id != c.object_id and x.temporal_status not in
                 (SUPERSEDED,) and _same_slot(c.object_id, x.object_id)]
        if c.temporal_status == SUPERSEDED:
            out.append({
                "flag": FLAG, "axis": "current_vs_superseded",
                "superseded": c.object_id, "repealed_by": by,
                "current_peers": peers[:4],
                "resolution": ("النافذ هو الصك اللاحق" if by else None),
                "basis_available": bool(by),
                "note": ("سند الإلغاء موجود في القاعدة." if by else
                         "لا سند إلغاء صريح في القاعدة — لا يُحسم آليًا."),
            })
    return out


def _same_slot(a, b):
    """المادة نفسها في قانونين مختلفين (ملغى/نافذ) — بالرقم وحده، تحفّظًا."""
    ra = re.match(r"^.*-m(\d{1,4})$", a or "")
    rb = re.match(r"^.*-m(\d{1,4})$", b or "")
    return bool(ra and rb and ra.group(1) == rb.group(1))
