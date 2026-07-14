# RUNBOOK — تعليمات التشغيل

**آخر تحديث:** 2026-07-14

---

## 1. إدخال مصدر قانوني (الطريقة المعتادة — بلا كود)

1. ادخل على **https://admin.soutaladalah.com** بالمستخدم `dralmarri`.
2. من القائمة: **رفع المصادر**.
3. اختر **طريقة واحدة**:
   - **رفع ملف** — `.docx` · `.pdf` (نصي) · `.html` · `.txt` · `.md`
   - **لصق نص** — الصق النص القانوني حرفيًا (20 حرفًا فأكثر، حتى 500,000 حرف)
4. املأ الحقول. **الإلزامية:** الفرع · الموضوع · عنوان تصنيف محكمة التمييز.
5. اضغط **حفظ وبدء المعالجة**، وتابع حالة المعالجة أسفل النموذج حتى تظهر:
   - **اكتملت المعالجة** — مع عدد الكائنات ومعرّف الدفعة
   - **مكرر** — مع الدفعة السابقة (لم تُنشأ نسخة)
   - **فشلت** — مع سبب الرفض بالعربية

**المبدأ:** موضوعًا موضوعًا لا دفعة واحدة. النص الأصلي الحرفي → `source_verified`.

---

## 2. الخدمات

```bash
systemctl status legalmind-admin legalmind-ingest   # الحالة
systemctl restart legalmind-admin legalmind-ingest  # إعادة التشغيل
journalctl -u legalmind-ingest -f                   # سجل المعالجة الحي
curl -s http://127.0.0.1:8088/health                # فحص الصحة
```

| الخدمة | الدور |
|---|---|
| `legalmind-admin` | واجهة الإدارة و API (uvicorn، 127.0.0.1:8088) |
| `legalmind-ingest` | مراقب `inbox` — يعالج كل مصدر يقع فيه |
| `legalmind-postgres` | Docker — 127.0.0.1:55432 — **مصدر الحقيقة** |
| `legalmind-qdrant` | Docker — 6333 — فهرس مشتق |
| `legalmind-backup.timer` | نسخ احتياطي يومي |

---

## 3. الاختبارات

```bash
cd /opt/LegalMind
set -a && . deploy/.env && set +a

PYTHONPATH=/opt/LegalMind .venv/bin/python -m pytest engine/test_ingestion.py -v   # 12 اختبارًا
PYTHONPATH=/opt/LegalMind .venv/bin/python engine/test_normalizer.py               # 19 فحصًا
PYTHONPATH=/opt/LegalMind .venv/bin/python engine/truth_report.py                  # الأرقام الحقيقية
```

الاختبارات تعمل على PostgreSQL وQdrant **الحقيقيين** تحت فرع `اختبار آلي`، وتنظّف أثرها قبل كل اختبار وبعده. لا mocks: الاختبار الذي يعمل على بديل وهمي لا يثبت أن النظام يعمل.

---

## 4. إعادة بناء فهرس Qdrant

يجوز حذف Qdrant كليًا. المعرفة في PostgreSQL:

```bash
cd /opt/LegalMind && set -a && . deploy/.env && set +a
PYTHONPATH=/opt/LegalMind .venv/bin/python engine/legalmind_engine.py reindex
```

يُرجع `consistent: true` عند تطابق عدد الكائنات في PostgreSQL مع عدد النقاط في Qdrant.

---

## 5. إعادة نشر الواجهة

الواجهة التي يراها المستخدم في المتصفح هي **تطبيق Next.js** في `web/`، ويُبنى إلى ملفات ساكنة تُخدَّم من `/var/www/legalmind-v3`. تعديل `web/app/page.tsx` **لا يظهر** حتى يُبنى ويُنشر:

```bash
cd /opt/LegalMind/web
npx tsc --noEmit          # فحص الأنواع
npm run build             # يبني إلى out/
rsync -a --delete out/ /var/www/legalmind-v3/
chown -R www-data:www-data /var/www/legalmind-v3
```

> `admin/static/index.html` واجهة احتياطية يخدمها FastAPI على `/` مباشرةً (127.0.0.1:8088)، ولا تظهر عبر النطاق العام لأن nginx يخدم الـSPA بدلًا منها. تُبقى متوافقة مع الـAPI نفسه.

---

## 6. المصادقة

طبقتان بالبيانات نفسها (دفاع في العمق) — تسجيل دخول واحد يمر بهما:

1. **nginx** — `auth_basic`، bcrypt في `/etc/nginx/.htpasswd-legalmind`
2. **التطبيق** — HTTP Basic، **scrypt** في `LEGALMIND_ADMIN_PASSWORD_HASH` بـ `deploy/admin.env`

تغيير كلمة المرور (إدخال مخفي، لا تُحفظ صريحة ولا تُطبع):

```bash
cd /opt/LegalMind
admin/.venv/bin/python -m admin.manage_admin_credentials --username dralmarri
```

**بعدها حدّث طبقة nginx بالكلمة نفسها**، وإلا انكسر الدخول من المتصفح:

```bash
htpasswd -B /etc/nginx/.htpasswd-legalmind dralmarri   # يسأل الكلمة تفاعليًا
systemctl reload nginx
```

---

## 7. الحالة الحقيقية — لا تثق برقم مكتوب

أي رقم في أي ملف Markdown **ليس مصدر حقيقة**. الأرقام تُقرأ من قاعدة البيانات:

```bash
PYTHONPATH=/opt/LegalMind .venv/bin/python engine/truth_report.py
docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
  "SELECT object_type, COUNT(*) FROM knowledge_objects GROUP BY object_type;"
curl -s -X POST http://127.0.0.1:6333/collections/legalmind_multilingual_e5_base_v1/points/count \
  -H 'Content-Type: application/json' -d '{"exact":true}'
```
