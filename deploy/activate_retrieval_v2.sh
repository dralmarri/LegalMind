#!/usr/bin/env bash
set -euo pipefail
ROOT=/opt/LegalMind
cd "$ROOT"

echo "[1/5] حفظ أي تعديل محلي غير ملتزم"
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  git stash push -u -m "pre-retrieval-v2-activation-$(date +%Y%m%d-%H%M%S)" >/dev/null
fi

echo "[2/5] جلب main"
git fetch origin main
git checkout main
git pull --ff-only origin main

echo "[3/5] فحص بناء الملفات التي ستعمل في الإنتاج"
PY=/opt/LegalMind/admin/.venv/bin/python
"$PY" -m py_compile admin/main.py admin/retrieval_v2_runtime.py retrieval/*.py

echo "[4/5] إعادة تشغيل LegalMind"
systemctl restart legalmind-admin.service
sleep 4
systemctl is-active --quiet legalmind-admin.service

echo "[5/5] تحقق أن v2 رُكبت فعليًا داخل عملية الاستيراد"
set -a
[ -f deploy/admin.env ] && . deploy/admin.env || true
[ -f deploy/.env ] && . deploy/.env || true
set +a
"$PY" - <<'PY'
import admin.main as m
assert getattr(m.app_module, "_retrieval_v2_installed", False), "Retrieval v2 not installed"
assert hasattr(m.app_module, "_draft_build_context_baseline"), "baseline escape hatch missing"
print("RETRIEVAL_V2_ACTIVE")
PY

echo
echo "DONE: Retrieval v2 is active in production."
git log -1 --oneline
systemctl --no-pager --full status legalmind-admin.service | sed -n '1,12p'
