#!/bin/bash
# استكمال: إضافة "legislation" إلى مجموعة "laws" (السطر 5485) التي لم يشملها الإصلاح السابق
set -e
APP=/opt/LegalMind/admin/app.py
cp -a "$APP" /root/app.py.bak-laws-tab

python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
p = "/opt/LegalMind/admin/app.py"
src = open(p, encoding="utf-8").read()
old = '("legislation_article", "legislation_issuing_article", "legislation_preamble")'
new = '("legislation_article", "legislation", "legislation_issuing_article", "legislation_preamble")'
if new in src:
    print("معدّل مسبقاً — لا حاجة لتغيير")
elif old in src:
    src = src.replace(old, new)
    open(p, "w", encoding="utf-8").write(src)
    print("تمت الإضافة ✓")
else:
    print("تحذير: لم أجد النص المتوقع — لم يتغير شيء")
PYEOF

grep -n '"laws"' "$APP" | head -3
/opt/LegalMind/.venv/bin/python -m py_compile "$APP" && echo "الكود سليم ✓"
systemctl restart legalmind-admin
sleep 3
systemctl is-active legalmind-admin && echo "الخدمة تعمل ✓"
