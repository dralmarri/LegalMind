# P2.4B v1 — إغلاق رسمي (خط أساس ثابت لا يُعدَّل)

**التاريخ:** 2026-09-17. **الحالة: مغلقة نهائيًا. كل الملفات والبصمات أدناه خط أساس ثابت
(immutable baseline) — لا تعديل عليها بعد الآن. أي تطوير لاحق (P2.5/Arm B v2) ينشئ ملفات
وبصمات جديدة مستقلة تمامًا، ولا يُعاد فتح أو تعديل أيٍّ مما هنا.**

## البصمات النهائية المجمَّدة

```
Arm B v1 concepts/dependencies : c5153b06c1e92edb0cf30061d8183871fede15bcf6b51d1833c0ca5b9e292442
Holdout v1 (48 مثالًا)          : 7a40af35fbb545f936c1f384b17bf4faf406cbc8b1de4ef31d3163ee829e655c
آخر التزام Git لهذه الجولة      : 72d5327
```

## الملفات (لا تُعدَّل، تُقرأ فقط من الآن)

`tools/p24b_concept_backbone.py`، `tools/p24b_dev_set.py`، `tools/p24b_acceptance_protocol.py`،
`tools/p24b_holdout_set.py`، `tools/p24b_gold_set_paired_eval.py`، `tools/p24b_phase3_stability.py`،
`docs/p2_4b_arm_b_freeze.md`، `docs/p2_4b_holdout_freeze.md`.

## التصنيف النهائي المعتمد (بأمر المالك، حرفيًا)

| الطبقة | التصنيف |
|---|---|
| Concept/Dependency Layer | **PROMISING_BUT_NARROW** |
| Scope-Injection Integration | **NON_MONOTONIC** |
| **Overall Arm B v1** | **PROMISING_BUT_NOT_READY** |

## ملخص الأدلة الثلاثة (للرجوع لا لإعادة القياس)

- **Development Set (48 مثالًا):** recall=1.0 على التبعيات الخمس كلها بعد إصلاحين حقيقيين
  (اتساق تطبيع، تصادم تجذيع)؛ precision 0.714-1.0.
- **Gold Set40 (مزدوج، محاور مجمَّدة):** Verified/Critical Dimension Recall delta=0، Strict
  Case Scope Completeness delta=0، صفر إنقاذ (0/40)، فقد سلطة مفردة واحدة مؤكَّد (m513) لا
  يمس أي بُعد فعليًا (تمتصه مجموعة any_of)، +1 إلى +3 ثوانٍ لكل حالة نشطة.
- **الاستقرار 5x (gs-0002):** حتمية طبقة المفاهيم = PASS (5/5)؛ انحدار m513 = STABLE (5/5)؛
  DETERMINISTIC_SCOPE_MONOTONICITY = **FAIL** (فقد ضمان قناة الفصل لخمس سلطات: m513/514/515/
  553/554، لا واحدة فقط).
- **Independent Holdout v1 (48 مثالًا جديدًا، فُتح مرة واحدة):** Micro Recall=0.600 (تراجع
  حاد عن استدعاء دفتر التطوير الكامل)، Precision صمدت أو تحسَّنت (FPR ثابتة 0.024)، اكتُشف
  تصادم بين-مفهومي حقيقي («زوج» مشترك بين JUDICIAL_DISQUALIFICATION وMARITAL_STATUS_DENIAL)
  لم يظهر في دفتر التطوير. تصنيف الأخطاء: أغلبها CONCEPT_UNDERTRIGGER (نقص تغطية معجمية) لا
  إفراط تفعيل — يستبعد فرضية "جدول بحث مقنَّع" لكنه يثبت ضيق تعميم حقيقيًا.

## الدرس المعياري المركزي لهذه الجولة

فصل السببية بين "هل الفكرة المعمارية سليمة" و"هل التكامل الحالي آمن" أنتج حكمًا أدق من تصنيف
واحد مفروض: الطبقة المفاهيمية نفسها واعدة (دقة عالية، لا تفعيل كاذب خطير) بينما آلية دمجها
الحالية في `_draft_chap_ids` غير آمنة بنيويًا (تُسقط ضمانات حتمية قائمة). لولا هذا الفصل لكان
حكم إجمالي واحد (مثل NO_BENEFIT) قد أخفى فرصة حقيقية للتحسين في الطبقة الأولى.
