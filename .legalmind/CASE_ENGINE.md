# CASE_ENGINE — محرك القضايا

**الملف:** `admin/cases_api.py` (157 سطرًا) — ✅ يعمل
**الجداول:** `legal_cases`, `case_documents`, `case_authorities`, `case_drafts` — **كلها فارغة (0 صف)**

## 1. نموذج القضية

```text
legal_cases (القضية)
   ├── case_documents   (مستندات الملف)
   ├── case_authorities (الأسانيد ← knowledge_objects)
   └── case_drafts      (المسودات، مُصدَّرة بـ version)
```

`case_key` بنمط `CASE-{YYYYMMDD}-{HEX8}` يولّده `_case_key()`.

## 2. بوابة التغطية — أثمن ما في المشروع

`GET /api/cases/{id}/coverage` هي **التجسيد الفعلي لمبدأ «لا صياغة بلا سند»**:

```python
legislation = by_type.get("legislation", 0)
principles  = by_type.get("judicial_principle", 0)
templates   = by_type.get("judicial_template", 0) + by_type.get("legal_memorandum", 0)
ready = legislation > 0 and principles > 0 and templates > 0
```

| النتيجة | الحالة |
|---|---|
| الثلاثة متوفرة | `ready_for_grounded_draft` |
| أي نقص | `blocked_missing_authorities` + قائمة الناقص |

**هذه البوابة مقدسة. لا تُلتف عليها، ولا يُضاف لها تجاوز (override)، ولا تُجعل تحذيرًا.** هي الفرق بين مساعد قانوني ومولّد مذكرات كاذبة.

## 3. الحالة الفعلية للبوابة

اليوم البوابة تُرجع `blocked_missing_authorities` **دائمًا وحتمًا** — لأن `knowledge_objects` تحتوي على كائنين تجريبيين فقط بالفرع `اختبار`. لا قضية يمكن أن تصل إلى `ready`.

**هذا سلوك صحيح، لا عطل.** البوابة تعمل كما صُممت: لا معرفة ⇒ لا صياغة.

## 4. عيوب معروفة في المنطق

### 4.1 التغطية تقيس الكمّ لا الصلة 🔴

الاستعلام يعدّ الكائنات المطابقة لـ `(branch, topic, subtopic)`. أي أن وجود **أي** تشريع + **أي** مبدأ + **أي** نموذج في نفس التصنيف يفتح البوابة — **ولو لم يكن أيٌّ منها ذا صلة بوقائع القضية**.

هذا يفتح ثغرة «سند شكلي»: مذكرة مبنية على مبدأ في الموضوع الصحيح لكنه لا يخدم الطلب. **يجب أن تتطور البوابة** لتقيس الصلة (عبر محرك الاسترجاع) لا مجرد الوجود.

### 4.2 `case_authorities` لا يملؤه أحد

الجدول موجود، ولا يوجد مسار `POST` لربط سند بقضية. البوابة تحسب التغطية من `knowledge_objects` مباشرة، **متجاوزةً** `case_authorities` بالكامل. أي أن الأسانيد المرتبطة فعليًا بالقضية لا دور لها في قرار الجاهزية. تناقض تصميمي يجب إغلاقه.

### 4.3 لا آلة حالات للقضية

`status` حقل نصي حر (`draft` افتراضيًا). لا انتقالات محروسة.

### 4.4 المُرشِّح الفارغ يتوسّع

`(%s='' OR topic=%s)` — إذا كانت القضية بلا `topic`، تُحسب التغطية على **الفرع كله**. هذا متساهل ويجب تضييقه.

## 5. المسارات

| المسار | الحالة |
|---|---|
| `GET /api/cases` | ✅ |
| `POST /api/cases` | ✅ |
| `GET /api/cases/{id}` | ✅ يجلب الأسانيد والمسودات |
| `PATCH /api/cases/{id}` | ✅ بقائمة حقول مسموحة (`allowed`) |
| `GET /api/cases/{id}/coverage` | ✅ بوابة السند |
| `POST /api/cases/{id}/authorities` | ❌ **مفقود** |
| `POST /api/cases/{id}/drafts` | ❌ **مفقود** |

## 6. المصادقة

الراوتر محمي بالكامل عبر `admin/main.py`:
```python
app.include_router(cases_router, dependencies=[Depends(require_auth)])
```
سليم — الحماية مطبقة على مستوى الراوتر لا على كل مسار على حدة، فلا يمكن أن يُنسى مسار جديد بلا حماية.
