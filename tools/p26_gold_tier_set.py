#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.6 — **GOLD_TIER_SUBSTITUTE**: مجموعة تقييم نهائية مستقلة (10 حالات) بديلة عن Gold Set40
الأصلية (P2.1-P2.3) التي تعذَّر الوصول إلى `required_dimensions` المستقلة الخاصة بها محليًا في
هذه الجلسة (موثَّق في `docs/p2_6_freeze.md`). **لا تُعرَض كمكافئ للأصل** — بديل معياري بنفس
منهجية الاستبقاء المستقل: تأليف حقيقة أرضية يدوية قبل أي تشغيل، صفر إعادة استعمال من Dev Set،
تُفتح مرة واحدة بعد التجميد، بلا تعديل على المحرك أو العتبات بعد رؤية النتائج.

حالتان (gt-08، gt-09) مصمَّمتان عمدًا لاختبار الفجوة المكتشَفة في Dev Set (انحياز نحو
"required" على حساب "conditional"/"possible") — تصميم مبني على فئة الفشل المكتشَفة، لا على نص
حالة Dev بعينها، طبقًا لقاعدة إعادة استعمال فئات الفشل لا أمثلتها الحرفية."""

GOLD_TIER_SET = [
    {"id": "gt-01", "complexity": "single_issue",
     "question": "استأجرت محلًا تجاريًا وبعد شهرين اكتشفت تسربًا في السقف كان موجودًا وقت التسليم ولم يخبرني المالك به رغم علمه بأعمال ترميم سابقة في نفس الموقع.",
     "ground_truth_issues": [{"issue_id": "LEASED_PROPERTY_HIDDEN_DEFECT", "issue_type": "substantive",
                               "dimensions": [{"dimension_id": "LANDLORD_WARRANTY_FOR_DEFECTS",
                                                "dimension_text": "ضمان المؤجِّر للعيوب التي تحول دون الانتفاع بالعين المؤجَّرة",
                                                "status": "required", "critical": True},
                                               {"dimension_id": "LANDLORD_PRIOR_KNOWLEDGE_EFFECT",
                                                "dimension_text": "أثر علم المالك المسبق بالعيب على نطاق التزامه",
                                                "status": "required", "critical": True}]}]},
    {"id": "gt-02", "complexity": "negative_control",
     "question": "أخي يعمل محاميًا في مكتب كبير، وأنا أريد فقط معرفة كيفية استخراج شهادة عدم محكومية لتقديمها لجهة عملي الجديدة.",
     "ground_truth_issues": []},
    {"id": "gt-03", "complexity": "two_issue",
     "question": "بعتُ شقتي وسلَّمتها للمشتري، لكنه يرفض سداد القسط الأخير من الثمن بحجة أن مساحة الشقة الفعلية أقل مما ورد في العقد بمترين مربعين.",
     "ground_truth_issues": [
         {"issue_id": "REMAINING_PRICE_CLAIM", "issue_type": "substantive",
          "dimensions": [{"dimension_id": "RIGHT_TO_REMAINING_PRICE_AFTER_DELIVERY",
                           "dimension_text": "حق البائع في باقي الثمن بعد التسليم الفعلي للعقار",
                           "status": "required", "critical": True}]},
         {"issue_id": "AREA_SHORTAGE_DEFENSE", "issue_type": "substantive",
          "dimensions": [{"dimension_id": "PRICE_REDUCTION_FOR_AREA_SHORTAGE",
                           "dimension_text": "أثر نقص مساحة العقار المبيع عن المتفق عليه على الثمن المستحق",
                           "status": "required", "critical": True}]}]},
    {"id": "gt-04", "complexity": "three_four_issue",
     "question": "توفيت جدتي تاركة عقارًا مسجَّلًا باسمها، وأمي (ابنتها الوحيدة) توفيت قبلها بشهر، وعمي يرفض إعطاء أولاد أمي (أحفاد جدتي) أي نصيب في تركة جدتهم لأن والدتهم توفيت أولًا، ويطالب أيضًا بأحد الشيكات التي كانت بحوزة جدتي باسمه هو تحديدًا كهدية منها له قبل وفاتها.",
     "ground_truth_issues": [
         {"issue_id": "GRANDCHILDREN_INHERITANCE_RIGHT", "issue_type": "substantive",
          "dimensions": [{"dimension_id": "SUBSTITUTE_HEIR_RULE_PREDECEASED_PARENT",
                           "dimension_text": "حق أحفاد المتوفاة في نصيب بديل عن أمهم المتوفاة قبل جدتهم (الوصية الواجبة أو ما يقابلها)",
                           "status": "required", "critical": True}]},
         {"issue_id": "CHEQUE_GIFT_CLAIM", "issue_type": "evidentiary",
          "dimensions": [{"dimension_id": "PROOF_OF_GIFT_INTENT_FOR_CHEQUE",
                           "dimension_text": "إثبات نية الهبة في الشيك المحرَّر باسم أحد الورثة تحديدًا قبل الوفاة",
                           "status": "required", "critical": True}]},
         {"issue_id": "GIFT_VS_ESTATE_INTERPLAY", "issue_type": "substantive",
          "dimensions": [{"dimension_id": "GIFT_COUNTED_AGAINST_SHARE",
                           "dimension_text": "مدى احتساب قيمة الهبة (الشيك) على نصيب المُوهَب له من التركة إن ثبتت الهبة",
                           "status": "conditional", "condition": "إن ثبتت صحة الهبة ونفاذها",
                           "critical": False}]}]},
    {"id": "gt-05", "complexity": "cross_law",
     "question": "شركتنا وقَّعت عقد عمل عن بُعد مع مبرمج مقيم في بلد آخر بالكامل، والعقد يتضمن توقيعًا إلكترونيًا فقط، والآن نريد إنهاء تعاقده ونتساءل هل تُطبَّق عليه أحكام قانون العمل المحلي أصلًا وهل التوقيع الإلكتروني وحده كافٍ لإثبات قيام علاقة العمل.",
     "ground_truth_issues": [
         {"issue_id": "REMOTE_FOREIGN_WORKER_LAW_APPLICABILITY", "issue_type": "jurisdictional",
          "dimensions": [{"dimension_id": "LABOR_LAW_TERRITORIAL_APPLICABILITY",
                           "dimension_text": "مدى سريان قانون العمل المحلي على عامل مقيم خارج الدولة يعمل عن بُعد",
                           "status": "required", "critical": True}]},
         {"issue_id": "ELECTRONIC_SIGNATURE_EMPLOYMENT_PROOF", "issue_type": "evidentiary",
          "dimensions": [{"dimension_id": "DIGITAL_SIGNATURE_SUFFICIENCY_FOR_EMPLOYMENT_CONTRACT",
                           "dimension_text": "كفاية التوقيع الإلكتروني وحده لإثبات قيام عقد العمل وشروطه",
                           "status": "required", "critical": True}]}]},
    {"id": "gt-06", "complexity": "procedural_substantive",
     "question": "حصلت على حكم نهائي بإلزام خصمي بدين، لكن عند التنفيذ تبيَّن أن كل أمواله المعلَنة محجوزة سلفًا لصالح دائن آخر تقدَّم بحجزه قبل حجزي بأسبوع فقط، وأخشى ألا يتبقى لي شيء.",
     "ground_truth_issues": [
         {"issue_id": "COMPETING_ATTACHMENTS_PRIORITY", "issue_type": "procedural",
          "dimensions": [{"dimension_id": "ATTACHMENT_PRIORITY_RULE",
                           "dimension_text": "قاعدة الأولوية بين حجوز متعددة على نفس أموال المدين بحسب ترتيب توقيعها",
                           "status": "required", "critical": True}]},
         {"issue_id": "DEBT_ENFORCEMENT_BASIS", "issue_type": "substantive",
          "dimensions": [{"dimension_id": "JUDGMENT_CREDITOR_ENFORCEMENT_RIGHT",
                           "dimension_text": "أساس حق الدائن بموجب الحكم النهائي في التنفيذ على أموال المدين",
                           "status": "required", "critical": True}]}]},
    {"id": "gt-07", "complexity": "temporal_version",
     "question": "أبرمنا عقد شراكة تجارية عام 2018 وفق نظام الشركات الساري وقتها، وبعد صدور قانون شركات جديد عام 2022 يفرض حدًّا أدنى مختلفًا لرأس المال، هل يلزمنا تعديل عقدنا القائم لمطابقة الحد الجديد؟",
     "ground_truth_issues": [{"issue_id": "NEW_CAPITAL_REQUIREMENT_ON_EXISTING_COMPANY",
                               "issue_type": "temporal",
                               "dimensions": [{"dimension_id": "EXISTING_ENTITY_COMPLIANCE_WITH_NEW_LAW",
                                                "dimension_text": "مدى إلزام الشركات القائمة قبل نفاذ القانون الجديد بمطابقة شروطه (فترة سماح أو استثناء مكتسب)",
                                                "status": "required", "critical": True}]}]},
    {"id": "gt-08", "complexity": "exception_defense",
     "question": "أبرمت عقد توريد مع مصنع محلي، وتأخر التسليم أسبوعًا واحدًا عن الموعد المتفق، والمصنع يقول إن التأخير حصل بسبب انقطاع الكهرباء العام الذي شهدته المنطقة يومين فقط ضمن الأسبوع.",
     "ground_truth_issues": [{"issue_id": "SUPPLY_DELAY_PARTIAL_EXCUSE", "issue_type": "substantive",
                               "dimensions": [
                                   {"dimension_id": "DELAY_BREACH_BASIS",
                                    "dimension_text": "أساس مساءلة المورِّد عن التأخر عن الموعد المتفق عليه",
                                    "status": "required", "critical": True},
                                   {"dimension_id": "PARTIAL_FORCE_MAJEURE_PROPORTIONALITY",
                                    "dimension_text": "مدى تناسب مدة العذر القاهر المزعوم (يومان) مع مدة التأخير الكلية (أسبوع) وأثر ذلك على مقدار الإعفاء لا وجوده الكامل",
                                    "status": "conditional",
                                    "condition": "إن ثبتت صفة القوة القاهرة لانقطاع الكهرباء أصلًا كسبب خارج عن إرادة المورِّد",
                                    "critical": True}]}]},
    {"id": "gt-09", "complexity": "single_issue",
     "question": "زميلي في العمل ذكر أمامي أن الشركة تدرس تسريح بعض الموظفين نتيجة تراجع الأرباح، وأنا موظف منذ سنتين وأريد أن أعرف حقوقي في حال حصل ذلك لاحقًا.",
     "ground_truth_issues": [{"issue_id": "PROSPECTIVE_LAYOFF_RIGHTS_INQUIRY", "issue_type": "substantive",
                               "dimensions": [
                                   {"dimension_id": "GENERAL_TERMINATION_ENTITLEMENTS_OVERVIEW",
                                    "dimension_text": "الحقوق العامة المستحقة عند إنهاء الخدمة (مكافأة نهاية خدمة، إشعار) كخلفية عامة",
                                    "status": "possible",
                                    "condition": "الوقائع تصف احتمالًا مستقبليًا لم يقع بعد (مجرد دراسة الشركة، لا قرار فصل صادر)",
                                    "critical": False}]}]},
    {"id": "gt-10", "complexity": "evidentiary",
     "question": "لديّ رسائل واتساب مع مقاول تتضمن اتفاقًا على أعمال ترميم بمبلغ محدد، لكنه لم يوقِّع أي عقد ورقي، وبعد إنجاز نصف العمل توقف ورفض إكماله إلا بزيادة السعر.",
     "ground_truth_issues": [
         {"issue_id": "MESSAGING_APP_CONTRACT_EVIDENCE", "issue_type": "evidentiary",
          "dimensions": [{"dimension_id": "ELECTRONIC_MESSAGES_AS_CONTRACT_PROOF",
                           "dimension_text": "حجية رسائل التطبيقات الإلكترونية كدليل إثبات لاتفاق تعاقدي غير موثَّق كتابيًا رسميًا",
                           "status": "required", "critical": True}]},
         {"issue_id": "UNILATERAL_PRICE_INCREASE_MIDWAY", "issue_type": "substantive",
          "dimensions": [{"dimension_id": "BINDING_EFFECT_OF_AGREED_PRICE",
                           "dimension_text": "مدى إلزام المقاول بالسعر المتفق عليه ابتداءً وعدم جواز تعديله منفردًا أثناء التنفيذ",
                           "status": "required", "critical": True}]}]},
]

if __name__ == "__main__":
    from collections import Counter
    print(f"GOLD_TIER_SET size = {len(GOLD_TIER_SET)}")
    print(Counter(c["complexity"] for c in GOLD_TIER_SET))
    n_dims = sum(len(i["dimensions"]) for c in GOLD_TIER_SET for i in c["ground_truth_issues"])
    print(f"إجمالي الأبعاد: {n_dims}")
