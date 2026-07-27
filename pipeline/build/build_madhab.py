#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف (app.py فقط): إصلاح استحضار المذهبين عند عدم تحديد المذهب + إدراج إجراء محكمة الأسرة.
- عند عدم تحديد المذهب تُستحضَر حِزم 51/1984 (سنّي) و124/2019 (جعفري) معًا (كانت تقتصر على السنّي).
- يُضاف الإجراء المسبق لمحكمة الأسرة (12/2015 م8-11) في الجسر بالفرعين — فكلاهما موجود في القاعدة
  لكن لم يكن يصل السياق. لا إدخال ولا إعادة فهرسة. اختبار وظيفيّ يتحقّق من حضورهما."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/madhab_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 app.py =="; echo "المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
grep -q "madhab_set" "$TMP/app.py" && echo "إصلاح المذهب موجود" || {{ echo "خطأ"; exit 1; }}
cp -f "$APP" "$APP.bak.madhab"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.madhab" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: المذهبان + محكمة الأسرة =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def has(ids,p): return len([i for i in ids if i.startswith(p)])
V="زوج يضرب زوجته ويهددها وتطلب الطلاق للضرر وحضانة الأولاد"
# 1) بلا مذهب: يجب حضور المذهبين معًا + محكمة الأسرة
u=m._draft_bundles("استشارة",V,[],None,"أحوال شخصية")
print("  [بلا مذهب] 51/1984:",has(u,"legis-51-1984"),"| 124/2019:",has(u,"legis-124-2019"),"| 12/2015:",has(u,"legis-12-2015"))
assert has(u,"legis-51-1984") and has(u,"legis-124-2019"), "المذهبان لم يحضرا عند عدم التحديد!"
assert has(u,"legis-12-2015"), "إجراء محكمة الأسرة (12/2015) غائب!"
# 2) مذهب جعفري صراحةً: 124/2019 دون 51/1984
j=m._draft_bundles("استشارة",V,[],"جعفري","أحوال شخصية")
print("  [جعفري] 124/2019:",has(j,"legis-124-2019"),"| 51/1984:",has(j,"legis-51-1984"))
assert has(j,"legis-124-2019") and not has(j,"legis-51-1984"), "توجيه الجعفري خاطئ!"
# 3) مذهب سنّي صراحةً: 51/1984 دون 124/2019
s=m._draft_bundles("استشارة",V,[],"سني","أحوال شخصية")
print("  [سنّي] 51/1984:",has(s,"legis-51-1984"),"| 124/2019:",has(s,"legis-124-2019"))
assert has(s,"legis-51-1984") and not has(s,"legis-124-2019"), "توجيه السنّي خاطئ!"
# 4) الفرع الجزائيّ بلا مذهب: الجسر يجلب المذهبين + محكمة الأسرة
jz=m._draft_bundles("استشارة",V,[],None,"جزائي")
print("  [جزائي/بلا مذهب] 51/1984:",has(jz,"legis-51-1984"),"| 124/2019:",has(jz,"legis-124-2019"),"| 12/2015:",has(jz,"legis-12-2015"))
assert has(jz,"legis-12-2015"), "12/2015 غائب في الفرع الجزائيّ!"
print("  ✓ المذهبان يحضران عند عدم التحديد، والتوجيه صحيح عند التحديد، ومحكمة الأسرة حاضرة")
PY2
echo '=== تم: استحضار المذهبين عند عدم التحديد + إجراء محكمة الأسرة 12/2015 ==='
"""
(H / "run_madhab.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_madhab.sh && sha256sum run_madhab.sh"
(H / "DEPLOY_madhab.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_madhab.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
