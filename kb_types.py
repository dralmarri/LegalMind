# -*- coding: utf-8 -*-
"""مصدر مركزي واحد authoritative لتصنيف object_type عبر كل قنوات الاسترجاع
(P0-1، 2026-09-10) — بأمر صريح من المالك بعد تدقيق Phase 1 أثبت أن
legislation/legislation_archived (2,606 + 307 = 2,913 صفًا، ~4.7% من القاعدة)
مستبعدان جزئيًا من عدة قنوات (المعجمي، الاستشهاد الصريح، سد الفجوة، MCP)
بسبب allowlists متكررة يدويًا في 7 أماكن مختلفة اختلفت عرضًا لا تصميمًا.
كل قناة تستورد من هنا فقط من الآن — لا تُكرَّر هذه القوائم يدويًا في أي ملف آخر.

تحقق حي (تدقيق 2026-09-10، audit3/audit6): ~5% فقط من صفوف legislation
(135 من 2,606، شكل معرّف LEG-{رقم}-{مادة}-hash) تتداخل مع محتوى legis-*
موجود أصلًا (خدمة وطنية 20/2015، حقوق مؤلف 75/2019...)؛ البقية (~95%، وكل
legislation_archived) محتوى تنظيمي متخصص حقيقي غير مكرر إطلاقًا — تعليمات
البنك المركزي لكفاية رأس المال ولوائح هيئة أسواق المال، فرع تجاري بمعظمه —
لم يكن قابلًا للاسترجاع عمليًا في أغلب القنوات قبل هذه الرقعة."""

LEGISLATION_TYPES = (
    "legislation_article", "legislation", "legislation_issuing_article",
    "legislation_preamble", "legislation_archived",
)
PRINCIPLE_TYPES = ("judicial_principle", "judicial_principles_collection")
JUDGMENT_TYPES = ("full_judgment",)
TEMPLATE_TYPES = ("judicial_template",)
ALL_TYPES = LEGISLATION_TYPES + PRINCIPLE_TYPES + JUDGMENT_TYPES + TEMPLATE_TYPES

# كل قناة استرجاع تستعمل الآن نفس المجموعة — لا اختلاف عرضي بين القنوات بعد اليوم
LEXICAL_TYPES = LEGISLATION_TYPES
DIRECT_CITATION_TYPES = LEGISLATION_TYPES
GAP_SEARCH_TYPES = LEGISLATION_TYPES + PRINCIPLE_TYPES
MCP_LEGISLATION_TYPES = LEGISLATION_TYPES


def is_legislation_type(object_type):
    return object_type in LEGISLATION_TYPES


def is_principle_type(object_type):
    return object_type in PRINCIPLE_TYPES


# لواحق معرفات معروفة تاريخيًا لكائنات تشريعية — تصنيف شكل المعرّف فقط (لا بديل
# عن عمود object_type)؛ يُستعمل حصرًا حيث يُفحص شكل المعرّف مباشرة بلا استعلام
# قاعدة بيانات (كتصنيف سريع في البطارية). LEG-* أشكال غير منتظمة (بعضها رقمي
# نظيف legis-style، وبعضها صفحات/فصول عربية) فلا يُشتق منها رقم مادة أو قانون
# موثوق — استُعملت هنا فقط للتصنيف الثنائي (تشريع أم لا)، لا لاستخراج رقم
# قانون أو مادة. القناة الوحيدة القادرة على استخراج رقم/قانون تبقى محصورة
# بالأشكال legis-*/regl-*/lreg-* التي تتبع نمط prefix+"m"+N (حدٌّ معياري موثّق
# — انظر تقرير التدقيق قبل الرقعة).
LEGISLATION_ID_PREFIXES = ("legis-", "LEG-", "regl-", "lreg-")


def is_legislation_id(object_id):
    return bool(object_id) and object_id.startswith(LEGISLATION_ID_PREFIXES)
