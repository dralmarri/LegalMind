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
from .temporal import CURRENT, CONFLICT_DETECTED, SUPERSEDED, TRANSITION_VERIFIED

# سقوف نص المصدر — **مطابقة حرفيًا لسقوف الإنتاج** (`admin/app.py: caps`).
# سببها مقيس: بلا قصّ ينفق v2 ميزانية الـ85,000 نفسها على 46 مصدرًا لكل حالة
# بدل 104 في خط الأساس (انخفاض 56% في السلطات المقبولة) — وهو ما أسقط
# Legislative must-recall من 0.750 إلى 0.667 في التشغيل الحي. الإصلاح في
# استهلاك الميزانية لا في شراء سعة إضافية: الميزانية والعمق لم يتغيّرا.
CAPS = {LAYER_LEGISLATION: 2200, LAYER_PRINCIPLE: 1400,
        LAYER_JUDGMENT: 3500, LAYER_TEMPLATE: 3500}


def clip_text(layer, text):
    """يقصّ نص المصدر بسقف نوعه — بمنطق الإنتاج نفسه حرفيًا.

    يحفظ سطر السند الختامي («الطعن … جلسة …») كي لا يضيع موضع النشر من ذيل
    المبدأ، ويرتدّ لآخر جملة مكتملة بدل البتر وسط الكلام."""
    t = text or ""
    cap = CAPS.get(layer, 2000)
    if len(t) <= cap:
        return t
    tail = t.rstrip().rsplit("\n", 1)[-1]
    keep = ("\n[…]\n" + tail) if (("الطعن" in tail or "جلسة" in tail)
                                   and len(tail) < 400) else ""
    cut = t[:cap]
    dot = max(cut.rfind("."), cut.rfind("؟"), cut.rfind("!"))
    if dot > int(cap * 0.6):
        cut = cut[:dot + 1]
    return cut + ("" if keep else "\n[…]") + keep


def block_chars(layer, text):
    """حجم الكتلة كما ستُطبع فعلًا — تُحتسب عليه الميزانية.

    وحدة واحدة للقياس والطباعة معًا: أي انفصال بينهما يعيد العيب نفسه."""
    return len(clip_text(layer, text)) + 220

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
    warn = temporal_warning(c)
    body = clip_text(c.layer, t.get("text"))
    return ("<مصدر " + " ".join(attrs) + ">\n" + warn + body + "\n</مصدر>")


def temporal_warning(c):
    """تحذير صريح داخل الكتلة نفسها، لا في وسم يسهل تجاوزه.

    القاعدة (البند 8): المبدأ الذي يقتبس نصًا عُدِّل **لا يُحذف** — يبقى نافعًا
    فيما لم يمسّه التعديل — لكن **الجزء المتجاوَز زمنيًا يُوسَم** فلا يُقدَّم
    التفصيل القديم بوصفه القانون النافذ."""
    st = getattr(c, "temporal_status", "") or ""
    if st == CONFLICT_DETECTED:
        cf = getattr(c, "temporal_conflict", None) or {}
        parts = []
        for cl in (cf.get("clashes") or [])[:3]:
            parts.append("هذا المصدر يذكر %d %s بينما النص النافذ للمادة %s يذكر %s"
                         % (cl["principle_value"], cl["unit"],
                            cf.get("article_id", ""),
                            " أو ".join(str(v) for v in cl["article_values"])))
        return ("[⚠ تحذير زمني — لا تقدّم التفصيل القديم بوصفه النافذ: "
                + "؛ ".join(parts) + ". ما عدا هذه النقطة يبقى المبدأ صالحًا "
                "للاستشهاد.]\n") if parts else ""
    if st == SUPERSEDED:
        return ("[⚠ هذا المصدر موسوم ملغى/مستبدَل في القاعدة — لا يُستشهد به "
                "بوصفه نافذًا.]\n")
    if st == TRANSITION_VERIFIED:
        return ("[ℹ القاعدة تحمل سند انتقال لهذا المصدر — تحقّق من النص النافذ "
                "قبل الاستشهاد بالتفصيل.]\n")
    return ""


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
        "conflict_flags": [c for c in (conflicts or [])
                           if c.get("flag") == "POTENTIAL_AUTHORITY_CONFLICT"],
        "counts": {lay: len(v) for lay, v in by_layer.items() if v},
        "provenance": [slim(c) for c in admitted],
    }
    return packet, "\n\n".join(blocks)
