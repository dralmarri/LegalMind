#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف (app.py فقط): إضافة م46/م47 لِما يجلبه محفّز المخدرات — إذ تُحيل إليهما م74 في استثناء
عدم التقادم، فيَجزم النموذج انطباقها من عدمه بدل «غير مرفقين». لا إدخال ولا إعادة فهرسة."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()
SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/drugsref_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 app.py =="; echo "المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
cp -f "$APP" "$APP.bak.drugsref"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.drugsref" "$APP"; systemctl restart legalmind-admin; exit 1; }}
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
ids=m._draft_bundles("استشارة","متهم بتعاطي مخدرات هل تسقط الدعوى بالتقادم وهل واقعته من م46 او م47",[],None,"جزائي")
print("  م46:", "legis-159-2025-m46" in ids, "| م47:", "legis-159-2025-m47" in ids, "| م74:", "legis-159-2025-m74" in ids)
assert "legis-159-2025-m46" in ids and "legis-159-2025-m47" in ids, "م46/م47 لم تُستحضَر!"
print("  ✓ م46/م47 تُجلبان مع م74 (استثناء عدم التقادم)")
PY2
echo '=== تم: إضافة م46/م47 لمحفّز المخدرات (إحالة م74) ==='
"""
(H/"run_drugsref.sh").write_text(SH,encoding="utf-8")
one="printf '%s' '"+base64.b64encode(gzip.compress(SH.encode(),9)).decode()+"' | base64 -d | gunzip > run_drugsref.sh && sha256sum run_drugsref.sh"
(H/"DEPLOY_drugsref.txt").write_text(one+"\n",encoding="utf-8")
print("app sha:",s_app); print("run sha:",hashlib.sha256(SH.encode()).hexdigest())
