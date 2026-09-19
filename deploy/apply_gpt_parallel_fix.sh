#!/usr/bin/env bash
set -euo pipefail
cd /opt/LegalMind

echo '[1/5] حفظ أي تعديل محلي غير ملتزم'
if ! git diff --quiet || ! git diff --cached --quiet; then
  git stash push -u -m "pre-gpt-parallel-fix-$(date +%Y%m%d_%H%M%S)" >/dev/null
fi

echo '[2/5] تحديث main'
git fetch origin main
git checkout main
git pull --ff-only origin main

echo '[3/5] فحص البناء'
/opt/LegalMind/admin/.venv/bin/python -m py_compile admin/llm.py admin/llm_resilience.py admin/main.py

echo '[4/5] إعادة تشغيل LegalMind'
systemctl restart legalmind-admin.service
sleep 3

echo '[5/5] تحقق من التركيب ومن إعداد GPT بلا كشف المفاتيح'
/opt/LegalMind/admin/.venv/bin/python - <<'PY'
from admin import llm
from admin.llm_resilience import install, OPENAI_DRAFT_ATTEMPTS, DRAFT_TRANSPORT_TIMEOUT_SECONDS
install(llm)
assert getattr(llm, '_legalmind_resilience_installed', False)
print('GPT_PARALLEL_FIX_ACTIVE attempts=%d timeout=%ss' % (OPENAI_DRAFT_ATTEMPTS, int(DRAFT_TRANSPORT_TIMEOUT_SECONDS)))
print('OPENAI_KEY_PRESENT=', bool(llm._env('OPENAI_API_KEY')))
print('OPENAI_DRAFT_MODEL=', llm._env('LEGALMIND_OPENAI_DRAFT_MODEL') or 'NOT_SET')
PY

systemctl --no-pager --full status legalmind-admin.service | sed -n '1,14p'
echo 'DONE: GPT parallel drafting fix is active.'
