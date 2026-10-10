#!/usr/bin/env bash
set -euo pipefail
cd /opt/LegalMind

echo '[1/5] حفظ أي تعديل محلي غير ملتزم'
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  git stash push -u -m "pre-review-assessment-v2-$(date +%Y%m%d-%H%M%S)" >/dev/null
fi

echo '[2/5] تحديث main'
git fetch origin main
git checkout main
git pull --ff-only origin main

echo '[3/5] فحص البناء'
PY=/opt/LegalMind/admin/.venv/bin/python
"$PY" -m py_compile admin/app.py admin/main.py admin/draft_job_runtime.py

echo '[4/5] إعادة تشغيل LegalMind'
systemctl restart legalmind-admin.service
sleep 4
systemctl is-active --quiet legalmind-admin.service

echo '[5/5] تحقق من التصنيف القابل للتفسير'
set -a
source deploy/.env
set +a
"$PY" - <<'PY'
from admin import app as A
assert hasattr(A, "_compute_review_assessment")
# استنتاج/فجوة معلنة وحدها لا تُسقط الرأي كله إلى needs_review
x=A._compute_review_assessment("تحليل قانوني [للتحقق]", [], [], [])
assert x["status"] == "partial", x
# استشهاد غير موجود يبقى تحذيرًا صلبًا
y=A._compute_review_assessment("رأي", ["الطعن 999/9999"], [], [])
assert y["status"] == "needs_review", y
# بلا تنبيهات = verified
z=A._compute_review_assessment("رأي مسند", [], [], [])
assert z["status"] == "verified", z
print("EXPLAINABLE_REVIEW_ACTIVE")
print("STATUS_SAMPLE=", z["status"], x["status"], y["status"])
PY

git log -1 --oneline
systemctl --no-pager --full status legalmind-admin.service | sed -n '1,14p'
echo 'DONE: review status is now evidence-aware and returns explicit reasons.'
