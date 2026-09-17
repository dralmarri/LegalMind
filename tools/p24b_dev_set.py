#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.4B — Development Set (مستقل تمامًا عن Gold Set40): جُمَل مؤلَّفة يدويًا (لا مأخوذة من
أي حالة Gold Set ولا من نصها) لكل تبعية من تبعيات `p24b_concept_backbone.py`، بأربع فئات:
positive (نظائر إيجابية بصياغات مختلفة)، hard_negative (نفس المفردات الشكلية بلا تحقق الشرط)،
neighboring (مسألة قانونية مجاورة بنفس الحقل المعجمي)، ambiguous (حالات حدّية مقصودة).

كل مثال: {"text", "expected_dependencies" (قائمة معرِّفات التبعيات المتوقَّع تفعيلها، فارغة
إن لم يُتوقَّع أي تفعيل), "category"}. يُستهلَك حصرًا من `p24b_acceptance_protocol.py` —
Gold Set نفسه لا يُستورَد هنا ولا يُطَّلع عليه أثناء التأليف."""

DEV_SET = [
    # ============ JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK ============
    {"text": "أطلب رد القاضي الناظر للدعوى لوجود صلة قرابة بينه وبين خصمي.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "positive"},
    {"text": "تبيّن أن القاضي الذي أصدر الحكم قريب لأحد الخصوم، فهل يبطل الحكم لعدم صلاحيته؟",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "positive"},
    {"text": "هل يجوز طلب تنحي القاضي بسبب مصاهرته لأحد أطراف الدعوى؟",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "positive"},
    {"text": "الدائرة التي نظرت الدعوى كان أحد أعضائها له مصلحة شخصية في نتيجتها.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "positive"},
    {"text": "موكلي يريد تقديم طلب رد ضد القاضي لوجود عداوة سابقة بينهما.",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "positive"},
    {"text": "أصدر القاضي حكمه في الدعوى برفض الدفع الشكلي المقدَّم من المدعى عليه.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "بين الطرفين قرابة نسب من جهة الأم، وقد حضرا معًا حفل زفاف قريب مشترك.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "طلب المدعي من المحكمة الإسراع في نظر الدعوى المنظورة أمامها.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "نطلب رد الخبير المنتدب في الدعوى لصلة قرابته بأحد الخصوم.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "استبعاد المحكَّم لوجود مصلحة شخصية له في النزاع محل التحكيم.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "هل صلة القرابة بين القاضي وكاتب الجلسة تؤثر على صحة الحكم الصادر؟",
     "expected_dependencies": ["JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK"], "category": "ambiguous"},
    {"text": "القاضي غير مقتنع بأقوال الشهود بسبب علاقتهم الوثيقة بأحد الأطراف.",
     "expected_dependencies": [], "category": "ambiguous"},

    # ============ CHEQUE_SUBSTANTIVE_RULES_CHECK / CHEQUE_LIMITATION_CHECK ============
    {"text": "حرر المدين شيكًا بمبلغ 500 دينار ثم رفض البنك صرفه لعدم كفاية الرصيد، وأريد المطالبة بقيمته.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"], "category": "positive"},
    {"text": "أطالب بتحصيل قيمة شيك ارتد لعدم وجود رصيد كافٍ في حساب الساحب.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"], "category": "positive"},
    {"text": "مضت خمس سنوات على تاريخ الشيك ولم أطالب بقيمته، فهل سقط حقي بالتقادم؟",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"], "category": "positive"},
    {"text": "قدّم الدائن الشيك للصرف فرجع بدون رصيد، ويريد رفع دعوى بقيمته على الساحب.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"], "category": "positive"},
    {"text": "موكلي حامل شيك يريد استصدار أمر أداء بقيمته بعد امتناع المسحوب عليه عن الوفاء.",
     "expected_dependencies": ["CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_LIMITATION_CHECK"], "category": "positive"},
    {"text": "وقّع الطرفان شيكًا كضمان مؤجل الاستحقاق دون أي نزاع قائم حاليًا بشأنه.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "أريد المطالبة بمستحقاتي المتأخرة من صاحب العمل عن ستة أشهر.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "الشيك محفوظ لدى المحامي كضمان وليس هناك نية لصرفه في الوقت الراهن.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "أريد المطالبة بقيمة كمبيالة رفض المسحوب عليه قبولها عند الاستحقاق.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "صدر أمر أداء بذمتي عن قرض بنكي ولم أوفِ بأقساطه الشهرية.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "الشيك المرتجَع مذكور في العقد كوسيلة ضمان فقط، ولا رغبة حاليًا في المطالبة به.",
     "expected_dependencies": [], "category": "ambiguous"},
    {"text": "تسلّم شيكًا من صاحبه دون أي مشكلة في صرفه حتى الآن.",
     "expected_dependencies": [], "category": "ambiguous"},

    # ============ LINEAGE_COMMITTEE_MANDATORY_REVIEW ============
    {"text": "أريد رفع دعوى إثبات نسب ابني من زوجي دون وجود عقد رسمي.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "positive"},
    {"text": "ترغب موكلتي في رفع دعوى نفي نسب الطفل عن زوجها السابق.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "positive"},
    {"text": "هل يشترط تقديم طلب النسب إلى اللجنة المختصة قبل رفع الدعوى القضائية؟",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "positive"},
    {"text": "يطلب موكلي إثبات بنوته لوالده المتوفى عبر دعوى نسب مستقلة.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "positive"},
    {"text": "يدّعي الابن نسبه لأبيه رغم عدم وجود عقد زواج موثق بين الوالدين.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "positive"},
    {"text": "نسبة نجاح الدعوى تعتمد على قوة الأدلة المستندية المقدَّمة للمحكمة.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "الزيادة في الأجر كانت نسبية مقارنة بالعام الماضي وليست ثابتة.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "نسب الشرف والانتماء القبلي موضوع فخر لدى كثير من الأسر.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "أريد رفع دعوى ميراث عن والدي المتوفى وتوزيع التركة بين الورثة.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "أثبتت زوجتي حملها بشهادة طبية رسمية وتريد رفع دعوى نفقة عليّ.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "تنازل المدعي عن دعوى النسب المرفوعة بعد التصالح مع المدعى عليه.",
     "expected_dependencies": ["LINEAGE_COMMITTEE_MANDATORY_REVIEW"], "category": "ambiguous"},
    {"text": "هل نسبي لأبي محل شك رغم عدم وجود أي نزاع قضائي بشأنه؟",
     "expected_dependencies": [], "category": "ambiguous"},

    # ============ MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK ============
    {"text": "تزوجت عرفيًا من موكلي وهو الآن ينكر الزوجية أمام المحكمة.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "positive"},
    {"text": "موكلتي تدّعي الزوجية وزوجها يجحد وجود أي رابطة زواج بينهما.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "positive"},
    {"text": "هل تُسمع دعوى الزوجية إذا أنكر الطرف الآخر وجود عقد الزواج أصلًا؟",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "positive"},
    {"text": "أقام معها علاقة زواج غير موثقة والآن ينكرها بعد نشوء خلاف بينهما.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "positive"},
    {"text": "الزوج منكر للزواج العرفي الذي تم بينهما دون توثيق رسمي.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "positive"},
    {"text": "زواجنا موثق رسميًا بوثيقة زواج معتمدة ولا خلاف على قيامه بيننا.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "أريد رفع دعوى طلاق من زوجي بسبب الهجر المستمر منذ سنتين.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "ينكر المدعى عليه توقيعه على العقد المصوَّر المقدَّم في الدعوى.",
     "expected_dependencies": [], "category": "hard_negative"},
    {"text": "ينكر المدين توقيعه على سند المديونية الذي يطالبه به الدائن.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "زوجها يمتنع عن الإنفاق عليها رغم قيام الزوجية الموثقة بينهما.",
     "expected_dependencies": [], "category": "neighboring"},
    {"text": "أنكر الزواج شفهيًا لكنه أقرّ به كتابة في محضر رسمي سابق قبل الإنكار.",
     "expected_dependencies": ["MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK"], "category": "ambiguous"},
    {"text": "الخلاف بينهما على مؤخر الصداق فقط، وزواجهما غير محل إنكار من أحد.",
     "expected_dependencies": [], "category": "ambiguous"},
]

if __name__ == "__main__":
    print(f"DEV_SET size = {len(DEV_SET)}")
    from collections import Counter
    print(Counter(ex["category"] for ex in DEV_SET))
