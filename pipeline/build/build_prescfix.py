#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف (app.py فقط): محفّز التقادم العامّ ⇒ استحضار مدد سقوط الدعوى/العقوبة (16/1960 م3-م10)
في أيّ سؤالٍ جزائيّ يمسّ التقادم — فتكتمل الإجابة بالمدد لا بالمبدأ. لا إدخال ولا إعادة فهرسة."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/prescfix_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 app.py =="; echo "المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
grep -q "_prescription_ids" "$TMP/app.py" && echo "محفّز التقادم موجود" || {{ echo "خطأ"; exit 1; }}
cp -f "$APP" "$APP.bak.prescfix"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.prescfix" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق: سؤال جزائيّ عن التقادم يجلب 16/1960 م4/م6 =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
ids=m._draft_bundles("استشارة","متهم في جناية اتجار بالمخدرات، هل تسقط الدعوى الجزائية بالتقادم وما المدة",[],None,"جزائي")
print("  م4 (تقادم الجنايات):", "legis-16-1960-m4" in ids, "| م6 (الجنح):", "legis-16-1960-m6" in ids,
      "| م8 (الانقطاع):", "legis-16-1960-m8" in ids)
assert "legis-16-1960-m4" in ids and "legis-16-1960-m6" in ids, "مواد التقادم لم تُستحضَر!"
# لا تفعيل زائف على سؤالٍ بلا تقادم
ids2=m._draft_bundles("استشارة","عقوبة حيازة سلاح غير مرخص",[],None,"جزائي")
assert "legis-16-1960-m4" not in ids2, "تفعيل زائف للتقادم!"
print("  ✓ مدد التقادم (16/1960 م3-م10) تُستحضَر عند ذكر التقادم، ولا تُفعَّل لغيره")
PY2
echo '=== تم: محفّز التقادم العامّ (16/1960 م3-م10) لكل الفروع الجزائية ==='
"""
(H / "run_prescfix.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_prescfix.sh && sha256sum run_prescfix.sh"
(H / "DEPLOY_prescfix.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_prescfix.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
