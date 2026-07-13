# LegalMind Automatic Ingestion Engine

## ما الذي يفعله؟

يراقب المجلد:

`/opt/legalmind-ingest/inbox`

ويعالج ملفات:

- `.docx`
- `.txt`
- `.md`

ثم:

1. يحفظ بصمة SHA-256 للمصدر.
2. يستخرج النص.
3. يكتشف المواد التشريعية أو المبادئ القضائية.
4. ينشئ كائنات معرفية ثابتة.
5. يدخل المصدر والكائنات والدفعة إلى PostgreSQL.
6. ينشئ فهرسًا متجهيًا في Qdrant باستخدام تمثيل hashing محلي قابل للاستبدال لاحقًا بنموذج embeddings عربي.
7. ينقل الملف إلى `archive` عند النجاح أو `failed` عند الفشل.

## ملف البيانات الجانبي

يمكن وضع ملف JSON بجوار المصدر بالاسم نفسه مضافًا إليه `.json`.

مثال:

`law-51-1984.docx`

`law-51-1984.docx.json`

```json
{
  "source_type": "legislation",
  "source_key": "LAW-KW-51-1984",
  "law_id": "KW-51-1984",
  "title": "القانون رقم 51 لسنة 1984 في شأن الأحوال الشخصية",
  "branch": "أحوال شخصية",
  "topic": "التشريعات الأساسية",
  "verification_status": "source_verified"
}
```

مثال المبادئ:

```json
{
  "source_type": "judicial_principle",
  "source_key": "PS-JURISDICTION-0002",
  "title": "اختصاص دائرة الأحوال الشخصية",
  "branch": "أحوال شخصية",
  "topic": "الاختصاص",
  "subtopic": "اختصاص دائرة الأحوال الشخصية",
  "id_prefix": "JUR-PS-JURISDICTION"
}
```

## الإدخال

انسخ الملف وملف JSON الجانبي إلى:

```bash
cp law.docx law.docx.json /opt/legalmind-ingest/inbox/
```

راقب السجل:

```bash
journalctl -u legalmind-ingest.service -f
```

## اختبار مباشر

```bash
cd /opt/LegalMind
set -a; source deploy/.env; set +a
.venv/bin/python engine/legalmind_engine.py ingest /path/to/file.docx
```

## ملاحظة مهمة

التمثيل المتجهي الحالي deterministic hashing embedding لتشغيل المنظومة دون API خارجي. هو ليس بديلًا نهائيًا عن نموذج embeddings عربي قانوني، لكنه يضمن أن خط الإدخال يعمل الآن دون تكلفة أو اعتماد خارجي. عند إضافة نموذج embeddings لاحقًا لا تتغير معرفات الكائنات أو قاعدة PostgreSQL.
