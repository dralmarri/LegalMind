#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط: ضبطُ محفّز البيئة `_environment_ids` — إعادةُ ترتيبٍ بالأولوية: المواد المحدّدة (جسورُ
المخالفة⇄العقوبة + النواة، 17 مادة) تتصدّر القائمة لتنجو من قصّ الميزانية، ثم النطاقاتُ العريضةُ للأبواب
بأسقفٍ مضبوطة (سياقٌ داعم). خفّض الإجمالي من ~90 إلى ~58 معرّفًا لسؤال «نفايات خطرة في جون الكويت»،
فتنجو م68/م73/م130/م131/م149 بلا مزاحمة. المحتوى مُدخَلٌ سلفًا (8550) فلا فهرسة. نسخةٌ احتياطية + استرجاع."""
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
TMP=/tmp/envtune_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
grep -q "الجسورُ أوّلًا ثم السياق" "$TMP/app.py" && echo "موجود: ترتيب الأولوية (الجسور أوّلًا)" || {{ echo "خطأ"; exit 1; }}
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.envtune"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.envtune" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
ids=m._environment_ids(m._draft_norm_ar("مصنع ألقى نفايات خطرة في جون الكويت، ما العقوبة الجزائية والمسؤولية المدنية عن الأضرار البيئية؟"))
print("  إجمالي معرّفات البيئة:", len(ids), "(كان ~90 قبل الضبط)")
head=ids[:17]
crit=[28,29,130,131,68,73,141,142,146,108,149,150,159,160,161]
for n in crit:
    assert ("legis-42-2014-m%d"%n) in ids, "م%d غائبة!"%n
# الجسور يجب أن تتصدّر (ضمن أوّل 17)
for n in crit:
    assert ("legis-42-2014-m%d"%n) in head, "م%d ليست في المقدّمة!"%n
print("  ✓ الجسور الـ17 (م28/م29/م130/م131/م68/م73/م141/م142/م149/م160...) تتصدّر القائمة")
# التحقّق عبر الغلاف الكامل أيضًا
full=set(m._draft_bundles("استشارة","مصنع ألقى نفايات خطرة في جون الكويت، ما العقوبة والمسؤولية المدنية؟",[],None,None))
for n in (68,73,130,131,149):
    assert ("legis-42-2014-m%d"%n) in full
print("  ✓ عبر _draft_bundles: م68/م73/م130/م131/م149 حاضرة")
# لا انحدار: المرور
assert "legis-67-1976-m38" in set(m._draft_bundles("استشارة","عقوبة القيادة تحت تأثير المسكر في قانون المرور",[],None,None))
print("  ✓ لا انحدار: محفّز المرور سليم")
print("  === تمّ =====")
PY2
echo '=== تم: ضبط نطاقات محفّز البيئة — الجسور المحدّدة تتصدّر فتنجو من القصّ، والإجمالي أخفّ — تطبيقيٌّ فقط ==='
"""
(H / "run_envtune.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_envtune.sh && sha256sum run_envtune.sh"
(H / "DEPLOY_envtune.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_envtune.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; app sha embedded")
r = subprocess.run(["bash", "-n", str(H / "run_envtune.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
