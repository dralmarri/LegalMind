#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط: توسيعُ `_LAWREF_RE` بنمطٍ ثالث «N لسنه YYYY» المجرّد كي يُلتقَط تعريفُ القانون حين
يفصل اسمُه بين «قانون» ورقمه («قانون المفرقعات 35 لسنة 1985») — فيعمل رسمُ الديباجات لهذه الصياغة.
آمنٌ: لاحقة «لسنه YYYY» خاصّةٌ بأرقام القوانين لا المواد (لا يلتقط «المادة 35 من قانون الجزاء»). المحتوى
مُدخَلٌ سلفًا فلا فهرسة. نسخةٌ احتياطية + استرجاعٌ تلقائيّ + اختبارٌ وظيفيّ (يشمل الاستعلام الذي كان يفشل)."""
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
TMP=/tmp/lawref_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
grep -q "a, b, c, d, e, f in _LAWREF_RE" "$TMP/app.py" && echo "موجود: نمط N لسنه YYYY" || {{ echo "خطأ: لم يُحدَّث المستهلك"; exit 1; }}
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.lawref"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.lawref" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q): return set(m._draft_bundles("استشارة",q,[],None,None))
# الاستعلام الذي كان يفشل (اسمُ القانون يفصل «قانون» عن رقمه):
d=ids("ما القوانين المتصلة بقانون المفرقعات 35 لسنة 1985؟")
assert "legis-35-1985-preamble" in d, "لم يُلتقَط 35/1985 من الصياغة المسمّاة!"
print("  ✓ رسم الديباجات يعمل الآن للصياغة «قانون المفرقعات 35 لسنة 1985»")
# صياغاتٌ أخرى ما زالت تعمل:
for q,law in [("القانون رقم 88 لسنة 1995 لمحاكمة الوزراء","legis-88-1995-preamble"),
              ("أحكام القانون 20 لسنة 2019 للغش التجاري","legis-20-2019-preamble")]:
    assert law in ids(q), q
print("  ✓ الصيغ الأخرى (88/1995، 20/2019) سليمة")
# لا التقاطٌ زائف لأرقام المواد:
import re
assert m._LAWREF_RE.findall(m._draft_norm_ar("نص المادة 35 من قانون الجزاء رقم 16")) == [] or \
       all(t[4]=="" for t in m._LAWREF_RE.findall(m._draft_norm_ar("المادة 35 من قانون الجزاء")))
print("  ✓ لا التقاط زائف لـ«المادة N» (النمط الثالث يتطلّب «لسنه YYYY»)")
print("  === تمّ =====")
PY2
echo '=== تم: توسيع _LAWREF_RE بالنمط «N لسنه YYYY» — رسمُ الديباجات يلتقط الصياغات المسمّاة — تطبيقيٌّ فقط ==='
"""
(H / "run_lawref.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_lawref.sh && sha256sum run_lawref.sh"
(H / "DEPLOY_lawref.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_lawref.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; app sha embedded")
r = subprocess.run(["bash", "-n", str(H / "run_lawref.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
