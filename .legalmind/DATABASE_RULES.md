# DATABASE_RULES — قواعد قاعدة البيانات

## 1. الاتصال

| البند | القيمة الفعلية |
|---|---|
| المحرك | PostgreSQL 16 (`postgres:16-alpine`) |
| الحاوية | `legalmind-postgres` |
| المنفذ | **`127.0.0.1:55432`** ← وليس 5432 |
| قاعدة البيانات | `legalmind` |
| البيانات | `/opt/legalmind-data/postgres` |

**لماذا 55432؟** المنفذ 5432 محجوز لحاوية `qcases-postgres` (pgvector) وهي **مشروع منفصل**. لا تلمسها ولا تنقل المنفذ.

## 2. الجداول التسعة والحالة الفعلية

| الجدول | الصفوف | الملاحظة |
|---|---:|---|
| `sources` | **1** | تجريبي |
| `knowledge_objects` | **2** | تجريبي، `branch = اختبار` |
| `ingestion_batches` | **2** | دفعتا اختبار |
| `relationships` | **0** | ❌ لا يكتب فيه أحد |
| `verification_issues` | **0** | ❌ الطابور في Markdown |
| `legal_cases` | **0** | |
| `case_documents` | **0** | |
| `case_authorities` | **0** | ❌ لا مسار كتابة |
| `case_drafts` | **0** | ❌ لا محرك صياغة |

## 3. القواعد الحاكمة

### 3.1 `original_text` مقدس
لا يُحدَّث بعد الإدخال أبدًا. التصحيح يذهب إلى `normalized_text`.
`ON CONFLICT DO UPDATE` الحالي **يدهس `original_text`** — مقبول فقط لأن SHA-256 يضمن أن نفس المصدر يعطي نفس النص. لا تُغيّر هذا الافتراض.

### 3.2 المعرّفات دائمة
`knowledge_objects.id` نصي ومُشتق دلاليًا (`LEG-KW-51-1984-ART-338`). **لا يُعاد تسميته أبدًا** — يُستشهد به داخل مستندات قانونية.

### 3.3 الحذف ممنوع
لا حذف كائنات معرفية. الإبطال بتغيير `verification_status` (`historical_only`, `superseded`). التاريخ القانوني لا يُمحى.

استثناء وحيد ومسموح: **تصفير البيانات التجريبية** (`branch = اختبار`) — راجع `TASKS/0001.md`.

### 3.4 كل هجرة ملف مرقّم
`deploy/sql/` بترقيم متسلسل. `001_schema.sql` (في `postgres/init/`) و`002_cases_workspace.sql`. أي تغيير جديد ⇒ `003_*.sql`. **لا تعديل ملف هجرة سابق.**

⚠️ `postgres/init/` يعمل **مرة واحدة فقط** عند تهيئة قاعدة فارغة. قاعدة البيانات موجودة الآن ⇒ الملفات هناك **لن تُطبَّق ثانية**. الهجرات الجديدة تُطبَّق يدويًا أو بسكربت.

### 3.5 `verification_status` افتراضه متساهل ⚠️
الافتراضي `operationally_accepted` في **كل** الجداول. أي كائن يدخل دون تحديد صريح يُعتبر **معتمدًا للتشغيل**.

هذا يعكس قرار صاحب المشروع («اعتماد دون مراجعة بندية»)، لكنه يعني أن **الآلة لا تستطيع تمييز المُراجَع من غير المُراجَع**. عند حقن معرفة حقيقية، **مرّر الحالة صراحةً دائمًا** ولا تعتمد على الافتراضي.

### 3.6 لا نصوص عارية في القضايا
`case_authorities` يربط بـ `object_id` بمفتاح أجنبي. لا يُنسخ نص السند داخل القضية. السند **مرجع** لا نسخة.

## 4. النزاهة المرجعية

```text
sources ◄── knowledge_objects ◄── relationships (from/to, CASCADE)
                    ▲
                    └── case_authorities ──► legal_cases (CASCADE)
```

`case_documents.source_key → sources` و`case_authorities.object_id → knowledge_objects` — **لا سند وهمي ممكن على مستوى المخطط.** تصميم سليم.

## 5. الفهارس القائمة

`idx_ko_classification (branch, topic, subtopic, micro_issue)` · `idx_ko_type` · `idx_ko_metadata_gin` · `idx_rel_from` · `idx_rel_to` · `idx_cases_classification` · `idx_case_authorities_case` · `idx_case_drafts_case`

**ناقص للاسترجاع:** لا فهرس بحث نصي كامل (FTS) على `normalized_text`. مطلوب للبحث الهجين ([[RETRIEVAL_ENGINE]] §4).

## 6. Qdrant

| البند | القيمة |
|---|---|
| Collection | `legalmind_objects_v1` |
| الأبعاد | 384 (اعتباطي — من `hash_embedding`) |
| المسافة | Cosine |
| النقاط | **2** (تجريبية) |
| الحالة | green |

**Qdrant فهرس مشتق، لا مصدر حقيقة.** يُعاد بناؤه بالكامل من PostgreSQL متى شئنا. لا تخزن فيه بيانات لا توجد في PostgreSQL.

`point_id` مشتق: أول 8 بايت من `sha256(object_id)` → عدد صحيح 63-bit. حتمي وقابل لإعادة الإنتاج. **حافظ على هذه الدالة** — تغييرها يفصل النقاط عن كائناتها.

## 7. النسخ الاحتياطي 🔴

`legalmind-backup.service` **فاشلة** (`203/EXEC`) لأن `deploy/backup.sh` صلاحياته 644 وليست تنفيذية.

**لا توجد نسخة احتياطية واحدة.** مقبول اليوم (البيانات تجريبية). **كارثي** فور حقن المعرفة الحقيقية. يُصلَح قبل أي حقن — راجع `TASKS/0001.md` مهمة T-04.
