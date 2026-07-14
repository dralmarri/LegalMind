# حالة استئناف المشروع

> ⚠️ **هذا الملف تجاوزه `.legalmind/RESUME_STATE.md` — اقرأ ذاك أولًا.**
> تدقيق 2026-07-14 كشف أن عدة أرقام هنا **لا تقابل أي بيانات فعلية**. صُحِّحت أدناه ووُسمت.
> المرجع الكامل: `.legalmind/CURRENT_PROJECT_AUDIT.md`

- `project_status`: active
- `last_completed_batch`: BATCH-20260714-AUDIT-0001
- `current_branch`: أحوال شخصية
- `current_topic`: تدقيق الحالة وإنشاء طبقة الذاكرة
- `current_classification_title`: LegalMind Memory Layer v1
- `last_saved_object`: .legalmind/CURRENT_PROJECT_AUDIT.md
- `ontology_version`: 2.0

## الأرقام المُصحَّحة بعد التدقيق 🔴

- `judicial_principles_in_markdown`: 23
- `judicial_principles_in_database`: **0** ← غير محقونة
- `synthesized_rules_in_markdown`: 6
- `synthesized_rules_in_database`: **0** ← غير محقونة
- `legislation_sources_described`: 4
- `legislation_objects_generated`: **0**
  - ⛔ **مسحوب.** كان مُعلنًا `869`. **لا توجد ولا ملف `.jsonl` ولا `KW-*.index.json` في المستودع.**
  - `validate_knowledge.py` يؤكد: `Expected total 869, got 0` → **exit 1**
- `knowledge_objects_in_database`: **2** ← كلاهما تجريبي (`branch = اختبار`)
- `qdrant_points`: **2** ← تجريبية
- `real_legal_knowledge_in_database`: **0**

## الأعطال المفتوحة

- `ci_status`: **red** — `validate_knowledge.py` exit 1
- `backup_service`: **failed** — `203/EXEC` (`deploy/backup.sh` صلاحياته 644، غير تنفيذي)
- `embedding_model`: **none** — `hash_embedding` هو hashing trick لا نموذج دلالي
- `retrieval_engine`: **not_built** — لا كود يقرأ من Qdrant
- `drafting_engine`: **not_built**

- `pipeline_status`: infrastructure_ready_knowledge_empty
- `engine_script`: engine/legalmind_engine.py
- `admin_backend`: admin/app.py
- `admin_frontend`: admin/static/index.html
- `admin_service`: deploy/legalmind-admin.service
- `admin_installer`: deploy/install_admin_portal.sh
- `admin_domain`: admin.soutaladalah.com
- `supported_judicial_sources`:
  - full_judgment
  - judicial_principles_collection
  - single_judicial_principle
  - judicial_template
  - legal_memorandum
- `inbox_path`: /opt/legalmind-ingest/inbox
- `archive_path`: /opt/legalmind-ingest/archive
- `failed_path`: /opt/legalmind-ingest/failed
- `postgres_host_port`: 55432
- `qdrant_collection`: legalmind_objects_v1
- `pending_verification_items_in_markdown`: 4
- `pending_verification_items_in_database`: **0** ← الطابور غير متزامن
- `active_task`: `.legalmind/TASKS/0001.md` — Personal Status Completion
- `next_action`: ⛔ **مطلوب من صاحب المشروع:** رفع النصوص الكاملة لقوانين الأحوال الشخصية الأربعة (KW-51-1984، KW-124-2019، KW-12-2015، KW-53-2026) بصيغة `.docx` أو `.txt` أو `.md` — **لا PDF**. بدونها لا تُفتح بوابة الصياغة أبدًا (تشترط `legislation > 0`) ولا يُغلق الفرع.
- `next_action_unblocked`: المرحلة أ من TASKS/0001 — إصلاح النسخ الاحتياطي (`chmod +x deploy/backup.sh`)، إصلاح CI، تصفير البيانات التجريبية.
- `updated_at`: 2026-07-14
