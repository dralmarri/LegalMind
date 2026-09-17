#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.4B — PHASE 0: Independent Holdout (مجمَّد، غير مُشغَّل بعد).

**تحذير إلزامي:** هذا الملف لا يُستورَد ولا يُشغَّل ولا تُحسَب نتائجه في أي مكان حتى PHASE 4
(بعد اكتمال Gold Set40 + استقرار 5x + تجميد كامل). أُلِّف بمعزل تام عن Gold Set40 — لا اطلاع
على `required_dimensions`/`must_find`/قوائم إخفاقات P2.1-P2.3/سلطات أُنقذت أو فُقدت/صياغة أي
حالة Gold Set. الأمثلة كلها جديدة (لا إعادة صياغة لأمثلة `p24b_dev_set.py`) ولم تُشغَّل ضد
`p24b_concept_backbone.recognize()` إطلاقًا قبل التجميد — التنبؤات في `expected_dependencies`
حكم قانوني/لغوي يدوي بحت، لا نتيجة اختبار.

**فئات الأمثلة:** unseen_positive (نظير جديد بمفردات مغطاة)، morphological_variant (صيغة
صرفية مختلفة: مثنى/جمع/ضمائر متصلة)، hard_negative، neighboring، ambiguous، negation (يُختبَر
القصور الموثَّق عمدًا — لا يُصلَح)، negative_control (الخمسة المطلوبة صراحة: شيك بلا مطالبة،
نسب شكلي غير قانوني، نسبة/نسبه، قاضٍ بلا مسألة رد، زواج بلا إنكار/نزاع).

**ملاحظة منهجية:** بعض الأمثلة تتعمَّد اختبار مفردات **غير مغطاة إطلاقًا** بالقواعد الحالية
(مرادفات مثل «يتصل/يتنصل» بدل «ينكر»، أو «لا يعترف» بدل جذر الإنكار، أو أشكال الهمزة مثل
«الأزواج») — `expected_dependencies` يعكس **الحكم القانوني الصحيح** بصرف النظر عن قدرة
القواعد الحالية على اكتشافه؛ الغرض تحديدًا كشف حدود التعميم الحقيقية لا تصنُّع نتيجة مثالية.
حقل `notes` يوثِّق التوقع المسبق لسبب الفشل إن وُجد — **تنبؤ مسجَّل مسبقًا لا تبريرًا لاحقًا**."""

HOLDOUT_SET = [
    # ============ JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK ============
    {"text": "يطعن المحكوم عليه في الحكم لأن القاضي كان قريبًا لخصمه إلى الدرجة الثالثة.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "unseen_positive"},
    {"text": "الدائرة المشكَّلة من ثلاثة قضاة، أحدهم صهر لأحد المتقاضين في الدعوى.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "morphological_variant",
     "notes": "قضاة (جمع) + صهر — تجب مطابقتها إن كانت القواعد تعمم على الجمع كما صُمِّمت."},
    {"text": "لماذا لم يُفصح القاضي عن مصلحته الشخصية في موضوع الدعوى قبل أن يبدأ نظرها؟",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "unseen_positive"},
    {"text": "قرابته لأحد الخصوم معروفة للجميع في أروقة المحكمة منذ سنوات.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "morphological_variant",
     "notes": "قرابته (لاحق ملكية) بلا كلمة قاضٍ صريحة — يتوقَّع عدم التفعيل فعليًا لغياب _JUDGE_WORDS رغم أن السياق يوحي بذلك؛ ثغرة تعميم صادقة لا خطأ ترميز."},
    {"text": "تنحّى القاضي طوعًا عن نظر الدعوى دون أن يتقدَّم أي من الخصوم بطلب رد ضده.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "unseen_positive"},
    {"text": "تقدَّم الوكيل بطلب لاستبعاد القاضي لأنه كان قد أفتى سابقًا في ذات موضوع النزاع.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "ambiguous",
     "notes": "سبب رد حقيقي (م102-و) لكن بمفردة «أفتى» غير المغطاة في _DISQUAL_WORDS — يُتوقَّع فقد اكتشاف (FN) صادق يكشف حدود التغطية المعجمية للمفهوم لا خطأ تصميم."},
    {"text": "استمع القاضي لمرافعة المحامي طويلًا قبل أن يفصل في الطلب العارض المقدَّم.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "بين المحامي والقاضي زمالة دراسية قديمة أيام الجامعة لم تُذكر في أي مذكرة.",
     "expected_dependencies": [], "category": "hard_negative",
     "notes": "زمالة ليست من كلمات _DISQUAL_WORDS — يُختبَر عدم التفعيل الكاذب على علاقة غير مشمولة."},
    {"text": "طلب أحد الخصوم استبعاد المترجم المحلَّف عن الدعوى لعدم حياده في نقل الشهادة.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "اعترض الدفاع على أحد الخبراء الفنيين المنتدبين لصلته السابقة بأحد الأطراف.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "أصدرت الدائرة حكمها بإلزام المدعى عليه بالمبلغ المطالَب به مع الفائدة القانونية.",
     "expected_dependencies": [], "category": "negative_control",
     "notes": "قاضٍ/دائرة مذكورة بلا أي مسألة رد أو عدم صلاحية — ضابطة سلبية صريحة كما طُلب."},
    {"text": "أقاربهم يعملون جميعًا في وزارة العدل، لكن لا علاقة لأحد منهم بنظر هذه الدعوى تحديدًا.",
     "expected_dependencies": [], "category": "morphological_variant",
     "notes": "أقاربهم (جمع بلاحق ملكية) بلا كلمة قاضٍ صريحة — يختبر جانب الشرط الآخر من AND."},

    # ============ CHEQUE_SUBSTANTIVE_RULES_CHECK / CHEQUE_LIMITATION_CHECK ============
    {"text": "استلم الدائن عدة شيكات من المدين ولم يتمكن من صرف أي منها لعدم وجود رصيد كافٍ.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"], "category": "unseen_positive"},
    {"text": "يسعى حامل الشيك إلى استرداد كامل قيمته بعد رفض المصرف الوفاء به عند التقديم.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"], "category": "unseen_positive"},
    {"text": "حرَّر التاجر شيكين متتاليين لصالح المورِّد ورفض البنك صرف كليهما لعدم كفاية الرصيد.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"], "category": "morphological_variant",
     "notes": "شيكين (مثنى) — يختبر تعميم مطابقة البادئة «شيك» على المثنى."},
    {"text": "شيكه الأخير ارتد لعدم كفاية الرصيد، فطالبه الدائن بقيمته كاملة على الفور.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"], "category": "morphological_variant",
     "notes": "شيكه (لاحق ملكية) — يختبر التعميم على الصيغة الملكية للشيك."},
    {"text": "تجاوزت المدة القانونية للمطالبة بقيمة الشيك، فهل ما زال بإمكاني رفع دعوى إثراء بلا سبب؟",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"], "category": "unseen_positive"},
    {"text": "احتفظ المستأجر بشيكات التأمين لدى المالك دون أي نية لصرفها خلال مدة عقد الإيجار.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "أرسل العميل صورة من الشيك للتأكد من صحة البيانات المدوَّنة عليه فقط لا أكثر.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "يطالب الدائن بقيمة سند إذني موقَّع من المدين لم يوفِ باستحقاقه في موعده.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "رفض البنك تنفيذ حوالة مصرفية داخلية بسبب نقص في البيانات المطلوبة لإتمامها.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "أرفق المدعي صورة الشيك ضمن مستندات الدعوى كدليل إثبات للعلاقة التعاقدية فقط، دون طلب الحكم بقيمته.",
     "expected_dependencies": [], "category": "negative_control",
     "notes": "شيك مذكور بلا مطالبة فعلية — ضابطة سلبية صريحة؛ قد يفشل النظام هنا (بلا حرف نفي حتى) لوجود كلمة «إثبات» غير المرتبطة بمطالبة الشيك — يُترقَّب."},
    {"text": "لم يُطالب حامل الشيك بقيمته حتى الآن رغم ارتداده منذ عدة أشهر متتالية.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"], "category": "negation",
     "notes": "نزاع شيك حقيقي وقائم فعليًا (شيك مرتد لم يُطالَب به بعد) رغم صياغة النفي — الحاجة القانونية حقيقية (التقادم بالذات وثيق الصلة)، بخلاف أمثلة النفي في دفتر التطوير التي وصفت غياب أي نزاع من الأساس؛ يُتوقَّع أن يُفعَّل صدفةً هنا رغم صياغة النفي (كيس الكلمات لا يميّز الحالتين أصلًا)."},
    {"text": "الشيك مصرفي مضمون الدفع بالكامل ولا وجود لأي نزاع حول صرفه بين الطرفين.",
     "expected_dependencies": [], "category": "ambiguous",
     "notes": "شيك بلا نزاع فعلي — يُتوقَّع تفعيل كاذب (عمى النفي/غياب النزاع الموثَّق) لوجود «صرف»."},

    # ============ LINEAGE_COMMITTEE_MANDATORY_REVIEW ============
    {"text": "يسعى الأب إلى إثبات بنوة ابنه المولود خارج إطار زواج موثَّق رسميًا بين والديه.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "unseen_positive"},
    {"text": "رفعت الأم دعوى لإثبات نسب طفلها إلى والده البيولوجي بعد رفضه الاعتراف به.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "unseen_positive"},
    {"text": "الشقيقان يطالبان بإثبات نسبهما لوالدهما المتوفى حديثًا للحصول على نصيبهما من الميراث.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "morphological_variant",
     "notes": "نسبهما (مثنى ملكية) — مغطاة صراحة في _LINEAGE_RE."},
    {"text": "تريد نفي نسبها عن الرجل الذي تزوجته أمها لاحقًا بعد انفصالها عن والدها الحقيقي.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "morphological_variant",
     "notes": "نسبها — مغطاة صراحة في _LINEAGE_RE."},
    {"text": "هل يمكن رفع دعوى نسب مباشرة أمام المحكمة دون المرور على أي جهة إدارية مختصة أولًا؟",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "unseen_positive"},
    {"text": "ينتمي الطرفان إلى نفس القبيلة والعائلة الكبيرة، لكن لا نزاع قضائي بينهما بهذا الخصوص.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "تطالب الوالدة بحضانة أبنائها الثلاثة بعد واقعة الطلاق التي وقعت بينها وبين زوجها.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "نسبة الحضور في جلسات المحكمة كانت ضعيفة هذا الشهر مقارنة بالشهر الماضي.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "نسبة الحضور في الجلسة كانت ضعيفة، وطلب المحامي إثبات ذلك رسميًا في محضر الجلسة.",
     "expected_dependencies": [], "category": "negative_control",
     "notes": "ضابطة سلبية «نسبة مقابل نسبه»: «نسبة» + «إثبات» — يُتوقَّع تفعيل كاذب بسبب تصادم ة/ه الموثَّق سلفًا؛ هذا هو الاختبار المباشر لتعميم تلك الثغرة المعروفة على جملة جديدة."},
    {"text": "التحليل المقدَّم نسبي تمامًا ولا يصلح دليلًا قاطعًا لإثبات أي شيء أمام القضاء.",
     "expected_dependencies": [], "category": "negative_control",
     "notes": "ضابطة سلبية: «نسبي» (صفة) + «إثبات» — يُتوقَّع عدم التفعيل لأن التعبير الدقيق يستبعد «نسبي» عمدًا (لا ينتهي بلاحق ملكية مقبول)."},
    {"text": "تنازلت الأسرة عن كل مطالبة بنسب الطفل بعد التصالح الودي التام بين الطرفين المعنيين.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "ambiguous",
     "notes": "بنسب (بحرف الجر «ب» ملتصقًا) — يُتوقَّع فقد اكتشاف (FN) لأن `_strip_al` ينزع «ال» فقط لا حروف الجر المفردة (ب/ل/ك/و)؛ ثغرة تعميم صادقة."},
    {"text": "الأبناء الثلاثة يطلبون إثبات نسبهم لوالدهم المتوفى حديثًا في دعوى واحدة مشتركة.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "morphological_variant",
     "notes": "نسبهم — مغطاة صراحة في _LINEAGE_RE."},

    # ============ MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK ============
    {"text": "عقدا زواجًا عرفيًا بينهما، والزوج الآن يتنصَّل تمامًا من الاعتراف بوقوعه أصلًا.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "unseen_positive",
     "notes": "«يتنصَّل» مرادف دلالي لا معجمي لجذر الإنكار المغطى (نكر/جحد) — يُتوقَّع فقد اكتشاف (FN) صادق."},
    {"text": "بعد نشوء الخلاف المالي بينهما، بدأ الزوج بإنكار قيام رابطة الزوجية بينهما أصلًا.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "unseen_positive"},
    {"text": "الأزواج الثلاثة في القضايا المتشابهة أنكروا جميعًا وقوع الزواج العرفي المدَّعى به.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "morphological_variant",
     "notes": "«الأزواج» (جمع، بعد نزع الهمزة يصبح «ازواج») لا يبدأ بـ«زواج» الكانونية — يُتوقَّع فقد اكتشاف (FN) بسبب فارق الهمزة، رغم وجود «أنكروا» (جذر نكر) في نفس الجملة."},
    {"text": "تنكرها زوجته أمام القاضي رغم إقراره الكتابي بها في محضر رسمي سابق.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "morphological_variant",
     "notes": "تنكرها (فعل مضارع بلاحق ضمير) — يختبر مطابقة الاحتواء على تصريف مختلف."},
    {"text": "هل تُقبل دعوى الزوجية إذا كان الطرف الآخر لا يعترف بوجود أي علاقة زواج بينهما؟",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "ambiguous",
     "notes": "«لا يعترف» مرادف دلالي للإنكار لكن بجذر مختلف تمامًا (عرف لا نكر) — يُتوقَّع فقد اكتشاف (FN) صادق يكشف حدود التغطية المعجمية."},
    {"text": "تزوَّجا بعقد رسمي موثَّق لدى الجهات المختصة، ولا خلاف بينهما على قيامه إطلاقًا.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "طلبت الزوجة التطليق للضرر مع إقرارها الكامل الصريح بقيام رابطة الزوجية بينهما.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "ينكر المستأجر توقيعه على عقد الإيجار المقدَّم من المؤجر ضمن مستندات الدعوى.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "جحد الوريث نصيب أخيه في التركة رغم وضوح الأنصبة الشرعية المقرَّرة قانونًا.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "استقر الزوجان على تسوية النزاع المالي بينهما وديًا دون اللجوء إلى القضاء إطلاقًا.",
     "expected_dependencies": [], "category": "negative_control",
     "notes": "زواج مذكور بلا أي إنكار أو نزاع على قيامه — ضابطة سلبية صريحة كما طُلب."},
    {"text": "لم تنكر الزوجة قط وجود رابطة الزواج بينهما رغم كل الخلافات التي مرّا بها معًا.",
     "expected_dependencies": [], "category": "negation",
     "notes": "نفي صريح للإنكار (لا إنكار حقيقيًا قائمًا) — يُتوقَّع تفعيل كاذب (عمى النفي، مطابق تمامًا لنمط دفتر التطوير) لأن «تنكر» يحوي جذر «نكر» بصرف النظر عن «لم» السابقة له."},
    {"text": "أقرَّ الزوج بالزواج مبدئيًا ثم عاد لينكره تمامًا بعد جلسة التسوية الأولى بينهما.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "ambiguous",
     "notes": "إنكار لاحق حقيقي رغم إقرار سابق — «لينكره» يحوي جذر نكر فيُتوقَّع اكتشاف صحيح."},
]

if __name__ == "__main__":
    # طباعة العدّ والتوزيع فقط — صفر استدعاء لـ recognize() هنا أو في أي مكان آخر قبل PHASE 4.
    from collections import Counter
    print(f"HOLDOUT_SET size = {len(HOLDOUT_SET)}")
    print(Counter(ex["category"] for ex in HOLDOUT_SET))
