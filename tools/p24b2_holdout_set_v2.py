#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.5 — Experiment B2-R: Independent Holdout v2. **مجمَّدة — لا تُفتح إلا مرة واحدة بعد
التجميد، ولا تُعدَّل أو تُستخدم في أي تكرار تصميم لاحق.**

جُمَل جديدة كليًا — صفر إعادة استعمال لأي جملة من `p24b_holdout_set.py` (Holdout v1) أو
`p24b2_dev_set_v2.py` (Dev Set v2)، وصفر اقتباس لصياغاتها الحرفية. تغطي لكل مفهوم من
المفاهيم الأربعة: نظائر إيجابية، صيغ صرفية، نفي، نقائض حادة، مسائل مجاورة، حالات ملتبسة،
وصياغة عامية قصيرة؛ + الأزواج الستة كلها من تصادم بين-مفهومي (C(4,2)=6)؛ + أربعة أسئلة
مركَّبة طويلة (واحد لكل مفهوم)؛ + ستة ضوابط سلبية من مجالات قانونية غير ذات صلة إطلاقًا
(إيجار، جزائي، تعويض مدني، إداري، عمالي، شركات) لقياس الدقة على ضجيج واقعي متنوع.

كل مثال يحمل `provenance` صريحة. لا مرجع لأي معرِّف حالة/سلطة/Gold Set في أي قاعدة هنا."""

HOLDOUT_SET_V2 = [
    # ============ JUDICIAL_DISQUALIFICATION ============
    {"text": "علم الخصم أن أحد أعضاء الهيئة القضائية الناظرة لقضيته هو ابن عم زوجته، فبادر بتقديم طلب لرده.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "positive",
     "provenance": "holdout_v2_new"},
    {"text": "كشفت المذكرة أن أحد المستشارين في الدائرة كان قد قدَّم استشارة قانونية لأحد طرفي النزاع قبل سنوات.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "positive",
     "provenance": "holdout_v2_new"},
    {"text": "قضاة الاستئناف الثلاثة تربطهم مصاهرة مباشرة بأحد أطراف الطعن المنظور أمامهم.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "morphological_variant",
     "provenance": "holdout_v2_new — جمع قضاة + مصاهرة"},
    {"text": "لم يثبت أي رابط قرابة أو مصلحة بين القاضي وأي من طرفي الخصومة المعروضة عليه.",
     "expected_dependencies": [], "category": "negation", "provenance": "holdout_v2_new"},
    {"text": "أجَّل القاضي الجلسة القادمة بناءً على طلب مشترك من الطرفين لتقديم مستندات إضافية.",
     "expected_dependencies": [], "category": "hard_negative", "provenance": "holdout_v2_new"},
    {"text": "طعن الدفاع في حياد الخبير الهندسي المنتدب لصلته العائلية بأحد أطراف الدعوى.",
     "expected_dependencies": [], "category": "neighboring", "provenance": "holdout_v2_new — خبير لا قاضٍ"},
    {"text": "يُشاع أن القاضي وأحد المحامين ينتميان لنفس النادي الرياضي منذ زمن طويل.",
     "expected_dependencies": [], "category": "ambiguous",
     "provenance": "holdout_v2_new — علاقة اجتماعية غير مؤهَّلة قانونًا"},
    {"text": "أبغى أطلب رد القاضي لأنه قريب المدعي، شلون أسوي كذا؟",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "colloquial",
     "provenance": "holdout_v2_new — صياغة عامية قصيرة"},

    # ============ CHEQUE_PAYMENT_CLAIM ============
    {"text": "سلَّم البائع المشتري شيكًا بقيمة الصفقة، وعند تقديمه للبنك تبيَّن أن الحساب مغلق.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK"], "category": "positive",
     "provenance": "holdout_v2_new"},
    {"text": "بعد رفض المصرف صرف الشيك، يسأل حامله عن الطريق الأقصر لاسترداد كامل المبلغ المستحق.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK"], "category": "positive",
     "provenance": "holdout_v2_new"},
    {"text": "الشيكات الثلاثة التي حررتها الشركة ارتدت جميعها لعدم كفاية الرصيد.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK"], "category": "morphological_variant",
     "provenance": "holdout_v2_new — جمع شيكات"},
    {"text": "لم يتقدَّم حامل الشيك بأي مطالبة رسمية رغم مرور وقت طويل على تاريخ استحقاقه.",
     "expected_dependencies": [], "category": "negation", "provenance": "holdout_v2_new"},
    {"text": "احتفظت الشركة بدفتر شيكات فارغ ضمن أرشيفها المحاسبي القديم.",
     "expected_dependencies": [], "category": "hard_negative", "provenance": "holdout_v2_new"},
    {"text": "طالب الدائن بتنفيذ الحوالة المصرفية التي تأخر البنك في تحويلها لحسابه.",
     "expected_dependencies": [], "category": "neighboring", "provenance": "holdout_v2_new — حوالة لا شيك"},
    {"text": "الشيك سيُستحق الصرف الشهر القادم ولا يوجد أي نزاع قائم بشأنه حاليًا.",
     "expected_dependencies": [], "category": "ambiguous",
     "provenance": "holdout_v2_new — أجل مستقبلي بلا مطالبة حالية"},
    {"text": "شيكي ارتد وأبي أطالب بحقي بسرعة، وش أسوي؟",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK"], "category": "colloquial",
     "provenance": "holdout_v2_new — صياغة عامية قصيرة"},

    # ============ LINEAGE_ESTABLISHMENT ============
    {"text": "تقدَّمت المرأة بدعوى لإثبات نسب ابنتها إلى الرجل الذي تنكَّر لها بعد الولادة.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "positive",
     "provenance": "holdout_v2_new"},
    {"text": "رغب الشقيقان في نفي نسب أخيهما الأصغر بعد ظهور شكوك حول صحة نسبه لوالدهما.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "positive",
     "provenance": "holdout_v2_new"},
    {"text": "الورثة الأربعة يسعون لإثبات نسبهم جميعًا لجدهم المتوفى ضمن دعوى موحَّدة.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "morphological_variant",
     "provenance": "holdout_v2_new — نسبهم"},
    {"text": "لم يعد الأب يرغب في نفي نسب ابنه بعد اقتناعه التام بنتيجة الفحص الطبي القاطعة.",
     "expected_dependencies": [], "category": "negation",
     "provenance": "holdout_v2_new — اختبار صادق: لا معالجة نفي مصمَّمة لهذا المفهوم بعد "
                   "(قيد معرفي موثَّق)، يُتوقَّع فشل هنا لا إصلاح آني"},
    {"text": "يتقاسم الورثة تركة والدهم دون أي خلاف على صحة نسب أي منهم.",
     "expected_dependencies": [], "category": "hard_negative", "provenance": "holdout_v2_new"},
    {"text": "طلبت الأم الحصول على نفقة أبنائها الثلاثة بعد امتناع والدهم عن الإنفاق عليهم.",
     "expected_dependencies": [], "category": "neighboring", "provenance": "holdout_v2_new — نفقة لا نسب"},
    {"text": "نسبة كبيرة من قضايا النسب المسجَّلة هذا العام تتعلق بحالات زواج غير موثَّق رسميًا.",
     "expected_dependencies": [], "category": "ambiguous",
     "provenance": "holdout_v2_new — تصادم نسبة/نسب في جملة إحصائية عامة لا دعوى فعلية"},
    {"text": "ودي أثبت نسب بنتي بأسرع طريقة ممكنة، الإجراءات وش تكون؟",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "colloquial",
     "provenance": "holdout_v2_new — صياغة عامية قصيرة، فعل «أثبت»"},

    # ============ MARITAL_STATUS_DENIAL ============
    {"text": "بعد وفاة والدها، فوجئت الزوجة بأن أسرة المتوفى تنفي وقوع الزواج بينهما من الأساس.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "positive",
     "provenance": "holdout_v2_new"},
    {"text": "هل يمكن سماع دعوى الزوجية متى كان الطرف الآخر يرفض الاعتراف بوجود أي عقد بينهما؟",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "positive",
     "provenance": "holdout_v2_new"},
    {"text": "الزوجتان كلتاهما أنكرتا قيام أي رابطة زوجية موثَّقة مع المتوفى.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "morphological_variant",
     "provenance": "holdout_v2_new — مثنى زوجتان + فعل مثنى مؤنث"},
    {"text": "لم يجحد الزوج يومًا وجود عقد الزواج بينهما رغم نشوب خلافات مالية حادة بينهما.",
     "expected_dependencies": [], "category": "negation", "provenance": "holdout_v2_new"},
    {"text": "عقد الزواج مسجَّل رسميًا في المحكمة ولا خلاف إطلاقًا بين الطرفين على قيامه.",
     "expected_dependencies": [], "category": "hard_negative", "provenance": "holdout_v2_new"},
    {"text": "أنكر الشريك التجاري توقيعه على اتفاقية الشراكة المبرمة بينه وبين المدعي.",
     "expected_dependencies": [], "category": "neighboring", "provenance": "holdout_v2_new — شراكة لا زوجية"},
    {"text": "الزوجان منفصلان بالأمر الواقع منذ سنوات دون أي طلاق رسمي أو نزاع قضائي قائم بينهما.",
     "expected_dependencies": [], "category": "ambiguous",
     "provenance": "holdout_v2_new — انفصال واقعي بلا إنكار للزوجية نفسها"},
    {"text": "زوجي ينكر إنه متزوجني أصلًا، أقدر أرفع قضية زوجية؟",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "colloquial",
     "provenance": "holdout_v2_new — صياغة عامية قصيرة"},

    # ============ الأزواج الستة من تصادم بين-مفهومي (C(4,2)=6) ============
    {"text": "زوج القاضية تقدَّم بدعوى مطالبة بقيمة شيك مرتد في نزاع تجاري منفصل تمامًا عن عملها.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK"], "category": "cross_concept_pair",
     "pair": "JUDICIAL/CHEQUE",
     "provenance": "holdout_v2_new — اختبار عكس الاتجاه الجندري لصياغة «زوج/زوجة القاضي» "
                   "(دفتر التطوير اختبر «زوجة القاضي» فقط)؛ لا علاقة رد فعلية، والشيك حقيقي منفصل"},
    {"text": "الزوج ينكر قيام الزواج بينهما، وهي تحمل شيكًا موقَّعًا منه تريد المطالبة بقيمته في نزاع مستقل.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK", "CHEQUE_SUBSTANTIVE_RULES_CHECK"],
     "category": "cross_concept_pair", "pair": "CHEQUE/MARITAL",
     "provenance": "holdout_v2_new — مفهومان مستقلان صحيحان معًا بلا مفردات مشتركة"},
    {"text": "زوجة أحد قضاة الدائرة تنكر أمام محكمة أخرى وقوع أي زواج شرعي بينهما.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "cross_concept_pair",
     "pair": "JUDICIAL/MARITAL",
     "provenance": "holdout_v2_new — «زوجة» بتاء مربوطة لا تفتح علاقة القاضي، دعوى الزوجية منفصلة تمامًا"},
    {"text": "القاضي قريب لزوجة أحد الخصوم التي تنكر حاليًا رابطة الزواج بينهما في قضية منفصلة.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK",
                                "MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"],
     "category": "cross_concept_pair", "pair": "JUDICIAL/MARITAL",
     "provenance": "holdout_v2_new — مفهومان صحيحان معًا (قرابة القاضي بزوجة الخصم + نزاع زوجية فعلي منفصل)"},
    {"text": "أحد أعضاء الدائرة قريب لأحد أطراف دعوى إثبات النسب المنظورة أمامهم، وهي دعوى نسب فعلية.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK", "LINEAGE_COMMITTEE_MANDATORY_REVIEW"],
     "category": "cross_concept_pair", "pair": "JUDICIAL/LINEAGE",
     "provenance": "holdout_v2_new — مفهومان صحيحان معًا"},
    {"text": "الأم رفعت دعوى لإثبات نسب طفلها، وفي ذات الوقت تحتفظ بشيك من زوجها السابق دون أي نية للمطالبة به.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "cross_concept_pair",
     "pair": "LINEAGE/CHEQUE",
     "provenance": "holdout_v2_new — الشيك محفوظ بلا مطالبة فعلية، فلا يصح توقُّع CHEQUE"},
    {"text": "يريد إثبات نسب ابنته من جهة، ومن جهة أخرى يطالب بقيمة شيك متعثر السداد في نزاع تجاري منفصل.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW", "CHEQUE_SUBSTANTIVE_RULES_CHECK"],
     "category": "cross_concept_pair", "pair": "LINEAGE/CHEQUE",
     "provenance": "holdout_v2_new — مفهومان مستقلان صحيحان معًا في جملتين مفصولتين بفاصلة"},
    {"text": "جحدت المرأة نسب ابنها الذي أنجبته أثناء زواجها الموثَّق من زوجها الحالي.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "cross_concept_pair",
     "pair": "LINEAGE/MARITAL",
     "provenance": "holdout_v2_new — إنكار موضوعه النسب لا الزوجية (الزواج «موثَّق» صراحة)؛ يُتوقَّع تكرار "
                   "قيد التصادم الدلالي الموثَّق (احتمال FP على MARITAL) — اختبار صادق لا إصلاح مسبق"},

    # ============ أسئلة مركَّبة طويلة (واحد لكل مفهوم) ============
    {"text": "المحامي وكيل المدعى عليه في نزاع عقاري ضخم، وأثناء تحضير الدعوى تبيَّن أن أحد قضاة الدائرة "
             "كان قد سبق أن قدَّم استشارة قانونية مدفوعة الأجر لصالح المدعي قبل توليه القضاء بسنوات، "
             "فتقدَّم فورًا بمذكرة رسمية يطلب فيها استبعاد هذا القاضي تحديدًا من نظر النزاع بأكمله.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "positive",
     "provenance": "holdout_v2_new — سؤال مركَّب طويل"},
    {"text": "أبرم موكلي عقد مقاولة مع شركة إنشاءات، وحصل منها على شيك بقيمة الدفعة الأخيرة، وبعد تقديمه "
             "للبنك في الموعد المحدَّد رفض المصرف صرفه بحجة عدم توفر رصيد كافٍ في حساب الشركة، وهو يسأل "
             "الآن عن أفضل السبل لاسترداد كامل المبلغ المستحق له بأسرع وقت ممكن.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK"], "category": "positive",
     "provenance": "holdout_v2_new — سؤال مركَّب طويل"},
    {"text": "رُزقت المرأة بطفل من علاقة زواج عرفي غير موثَّق رسميًا، وبعد انفصالها عن الرجل رفض الاعتراف "
             "بالطفل أو بصلته به، فتسأل الآن عن الإجراءات الكاملة الواجب اتباعها أمام المحكمة المختصة "
             "لإثبات نسب طفلها إليه رسميًا.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "positive",
     "provenance": "holdout_v2_new — سؤال مركَّب طويل"},
    {"text": "تزوَّجت المرأة من رجل بموجب عقد عرفي بسيط لم يُوثَّق لدى الجهات الرسمية المختصة في حينه، "
             "وبعد سنوات من الحياة الزوجية المشتركة وإنجاب طفلين، بدأ الزوج يتهرَّب من الاعتراف بوجود "
             "هذا الزواج أصلًا كلما طالبته بحقوقها الزوجية والمالية.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "positive",
     "provenance": "holdout_v2_new — سؤال مركَّب طويل"},

    # ============ ضوابط سلبية من مجالات غير ذات صلة إطلاقًا (قياس دقة على ضجيج واقعي) ============
    {"text": "تقدَّم المستأجر بدعوى لإخلاء العين المؤجَّرة بعد امتناع المالك عن صيانة المصعد لعدة أشهر.",
     "expected_dependencies": [], "category": "negative_control", "provenance": "holdout_v2_new — إيجار"},
    {"text": "أُدين المتهم بجريمة السرقة بالإكراه وحُكم عليه بالحبس مع الشغل لمدة ثلاث سنوات.",
     "expected_dependencies": [], "category": "negative_control", "provenance": "holdout_v2_new — جزائي"},
    {"text": "رفعت الشركة دعوى تعويض عن الأضرار الناتجة عن تأخر المقاول في تسليم المشروع.",
     "expected_dependencies": [], "category": "negative_control", "provenance": "holdout_v2_new — مدني/تعويض"},
    {"text": "أصدرت الجهة الإدارية قرارًا بإلغاء ترخيص المحل التجاري لمخالفته اشتراطات السلامة.",
     "expected_dependencies": [], "category": "negative_control", "provenance": "holdout_v2_new — إداري"},
    {"text": "طلب الموظف إلغاء قرار نقله التعسفي إلى إدارة أخرى دون سبب مشروع.",
     "expected_dependencies": [], "category": "negative_control", "provenance": "holdout_v2_new — عمالي/إداري"},
    {"text": "تنازع الشريكان على توزيع أرباح الشركة في نهاية السنة المالية المنصرمة.",
     "expected_dependencies": [], "category": "negative_control", "provenance": "holdout_v2_new — شركات"},
]

if __name__ == "__main__":
    from collections import Counter
    print(f"HOLDOUT_SET_V2 size = {len(HOLDOUT_SET_V2)}")
    print(Counter(ex["category"] for ex in HOLDOUT_SET_V2))
    print("cross_concept_pairs covered:", sorted({ex["pair"] for ex in HOLDOUT_SET_V2 if "pair" in ex}))
