#!/usr/bin/env bash
set -euo pipefail
ROOT=/opt/LegalMind
cd "$ROOT"

echo "[1/5] حفظ أي تعديل محلي غير ملتزم"
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  git stash push -u -m "pre-gpt-background-fix-$(date +%Y%m%d-%H%M%S)" >/dev/null
fi

echo "[2/5] تحديث main"
git fetch origin main
git checkout main
git pull --ff-only origin main

echo "[3/5] فحص البناء"
PY=/opt/LegalMind/admin/.venv/bin/python
"$PY" -m py_compile admin/app.py admin/llm.py admin/llm_resilience.py

echo "[4/5] إعادة تشغيل LegalMind"
systemctl restart legalmind-admin.service
sleep 4
systemctl is-active --quiet legalmind-admin.service

echo "[5/5] تحقق من إصلاح GPT الخلفي"
"$PY" - <<'PY'
import admin.main as m
from admin import llm as L
R = __import__("admin.llm_resilience", fromlist=["*"])
assert getattr(L, "_legalmind_resilience_installed", False)
assert hasattr(R, "OPENAI_BACKGROUND_MAX_SECONDS")
print("GPT_BACKGROUND_MODE_ACTIVE max_wait=%ss" % int(R.OPENAI_BACKGROUND_MAX_SECONDS))
print("RETRIEVAL_V2_ACTIVE=", bool(getattr(m.app_module, "_retrieval_v2_installed", False)))
print("OPENAI_DRAFT_MODEL=", L._env("LEGALMIND_OPENAI_DRAFT_MODEL"))
PY

systemctl --no-pager --full status legalmind-admin.service | sed -n '1,12p'
echo "DONE: GPT background generation fix is active."
