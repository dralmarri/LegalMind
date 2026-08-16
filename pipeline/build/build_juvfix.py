#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف (app.py فقط): ربط «حدث/قاصر + جريمة» ⇒ استحضار مواد عقوبات الأحداث (111/2015 م15-32)
مبكّرًا لتنجو من القصّ. مطابقة بحدود الكلمة (فلا تُفعِّلها «يحدث»). لا إدخال ولا إعادة فهرسة."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/juvfix_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 app.py =="; echo "المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
grep -q "_juvenile_penalty_ids" "$TMP/app.py" && echo "التحسين موجود" || {{ echo "خطأ"; exit 1; }}
cp -f "$APP" "$APP.bak.juvfix"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.juvfix" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: «حدث + جريمة» ⇒ عقوبات الأحداث (م15) =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
ids=m._draft_bundles("استشارة","حدث عمره 16 سنة ارتكب سرقة ما التدابير والعقوبة",[],None,"جزائي")
pos=ids.index("legis-111-2015-m15")+1 if "legis-111-2015-m15" in ids else None
print("  م15 (عقوبة الحدث) ترتيب:",pos)
assert "legis-111-2015-m15" in ids, "م15 لم تُستحضَر!"
# لا تُفعَّل على «يحدث خلاف» (حدود الكلمة)
ids2=m._draft_bundles("استشارة","يحدث خلاف حول عقد إيجار",[],None,"جزائي")
assert not [i for i in ids2 if i.startswith("legis-111-2015-m1")], "تفعيل زائف على «يحدث»!"
print("  ✓ «حدث+جريمة» يجلب م15، و«يحدث» لا يُفعِّلها")
PY2
echo '=== تم: ربط جريمة الحدث بمواد عقوبات الأحداث (111/2015 م15-32) ==='
"""
(H / "run_juvfix.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_juvfix.sh && sha256sum run_juvfix.sh"
(H / "DEPLOY_juvfix.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app); print("run_juvfix.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
