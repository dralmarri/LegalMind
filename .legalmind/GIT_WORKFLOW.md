# GIT_WORKFLOW — سير العمل في Git

## 1. الحالة

| البند | القيمة |
|---|---|
| الفرع الرئيسي | `main` |
| الفروع البعيدة | `origin/main`, `origin/agent/knowledge-system-v1`, `origin/claude/legal-source-verification-77jafr` |
| CI | `.github/workflows/legal-knowledge-validation.yml` — 🔴 **أحمر** |

## 2. رسائل الـ Commit

النمط المتبع في كل التاريخ: **فعل أمر بالإنجليزية، سطر واحد، بلا نقطة.**

```
Protect LegalMind case routes with existing admin authentication
Fix case API router authentication wiring
Add one-command LegalMind 4 deployment
Build LegalMind 4 legal operating workspace
```

**الأفعال المستخدمة:** `Add`, `Fix`, `Build`, `Run`, `Wire`, `Protect`, `Export`, `Record`, `Wait`.
**لا** conventional commits (`feat:`, `fix:`). **لا تُدخل نمطًا جديدًا.**

## 3. حجم الـ Commit

التاريخ يُظهر commits صغيرة مركّزة (ملف أو ملفان). **حافظ على ذلك.**

## 4. ما لا يُلتزم به أبدًا

| ممنوع | السبب |
|---|---|
| `deploy/.env`, `deploy/admin.env` | **أسرار** — لهما `.example` |
| `.venv/`, `admin/.venv/` | بيئات افتراضية |
| `__pycache__/` | مُولَّد |
| `web/node_modules/`, `web/.next/`, `web/out/` | مُولَّد |
| `web/next-env.d.ts` | مُولَّد |

⚠️ **كل هذه ظاهرة اليوم كـ untracked** ولا يوجد `.gitignore` في المستودع. **هذا خطر تسريب أسرار مباشر:** `git add -A` سهوًا يلتزم بكلمة مرور قاعدة البيانات.

**إجراء لازم:** إنشاء `.gitignore`. أُنجز ضمن هذه المهمة (T-00).

## 5. قاعدة الالتزام

**لا `git add -A` ولا `git add .` في هذا المستودع** حتى يوجد `.gitignore` مُختبَر. أضف الملفات صراحةً بالاسم.

## 6. الحماية القانونية

commit يمس تصنيفًا أو سندًا أو حالة توثيق **يجب أن يذكر ذلك صراحةً** في رسالته. مراجعة الكود القانوني ليست مراجعة كود عادية.

## 7. الفروع

- `main` — الفرع المستقر.
- الفروع البعيدة القائمة نتاج عمل وكلاء سابقين. **راجعها قبل حذفها** — قد تحمل عملًا غير مدموج.

## 8. Push

**لا يُدفع إلى `origin` إلا بطلب صريح من صاحب المشروع.**
