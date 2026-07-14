# DEPLOYMENT — النشر

## 1. الخادم

| البند | القيمة |
|---|---|
| المضيف | `srv1184869` |
| النظام | Linux 6.8.0 |
| جذر المشروع | `/opt/LegalMind` |
| البيانات | `/opt/legalmind-data/{postgres,qdrant}` |
| الإدخال | `/opt/legalmind-ingest/{inbox,archive,failed}` |
| النسخ | `/opt/legalmind-backups` |
| النطاق الزمني | `Asia/Kuwait` |

## 2. الخدمات — الحالة الفعلية

| الخدمة | الحالة |
|---|---|
| `legalmind-postgres` (Docker) | ✅ Up 13h, healthy |
| `legalmind-qdrant` (Docker) | ✅ Up 13h |
| `legalmind-admin.service` | ✅ active |
| `legalmind-api.service` | ✅ active |
| `legalmind-ingest.service` | ✅ active |
| `legalmind-backup.service` | 🔴 **failed — 203/EXEC** |
| `legalmind-web.service` | مُعرَّف (الويب static export عبر Nginx) |

### حاويات مشاريع أخرى على نفس الخادم — لا تُلمس

`n8n-n8n-1` (:5679) · `qcases-postgres` (pgvector، **:5432**) · `n8n` (متوقف).
`qcases-postgres` يحجز 5432 ⇒ **LegalMind على 55432**. لا تُغيّر هذا.

## 3. عطل النسخ الاحتياطي 🔴

```
legalmind-backup.service: Main process exited, code=exited, status=203/EXEC
```

**التشخيص المؤكد:**
```bash
$ grep ExecStart deploy/legalmind-backup.service
ExecStart=/opt/LegalMind/deploy/backup.sh      # المسار صحيح، والملف موجود

$ ls -la deploy/backup.sh
-rw-r--r-- 1 root root 667 ...                 # ❌ صلاحيات 644 — غير قابل للتنفيذ
```

`203/EXEC` = systemd لم يستطع **تنفيذ** الملف. السبب صلاحيات، لا مسار.

**الإصلاح:** `chmod +x deploy/backup.sh` — سطر واحد.

**الخطورة:** **لا توجد نسخة احتياطية واحدة.** مقبول اليوم (البيانات تجريبية بالكامل). **كارثي** فور حقن المعرفة الحقيقية. يُصلَح **قبل** أي حقن.

## 4. سكربتات النشر

| السكربت | الغرض |
|---|---|
| `bootstrap_vps.sh` | تهيئة خادم جديد |
| `install_legalmind_v4.sh` | ⭐ **الأحدث** — تثبيت/تحديث بأمر واحد |
| `install_legalmind_v3.sh` | سابق |
| `install_admin_portal.sh` / `deploy_admin_portal.sh` | بوابة الإدارة |
| `install_ingestion_engine.sh` | محرك الإدخال |
| `install_backup_timer.sh` | مؤقّت النسخ |
| `test_ingestion_engine.sh` | اختبار المحرك من طرف إلى طرف |

كلها `set -euo pipefail` و idempotent (تصلح للتثبيت والتحديث).

## 5. الأسرار

`deploy/.env` و`deploy/admin.env` — **غير متتبَّعين في Git** (لهما `.example`). ✅ سليم.

⚠️ `deploy/.env` يحتوي على `POSTGRES_PASSWORD` و`DATABASE_URL` بكلمة المرور نصًا صريحًا. **لا تعرضهما في مخرجات ولا تلتزم بهما.**

## 6. الشبكة

كل شيء مربوط على `127.0.0.1` فقط:
- PostgreSQL `127.0.0.1:55432`
- Qdrant `127.0.0.1:6333/6334`
- Admin `127.0.0.1:8000`
- Web `127.0.0.1:3000`

**لا خدمة مكشوفة للإنترنت مباشرة.** Nginx هو نقطة الدخول الوحيدة (TLS + HTTP Basic). ✅ تصميم سليم.

## 7. الهجرات

⚠️ `deploy/postgres/init/` يُنفَّذ **مرة واحدة فقط** عند تهيئة قاعدة فارغة (`docker-entrypoint-initdb.d`). قاعدة البيانات **موجودة الآن** ⇒ أي تعديل هناك **لن يُطبَّق**.

`002_cases_workspace.sql` في `deploy/sql/` (خارج `init/`) ⇒ طُبِّق يدويًا.
**الهجرات الجديدة (`003_*.sql`) تُطبَّق يدويًا أو بسكربت. لا تعتمد على `init/`.**

## 8. الاستعادة

مسار الاستعادة **غير مُختبَر قط**. نسخة احتياطية لم تُختبر استعادتها ليست نسخة احتياطية.
