#!/bin/bash
# الإصلاح: إضافة النوع الجديد "legislation" إلى قوائم أنواع البحث في الاستوديو
set -e
APP=/opt/LegalMind/admin/app.py
cp -a "$APP" /root/app.py.bak-draft-types
echo "نسخة احتياطية: /root/app.py.bak-draft-types"

python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
import re
p = "/opt/LegalMind/admin/app.py"
src = open(p, encoding="utf-8").read()

hits = 0
def add(m):
    global hits
    lst = m.group(0)
    if '"legislation"' in lst:   # موجود أصلاً كعنصر مستقل
        return lst
    hits += 1
    return lst.replace('"legislation_article"', '"legislation_article", "legislation"', 1)

# أي قائمة أنواع تحتوي legislation_article يُضاف إليها legislation
src = re.sub(r'\[[^\[\]]*"legislation_article"[^\[\]]*\]', add, src)
open(p, "w", encoding="utf-8").write(src)
print("عدد القوائم المعدلة:", hits)
PYEOF

echo ""
echo "== القوائم بعد التعديل =="
grep -n '"legislation_article"' "$APP" | head -10

echo ""
echo "== فحص سلامة الكود ثم إعادة تشغيل الخدمة =="
/opt/LegalMind/.venv/bin/python -m py_compile "$APP" && echo "الكود سليم ✓"
systemctl restart legalmind-admin
sleep 3
systemctl is-active legalmind-admin && echo "الخدمة تعمل ✓"
echo ""
echo "===== اكتمل الإصلاح — أعد طرح السؤال في الاستوديو الآن ====="
