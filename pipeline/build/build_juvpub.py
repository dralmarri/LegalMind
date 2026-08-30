#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف (app.py فقط): محفّز حظر نشر أسماء/صور الأحداث ⇒ استحضار 111/2015 م67 (الحظر + الجزاء
1000-5000 د) مع م40/م43 — فلا يُظنّ نصّ الحظر وعقوبته «غير مرفق». لا إدخال ولا إعادة فهرسة."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/juvpub_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 app.py =="; echo "المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
grep -q "_juv_publication_ids" "$TMP/app.py" && echo "محفّز حظر النشر موجود" || {{ echo "خطأ"; exit 1; }}
cp -f "$APP" "$APP.bak.juvpub"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.juvpub" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق: سؤال نشر اسم الحدث يجلب م67 (الحظر + الجزاء) =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
ids=m._draft_bundles("استشارة","حدث ارتكب سرقة هل يجوز نشر اسمه وصورته في الصحف وما عقوبة ذلك",[],None,"جزائي")
print("  م67 (حظر النشر + الجزاء):", "legis-111-2015-m67" in ids, "| م40 (سرّية):", "legis-111-2015-m40" in ids, "| م43 (الصحيفة):", "legis-111-2015-m43" in ids)
assert "legis-111-2015-m67" in ids, "م67 لم تُستحضَر!"
# لا تفعيل زائف: نشر بلا حدث
ids2=m._draft_bundles("استشارة","نشر إعلان قضائي في الجريدة الرسمية",[],None,"مدني")
assert "legis-111-2015-m67" not in ids2, "تفعيل زائف على نشر غير الأحداث!"
print("  ✓ م67 حاضرة لسؤال نشر اسم الحدث، ولا تُفعَّل لغيره")
PY2
echo '=== تم: محفّز حظر نشر اسم/صورة الحدث (111/2015 م67 — الحظر والجزاء) ==='
"""
(H / "run_juvpub.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_juvpub.sh && sha256sum run_juvpub.sh"
(H / "DEPLOY_juvpub.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_juvpub.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
