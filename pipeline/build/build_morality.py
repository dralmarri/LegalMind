#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ app-only: جسر جرائم الآداب/الدعارة في قانون الجزاء 16/1960 (_morality_ids) — يستحضر م180/م191/
م192/م199/م200-م204 لأسئلة الآداب المستقلّة ولوقائع الاتجار بالأشخاص للاستغلال الجنسيّ. مواد مُتحقَّقة،
مُدخَلة سلفًا؛ لا إدخال ولا إعادة فهرسة. اختبارٌ وظيفيّ + استرجاعٌ تلقائيّ."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/morality_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
grep -q "_morality_ids" "$TMP/app.py" && echo "جسر الآداب موجود" || {{ echo "خطأ"; exit 1; }}
echo "== نشر app.py (بلا إدخال/فهرسة) =="
cp -f "$APP" "$APP.bak.morality"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.morality" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q,b=None): return set(m._draft_bundles("استشارة",q,[],None,b))
# (1) الاتجار للاستغلال الجنسيّ ⇒ 91/2013 + عنقود الآداب في 16/1960
a=ids("جماعة اتجرت بنساء أجنبيات لغرض الاستغلال الجنسي وأكرهتهن على الدعارة")
need=["legis-91-2013-m2","legis-16-1960-m201","legis-16-1960-m202","legis-16-1960-m203","legis-16-1960-m191"]
print("  الاتجار الجنسيّ ⇒ 91/2013 + آداب 16/1960:", {{k.split('-1960-')[-1].split('-2013-')[-1]:(k in a) for k in need}})
assert all(k in a for k in need), "جسر الآداب لم يعمل مع الاتجار!"
# (2) سؤال آداب مستقلّ (بلا اتجار)
b=ids("عقوبة إنشاء وإدارة محل للدعارة والقوادة والتحريض على الفجور")
assert all(("legis-16-1960-m%d"%n) in b for n in (200,202,203,204)); print("  ✓ جرائم الدعارة المستقلّة (م200-م204)")
# (3) هتك العرض
c=ids("جريمة هتك العرض بالإكراه على قاصر")
assert "legis-16-1960-m191" in c and "legis-16-1960-m192" in c; print("  ✓ هتك العرض (م191/م192)")
# (4) التصنيف
br=m._resolve_branch(None, m._draft_norm_ar("جريمة الدعارة والفجور"))
print("  التصنيف (دعارة ⇒):", br); assert "جزاي" in m._draft_norm_ar(br)
# (5) لا تفعيل زائف
assert not any("legis-16-1960-m20" in x for x in ids("عقوبة السرقة والنصب") if x in ("legis-16-1960-m200","legis-16-1960-m201"))
print("  ✓ لا تفعيل زائف")
print("  === تمّ: جسر جرائم الآداب/الدعارة 16/1960 (مستقلّ + مع الاتجار الجنسيّ) ===")
PY2
echo '=== تم: نشر app-only — جسر جرائم الآداب/الدعارة في 16/1960 (م180/م191-م204) ==='
"""
(H / "run_morality.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_morality.sh && sha256sum run_morality.sh"
(H / "DEPLOY_morality.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_morality.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
