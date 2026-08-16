#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف (app.py فقط): تقليص حزمة العنف الأسري 11/2026 إلى موادّها الحاكمة (12 مادة عملية بدل 29)،
وإضافة نواة جريمة الضرب المصغّرة (16/1960 م160/م163/م173) إلى جانب الجسر الجزائيّ — ليتّسع المقعد
فتنجو معًا: مواد 11/2026 الحاكمة + جريمة الضرب + الآثار الأسرية، في الاستشارة نفسها.
لا إدخال ولا إعادة فهرسة. اختبار وظيفيّ يتحقّق من نجاة المواد ضمن أوائل المعرّفات (عتبة القصّ)."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/famcore_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 app.py =="; echo "المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
grep -q "_FAMVIOL_CORE" "$TMP/app.py" && echo "التقليص موجود" || {{ echo "خطأ"; exit 1; }}
cp -f "$APP" "$APP.bak.famcore"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.famcore" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: نجاة المواد الحاكمة الأربعة ضمن أوائل المعرّفات (عتبة القصّ ~18-24) =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
V="زوج يضرب زوجته بصفة متكررة أمام أطفالها ويهددها وتطلب الطلاق وحضانة الأولاد"
def pos(ids,x): return (ids.index(x)+1) if x in ids else None
for br in ("جزائي","أحوال شخصية"):
    ids=m._draft_bundles("استشارة",V,[],None,br)
    p160=pos(ids,"legis-16-1960-m160")      # جريمة الضرب
    p13 =pos(ids,"legis-11-2026-m13")       # أمر الحماية
    p126=pos(ids,"legis-51-1984-m126")      # التفريق للضرر
    nf=len([i for i in ids if i.startswith("legis-11-2026")])
    print("  ["+br+"] ضرب م160 @"+str(p160)+" | أمر الحماية م13 @"+str(p13)+" | تفريق م126 @"+str(p126)+" | مواد 11/2026: "+str(nf))
    assert nf<=12, "11/2026 لم تُقلَّص! ("+str(nf)+")"
    assert p160 and p160<=24, "جريمة الضرب م160 خارج عتبة النجاة في فرع "+br
print("  ✓ التقليص فعّال، وجريمة الضرب تنجو في الفرعين")
PY2
echo '=== تم: تقليص 11/2026 إلى الحاكمة + ضمان نجاة جريمة الضرب في الفرعين ==='
"""
(H / "run_famcore.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_famcore.sh && sha256sum run_famcore.sh"
(H / "DEPLOY_famcore.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_famcore.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
