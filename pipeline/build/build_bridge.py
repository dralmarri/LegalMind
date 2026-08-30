#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف (app.py فقط): «الجسر الأسريّ–الجزائيّ». عند محتوى عنفٍ أسريّ/إساءةٍ للطفل يصل الطرف
الناقص في كلّ فرع: الفرع الجزائيّ يجلب الآثار الأسرية (التفريق للضرر/الحضانة/الخلع بحسب المذهب)،
وفرع الأحوال يجلب جرائم الاعتداء على النفس (16/1960 م160-167 + م152 + م173). مقيَّد بالمحتوى، متقدّم
الترتيب لينجو من القصّ. لا إدخال ولا إعادة فهرسة. نسخة احتياطية + إعادة تشغيل + اختبار وظيفيّ للفرعين."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/bridge_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 app.py =="; echo "المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
grep -q "_nexus_bridge" "$TMP/app.py" && echo "الجسر موجود" || {{ echo "خطأ: الجسر مفقود"; exit 1; }}
cp -f "$APP" "$APP.bak.bridge"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.bridge" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: الجسر يصل الفرعين =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
V="زوج يضرب زوجته أمام أطفالها ويهددها بالقتل"
def has(ids,pref): return [i for i in ids if i.startswith(pref)]
# 1) الفرع الجزائيّ: يجب أن يجلب الآثار الأسرية (51/1984) إلى جانب جرائم 16/1960
jz=m._draft_bundles("استشارة",V,[],None,"جزائي")
print("  [جزائي] جرائم 16/1960:",len(has(jz,"legis-16-1960")),"| آثار أسرية 51/1984:",len(has(jz,"legis-51-1984")),"| عنف أسري 11/2026:",len(has(jz,"legis-11-2026")))
assert has(jz,"legis-51-1984"), "الفرع الجزائيّ لم يجلب الآثار الأسرية!"
# 2) فرع الأحوال: يجب أن يجلب جرائم الاعتداء (16/1960) إلى جانب الأحوال والعنف الأسري
ah=m._draft_bundles("استشارة",V,[],None,"أحوال شخصية")
print("  [أحوال] جرائم 16/1960:",len(has(ah,"legis-16-1960")),"| أحوال 51/1984:",len(has(ah,"legis-51-1984")),"| عنف أسري 11/2026:",len(has(ah,"legis-11-2026")))
assert "legis-16-1960-m160" in ah, "فرع الأحوال لم يجلب جريمة الضرب (م160)!"
# 3) المذهب الجعفري: الآثار من 124/2019 لا 51/1984
jf=m._draft_bundles("استشارة",V,[],"جعفري","جزائي")
print("  [جزائي/جعفري] 124/2019:",len(has(jf,"legis-124-2019")),"| 51/1984:",len(has(jf,"legis-51-1984")))
assert has(jf,"legis-124-2019") and not has(jf,"legis-51-1984"), "توجيه المذهب الجعفري خاطئ!"
# 4) لا تفعيل على غير النِّزاع الأسريّ
rb=m._draft_bundles("استشارة","موظف قبل رشوة مقابل إنجاز معاملة",[],None,"جزائي")
print("  [جزائي/رشوة] آثار أسرية 51/1984 (يجب 0):",len(has(rb,"legis-51-1984")))
assert not has(rb,"legis-51-1984"), "الجسر اشتعل خطأً على قضية رشوة!"
print("  ✓ الجسر يصل الفرعين، يوجّه المذهب، ولا يشتعل على غير النِّزاع الأسريّ")
PY2
echo '=== تم: الجسر الأسريّ–الجزائيّ (العنف الأسري + الطفل ↔ الجزاء + الأحوال) ==='
"""
(H / "run_bridge.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_bridge.sh && sha256sum run_bridge.sh"
(H / "DEPLOY_bridge.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_bridge.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
