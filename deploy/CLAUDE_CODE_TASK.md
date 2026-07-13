# مهمة Claude Code — تشغيل LegalMind 2.0 على VPS

اقرأ أولًا:

1. `knowledge-system/AGENTS.md`
2. `knowledge-system/ONTOLOGY.md`
3. `knowledge-system/WORKFLOW.md`
4. `knowledge-system/VALIDATION.md`
5. `knowledge-system/RESUME_STATE.md`

## الهدف

إكمال منصة LegalMind على الخادم دون تغيير النصوص الأصلية أو اختلاق بيانات قانونية.

## قواعد ملزمة

- PostgreSQL هو مخزن الكائنات والعلاقات وحالات التوثيق.
- Qdrant هو مخزن المتجهات فقط، ولا يعد مصدر حقيقة.
- ملفات المصدر تبقى غير قابلة للاستبدال وتتحقق ببصمة SHA-256.
- أي تحليل آلي يحمل `operationally_accepted` أو `machine_pending_human`، ولا يحمل `human_verified` دون مراجعة بشرية.
- لا تعتبر الدفعة مكتملة قبل تحديث `RESUME_STATE.md` و`CHANGELOG.md` وإنشاء نسخة احتياطية وGit commit.

## المطلوب تنفيذه

1. شغّل `deploy/bootstrap_vps.sh` وتحقق من صحة PostgreSQL وQdrant.
2. أنشئ حزمة Python تحت `backend/` باستخدام FastAPI وSQLAlchemy وpsycopg وqdrant-client.
3. أنشئ migrations قابلة للتكرار، ولا تعتمد فقط على ملفات init الخاصة بالحاويات.
4. أنشئ مستوردًا لملفات JSONL التشريعية والمبادئ القضائية يدعم upsert والمعاملات وقابلية الاستئناف.
5. أنشئ endpoints للصحة، البحث بالتصنيف، جلب الكائن، العلاقات، طابور التوثيق، وسجل الدفعات.
6. أنشئ retrieval متعدد المراحل: metadata filter ثم lexical/vector ranking ثم validation.
7. امنع أي إجابة بلا `source_key` وروابط كائنات داعمة.
8. أضف اختبارات pytest تشمل التكرار، القيود الزمنية، وعدم الاستشهاد بالمصادر غير المطابقة.
9. حدّث التوثيق وحالة الاستئناف ونفذ commit بعد نجاح الاختبارات.

## معايير القبول

- `docker compose ps` يظهر PostgreSQL وQdrant بحالة healthy.
- migrations تعمل على قاعدة فارغة.
- الاستيراد قابل للتكرار دون تكرار الصفوف.
- كل كائن تشريعي يحتفظ بالنص الأصلي وبصمة المصدر.
- البحث عن «اختصاص دائرة الأحوال الشخصية» يعيد المواد والمبادئ المرتبطة فقط.
- النسخ الاحتياطي اليومي مفعل ويحتفظ بـ30 يومًا.
