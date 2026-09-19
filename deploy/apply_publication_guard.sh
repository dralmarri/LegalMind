#!/usr/bin/env bash
set -euo pipefail
cd /opt/LegalMind

echo '[1/6] حفظ أي تعديل محلي غير ملتزم'
if ! git diff --quiet || ! git diff --cached --quiet; then
  git stash push -u -m "auto-stash before publication guard $(date +%Y%m%d_%H%M%S)" >/dev/null
fi

echo '[2/6] تحديث main'
git fetch origin main
git checkout main
git pull --ff-only origin main

echo '[3/6] فحص البناء'
/opt/LegalMind/admin/.venv/bin/python -m py_compile admin/publication_guard.py tools/probe_appeal_publication.py

echo '[4/6] حسم الطعن 1049/2004 مباشرة من PostgreSQL'
set +e
/opt/LegalMind/admin/.venv/bin/python tools/probe_appeal_publication.py 1049 2004 | tee /tmp/appeal_1049_2004_publication.json
PROBE_RC=${PIPESTATUS[0]}
set -e

# The guard is installed as a reusable exact-numeric verifier.  Do not mutate source data
# automatically when duplicate records disagree: the correct repair is to identify the bad
# source row, not to make one publication location win by code.
echo '[5/6] تحقق من وحدة الحارس'
/opt/LegalMind/admin/.venv/bin/python - <<'PY'
from admin.publication_guard import _norm_pub
assert _norm_pub('  مج القسم الخامس — المجلد السابع ص 511 ') == 'مج القسم الخامس - المجلد السابع ص 511'
print('PUBLICATION_GUARD_ACTIVE')
PY

echo '[6/6] النتيجة'
if [ "$PROBE_RC" -eq 0 ]; then
  echo 'APPEAL_1049_2004_PUBLICATION=UNIQUE'
else
  echo 'APPEAL_1049_2004_PUBLICATION=CONFLICT_OR_MISSING'
  echo 'لم تُعدّل البيانات تلقائيًا؛ التقرير أعلاه يعرض كل المعرّفات ومواضع النشر المتعارضة حرفيًا.'
fi

git log -1 --oneline
