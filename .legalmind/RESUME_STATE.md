# RESUME_STATE — حالة الاستئناف

> **اقرأ هذا الملف أولًا في أي جلسة جديدة.**
> كل رقم هنا مُتحقَّق منه من قاعدة البيانات الحية أو نظام الملفات — لا من محادثة سابقة.

**آخر تحديث:** 2026-07-14
**آخر عمل مُنجَز:** تدقيق شامل + إنشاء طبقة الذاكرة `.legalmind/`

---

## 1. أين نحن

```text
الصدق  ←── نحن هنا (المرحلة أ من TASKS/0001)
   │
المعرفة
   │
الاسترجاع
   │
الاستدلال
   │
الصياغة
```

**المهمة النشطة:** `TASKS/0001.md` — Personal Status Completion (`not_started`)

---

## 2. الحالة الفعلية — أرقام مُتحقَّقة

### قاعدة البيانات (PostgreSQL `legalmind` @ 127.0.0.1:55432)

| الجدول | الصفوف |
|---|---:|
| `sources` | **1** ← تجريبي |
| `knowledge_objects` | **2** ← تجريبي (`branch = اختبار`) |
| `ingestion_batches` | **2** |
| `relationships` | **0** |
| `verification_issues` | **0** |
| `legal_cases` | **0** |
| `case_documents` | **0** |
| `case_authorities` | **0** |
| `case_drafts` | **0** |

### Qdrant

`legalmind_objects_v1` — **2 نقطة** (تجريبية)، 384-dim، Cosine، green.

### المعرفة القانونية الحقيقية

**صفر في قاعدة البيانات.** 23 مبدأ + 6 قواعد موجودة **كـ Markdown فقط** في `knowledge-system/data/personal-status/`.

---

## 3. الحقائق المسحوبة 🔴

| الادعاء السابق | الواقع |
|---|---|
| `legislation_objects_generated: 869` | **0 — لا ملف واحد. الرقم وهمي.** |
| `judicial_principles_indexed: 23` | 0 في قاعدة البيانات (23 في Markdown) |
| `synthesized_rules: 6` | 0 في قاعدة البيانات |
| `pipeline_status: admin_portal_ready` | صحيح، لكن **بلا معرفة تمر فيه** |

---

## 4. الأعطال المفتوحة

| # | العطل | الخطورة |
|---|---|---|
| 1 | `legalmind-backup.service` فاشلة (`203/EXEC` — `backup.sh` غير تنفيذي) | 🔴 لا نسخ احتياطي |
| 2 | CI أحمر — `validate_knowledge.py` exit 1 | 🔴 `main` فاشل |
| 3 | `hash_embedding` ليس تضمينًا دلاليًا | 🔴 لا استرجاع ممكن |
| 4 | لا محرك استرجاع (Qdrant لا يُقرأ منه) | 🔴 |
| 5 | لا محرك صياغة | 🔴 |
| 6 | الواجهة تعرض ميزات غير موجودة | 🟡 ثقة كاذبة |
| 7 | لا `.gitignore` → خطر تسريب `deploy/.env` | ✅ **أُصلح** |

---

## 5. ما يعمل فعلًا ✅

PostgreSQL 16 · Qdrant v1.14.1 · `legalmind-admin` · `legalmind-api` · `legalmind-ingest` · خط الإدخال (مُثبت من طرف إلى طرف) · **بوابة السند** في `case_coverage` · 9 جداول سليمة · واجهة عربية RTL مكتملة الشكل.

---

## 6. الخطوة التالية

### مطلوب من صاحب المشروع ⛔

> **رفع النصوص الكاملة لقوانين الأحوال الشخصية الأربعة** (`.docx` / `.txt` / `.md` — **لا PDF**):
> KW-51-1984 · KW-124-2019 · KW-12-2015 · KW-53-2026
>
> هذا **الحاجز الحقيقي**. بدونه لا تُفتح بوابة الصياغة أبدًا (تشترط `legislation > 0`)، ولا يُغلق الفرع.

### قابل للتنفيذ فورًا دون تدخل

`TASKS/0001.md` المرحلة أ: T-01 (سحب 869) · T-03 (إصلاح CI) · **T-04 (إصلاح النسخ الاحتياطي — `chmod +x`)** · T-05 (تصفير التجريبي).

---

## 7. ثوابت البيئة

```text
جذر المشروع     /opt/LegalMind
PostgreSQL       127.0.0.1:55432   (5432 محجوز لـ qcases-postgres — لا تلمسه)
Qdrant           127.0.0.1:6333/6334
Admin            127.0.0.1:8000
Web              127.0.0.1:3000
الإدخال          /opt/legalmind-ingest/{inbox,archive,failed}
البيانات          /opt/legalmind-data/{postgres,qdrant}
النسخ            /opt/legalmind-backups
```

---

## 8. تحذير للجلسة القادمة

**لا تثق برقم في وثيقة قديمة.** هذا المشروع أعلن 869 مادة تشريعية غير موجودة، و23 مبدأً غير محقون. تحقق من قاعدة البيانات مباشرةً قبل البناء على أي رقم:

```bash
docker exec legalmind-postgres psql -U legalmind -d legalmind -tA \
  -c "SELECT object_type, count(*) FROM knowledge_objects GROUP BY 1;"
```
