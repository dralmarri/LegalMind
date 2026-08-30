#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف (app.py فقط): يضيف حزمة «عقوبات إقرار الذمة المالية والكسب غير المشروع» (2/2016 م46-48)
ويُقدّمها لتنجو من قصّ الميزانية. سبب الإصلاح: إجابة اختبارٍ واقعيّ قالت خطأً إنّ جزاء «عدم تقديم
إقرار الذمة في الموعد» غير موجود في المصادر، بينما م46 يعاقب عليه صراحةً (غرامة + جواز العزل) —
لكنّه لم يكن يُستحضَر (لغته بعيدة دلاليًّا فلم يجلبه المتجه، وحزمة العقوبات العامة لم تشتعل).
لا إدخال ولا إعادة فهرسة. نسخة احتياطية + إعادة تشغيل + اختبار وظيفيّ يتأكّد من حضور م46."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/declpen_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 app.py =="; echo "المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
grep -q "عقوبات إقرار الذمة المالية والكسب غير المشروع" "$TMP/app.py" && echo "حزمة عقوبات الذمة موجودة" || {{ echo "خطأ: مفقودة"; exit 1; }}
cp -f "$APP" "$APP.bak.declpen"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.declpen" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: م46 (عقوبة عدم تقديم/تأخّر الإقرار) ضمن المستحضَر =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
facts=("مدير إدارة المشتريات في وزارة من الخاضعين لإقرار الذمة المالية لم يقدم إقراره "
       "وتلقى مبالغ من شركة مقاولات مقابل ترسية عقد عليها وأبلغ موظف الشركة هيئة نزاهة "
       "ما المسؤوليات الجزائية للموظف وللشركة وما الحماية للمبلغ")
ids=m._draft_bundles("استشارة",facts,[],None,"جزائي")
for need in ("legis-2-2016-m46","legis-2-2016-m47","legis-2-2016-m48"):
    pos=ids.index(need)+1 if need in ids else None
    print("  "+need+" -> ترتيب", pos)
assert "legis-2-2016-m46" in ids, "م46 غائبة!"
print("  ✓ عقوبة عدم تقديم/تأخّر إقرار الذمة (م46) حاضرة")
PY2
echo '=== تم: إصلاح استحضار عقوبات إقرار الذمة المالية (2/2016 م46-48) ==='
"""
(H / "run_declpen.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_declpen.sh && sha256sum run_declpen.sh"
(H / "DEPLOY_declpen.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_declpen.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
