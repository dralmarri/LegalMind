# INGESTION_ENGINE — محرك الإدخال

**الملف:** `engine/legalmind_engine.py` (273 سطرًا) — **✅ يعمل ومُثبت من طرف إلى طرف**
**الخدمة:** `legalmind-ingest.service` (active) — حلقة `watch` كل 10 ثوانٍ

## 1. المسار

```text
/opt/legalmind-ingest/inbox/
   file.docx  +  file.docx.json  (sidecar metadata)
        │
        ├── read_source()      .docx | .txt | .md   ← لا PDF
        ├── normalize_text()   NFKC، حذف التطويل (ـ)، ضغط المسافات
        ├── classify()         حسب source_type في الـ sidecar
        │      ├── legislation          → split_articles()   ^المادة N$
        │      ├── judicial_principle   → split_principles()  ^N-
        │      ├── full_judgment        → كائن واحد
        │      └── template/memorandum  → كائن واحد
        ├── PostgreSQL: sources + knowledge_objects + ingestion_batches
        ├── Qdrant:     PUT points (hash_embedding)
        └── shutil.move → archive/   |   عند الخطأ → failed/
```

## 2. عقد الـ Sidecar

لكل ملف مرفوع، ملف `.json` مجاور يكتبه `admin/app.py::upload`:

```json
{
  "source_type": "judicial_principles_collection",
  "object_type": "judicial_principle",
  "branch": "أحوال شخصية",
  "topic": "الاختصاص",
  "subtopic": "اختصاص دائرة الأحوال الشخصية",
  "micro_issue": "الدوائر السنية والجعفرية",
  "id_prefix": "JUR-PS-JURISDICTION",
  "source_key": "PS-JURISDICTION-SRC-0001",
  "title": "..."
}
```

**`id_prefix` هو الحقل الأخطر.** بدونه يولّد المحرك المعرّف من `slug()` على اسم الملف — فتضيع الهوية الدائمة وتنكسر الاستشهادات. عند حقن المعرفة الموجودة، **يجب** تمريره صراحة.

## 3. الخصائص السليمة (لا تُكسر)

- **Idempotent:** `ON CONFLICT DO UPDATE` على `sources` و`knowledge_objects`. إعادة الإدخال آمنة.
- **SHA-256** لكل ملف مصدر → كشف التكرار والتلاعب.
- **`original_text` محفوظ** دائمًا؛ التطبيع في `normalized_text`.
- **فصل `archive/` عن `failed/`** — لا يضيع ملف فاشل.
- **معالجة الأرقام العربية** (٠-٩ → 0-9) في `ARABIC_DIGITS`.
- **تكرار رقم المادة** يُعالَج بلاحقة `-OCC-2` بدل الدهس.

## 4. القيود المعروفة

| القيد | الأثر |
|---|---|
| ❌ لا PDF، لا OCR | **المصادر القضائية الكويتية الواقعية PDF ممسوح.** فجوة تشغيلية حتمية. |
| ❌ لا `synthesized_rule` | القواعد الجامعة الست لا يمكن حقنها بالمحرك الحالي |
| ❌ لا يكتب `relationships` | `relationship_count` يبقى 0 دائمًا |
| ❌ لا يكتب `verification_issues` | طابور التوثيق خارج قاعدة البيانات |
| ❌ لا يملأ `temporal_scope` | القيد الزمني ضائع رغم وجود العمود |
| ⚠️ `hash_embedding` ليس دلاليًا | راجع [[RETRIEVAL_ENGINE]] — الخلل الأخطر |
| ⚠️ الفرع الافتراضي `أحوال شخصية` | خطر صامت: ملف بلا `branch` يُصنَّف أحوالًا شخصية |
| ⚠️ التقسيم بـ regex فقط | مادة بصيغة غير متوقعة تُبتلع في المادة السابقة |

## 5. الفشل مضمون الاحتواء

عند أي استثناء: الملف يُنقل إلى `failed/`، والاستثناء يُرفع. لكن **صف `ingestion_batches` يبقى بحالة `started`** ولا يُحدَّث إلى `failed` — عيب رصد يجب إصلاحه.

## 6. الحالة الفعلية

- الأرشيف يحتوي على **ملفَّي اختبار فقط** (`tmp.8ghA6Fnw6u.md`، `tmp.Xho4rswwR1.md`).
- الصندوق الوارد **فارغ**.
- مجلد الفاشل **فارغ**.
- دفعتان مكتملتان، كائنان تجريبيان.

**الأنبوب سليم. لم يُمرَّر عبره محتوى قانوني حقيقي قط.**
