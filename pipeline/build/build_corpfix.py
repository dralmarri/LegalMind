#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف (app.py فقط): يضيف حزمة «مسؤولية الشخص الاعتباري عن جرائم الفساد» (31/1970 م59-61)
ويُقدّمها في الترتيب لتنجو من قصّ الميزانية، ويطعّم حزمة الرشوة بمحفّزات «مقابل ترسية/مبالغ مقابل».
سبب الإصلاح: إجابة اختبارٍ واقعيّ قالت خطأً «لا نصّ لمسؤولية الشخص الاعتباري في المصادر» بينما م59/م60
مُدخَلتان — لكنهما كانتا تُقصّان (ترتيب 53/54). لا إدخال ولا إعادة فهرسة. نسخة احتياطية + إعادة تشغيل
+ اختبار وظيفيّ يتأكّد أنّ م59/م60 ضمن المستحضَر لسؤالٍ عن مسؤولية شركة في قضية فساد."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/corpfix_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 app.py =="; echo "المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
grep -q "مسؤولية الشخص الاعتباري (الشركات) عن جرائم الفساد" "$TMP/app.py" && echo "حزمة الشخص الاعتباري موجودة" || {{ echo "خطأ: مفقودة"; exit 1; }}
cp -f "$APP" "$APP.bak.corpfix"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.corpfix" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: م59/م60 ضمن المستحضَر (وترتيبها ينجو) =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
facts=("مدير إدارة المشتريات في وزارة من الخاضعين لإقرار الذمة المالية لم يقدم إقراره "
       "وتلقى مبالغ من شركة مقاولات مقابل ترسية عقد عليها وأبلغ موظف الشركة هيئة نزاهة "
       "ما المسؤوليات الجزائية للموظف وللشركة وما الحماية للمبلغ")
ids=m._draft_bundles("استشارة",facts,[],None,"جزائي")
for need in ("legis-31-1970-m59","legis-31-1970-m60"):
    pos=ids.index(need)+1 if need in ids else None
    print("  "+need+" -> ترتيب", pos)
    assert need in ids, need+" غائبة!"
print("  ✓ مسؤولية الشخص الاعتباري (م59/م60) حاضرة ومتقدّمة الترتيب")
PY2
echo '=== تم: إصلاح استحضار مسؤولية الشخص الاعتباري (31/1970 م59-61) في قضايا الفساد ==='
"""
(H / "run_corpfix.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_corpfix.sh && sha256sum run_corpfix.sh"
(H / "DEPLOY_corpfix.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_corpfix.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
