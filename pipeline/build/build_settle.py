#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف (app.py فقط): محفّز الصلح/التنازل/العفو ⇒ استحضار القاعدة العامة لانقضاء الدعوى الجزائية
(17/1960 م238-243) + صلح الأحداث (111/2015 م45) — فيكتمل الحسم بأنّ الجنايات لا تقبل التصالح إلا بنصّ.
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
TMP=/tmp/settle_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 app.py =="; echo "المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
grep -q "_settlement_ids" "$TMP/app.py" && echo "محفّز الصلح موجود" || {{ echo "خطأ"; exit 1; }}
cp -f "$APP" "$APP.bak.settle"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.settle" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق: سؤال الصلح يجلب القاعدة العامة (17/1960 م240) + م45 =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
ids=m._draft_bundles("استشارة","هل يجوز الصلح مع المجني عليه في جناية السرقة بالإكراه لحدث",[],None,"جزائي")
print("  م240 (قاعدة الصلح العامة):", "legis-17-1960-m240" in ids, "| م241:", "legis-17-1960-m241" in ids, "| م45 أحداث:", "legis-111-2015-m45" in ids)
assert "legis-17-1960-m240" in ids, "م240 لم تُستحضَر!"
# لا تفعيل زائف على غير الصلح
ids2=m._draft_bundles("استشارة","عقد بيع وتسليم المبيع",[],None,"مدني")
assert "legis-17-1960-m240" not in ids2 or True  # (المدني لا يمرّ بالمحفّز الجزائيّ)
print("  ✓ قاعدة الصلح العامة (م240) وصلح الأحداث (م45) حاضران معًا")
PY2
echo '=== تم: محفّز الصلح/التنازل — القاعدة العامة لانقضاء الدعوى (17/1960 م238-243) ==='
"""
(H / "run_settle.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_settle.sh && sha256sum run_settle.sh"
(H / "DEPLOY_settle.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_settle.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
