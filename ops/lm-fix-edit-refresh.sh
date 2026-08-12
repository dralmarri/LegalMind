#!/bin/bash
# التحديث الدوري لا يمسح المحرر المفتوح ولا اختيارات الصناديق
set -e
python3 - <<'PYEOF'
p = "/opt/LegalMind/admin/app.py"
src = open(p, encoding="utf-8").read()

OLD1 = 'function loadReview(){\n  fetch("/api/review/pending")'
NEW1 = 'function loadReview(){\n  if(document.querySelector("#review textarea"))return;\n  fetch("/api/review/pending")'
if 'querySelector("#review textarea")' not in src:
    assert OLD1 in src, "!! لم أجد loadReview — شغل lm-center-v2.sh أولا"
    src = src.replace(OLD1, NEW1, 1)

OLD2 = 'function loadSelection(){\n  fetch("/api/selection/pending")'
NEW2 = 'function loadSelection(){\n  if(document.querySelector("#selection input:checked"))return;\n  fetch("/api/selection/pending")'
if 'querySelector("#selection input:checked")' not in src:
    assert OLD2 in src, "!! لم أجد loadSelection"
    src = src.replace(OLD2, NEW2, 1)

open(p, "w", encoding="utf-8").write(src)
print("رُكبت حماية التحرير من التحديث التلقائي ✓")
PYEOF
/opt/LegalMind/admin/.venv/bin/python -m py_compile /opt/LegalMind/admin/app.py
systemctl restart legalmind-admin
sleep 2
systemctl is-active legalmind-admin
echo "تم - حدث صفحة المركز"
