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

echo '[4/6] فحص الطعن 1049/2004 مباشرة من PostgreSQL'
/opt/LegalMind/admin/.venv/bin/python tools/probe_appeal_publication.py 1049 2004 | tee /tmp/appeal_1049_2004_publication.json

echo '[5/6] تحقق من قاعدة تعدد مواضع النشر'
/opt/LegalMind/admin/.venv/bin/python - <<'PY'
from admin.publication_guard import _norm_pub, _matches_allowed
assert _norm_pub('  مج القسم الخامس — المجلد السابع ص 511 ') == 'مج القسم الخامس - المجلد السابع ص 511'
allowed = [
    'مج القسم الخامس - المجلد السابع ص 511',
    'مج القسم الخامس - المجلد الحادي عشر ص 141',
    'مج القسم الخامس المجلد السابع ص 135',
]
assert _matches_allowed('مج القسم الخامس - المجلد السابع ص 511', allowed)
assert _matches_allowed('مج القسم الخامس - المجلد الحادي عشر ص 141', allowed)
assert _matches_allowed('مج القسم الخامس المجلد السابع ص 135', allowed)
assert not _matches_allowed('مج القسم الخامس - المجلد التاسع ص 999', allowed)
print('MULTIPLE_VALID_PUBLICATIONS_ACTIVE')
PY

echo '[6/6] النتيجة'
echo 'APPEAL_PUBLICATION_RULE=ANY_STORED_LOCATION_IS_VALID'
git log -1 --oneline
