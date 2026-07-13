# بروتوكول الحفظ والاستعادة

## القاعدة الحاكمة
ذاكرة المحادثة ليست مخزنًا دائمًا. الحفظ الحقيقي هو الكتابة إلى ملفات المشروع وGitHub.

## بعد كل دفعة
يجب تحديث:
1. ملف الفرع.
2. `data/OBJECT_INDEX.md`.
3. `verification/VERIFICATION_QUEUE.md`.
4. `CHANGELOG.md`.
5. `RESUME_STATE.md`.
6. Git commit أو نسخة احتياطية.

## معرف الدفعة
`BATCH-YYYYMMDD-HHMM-<BRANCH>-<SEQUENCE>`

## دورة الحياة
`started → parsed → classified → linked → validated → saved → backed_up → completed`

لا توصف الدفعة بأنها مكتملة قبل تنفيذ جميع الخطوات.

## الاستعادة
في جلسة جديدة: اقرأ `AGENTS.md` و`RESUME_STATE.md`، ثم تحقق من `CHANGELOG.md` و`OBJECT_INDEX.md` وملف الفرع، واستأنف من `next_action` فقط.

## منع الفقد
- لا تحذف النص الأصلي.
- لا تغير معرف كائن قائم.
- التصحيح بسجل تعديل.
- الدمج يحتفظ بـ `merged_from`.
- الإلغاء يستخدم `superseded` بدل الحذف.
