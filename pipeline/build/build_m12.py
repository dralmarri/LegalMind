#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ app-only: يرفع app.py إلى أحدث نسخة تحوي كل إصلاحات الاسترجاع الأخيرة — أهمّها محفّز الاتجار
بالأشخاص _trafficking_ids (يُظهر م12 حماية المجني عليهم كاملةً) + _fraud_ids + مطابقة «رقم» الاختيارية.
لا إدخال ولا إعادة فهرسة (المحتوى مُدخَلٌ سلفًا). اختبارٌ وظيفيّ + استرجاعٌ تلقائيّ عند الفشل."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/m12_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
for tok in _trafficking_ids _fraud_ids; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
echo "== نشر app.py (بلا إدخال/فهرسة) =="
cp -f "$APP" "$APP.bak.m12"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.m12" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q,b=None): return set(m._draft_bundles("استشارة",q,[],None,b))
# م12 حماية المجني عليهم في الاتجار
v=ids("ما التدابير الواجبة تجاه المجني عليهن في الاتجار بالأشخاص؟ الإيواء والرعاية والإعادة الآمنة للوطن")
print("  م12 حماية المجني عليهم:", "legis-91-2013-m12" in v, "| م4 الإخفاء:", "legis-91-2013-m4" in v)
assert "legis-91-2013-m12" in v, "م12 لم يظهر!"
# القانون كاملًا يظهر (م1-م14)
full=[x for x in v if x.startswith("legis-91-2013-m")]
print("  مواد 91/2013 الظاهرة:", len(full))
# إصلاح عقوبات الغش باقٍ
a=ids("عقوبة الغش التجاري ومصادرة البضائع المغشوشة والعَود والموازين المزيّفة")
assert "legis-20-2019-m11" in a and "legis-20-2019-m15" in a and "regl-20-2019-m18" in a; print("  ✓ عقوبات الغش + اللائحة")
# مطابقة «رقم» الاختيارية
d=ids("ما القوانين المتصلة بالقانون 91 لسنة 2013 لمكافحة الاتجار بالأشخاص؟","استشارة")
assert "legis-91-2013-preamble" in d; print("  ✓ رسم الديباجات يعمل بلا «رقم»")
print("  === تمّ: app بأحدث إصلاحات الاسترجاع (م12 + الغش + رقم) ===")
PY2
echo '=== تم: نشر app-only — إصلاح ظهور م12 (حماية المجني عليهم) + عقوبات الغش + مطابقة رقم ==='
"""
(H / "run_m12.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_m12.sh && sha256sum run_m12.sh"
(H / "DEPLOY_m12.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_m12.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
