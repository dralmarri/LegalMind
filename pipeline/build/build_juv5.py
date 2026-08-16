#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف (app.py فقط): إضافة قائمة تدابير الأحداث (111/2015 م5) وأساس التسليم (م6) إلى محفّز
«حدث + جريمة» — إذ تُحيل إليها م16 صراحةً — فتُستحضَر مع مواد العقوبات. لا إدخال ولا إعادة فهرسة."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/juv5_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 app.py =="; echo "المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
cp -f "$APP" "$APP.bak.juv5"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.juv5" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق: م5 (قائمة التدابير) + م15 (العقوبة) حاضرتان =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
ids=m._draft_bundles("استشارة","حدث عمره 16 ضبط بسرقة بالإكراه ما التدابير والعقوبة",[],None,"جزائي")
print("  م5(تدابير):", "legis-111-2015-m5" in ids, "| م6(تسليم):", "legis-111-2015-m6" in ids, "| م15(عقوبة):", "legis-111-2015-m15" in ids)
assert "legis-111-2015-m5" in ids and "legis-111-2015-m15" in ids, "م5 أو م15 غائبة!"
print("  ✓ قائمة التدابير (م5) والعقوبة (م15) حاضرتان معًا")
PY2
echo '=== تم: إضافة قائمة تدابير الأحداث (م5/م6) للمحفّز ==='
"""
(H / "run_juv5.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_juv5.sh && sha256sum run_juv5.sh"
(H / "DEPLOY_juv5.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_juv5.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
