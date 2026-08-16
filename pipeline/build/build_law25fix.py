#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف (app.py فقط) يُصلح تفعيل حزمة 25/1996: توسيع المفاتيح لتُطابق لغة الوقائع الطبيعية
(«عمولة نقدية لوسيط»، «عقد توريد مع وزارة») + تقديم الحزمة في الترتيب لتنجو مواد العقوبة م4/م5
من قصّ الميزانية. لا إدخال ولا إعادة فهرسة (البيانات مُدخَلة أصلًا). نسخة احتياطية + إعادة تشغيل
+ اختبار وظيفيّ يتأكّد أنّ م4 وم5 ضمن المعرّفات المستحضَرة لسؤال طبيعيّ."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law25fix_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 app.py =="; echo "المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
grep -q "الكشف عن العمولات في عقود الدولة" "$TMP/app.py" && echo "الحزمة موجودة" || {{ echo "خطأ: الحزمة مفقودة"; exit 1; }}
cp -f "$APP" "$APP.bak.law25fix"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law25fix" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: م4/م5 ضمن المستحضَر لسؤال بلغة طبيعية =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
facts=("شركة فازت بعقد توريد مع وزارة قيمته ثلاثمائة ألف دينار ودفعت عمولة نقدية "
       "لوسيط سهّل لها إرساء الصفقة ولم تدرج ذكرها في العقد ولم تقدم عنها أي إقرار")
ids=m._draft_bundles("استشارة",facts,[],None,"جزائي")
law25=[i for i in ids if i.startswith("legis-25-1996")]
print("  مواد 25/1996 المستحضَرة:",len(law25),"->",law25)
for need in ("legis-25-1996-m4","legis-25-1996-m5"):
    assert need in ids, need+" مفقودة!"
print("  ✓ عقوبتا عدم الإقرار (م4) والبيان الكاذب/الإخفاء (م5) حاضرتان")
PY2
echo '=== تم: إصلاح تفعيل حزمة 25/1996 (مفاتيح أوسع + أولوية ترتيب تنجّي م4/م5) ==='
"""
(H / "run_law25fix.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law25fix.sh && sha256sum run_law25fix.sh"
(H / "DEPLOY_law25fix.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_law25fix.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
