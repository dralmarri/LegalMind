# -*- coding: utf-8 -*-
"""قبول السلطات: حدٌّ أدنى محميٌّ لكل طبقة + سعةٌ فائضة مشتركة.

الخلفية المقيسة (P2.7-O و Post-O): الحجز الصلب `9/9/2 بلا إعادة تخصيص` منع
الإزاحة بين الأنواع بنجاح تام (صفر إزاحة، تعايش 5/5) لكنه **خلّف 14 مقعدًا
ميتًا مقابل 150 مرشحًا قضائيًا مؤهلًا أُسقط** — ومنها سلطتان اجتازتا تقييم
العلاقة. وفي المقابل أثبت القياس أن `GLOBAL_POOL` بلا أي حماية **أسوأ**:
تنقلب التركيبة (قضائي 17–18 مقابل تشريعي 2–3) فتعود الإزاحة بعينها.

فالتصميم المعتمد هنا وسطٌ **مشتق من الرقمين معًا لا من هدف فاشل**:

  المرحلة 1 — كل طبقة تملأ **حدَّها الأدنى المحمي** من مرشحيها وحدهم. لا طبقة
              تلمس الحدَّ المحمي لطبقة أخرى، أبدًا. (هذا يحفظ مكسب O.)
  المرحلة 2 — ما تبقّى من السعة الكلية **مشترك**، يُوزَّع بالدرجة النهائية على
              كل الطبقات معًا. (هذا يحلّ عيب المقاعد الميتة.)
  وقاعدة التحرير: الحدُّ المحمي لطبقة **نفدت مرشحاتها** يُحرَّر إلى المشترك —
              لأن المقعد المحمي يحمي من المزاحمة، لا من الاستعمال حين لا يوجد
              من يزاحم عليه أصلًا. هذا بالضبط ما كان يعطّل مقاعد الأحكام
              العشرة في O بلا أي مستفيد.

الحدود المحمية **ليست منتقاة لإنقاذ هدف**: هي نسبة ثابتة من ميزانية الإنتاج
القائمة (`LBL_BUDGET` بنسبتها الموثقة 48k:24k:8k:5k)، والنسبة المعلنة قبل أي
قياس هي 0.5 — نصف السعة محميّ ونصفها مشترك. تُقاس الحساسية على 0.3/0.5/0.7
ويُعلَن الفرق بدل اختيار قيمة بعد رؤية النتيجة."""

from .model import LAYER_LEGISLATION, LAYER_PRINCIPLE, LAYER_JUDGMENT, LAYER_TEMPLATE

# ميزانية الإنتاج القائمة حرفيًا (admin/app.py ‏LBL_BUDGET) — مجموعها 85,000 حرفًا.
# حجم السياق النهائي **ثابت**: ما يتوسّع هو تجمّع المرشحين لا ما يصل النموذج.
PRODUCTION_BUDGET = {
    LAYER_LEGISLATION: 48000,
    LAYER_PRINCIPLE:   24000,
    LAYER_JUDGMENT:     8000,
    LAYER_TEMPLATE:     5000,
}
PROTECTED_FRACTION = 0.5

# سقف أعلى لكل طبقة — يحدّ نصيبها من **الفائض المشترك**، والحدّ المحمي يبقى كما هو.
# سببه مقيس: بلا سقف التهمت الأحكام (3,500 حرفًا للكتلة) والنماذج حصةَ التشريع،
# فارتفعت الأحكام 30→139 والنماذج 18→61 بينما هبط التشريع 1,391→514 والمبادئ
# 425→308. القيم معلَنة لا مضبوطة على هدف: التشريع والمبادئ بميزانية الإنتاج
# كاملةً، والأحكام **ضعف** ميزانية الإنتاج (مكسب قضائي مقصود لكنه محدود)،
# والنماذج عند حدّها المحمي فقط لأنها **غير قابلة للاستشهاد** أصلًا.
LAYER_CEILING = {
    LAYER_LEGISLATION: 48000,
    LAYER_PRINCIPLE:   24000,
    LAYER_JUDGMENT:    16000,
    LAYER_TEMPLATE:     2500,
}


def build_floors(total_budget=None, fraction=PROTECTED_FRACTION):
    b = dict(total_budget or PRODUCTION_BUDGET)
    return {k: int(v * fraction) for k, v in b.items()}


def admit(candidates, block_size_of, budget=None, fraction=PROTECTED_FRACTION):
    """يقبل المرشحين ضمن ميزانية الأحرف نفسها بسياسة الحد المحمي + الفائض.

    `candidates` مرتَّبة تنازليًا بالدرجة النهائية.
    `block_size_of(candidate) -> int` حجم كتلة المصدر بالأحرف (أو None فيُستبعد
    بمرحلة `no_text`).
    يعيد (admitted, report) ويضع `drop_stage` على كل مرشح ساقط."""
    budget = dict(budget or PRODUCTION_BUDGET)
    total = sum(budget.values())
    floors = build_floors(budget, fraction)
    used = {k: 0 for k in budget}
    admitted, total_used = [], 0

    def take(c, size, stage):
        nonlocal total_used
        c.admitted = True
        c.drop_stage = ""
        used[c.layer] = used.get(c.layer, 0) + size
        total_used += size
        admitted.append((c, stage))

    sizes, pending = {}, []
    for c in candidates:
        s = block_size_of(c)
        if s is None:
            c.drop_stage = "no_text"
            continue
        sizes[c.object_id] = s
        pending.append(c)

    # المرشح المثبَّت (استشهاد صريح من المستخدم) يسبق كل شيء ولا يُقصّ
    order = sorted(pending, key=lambda c: (not c.pinned, -c.final_score, c.object_id))

    # --- المرحلة 1: الحدود المحمية، كلٌّ من مرشحيه وحدهم ---
    left = []
    for c in order:
        s = sizes[c.object_id]
        fl = floors.get(c.layer, 0)
        if used.get(c.layer, 0) + s <= fl and total_used + s <= total:
            take(c, s, "protected_floor")
        else:
            left.append(c)

    # --- تحرير الحدود غير المستعمَلة لطبقات نفدت مرشحاتها ---
    still_wanting = {c.layer for c in left}
    released = 0
    for lay, fl in floors.items():
        if lay not in still_wanting:
            released += max(0, fl - used.get(lay, 0))

    shared_total = (total - sum(floors.values())) + released
    shared_used = 0

    # سقفُ طبقةٍ **لا مرشح لها إطلاقًا** يُوزَّع على الطبقات الحاضرة بنسبة سقوفها
    # — بنفس منطق تحرير الحدّ المحمي أعلاه، ولنفس السبب: ما لا طالب له لا يُجمَّد.
    # والتوزيع مقصورٌ على الطبقات **الغائبة كليًا** فلا يفتح بابًا لاحتكار طبقةٍ
    # حاضرةٍ نصيبَ أخرى حاضرة (وهو ما منعه السقف أصلًا).
    ceilings = dict(LAYER_CEILING)
    present = {c.layer for c in pending}
    absent_cap = sum(v for k, v in ceilings.items() if k not in present)
    if absent_cap:
        live = {k: v for k, v in ceilings.items() if k in present}
        tot_live = sum(live.values()) or 1
        for k, v in live.items():
            ceilings[k] = v + int(absent_cap * v / tot_live)

    # --- المرحلة 2: السعة المشتركة، بالدرجة عبر كل الطبقات، بسقف لكل طبقة ---
    for c in left:
        s = sizes[c.object_id]
        ceil = ceilings.get(c.layer)
        if ceil is not None and used.get(c.layer, 0) + s > ceil:
            c.drop_stage = "layer_ceiling"   # الطبقة بلغت سقفها، ولا تزاحم غيرها
            continue
        # لا يجوز أن يتعدى أي مرشح على حدٍّ محميٍّ لطبقة أخرى ما زالت تطلبه
        if shared_used + s > shared_total or total_used + s > total:
            c.drop_stage = "shared_overflow_full"
            continue
        shared_used += s
        take(c, s, "shared_overflow")

    # السقف لا يُحرَّر بعد ذلك: كل صيغة تحرير جرّبتُها أعادت الاحتكار (قيس:
    # الأحكام أخذت 33,480 ثم 22,320 من سقف 16,000). التوزيع الوحيد المسموح هو
    # نصيبُ طبقةٍ غائبة كليًا، وقد جرى قبل المرحلة 2.
    report = {
        "total_budget": total,
        "protected_fraction": fraction,
        "floors": floors,
        "used_by_layer": used,
        "released_unused_floor": released,
        "layer_ceiling": ceilings,
        "shared_capacity": shared_total,
        "shared_used": shared_used,
        "admitted_count": len(admitted),
        "admitted_by_layer": {},
        "admitted_by_stage": {},
        "dropped_by_stage": {},
        "dead_capacity": total - total_used,
    }
    for c, stage in admitted:
        report["admitted_by_layer"][c.layer] = report["admitted_by_layer"].get(c.layer, 0) + 1
        report["admitted_by_stage"][stage] = report["admitted_by_stage"].get(stage, 0) + 1
    for c in candidates:
        if not c.admitted and c.drop_stage:
            report["dropped_by_stage"][c.drop_stage] = report["dropped_by_stage"].get(c.drop_stage, 0) + 1
    return [c for c, _ in admitted], report
