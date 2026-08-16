#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ: (ب) جسر الجريمة الأصلية لغسل الأموال في app.py، و(أ) بناء رسم علاقات الديباجات وحفظه.
قراءةٌ فقط للقاعدة (لا إدخال ولا إعادة فهرسة)."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
PX = H / "preamble_xref.py"
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()
b_px = base64.b64encode(gzip.compress(PX.read_bytes(), 9)).decode()
s_px = hashlib.sha256(PX.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/predicate_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "app المتوقع: {s_app}"; echo "px المتوقع: {s_px}"
sha256sum "$TMP/app.py" "$TMP/preamble_xref.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/preamble_xref.py',encoding='utf-8').read()); print('px OK')"
grep -q "_predicate_offense_ids" "$TMP/app.py" && echo "جسر الجريمة الأصلية موجود" || {{ echo "خطأ"; exit 1; }}
echo "== (أ) بناء رسم علاقات الديباجات (قراءة فقط) =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py
echo "== نشر app.py (جسر الجريمة الأصلية) =="
cp -f "$APP" "$APP.bak.predicate"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.predicate" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== (ب) تحقّق وظيفيّ: غسل ⇄ الجريمة الأصلية =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
ids=m._draft_bundles("استشارة","متهم بغسل أموال متحصلة من الاتجار بالمخدرات، ما الجرائم والعقوبات",[],None,"جزائي")
print("  غسل (106 م2):", "legis-106-2013-m2" in ids, "| الجريمة الأصلية مخدرات (159 م42):", "legis-159-2025-m42" in ids)
assert "legis-106-2013-m2" in ids and "legis-159-2025-m42" in ids, "جسر الجريمة الأصلية لم يعمل!"
ids2=m._draft_bundles("استشارة","غسل أموال متحصلة من رشوة واختلاس مال عام",[],None,"جزائي")
print("  فساد ⇒ مال عام (1993 م9):", "legis-1-1993-m9" in ids2, "| رشوة/تربّح (31/1970 م35):", "legis-31-1970-m35" in ids2)
assert "legis-1-1993-m9" in ids2, "جسر الفساد لم يعمل!"
# لا تفعيل زائف: مخدرات بلا غسل
ids3=m._draft_bundles("استشارة","اتجار بالمخدرات فقط",[],None,"جزائي")
assert "legis-106-2013-m2" not in ids3, "تفعيل زائف لغسل الأموال!"
print("  ✓ الجسر يربط الغسل بقانون الجريمة الأصلية، ولا يُفعَّل لجريمةٍ بلا غسل")
PY2
echo '=== تم: (أ) رسم علاقات الديباجات + (ب) جسر الجريمة الأصلية لغسل الأموال ==='
"""
(H / "run_predicate.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_predicate.sh && sha256sum run_predicate.sh"
(H / "DEPLOY_predicate.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app); print("px sha:", s_px)
print("run_predicate.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
