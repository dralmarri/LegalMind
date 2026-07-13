# LegalMind Kuwait Legal Ontology v1.0

## 1. الغرض

هذه الأنطولوجيا هي النموذج المعرفي الحاكم لنظام LegalMind. وهي مستقلة عن نموذج الذكاء الاصطناعي وقاعدة البيانات ومحرك البحث.

## 2. الطبقات الأساسية

```text
Legal Branch
└── Topic
    └── Court Classification Title
        └── Micro Issue
            └── Knowledge Object
```

- **Legal Branch**: الفرع القانوني الرئيس.
- **Topic**: الموضوع العام.
- **Court Classification Title**: عنوان التصنيف الأصلي الذي وضعته محكمة التمييز أو المصدر الرسمي.
- **Micro Issue**: الجزئية القانونية الدقيقة التي يعالجها العنصر.
- **Knowledge Object**: التشريع أو الحكم أو المبدأ أو القاعدة أو النموذج أو الإجراء أو الدفع.

## 3. الكيانات القانونية

### 3.1 الأشخاص والأدوار

`legal_person_role`

أمثلة: زوج، زوجة، حاضنة، محضون، ولي، وصي، قاصر، وارث، موصي، موصى له، مدعٍ، مدعى عليه.

### 3.2 الأشياء والمصالح القانونية

`legal_object`

أمثلة: متاع الزوجية، التركة، المهر، المسكن، جواز السفر، الاسم، النسب، الوصية، الوقف.

### 3.3 الوقائع والأحداث القانونية

`legal_event`

أمثلة: زواج، طلاق، وفاة، ولادة، وصية، هبة، تنازل، نشوء نزاع، صدور حكم.

### 3.4 الأفعال والطلبات القانونية

`legal_action`

أمثلة: يطلب، يطعن، ينكر، يقر، يهب، يوصي، يطالب بالتسليم، يطلب التصحيح، يطلب التمكين.

### 3.5 المفاهيم القانونية

`legal_concept`

أمثلة: الاختصاص النوعي، الاختصاص الدولي، التنظيم الداخلي، النصاب، النسب، الإرث، متاع الزوجية.

## 4. أنواع الكائنات المعرفية

- `legislation`
- `full_judgment`
- `judicial_principle`
- `synthesized_rule`
- `procedure`
- `legal_defense`
- `request`
- `evidence_requirement`
- `judicial_template`
- `legal_memorandum`
- `legal_concept`
- `legal_event`
- `legal_person_role`
- `legal_object`
- `legal_action`
- `cross_reference`
- `verification_issue`
- `reasoning_trace`

## 5. التصنيف المتعدد دون تكرار

لكل كائن:

- `primary_classification`: مساره الأصلي وفق تصنيف المصدر.
- `secondary_classifications`: مسارات موضوعية إضافية للاسترجاع.
- `semantic_tags`: ألفاظ ومفاهيم مرتبطة.

لا تنشأ نسخة جديدة من المبدأ عند ظهوره في أكثر من موضوع. يبقى له معرف واحد، وتضاف إليه علاقات ومسارات ثانوية.

## 6. العلاقات المعتمدة

- `interprets`: يفسر تشريعًا.
- `applies`: يطبق تشريعًا أو قاعدة.
- `cites`: يذكر مصدرًا صراحة.
- `derived_from`: مستنبط من.
- `supports`: يدعم قاعدة أو دفعًا أو طلبًا.
- `limits`: يقيد قاعدة.
- `distinguishes`: يميز حالة عن أخرى.
- `conflicts_with`: يتعارض مع.
- `supersedes`: يحل محل.
- `used_in`: يستخدم في نموذج أو مذكرة.
- `requires`: يتطلب مستندًا أو واقعة أو إجراءً.
- `has_primary_classification`: التصنيف الأصلي.
- `has_secondary_classification`: تصنيف إضافي.
- `has_temporal_scope`: نطاق زمني.
- `excludes`: استبعاد دلالي صريح.

## 7. قوة المصادر

الترتيب الوظيفي لا يلغي قواعد الحجية القانونية:

1. النص التشريعي الرسمي النافذ.
2. الحكم الكامل الموثق.
3. المبدأ القضائي المنشور.
4. القاعدة الجامعة المستنبطة والمدعومة.
5. الإجراء والدفوع.
6. النموذج والمذكرة كأسلوب وتطبيق، لا كمصدر منشئ للقاعدة.

## 8. القيود الزمنية

كل كائن قد يتضمن:

- `valid_from`
- `valid_to`
- `historical_only`
- `superseded_by`
- `temporal_note`

لا يعرض الحكم التاريخي بوصفه قاعدة حالية من دون بيان قيده.

## 9. الروابط السلبية

`negative_links` تحدد الموضوعات أو الأسئلة التي لا يجوز استخدام الكائن فيها، رغم قربها اللفظي.

مثال: مبدأ تسليم جوازات سفر الأولاد لا يستعمل كسند عام للحضانة إذا كان مناطه اختصاصًا مدنيًا.

## 10. حالة الاعتماد

- `source_verified`
- `verified`
- `machine_pending_human`
- `needs_source_review`
- `conflict_detected`
- `historical_only`
- `superseded`
- `repealed`
- `incomplete`

كل استنباط آلي يبقى `machine_pending_human` حتى اعتماده بشريًا.
