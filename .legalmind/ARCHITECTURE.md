# ARCHITECTURE — البنية الفعلية

> مُتحقَّق منها من الخدمات الحية بتاريخ 2026-07-14. ما هو غير موجود مُعلَّم صراحة بـ ❌.

## 1. مخطط النظام كما هو فعلًا

```text
                    ┌─────────────────────────────┐
                    │  المستخدم (HTTP Basic)      │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Nginx (TLS, Basic Auth)    │
                    └──────┬───────────────┬──────┘
                           │               │
              ┌────────────▼───┐   ┌───────▼────────────┐
              │ web/ (Next.js) │   │ admin/ (FastAPI)   │
              │ static export  │   │ :8000              │
              │ عميل فقط        │   │ legalmind-admin    │
              └────────┬───────┘   └───────┬────────────┘
                       │ fetch /api/*      │
                       └───────────────────┤
                                           │
                    ┌──────────────────────▼──────────────────┐
                    │  admin/app.py    → المصادر + الإحصاءات   │
                    │  admin/cases_api.py → القضايا + التغطية  │
                    └──────┬────────────────────────┬─────────┘
                           │                        │
              ┌────────────▼────────┐    ┌──────────▼──────────┐
              │  PostgreSQL 16      │    │  Qdrant v1.14.1     │
              │  127.0.0.1:55432    │    │  127.0.0.1:6333     │
              │  9 جداول             │    │  legalmind_objects_v1│
              │  ✅ يعمل             │    │  ✅ يعمل (اكتب فقط)  │
              └────────────▲────────┘    └──────────▲──────────┘
                           │                        │
                    ┌──────┴────────────────────────┴─────────┐
                    │  engine/legalmind_engine.py             │
                    │  legalmind-ingest.service (watch loop)  │
                    │  يراقب /opt/legalmind-ingest/inbox      │
                    └─────────────────────────────────────────┘

                    ❌ لا يوجد محرك استرجاع (Retrieval API)
                    ❌ لا يوجد محرك صياغة (Drafting generation)
                    ❌ لا يوجد نموذج تضمين دلالي (Embedding model)
```

## 2. الخدمات الحية — مُتحقَّق منها

| الخدمة | الحالة الفعلية |
|---|---|
| `legalmind-postgres` (Docker) | ✅ Up 13h, healthy, `127.0.0.1:55432→5432` |
| `legalmind-qdrant` (Docker) | ✅ Up 13h, `127.0.0.1:6333/6334` |
| `legalmind-admin.service` | ✅ active (running) |
| `legalmind-api.service` | ✅ active (running) |
| `legalmind-ingest.service` | ✅ active (running) |
| `legalmind-backup.service` | ❌ **failed** — `status=203/EXEC` |

### حاويات غير تابعة للمشروع تعمل على نفس الخادم

`n8n-n8n-1`, `qcases-postgres` (pgvector على المنفذ **5432 العام**), `n8n` (متوقف). **لا تلمسها.** لاحظ أن `qcases-postgres` يحجز المنفذ 5432، ولهذا يعمل postgres الخاص بـ LegalMind على **55432**.

## 3. طبقات النظام

### 3.1 طبقة الإدخال — `engine/legalmind_engine.py` ✅ تعمل

حلقة `watch` تراقب `/opt/legalmind-ingest/inbox` كل 10 ثوانٍ.

```text
inbox/file.docx + file.docx.json (sidecar metadata)
   → read_docx / read_txt / read_md
   → normalize_text (NFKC، حذف التطويل، ضغط المسافات)
   → classify() حسب source_type
   → split_articles()  (regex: ^المادة N$)
     أو split_principles() (regex: ^N- )
   → INSERT sources + knowledge_objects + ingestion_batches (PostgreSQL)
   → PUT points (Qdrant)
   → shutil.move → archive/  (أو failed/ عند الخطأ)
```

**الأنواع المدعومة:** `.docx`, `.txt`, `.md` فقط. لا PDF. لا OCR.

### 3.2 طبقة التخزين — PostgreSQL ✅ + Qdrant ⚠️

9 جداول (راجع [[DATABASE_RULES]]). Qdrant يُكتب إليه ولا يُقرأ منه أبدًا — **لا يوجد كود استرجاع في المشروع كله**.

### 3.3 طبقة التطبيق — `admin/` ✅ تعمل جزئيًا

| المسار | الوظيفة | الحالة |
|---|---|---|
| `GET /api/stats` | إحصاءات الكائنات والدفعات | ✅ |
| `GET /api/jobs` | سجل دفعات المعالجة | ✅ |
| `GET /api/topics` | شجرة التصنيف | ✅ |
| `GET /api/documents` | قائمة الكائنات | ✅ |
| `POST /api/upload` | رفع + كتابة sidecar | ✅ |
| `POST /api/requeue/{batch}` | إعادة معالجة دفعة | ✅ |
| `GET/POST /api/cases` | إدارة القضايا | ✅ |
| `GET /api/cases/{id}/coverage` | **بوابة السند** | ✅ |
| `POST /api/search` | استرجاع | ❌ **غير موجود** |
| `POST /api/drafts` | توليد مسودة | ❌ **غير موجود** |

### 3.4 طبقة الواجهة — `web/` ⚠️ واجهة بلا محرك

Next.js 15 + React 19 + Tailwind، بـ `output: 'export'` (static export). عشر شاشات في `web/app/page.tsx`.

**تحذير معماري:** مربع «ابحث في المعرفة» ليس بحثًا. إنه `filter()` على مصفوفة `documents` المُحمَّلة مسبقًا في المتصفح (`/api/documents?limit=1000`). فهو مطابقة نصية جزئية من جانب العميل، ولا يمس Qdrant ولا PostgreSQL.

«استوديو الصياغة» (`DraftingView`) هو **مُنتقي قضايا** فقط، ولا يوجد خلفه أي منطق توليد.

## 4. الخلل المعماري الجوهري — التضمين ليس دلاليًا

`engine/legalmind_engine.py::hash_embedding()`:

```python
def hash_embedding(text, size=384):
    vector = [0.0] * size
    for token in tokens:
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % size   # hashing trick
        sign  = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    return normalized(vector)
```

هذا **ليس نموذج تضمين**. إنه *hashing trick* على حقيبة كلمات: كل كلمة تُسقَط في خانة عشوائية ثابتة عبر SHA-256.

**النتيجة القانونية الخطيرة:** المتجه لا يحمل أي معنى دلالي. «الحضانة» و«حضانة الصغير» و«رعاية المحضون» متجهات شبه متعامدة. البحث الدلالي **مستحيل** بهذه البنية. المرادفات القانونية العربية — وهي جوهر البحث القانوني — لن تُسترجع أبدًا.

384 بُعدًا اختيار عشوائي هنا ولا يقابل أي نموذج.

**القرار:** يجب استبدال هذه الدالة بنموذج تضمين عربي حقيقي قبل بناء أي استرجاع. راجع [[RETRIEVAL_ENGINE]] و`TASKS/0001.md`.

## 5. ازدواج مصدر الحقيقة — الخلل الثاني

يوجد **مخزنان للمعرفة لا يعرف أحدهما الآخر**:

| المخزن | المحتوى | الحالة |
|---|---|---|
| `knowledge-system/**/*.md` | 23 مبدأ + 6 قواعد جامعة، مُصنَّفة ومُراجَعة بشريًا | نص Markdown مُنسَّق |
| PostgreSQL + Qdrant | 2 كائن تجريبي (`branch = اختبار`) | ما يراه التطبيق فعلًا |

المعرفة القانونية الحقيقية **ليست في قاعدة البيانات**. التطبيق لا يستطيع رؤيتها. أي واجهة أو استرجاع أو صياغة تعمل اليوم فوق **فراغ**.

**القرار المعماري:** قاعدة البيانات هي مصدر الحقيقة الوحيد للتشغيل. `knowledge-system/` هو طبقة **مصدر ومواصفة** تُغذّي قاعدة البيانات ولا تنافسها. راجع [[KNOWLEDGE_MODEL]].

## 6. الكود الميت

`index.html`, `script.js`, `style.css`, `server.js`, `package.json` في جذر المشروع — تطبيق ثابت قديم على المنفذ 5000، لا علاقة له بـ LegalMind 4، ولا تشير إليه أي خدمة. مرشح للحذف (راجع [[CHANGE_POLICY]]).

## 7. المصادقة

HTTP Basic بمستخدم واحد مشترك (`LEGALMIND_ADMIN_USER`). لا هوية فردية، لا صلاحيات، لا سجل تدقيق. مقبول لمستخدم واحد؛ **غير مقبول** عند إضافة أي مستخدم ثانٍ.
