# LegalMind Kuwait Legal Ontology v2.0

## 1. الغرض

هذه الأنطولوجيا هي النموذج المعرفي الحاكم لنظام LegalMind. وهي مستقلة عن نموذج الذكاء الاصطناعي وقاعدة البيانات ومحرك البحث، وهدفها تحويل المصادر القانونية الكويتية إلى شبكة معرفة قابلة للاسترجاع والاستدلال والصياغة الموثقة.

## 2. المبادئ الحاكمة

1. المصدر الأصلي لا يغيَّر.
2. كل استنتاج يحمل مصادره الداعمة.
3. التصنيف يتبع أصل الموضوع وعنوان المصدر، لا نوع الدائرة وحده.
4. الكائن الواحد قد يظهر في مسارات متعددة دون تكرار نصه.
5. القيد الزمني جزء من القاعدة وليس ملاحظة هامشية.
6. النموذج القضائي أداة صياغة، وليس مصدرًا منشئًا للقاعدة.
7. لا يجوز إنتاج جواب نهائي إذا كانت سلسلة الاستدلال بلا سند أو بها تعارض غير معلن.

## 3. طبقات المعرفة

```text
Legal Domain
└── Legal Branch
    └── Topic
        └── Court Classification Title
            └── Micro Issue
                ├── Legal Sources
                ├── Legal Concepts
                ├── Persons and Roles
                ├── Events and Facts
                ├── Procedures and Remedies
                └── Drafting Artifacts
```

## 4. أنواع الكائنات

### 4.1 المصادر القانونية

- `legislation`
- `legislation_article`
- `full_judgment`
- `judicial_principle`
- `official_decision`
- `regulation`
- `circular`

### 4.2 الكائنات المستنبطة

- `synthesized_rule`
- `legal_concept`
- `legal_test`
- `exception`
- `condition`
- `legal_effect`
- `burden_of_proof`
- `temporal_rule`

### 4.3 الكائنات الإجرائية

- `procedure`
- `jurisdiction_rule`
- `admissibility_rule`
- `deadline`
- `fee`
- `legal_defense`
- `request`
- `remedy`
- `evidence_requirement`

### 4.4 كائنات الصياغة

- `judicial_template`
- `legal_memorandum`
- `drafting_clause`
- `document_requirement`

### 4.5 الكيانات الواقعية

- `legal_person_role`
- `legal_object`
- `legal_event`
- `legal_action`
- `factual_element`

### 4.6 كائنات الضبط والتوثيق

- `cross_reference`
- `verification_issue`
- `reasoning_trace`
- `source_conflict`
- `version_record`

## 5. الحقول المشتركة الإلزامية

```yaml
id:
type:
branch:
topic:
classification_title:
micro_issue:
title:
original_source_id:
source_reference:
primary_classification:
secondary_classifications: []
semantic_tags: []
positive_links: []
negative_links: []
valid_from:
valid_to:
temporal_status:
verification_status:
created_at:
updated_at:
batch_id:
```

## 6. الأشخاص والأدوار في الأحوال الشخصية

الأدوار الأساسية:

- زوج
- زوجة
- مطلقة
- خاطب
- مخطوبة
- أب
- أم
- حاضن
- حاضنة
- محضون
- ولي
- وصي
- ناظر
- قاصر
- فاقد الأهلية
- ناقص الأهلية
- وارث
- مورث
- موصي
- موصى له
- موقوف عليه
- واقف
- طالب نسب
- منسوب إليه
- مدعٍ
- مدعى عليه
- مستأنف
- مستأنف ضده

كل دور يحمل:

```yaml
capacity_source:
capacity_start_event:
capacity_end_event:
rights: []
duties: []
procedural_standing: []
```

## 7. المفاهيم الأساسية لفرع الأحوال الشخصية

- الزواج
- الخطبة
- المهر
- النفقة
- الطاعة
- النشوز
- الطلاق
- الخلع
- الفسخ
- العدة
- النسب
- تصحيح الاسم
- الحضانة
- الرؤية
- الولاية
- الوصاية
- الوصية
- الوقف
- التركة
- الميراث
- الاختصاص النوعي
- الاختصاص المحلي
- الاختصاص الدولي
- التنظيم الداخلي للدوائر
- النظام العام
- تدخل النيابة العامة
- التسوية الأسرية
- الأوامر الوقتية
- التنفيذ الأسري

كل مفهوم يرتبط بالمصادر والوقائع والأدوار والإجراءات والنماذج ذات الصلة.

## 8. العلاقات المعتمدة

### 8.1 علاقات المصدر والقاعدة

- `contains_article`
- `interprets`
- `applies`
- `cites`
- `derived_from`
- `supports`
- `limits`
- `creates_exception_to`
- `distinguishes`
- `conflicts_with`
- `supersedes`
- `repeals`
- `amends`
- `specializes`
- `procedural_for`
- `implements`

### 8.2 علاقات الوقائع والآثار

- `requires_fact`
- `triggered_by`
- `establishes`
- `negates`
- `results_in`
- `bars`
- `preserves`
- `transfers_right_to`
- `terminates_right_of`

### 8.3 علاقات الإجراء والصياغة

- `filed_before`
- `requires_pre_step`
- `requires_document`
- `subject_to_deadline`
- `subject_to_fee`
- `available_to_role`
- `used_in`
- `supports_request`
- `supports_defense`
- `drafted_from`

### 8.4 علاقات التصنيف والاسترجاع

- `has_primary_classification`
- `has_secondary_classification`
- `has_micro_issue`
- `has_semantic_tag`
- `excludes`
- `related_to`

## 9. وظائف التشريع

كل تشريع أو مادة تصنف وظيفيًا إلى واحد أو أكثر من الآتي:

- `substantive_rule`
- `procedural_rule`
- `special_procedural_rule`
- `jurisdiction_rule`
- `interpretation_rule`
- `system_article`
- `evidence_rule`
- `remedy_rule`
- `penalty_rule`
- `transition_rule`

ويؤثر هذا التصنيف على ترتيب الاسترجاع بحسب نوع سؤال المستخدم.

## 10. استراتيجية باب الدخول

```yaml
question_type: substantive
entry_point: legislation
priority:
  - applicable_substantive_law
  - applicable_special_law
  - judicial_principles
  - synthesized_rules
```

```yaml
question_type: procedural
entry_point: special_procedural_law
priority:
  - special_procedural_law
  - family_court_law
  - general_procedure
  - procedure_objects
  - templates
```

```yaml
question_type: drafting
entry_point: judicial_template
priority:
  - verified_template
  - required_facts
  - required_documents
  - legislation
  - judicial_principles
  - requests_and_defenses
```

## 11. نمط القاعدة القانونية

كل قاعدة قابلة للاستدلال تمثل هكذا:

```yaml
rule_id:
if:
  all: []
  any: []
  none: []
then:
  legal_effect:
exceptions: []
procedural_consequences: []
evidence_needed: []
supported_by: []
contrary_sources: []
temporal_scope:
verification_status:
```

مثال بنيوي:

```yaml
rule_id: RULE-PS-CUSTODY-MOTHER-PRIORITY
if:
  all:
    - child_age_within_statutory_period
    - custodian_is_qualified
  none:
    - statutory_disqualification
then:
  legal_effect: mother_has_priority_of_custody
exceptions:
  - remarriage_if_applicable_under_governing_law
supported_by: []
```

## 12. سلسلة الاستدلال الإلزامية

كل جواب قانوني يجب أن ينشئ أثرًا داخليًا يتضمن:

1. سؤال المستخدم.
2. نوع السؤال.
3. الوقائع الصريحة.
4. الوقائع الناقصة.
5. الفرع والموضوع والعنوان والمسألة الدقيقة.
6. القانون الحاكم والمذهب عند اللزوم.
7. النصوص النافذة.
8. المبادئ القضائية المطابقة.
9. القواعد الجامعة المستخدمة.
10. الاستثناءات والقيود الزمنية.
11. سبب استبعاد المصادر القريبة غير المطابقة.
12. النتيجة.
13. درجة الاكتمال والثقة المصدرية.

## 13. قواعد المذهب والقانون الحاكم

قبل الاسترجاع الموضوعي في الأحوال الشخصية يجب تحديد:

- مذهب الأطراف أو المعيار القانوني المحدد له.
- طبيعة المسألة: زواج، طلاق، وصية، ميراث، وقف، نسب.
- القانون الموضوعي الحاكم.
- القانون الإجرائي الحاكم.
- أي قانون خاص لاحق يخصص أو يستبدل الإجراء السابق.

لا يجوز دمج قاعدة سنية وجعفرية في جواب واحد دون بيان اختلاف القانون الحاكم.

## 14. القيود الزمنية والنسخ

كل علاقة تغيير تشريعي تمثل صراحة:

```yaml
change_type: amends | repeals | supersedes | specializes
source:
target:
effective_from:
scope:
notes:
```

الأحكام القديمة لا تحذف؛ بل توسم:

- `historical_only`
- `requires_temporal_reassessment`
- `superseded_in_part`
- `still_valid_on_distinct_issue`

## 15. قوة المصادر

1. النص الرسمي النافذ.
2. القانون الخاص على العام في نطاقه.
3. الحكم الكامل الموثق.
4. المبدأ القضائي المنشور.
5. القاعدة الجامعة المدعومة.
6. الإجراء والدفع.
7. النموذج والمذكرة كأسلوب وتطبيق فقط.

## 16. الروابط السلبية

`negative_links` تمنع استخدام كائن بسبب التشابه اللفظي وحده.

أمثلة:

- مبدأ اختصاص لا يستخدم لإثبات الحق الموضوعي إلا إذا تضمنه صراحة.
- حكم تاريخي قبل قانون لاحق لا يقدم كقاعدة حالية.
- نموذج دعوى لا يستخدم كسند تشريعي.
- مبدأ متعلق بالنسب غير المباشر لا يستخدم تلقائيًا للنسب المباشر.

## 17. حالات الاعتماد

- `source_verified`
- `operationally_accepted`
- `verified`
- `machine_pending_human`
- `needs_source_review`
- `requires_temporal_reassessment`
- `conflict_detected`
- `historical_only`
- `superseded_in_part`
- `superseded`
- `repealed`
- `incomplete`

الاعتماد التشغيلي يسمح بالاستخدام مع إظهار مصدر الاشتقاق، ولا يعني مراجعة بشرية بندية.

## 18. معيار قبول الجواب

لا يقبل الجواب إذا تحقق أي من الآتي:

- لا توجد مادة أو قاعدة قضائية مطابقة.
- استخدم مصدر منسوخ دون بيان.
- خلط بين القانون السني والجعفري.
- خلط بين الحق الموضوعي والإجراء.
- استند إلى نموذج بوصفه مصدرًا.
- أخفى تعارضًا مؤثرًا.
- لم يذكر أن الوقائع الناقصة قد تغير النتيجة.

## 19. معيار قبول كائن جديد

لا يحفظ الكائن إلا إذا كان له:

- معرف ثابت.
- مصدر واضح.
- تصنيف أولي.
- مسألة دقيقة.
- حالة زمنية.
- حالة توثيق.
- سجل دفعة.

ولا تعتبر الدفعة مكتملة قبل تحديث الفهرس وطابور التوثيق وسجل التغييرات وحالة الاستئناف والنسخة الاحتياطية أو commit.
