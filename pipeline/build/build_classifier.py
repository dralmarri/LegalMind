#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف (app.py فقط): مُصنّف الفرع المحتوائيّ التلقائيّ لكلّ فروع القانون.
يستنتج الفرع (أحوال/جزائي/عمل/تجاري/إداري/مدني) من وقائع الطلب: يملؤه عند غيابه، ويصحّح الوسم
الصريح فقط عند تعارضٍ قاطع (إشارات قوية ≥3 للفرع المكتشَف + صفر دعم للفرع الموسوم). مطابقة بحدود
الكلمة مع بادئات عربية لتفادي المطابقات الزائفة. لا إدخال ولا إعادة فهرسة. اختبار وظيفيّ شامل."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/classifier_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 app.py =="; echo "المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
grep -q "_resolve_branch" "$TMP/app.py" && echo "المصنّف موجود" || {{ echo "خطأ"; exit 1; }}
cp -f "$APP" "$APP.bak.classifier"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.classifier" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: التصنيف التلقائيّ + سلامة الوسم =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
# 1) الاكتشاف عند غياب الوسم عبر الفروع الستة
cases=[("زوج يضرب زوجته ويطلب الطلاق وحضانة الأولاد","أحوال شخصية"),
       ("موظف قبل رشوة مقابل إنجاز معاملة","جزائي"),
       ("عامل فُصل تعسفياً ويطالب بمكافأة نهاية الخدمة","عمل"),
       ("نزاع بين الشركاء في شركة وطلب تصفيتها","تجاري"),
       ("طعن بإلغاء قرار إداري بالفصل من الخدمة المدنية","إداري"),
       ("نزاع على فسخ عقد إيجار وتعويض عن الضرر","مدني")]
ok=0
for facts,exp in cases:
    got=m._resolve_branch(None, m._draft_norm_ar(facts))
    ok += (got==exp)
    print("  [بلا وسم] "+facts[:34]+"… → "+got+(" ✓" if got==exp else " ✗ متوقع "+exp))
assert ok==len(cases), "فشل الاكتشاف في بعض الفروع"
# 2) احترام الوسم الصريح الصحيح
assert m._resolve_branch("مدني", m._draft_norm_ar("عقد بيع وفسخه"))=="مدني", "لم يُحترَم الوسم المدني"
# 3) تصحيح التعارض القاطع
corr=m._resolve_branch("مدني", m._draft_norm_ar("موظف قبل رشوة والمتهم أنكر والنيابة العامة تحقق في الجريمة"))
print("  [تعارض قاطع] موسوم=مدني، محتوى جزائيّ قويّ → "+corr)
assert corr=="جزائي", "لم يُصحَّح التعارض القاطع"
# 4) لا هَجْر لطلبٍ جزائيّ صريح ذي محتوى جزائيّ
assert m._resolve_branch("جزائي", m._draft_norm_ar("سرقة واعتداء"))=="جزائي", "هُجِر وسمٌ جزائيّ صحيح!"
print("  ✓ الاكتشاف صحيح في الفروع الستة، والوسم الصريح مُحترَم، والتعارض القاطع يُصحَّح")
PY2
echo '=== تم: مُصنّف الفرع المحتوائيّ التلقائيّ لكل فروع القانون ==='
"""
(H / "run_classifier.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_classifier.sh && sha256sum run_classifier.sh"
(H / "DEPLOY_classifier.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_classifier.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
