# -*- coding: utf-8 -*-
"""حزمة الأدلة (Authority Packet) — الناتج النهائي ليس كتلًا نصية مسطّحة.

الخط القائم يسلّم النموذج قائمة `<مصدر>` بلا بنية: النموذج هو من يكتشف أيُّ
مادةٍ حاكمة وأيُّ مبدأ يفسّرها وأيُّها استثناء وأيُّها متقادم. وهذا يضع على
النموذج عبئًا تركيبيًا يملك النظامُ بياناته أصلًا. الحزمة هنا تسلّمه البنية
جاهزة لكل مسألة:

    المسألة/البُعد
      → التشريع الحاكم
      → التفسير/التطبيق القضائي
      → الاستثناءات والمتطلبات الإجرائية
      → الحالة الزمنية
      → التعارضات
      → الحكم الكامل حين يكون نافعًا ماديًا
      → سلسلة النسب (provenance)

وسمة `الحالة_الزمنية` تُطبع داخل كل كتلة، فلا يصل النموذج مصدرٌ قديمٌ بلا
تحذير على وجهه."""
from .model import (LAYER_LEGISLATION, LAYER_PRINCIPLE, LAYER_JUDGMENT,
                    LAYER_TEMPLATE)
from .temporal import CURRENT, CONFLICT_DETECTED, SUPERSEDED

EXCEPTION_RELATIONS = ("EXCEPTION", "LIMITATION_OR_QUALIFICATION")
PROCEDURAL_RELATIONS = ("PROCEDURAL_REQUIREMENT", "PROCEDURAL_EFFECT",
                        "PREREQUISITE")


def _esc(v):
    return (v or "").replace('"', "'").strip()


def render_block(c, t):
    """كتلة مصدر واحدة بصيغة الإنتاج نفسها + الحالة الزمنية والقناة."""
    pub = _esc(t.get("publication"))
    if not pub and c.layer in (LAYER_PRINCIPLE, LAYER_JUDGMENT):
        snd = (t.get("text") or "").rstrip().rsplit("\n", 1)[-1].strip()
        if ("الطعن" in snd or "جلسة" in snd) and len(snd) < 400:
            pub = _esc(snd)
    attrs = ['نوع="%s"' % c.layer, 'معرف="%s"' % c.object_id,
             'فرع="%s"' % _esc(t.get("branch")),
             'موضوع="%s"' % _esc(t.get("topic")),
             'عنوان="%s"' % _esc(t.get("title"))]
    if pub:
        attrs.append('النشر="%s"' % pub)
    if c.temporal_status and c.temporal_status != CURRENT:
        attrs.append('الحالة_الزمنية="%s"' % c.temporal_status)
    return "<مصدر " + " ".join(attrs) + ">\n" + (t.get("text") or "") + "\n</مصدر>"


def build(admitted, texts, issues=None, conflicts=None):
    """يبني الحزمة المنظَّمة + نص السياق المُرسَل للنموذج."""
    issues = issues or [{"id": "general", "title": "المسألة محل الطلب"}]
    by_layer = {LAYER_LEGISLATION: [], LAYER_PRINCIPLE: [],
                LAYER_JUDGMENT: [], LAYER_TEMPLATE: []}
    for c in admitted:
        by_layer.setdefault(c.layer, []).append(c)

    def slim(c):
        return {"object_id": c.object_id, "layer": c.layer,
                "relation": c.relation or "",
                "temporal_status": c.temporal_status or CURRENT,
                "channels": sorted(c.channels),
                "channel_ranks": dict(c.channel_ranks),
                "fusion_score": c.fusion_score,
                "rerank_score": c.rerank_score,
                "final_score": c.final_score,
                "pinned": c.pinned}

    legis = by_layer.get(LAYER_LEGISLATION, [])
    packet_issues = []
    for iss in issues:
        packet_issues.append({
            "issue": iss.get("title") or iss.get("id"),
            "governing_legislation": [slim(c) for c in legis
                                      if c.relation not in EXCEPTION_RELATIONS],
            "judicial_interpretation": [slim(c) for c in by_layer.get(LAYER_PRINCIPLE, [])],
            "exceptions_and_procedure": [slim(c) for c in admitted
                                         if c.relation in EXCEPTION_RELATIONS
                                         or c.relation in PROCEDURAL_RELATIONS],
            "full_judgments": [slim(c) for c in by_layer.get(LAYER_JUDGMENT, [])],
        })

    temporal_flags = [slim(c) for c in admitted
                      if c.temporal_status and c.temporal_status != CURRENT]
    blocks = []
    for lay in (LAYER_LEGISLATION, LAYER_PRINCIPLE, LAYER_JUDGMENT, LAYER_TEMPLATE):
        for c in by_layer.get(lay, []):
            t = texts.get(c.object_id)
            if t:
                blocks.append(render_block(c, t))
    packet = {
        "issues": packet_issues,
        "temporal_flags": temporal_flags,
        "conflicts": conflicts or [],
        "counts": {lay: len(v) for lay, v in by_layer.items() if v},
        "provenance": [slim(c) for c in admitted],
    }
    return packet, "\n\n".join(blocks)
