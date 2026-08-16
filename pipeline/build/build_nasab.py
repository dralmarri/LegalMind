#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ app-only لمحفّزات 53/2026 (دعاوى النسب وتصحيح الأسماء): حزمتان في فرع الأحوال (النسب + تصحيح
الأسماء، للمذهبين) + إشارات المصنّف + إدراج 53/2026 في رسم الديباجات. لا إدخال ولا إعادة فهرسة (المواد
مُدخَلةٌ سلفًا). اختبارٌ وظيفيّ + استرجاعٌ تلقائيّ عند الفشل."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/nasab_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
grep -q "legis-53-2026" "$TMP/app.py" && echo "حزم 53/2026 موجودة" || {{ echo "خطأ"; exit 1; }}
echo "== نشر app.py (بلا إدخال/فهرسة) =="
cp -f "$APP" "$APP.bak.nasab"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.nasab" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q,b=None): return set(m._draft_bundles("استشارة",q,[],None,b))
# حزمة النسب (فرع الأحوال، بلا مذهب ⇒ للطرفين)
a=ids("دعوى إثبات النسب غير المباشر ونفيه أمام لجنة دعاوى النسب")
need_a=["legis-53-2026-m1","legis-53-2026-m4","legis-53-2026-m8","legis-53-2026-m14","legis-53-2026-m18"]
print("  النسب:", {{k.split('-m')[1]:(k in a) for k in need_a}})
assert all(k in a for k in need_a), "حزمة النسب ناقصة!"
# حزمة تصحيح الأسماء
b=ids("طلب تصحيح الاسم الشخصي وتغيير اللقب")
need_b=["legis-53-2026-m11","legis-53-2026-m12","legis-53-2026-m15","legis-53-2026-m17"]
print("  تصحيح الأسماء:", {{k.split('-m')[1]:(k in b) for k in need_b}})
assert all(k in b for k in need_b), "حزمة تصحيح الأسماء ناقصة!"
# التصنيف التلقائيّ: سؤال نسب بلا فرعٍ صريح ⇒ أحوال شخصية
br=m._resolve_branch(None, m._draft_norm_ar("طلب تصحيح الاسم أمام لجنة دعاوى النسب"))
print("  التصنيف (تصحيح الاسم ⇒):", br); assert "حوال" in br
# رسم الديباجات: سؤالٌ يسمّي 53/2026 ⇒ يستحضر ديباجته وقوانينه المتّصلة المُدخَلة (111/2015، 124/2019، 51/1984…)
d=ids("ما القوانين المتصلة بالمرسوم بقانون رقم 53 لسنة 2026 لدعاوى النسب وتصحيح الأسماء؟","أحوال شخصية")
rel=sorted(x for x in d if x.endswith("-preamble"))
print("  ديباجات متّصلة:", rel[:8])
assert "legis-53-2026-preamble" in d, "ديباجة 53/2026 غائبة!"
assert any(x in d for x in ("legis-111-2015-preamble","legis-124-2019-preamble","legis-51-1984-preamble","legis-12-2015-preamble")), "لم تُستحضَر القوانين المتّصلة!"
# لا تفعيل زائف: سؤال نفقة لا يجرّ 53/2026
c=ids("نفقة الزوجة والمتعة ونفقة العدة")
print("  عدم تفعيل 53 لسؤال نفقة:", not any("53-2026" in x for x in c)); assert not any("53-2026" in x for x in c)
print("  ✓ حزمتا النسب/الأسماء + المصنّف + رسم الديباجات — كلّها تعمل")
PY2
echo '=== تم: محفّزات 53/2026 (دعاوى النسب وتصحيح الأسماء) — حزمتان + إشارات مصنّف + رسم ديباجات (app-only) ==='
"""
(H / "run_nasab.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_nasab.sh && sha256sum run_nasab.sh"
(H / "DEPLOY_nasab.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_nasab.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
