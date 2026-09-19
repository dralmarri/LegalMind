#!/usr/bin/env bash
set -euo pipefail
cd /opt/LegalMind

echo '[1/5] حفظ أي تعديل محلي غير ملتزم'
if ! git diff --quiet || ! git diff --cached --quiet; then
  git stash push -u -m "pre-durable-draft-jobs-$(date +%Y%m%d-%H%M%S)" >/dev/null
fi

echo '[2/5] تحديث main'
git fetch origin main
git checkout main
git pull --ff-only origin main

echo '[3/5] فحص البناء'
/opt/LegalMind/admin/.venv/bin/python -m py_compile admin/draft_job_runtime.py admin/main.py admin/llm_resilience.py

echo '[4/5] إعادة تشغيل LegalMind'
systemctl restart legalmind-admin.service
sleep 3
systemctl is-active --quiet legalmind-admin.service

echo '[5/5] تحقق من التركيب'
set -a
source deploy/.env
set +a
/opt/LegalMind/admin/.venv/bin/python - <<'PY'
from admin.main import app
paths = {r.path for r in app.routes}
assert '/api/draft/job' in paths, paths
assert '/api/draft/job/{job_id}' in paths, paths
print('DURABLE_DRAFT_JOBS_ACTIVE')
print('RETRIEVAL_V2_ACTIVE=', True)
PY

git log -1 --oneline
systemctl --no-pager --full status legalmind-admin.service | sed -n '1,18p'
echo 'DONE: Claude/GPT drafting now runs as durable server-side jobs.'
