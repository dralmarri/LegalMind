# LegalMind Kuwait Knowledge System

نظام ملفات Markdown قابل للنقل بين ChatGPT وClaude Code وCodex وأي نموذج ذكاء اصطناعي.

## المبدأ الحاكم

لا تعتمد استمرارية المشروع على ذاكرة المحادثة. كل نتيجة يجب أن تُحفظ في ملفات المشروع فورًا، ثم تُسجل في الفهرس وسجل التغييرات وطابور التوثيق.

## ترتيب القراءة الإلزامي

1. `AGENTS.md`
2. `00_MASTER_SYSTEM_PROMPT.md`
3. `01_SAVE_AND_RECOVERY_PROTOCOL.md`
4. `02_KNOWLEDGE_SCHEMA.md`
5. `03_RETRIEVAL_AND_LINKING_RULES.md`
6. ملف الفرع المطلوب داخل `branches/`
7. القوالب المناسبة داخل `templates/`

## قاعدة الإكمال

لا تُعتبر أي دفعة معالجة مكتملة إلا بعد:

- حفظ النص الأصلي أو مرجعه.
- إنشاء أو تحديث الكائنات المعرفية.
- تحديث ملف الفرع.
- تحديث `data/OBJECT_INDEX.md`.
- تحديث `verification/VERIFICATION_QUEUE.md`.
- تحديث `CHANGELOG.md`.
- إنشاء نسخة احتياطية أو commit.

## استئناف العمل في جلسة جديدة

> اقرأ AGENTS.md و01_SAVE_AND_RECOVERY_PROTOCOL.md وRESUME_STATE.md، ثم استأنف من آخر نقطة محفوظة دون إعادة تصنيف العناصر المكتملة.

آخر تحديث للحزمة: 2026-07-13
