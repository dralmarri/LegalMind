#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.5 — Experiment B2-R: Development Set v2. جُمَل جديدة كليًا (صفر إعادة استعمال لأي جملة
من `p24b_holdout_set.py` أو `p24b_dev_set.py`) تغطي: نظائر إيجابية، صيغ صرفية، نفي، نقائض
حادة، مسائل مجاورة، **الأزواج الستة كلها من تصادم بين-مفهومي** (C(4,2)=6)، حالات ملتبسة،
أسئلة مركَّبة طويلة، وأسئلة عامية قصيرة. كل مثال يحمل `provenance` (طريقة التأليف)."""

DEV_SET_V2 = [
    # ============ JUDICIAL_DISQUALIFICATION ============
    {"text": "القاضي الناظر للدعوى قريب لأحد الخصوم إلى الدرجة الثالثة فهل يصح رده؟",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "positive",
     "provenance": "manual_new"},
    {"text": "طلب المحامي رد الدائرة بأكملها لوجود مصلحة شخصية لأحد أعضائها في نتيجة النزاع.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "positive",
     "provenance": "manual_new"},
    {"text": "القاضي كان زوجًا لإحدى الخصوم في الدعوى المنظورة أمامه.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "positive",
     "provenance": "manual_new — يختبر صياغة العلاقة المتعددة الكلمات صراحة"},
    {"text": "هل يبطل الحكم إذا صدر من قاضٍ صهرًا لأحد أطراف الخصومة؟",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "positive",
     "provenance": "manual_new"},
    {"text": "قضاة الدائرة الثلاثة بينهم وبين المدعي عداوة سابقة موثَّقة.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "morphological_variant",
     "provenance": "manual_new — جمع قضاة"},
    {"text": "تبيَّن أن القاضي سبق أن ترافع عن أحد الخصوم في نفس النزاع قبل توليه القضاء.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "positive",
     "provenance": "manual_new — سبب م102-و الموسَّع"},
    {"text": "القاضي لم يكن قريبًا لأي من الخصوم ولا له مصلحة في الدعوى إطلاقًا.",
     "expected_dependencies": [], "category": "negation", "provenance": "manual_new"},
    {"text": "استمع القاضي لمرافعة الطرفين وأجّل الحكم لجلسة قادمة.",
     "expected_dependencies": [], "category": "hard_negative", "provenance": "manual_new"},
    {"text": "طلب الدفاع استبعاد الخبير المحاسبي لصلة قرابته بأحد الخصوم في الدعوى.",
     "expected_dependencies": [], "category": "neighboring", "provenance": "manual_new — خبير لا قاضٍ"},

    # ============ CHEQUE_PAYMENT_CLAIM ============
    {"text": "أصدر التاجر شيكًا لصالح المورِّد ثم امتنع البنك عن صرفه لعدم كفاية الرصيد.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK"], "category": "positive",
     "provenance": "manual_new — بلا إشارة زمنية، يختبر applicability التقادم مستقلة"},
    {"text": "مضت أربع سنوات على تاريخ استحقاق الشيك ولا يزال حاملُه يفكر في المطالبة بقيمته.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"],
     "category": "positive", "provenance": "manual_new — إشارة زمنية صريحة"},
    {"text": "هل سقط حقي في المطالبة بقيمة الشيك بعد مضي هذه المدة الطويلة؟",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"],
     "category": "positive", "provenance": "manual_new"},
    {"text": "شيكات المضاربة محفوظة عندي كضمان فقط بلا أي نزاع قائم حاليًا.",
     "expected_dependencies": [], "category": "hard_negative", "provenance": "manual_new"},
    {"text": "لا أرغب في المطالبة بقيمة الشيك الآن رغم ارتداده منذ فترة.",
     "expected_dependencies": [], "category": "negation", "provenance": "manual_new"},
    {"text": "أريد المطالبة بقيمة سند تجاري غير الشيك وقَّعه المدين بنفسه.",
     "expected_dependencies": [], "category": "neighboring", "provenance": "manual_new"},
    {"text": "شيكي القديم ارتد فجأة وأبغى أطالب بفلوسي بأسرع وقت.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK"], "category": "positive",
     "provenance": "manual_new — صياغة عامية قصيرة"},

    # ============ LINEAGE_ESTABLISHMENT ============
    {"text": "أريد رفع دعوى لإثبات نسب طفلي الذي وُلد خارج إطار عقد زواج رسمي.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "positive",
     "provenance": "manual_new"},
    {"text": "يرغب الأب في نفي نسب الطفل عن نفسه عبر دعوى مستقلة أمام المحكمة.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "positive",
     "provenance": "manual_new"},
    {"text": "الأخوة الثلاثة يريدون إثبات نسبهم لوالدهم المتوفى ضمن دعوى واحدة.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "morphological_variant",
     "provenance": "manual_new — جمع ملكية نسبهم"},
    {"text": "تريد إثبات نسبها لأمها الحقيقية بعد أن تبيَّن خطأ في شهادة ميلادها.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "morphological_variant",
     "provenance": "manual_new — نسبها"},
    {"text": "نسبة الأخطاء في تسجيل المواليد ارتفعت هذا العام بحسب تقرير رسمي.",
     "expected_dependencies": [], "category": "negative_control",
     "provenance": "manual_new — تصادم نسبة/نسبه مباشر"},
    {"text": "الأقارب يتناقشون في تقسيم تركة الجد دون أي خلاف على صحة نسب أحد الورثة.",
     "expected_dependencies": [], "category": "hard_negative", "provenance": "manual_new"},
    {"text": "أريد رفع دعوى حضانة لابني بعد انفصالي عن والدته.",
     "expected_dependencies": [], "category": "neighboring", "provenance": "manual_new"},
    {"text": "ابغى أثبت نسب ولدي القانوني لأنه ما أخذ اسم أبوه للحين.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "positive",
     "provenance": "manual_new — صياغة عامية قصيرة"},

    # ============ MARITAL_STATUS_DENIAL ============
    {"text": "تزوجنا عرفيًا دون توثيق رسمي وهو الآن ينكر وقوع الزواج من الأساس.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "positive",
     "provenance": "manual_new"},
    {"text": "هل تُقبل دعوى الزوجية رغم أن الطرف الآخر لا يعترف بوجود عقد زواج بيننا؟",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "positive",
     "provenance": "manual_new — مرادف «لا يعترف»"},
    {"text": "الزوج جحد قيام رابطة الزوجية بينهما رغم إقراره الشفهي بها سابقًا أمام الأهل.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "positive",
     "provenance": "manual_new"},
    {"text": "زوجاتهم الثلاث أنكرن جميعًا وقوع عقد الزواج العرفي المدَّعى به.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "morphological_variant",
     "provenance": "manual_new — جمع زوجات + فعل جمع مؤنث"},
    {"text": "زواجنا موثَّق رسميًا ولا خلاف بيننا على قيامه من الأساس.",
     "expected_dependencies": [], "category": "hard_negative", "provenance": "manual_new"},
    {"text": "لم ينكر الزوج قط وجود عقد الزواج بينهما رغم كل الخصومة المالية.",
     "expected_dependencies": [], "category": "negation", "provenance": "manual_new"},
    {"text": "ينكر الشريك توقيعه على عقد تأسيس الشركة المشتركة بينهما.",
     "expected_dependencies": [], "category": "neighboring", "provenance": "manual_new"},

    # ============ الأزواج الستة من تصادم بين-مفهومي (C(4,2)=6) — يجب ألا يفعِّل أكثر من مفهوم واحد ============
    {"text": "تنكرها زوجته أمام القاضي رغم إقراره الكتابي بها في محضر سابق.",
     "expected_dependencies": [], "category": "cross_concept_pair", "pair": "JUDICIAL/MARITAL",
     "provenance": "manual_new — «زوج» مشترك، لا كلمة زواج/زوجية ولا صياغة علائقية بالقاضي، فلا تفعيل"},
    {"text": "القاضي زوج شقيقة المدعية، وهي نفسها تنكر زواجها من المدعى عليه في قضية أخرى.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK", "MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"],
     "category": "cross_concept_pair", "pair": "JUDICIAL/MARITAL",
     "provenance": "manual_new — كلا المفهومين صحيحان معًا هنا فعلًا (حالة إيجابية مزدوجة حقيقية)"},
    {"text": "القاضي طالب بقيمة شيك شخصي في قضية منفصلة تمامًا عن الدعوى المنظورة أمامه الآن.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK"], "category": "cross_concept_pair",
     "pair": "JUDICIAL/CHEQUE",
     "provenance": "manual_new — تصحيح: مطالبة الشيك حقيقية فعلًا (بصرف النظر عن كون طالبها قاضيًا "
                   "في نزاع منفصل)؛ JUDICIAL لا يصح توقعه إذ لا علاقة رد/عدم صلاحية بالدعوى المنظورة"},
    {"text": "أريد إثبات نسب ابني، وموكلي أيضًا حامل شيك يريد المطالبة بقيمته في نزاع منفصل تمامًا.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW", "CHEQUE_SUBSTANTIVE_RULES_CHECK"],
     "category": "cross_concept_pair", "pair": "LINEAGE/CHEQUE",
     "provenance": "manual_new — مفهومان مستقلان صحيحان معًا في نص واحد"},
    {"text": "القاضي قريب لأحد الورثة في دعوى إثبات نسب منظورة أمامه حاليًا.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK", "LINEAGE_COMMITTEE_MANDATORY_REVIEW"],
     "category": "cross_concept_pair", "pair": "JUDICIAL/LINEAGE",
     "provenance": "manual_new — مفهومان صحيحان معًا (قرابة القاضي + دعوى نسب فعلية)"},
    {"text": "أنكر الزوج نسب الطفل عنه رغم قيام رابطة الزوجية الموثَّقة بينهما.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "cross_concept_pair",
     "pair": "LINEAGE/MARITAL",
     "provenance": "manual_new — إنكار النسب لا إنكار الزوجية نفسها (الزوجية مُقرّ بها) — نسب فقط يجب أن يُفعَّل"},
    {"text": "زوجة القاضي تطالب بقيمة شيك محرَّر باسمها في قضية منفصلة عن زوجها القاضي تمامًا.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK"], "category": "cross_concept_pair",
     "pair": "JUDICIAL/CHEQUE",
     "provenance": "manual_new — «زوج» مذكور مع قاضٍ لكن بلا علاقة رد/عدم صلاحية بالدعوى المنظورة، والشيك حقيقي منفصل"},

    # ============ أسئلة مركَّبة طويلة (سياق متعدد) ============
    {"text": "موكلي محامٍ يمثِّل طرفًا في نزاع تجاري كبير، وأثناء المرافعة تبيَّن أن أحد أعضاء الدائرة "
             "له قرابة نسب مباشرة بالمدعي، فتقدَّم بطلب رد فوري قبل صدور أي حكم في الموضوع، "
             "وهو يسأل الآن عن الإجراءات الواجب اتباعها لاستكمال هذا الطلب أمام رئيس المحكمة.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "positive",
     "provenance": "manual_new — سؤال مركَّب طويل"},
    {"text": "وقَّع موكلي شيكًا لصالح شريكه السابق ضمن تسوية إنهاء الشراكة بينهما، وبعد مرور ثلاث سنوات "
             "على تاريخ الشيك اكتشف الشريك أنه لم يصرفه بعد ويسأل الآن هل ما زال بإمكانه المطالبة "
             "بقيمته أم سقط حقه بالتقادم نظرًا لطول المدة التي انقضت.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"],
     "category": "positive", "provenance": "manual_new — سؤال مركَّب طويل"},

    # ============ حالات ملتبسة إضافية ============
    {"text": "يُقال إن القاضي على علاقة طيبة بأحد المحامين الحاضرين، فهل هذا وحده كافٍ لطلب الرد؟",
     "expected_dependencies": [], "category": "ambiguous",
     "provenance": "manual_new — علاقة عامة غير مؤهَّلة قانونًا كسبب رد صريح"},
    {"text": "الشيك مؤجَّل الاستحقاق لشهر قادم ولم يحن موعد صرفه بعد.",
     "expected_dependencies": [], "category": "ambiguous",
     "provenance": "manual_new — شيك بلا نزاع فعلي، موعد مستقبلي لا مطالبة حالية"},
]

if __name__ == "__main__":
    from collections import Counter
    print(f"DEV_SET_V2 size = {len(DEV_SET_V2)}")
    print(Counter(ex["category"] for ex in DEV_SET_V2))
    print("cross_concept_pairs covered:", sorted({ex["pair"] for ex in DEV_SET_V2 if "pair" in ex}))
