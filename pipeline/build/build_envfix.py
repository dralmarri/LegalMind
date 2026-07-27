#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط: جسرُ «المخالفة⇄العقوبة» في محفّز البيئة `_environment_ids`. نصُّ العقوبة في 42/2014
يُحيل على مادةٍ برقمها («كل من خالف المادة (25)») فيبعُد دلاليًّا عن وصف المخالفة ويُقصّ؛ فنقرن كلَّ عقوبةٍ
بموضوعها: النفايات الخطرة⇒م130/م131 (تبلغ الإعدام)، التلوث البحري/جون الكويت (م68)⇒م141/م142/م146،
المحميات/التنوع⇒م149/م150 — لتظهرَ العقوبةُ مع المخالفة مهما صيغ السؤال. المحتوى مُدخَلٌ سلفًا (8550) فلا فهرسة."""
import base64, gzip, hashlib, pathlib, subprocess
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")


def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


b_app, s_app = enc(APP), sha(APP)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/envfix_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
grep -q "جسرُ المخالفة" "$TMP/app.py" && echo "موجود: جسر المخالفة⇄العقوبة" || {{ echo "خطأ"; exit 1; }}
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.envfix"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.envfix" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q): return set(m._draft_bundles("استشارة",q,[],None,None))
# السيناريو الذي فشل: مصنع ألقى نفايات خطرة في جون الكويت
a=ids("مصنع ألقى نفايات خطرة في جون الكويت، ما العقوبة الجزائية والمسؤولية المدنية عن الأضرار البيئية؟")
for n in (130,131,141,142,108,149):
    assert ("legis-42-2014-m%d"%n) in a, "عقوبة م%d لم تُستحضَر!"%n
print("  ✓ عقوبات الواقعة تُستحضَر: م130/م131 (نفايات خطرة⇒الإعدام) + م141/م142 (بحري) + م108/م149 (حظر جون الكويت وعقوبته)")
for n in (68,73):
    assert ("legis-42-2014-m%d"%n) in a, "الحظر الموضوعي م%d لم يُستحضَر!"%n
print("  ✓ الحظر الموضوعي البحري حاضر: م68 (المناطق المحظورة) + م71-76 ومنها م73 (تصريف المنشآت الصناعية)")
# المسؤولية المدنية أيضًا
assert any(("legis-42-2014-m%d"%n) in a for n in (159,160,161))
print("  ✓ المسؤولية المدنية (م159/م160/م161) حاضرة معها")
# الجسر يعمل ولو خلا السؤال من لفظ «عقوبة»
b=ids("إلقاء النفايات الخطرة في البيئة البحرية")
assert "legis-42-2014-m130" in b and "legis-42-2014-m141" in b
print("  ✓ الجسر يُطلَق على الموضوع ولو بلا لفظ «عقوبة»")
# لا انحدار: قانون آخر لا يتأثر
c=ids("ما عقوبة القيادة تحت تأثير المسكر في قانون المرور؟")
assert "legis-67-1976-m38" in c
print("  ✓ لا انحدار: محفّز المرور (م38) سليم")
print("  === تمّ =====")
PY2
echo '=== تم: جسر المخالفة⇄العقوبة لقانون البيئة 42/2014 — عقوبةُ النفايات الخطرة/التلوث البحري تظهر مع المخالفة — تطبيقيٌّ فقط ==='
"""
(H / "run_envfix.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_envfix.sh && sha256sum run_envfix.sh"
(H / "DEPLOY_envfix.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_envfix.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; app sha embedded")
r = subprocess.run(["bash", "-n", str(H / "run_envfix.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
