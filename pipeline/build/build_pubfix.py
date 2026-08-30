#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف (app.py فقط): توسيع كواشف جرائم المال العام (1/1993) لتلتقط الصياغة الواقعية
(«أضرّ بأموال الهيئة»، «عمولة»، «صفقة توريد»، «التحفّظ على الأموال») لا الاصطلاحية فقط، وإضافة
م20 (رد المال/الرأفة) وم24 (الإجراءات التحفظية شاملةً أموال الزوجة والأولاد) لِما يُستحضَر.
لا إدخال ولا إعادة فهرسة."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/pubfix_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 app.py =="; echo "المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
grep -q "صياغات واقعية" "$TMP/app.py" && echo "توسيع كواشف المال العام موجود" || {{ echo "خطأ"; exit 1; }}
cp -f "$APP" "$APP.bak.pubfix"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.pubfix" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق: السؤال الواقعيّ (عمولة/توريد/إضرار بأموال الهيئة) يجلب 1/1993 =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
q=("مدير إدارة المشتريات في هيئة عامة موظف عام تولى الإشراف على صفقة توريد بقيمة مليون دينار "
   "فتواطأ مع الشركة المورّدة وتعمّد رفع الأسعار مقابل عمولة قبضها لنفسه ثمانين ألف دينار مما أضرّ "
   "بأموال الهيئة، اكتُشف بعد تسع سنوات بعد إحالته للتقاعد. ما التكييف والعقوبة وهل تسقط بالتقادم "
   "وهل يُلزم بالرد وهل يمكن التحفّظ على أمواله وأموال زوجته وأولاده")
ids=m._draft_bundles("استشارة",q,[],None,"جزائي")
need=[("legis-1-1993-m11","الإضرار العمدي بالصفقة"),("legis-1-1993-m12","التربّح من التوريدات"),
      ("legis-1-1993-m16","العزل والرد وغرامة الضعف"),("legis-1-1993-m20","رد المال قبل المرافعة"),
      ("legis-1-1993-m21-mukarrar","عدم سقوط الدعوى بالتقادم"),("legis-1-1993-m24","التحفّظ على أموال المتهم والأسرة")]
for k,lbl in need:
    print("  "+lbl+" ("+k+"):", k in ids)
assert all(k in ids for k,_ in need), "بعض مواد 1/1993 الحاكمة لم تُستحضَر على السؤال الواقعيّ!"
# لا تفعيل زائف
for neg in ["عقد إيجار شقة سكنية","طلاق للضرر ونفقة حضانة"]:
    n=m._draft_bundles("استشارة",neg,[],None,"مدني")
    assert not [i for i in n if i.startswith("legis-1-1993")], "تفعيل زائف على: "+neg
print("  ✓ 1/1993 يُستحضَر على الصياغة الواقعية (م11/م12/م16/م20/م21مكرر/م24)، ولا يُفعَّل زيفًا")
PY2
echo '=== تم: توسيع كواشف المال العام 1/1993 للصياغة الواقعية + م20/م24 ==='
"""
(H / "run_pubfix.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_pubfix.sh && sha256sum run_pubfix.sh"
(H / "DEPLOY_pubfix.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_pubfix.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
