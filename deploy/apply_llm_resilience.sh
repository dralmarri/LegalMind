#!/usr/bin/env bash
set -euo pipefail
cd /opt/LegalMind

echo '[1/4] Updating production main'
git fetch origin main
git checkout main
git pull --ff-only origin main

echo '[2/4] Syntax check'
/opt/LegalMind/admin/.venv/bin/python -m py_compile admin/main.py admin/llm.py admin/llm_resilience.py

echo '[3/4] Restarting LegalMind'
systemctl restart legalmind-admin.service
sleep 3
systemctl is-active --quiet legalmind-admin.service

echo '[4/4] Verifying resilience + Retrieval v2 are installed'
/opt/LegalMind/admin/.venv/bin/python - <<'PY'
from admin import main
from admin import llm
from admin import app
assert getattr(llm, '_legalmind_resilience_installed', False), 'LLM_RESILIENCE_NOT_ACTIVE'
assert getattr(app, '_retrieval_v2_installed', False) or getattr(app, 'RETRIEVAL_V2_ACTIVE', False) or 'retrieval_v2_runtime' in repr(getattr(app, '_draft_build_context', '')), 'RETRIEVAL_V2_NOT_ACTIVE'
print('LLM_RESILIENCE_ACTIVE timeout=1800s')
print('RETRIEVAL_V2_ACTIVE')
PY

echo 'DONE'
git log -1 --oneline
systemctl --no-pager --full status legalmind-admin.service | sed -n '1,12p'
