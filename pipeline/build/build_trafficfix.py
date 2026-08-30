#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط: جعلُ محفّز قانون المرور `_traffic_ids` محايدَ الفرع — يُستحضَر في الغلاف
`_draft_bundles` لا في مسار الجزائيّ وحده، لأنّ أسئلة المرور تتوزّع فروعًا (الترخيص/التأمين قد يُصنَّف
مدنيًّا فلا يمرّ بمسار is_penal). المحتوى مُدخَلٌ سلفًا (60 كائنًا، 8367) فلا فهرسة. نسخةٌ احتياطية
+ استرجاعٌ تلقائيّ + اختبارٌ وظيفيّ (يعيد تشغيل الاستعلام المدنيّ التصنيف الذي كان يفشل)."""
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
TMP=/tmp/trafficfix_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
grep -q "tr = _traffic_ids(_blob)" "$TMP/app.py" && echo "موجود: _traffic_ids محايد الفرع في الغلاف" || {{ echo "خطأ"; exit 1; }}
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.trafficfix"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.trafficfix" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q): return set(m._draft_bundles("استشارة",q,[],None,None))
# الاستعلام المدنيّ التصنيف الذي كان يفشل (المسؤولية المدنية ⇒ فرع مدني، خارج مسار is_penal):
br=m._resolve_branch(None, m._draft_norm_ar("كيف أرخّص سيارة وما هو التأمين الإلزامي من المسئولية المدنية؟"))
print("  تصنيف سؤال الترخيص/التأمين:", br, "(قد يكون مدنيًّا — والمحفّز يعمل رغم ذلك)")
a=ids("كيف أرخّص سيارة وما هو التأمين الإلزامي من المسئولية المدنية؟")
assert all(("legis-67-1976-m%d"%n) in a for n in (4,5,6)), "الترخيص/التأمين لم يُستحضَر رغم الإصلاح!"
print("  ✓ الترخيص والتأمين (م4/م5/م6) — يعمل الآن أيًّا كان الفرع")
# ولا يزال المسار الجزائيّ يعمل:
b=ids("ما عقوبة القيادة تحت تأثير المسكر في قانون المرور؟")
assert "legis-67-1976-m38" in b and "legis-67-1976-m44" in b
print("  ✓ العقوبات الجزائية (م38/م44) لا تزال تعمل")
# سؤالٌ صريحُ الفرع المدنيّ لا يزال يُستحضِر المرور:
c=ids("سيارتي تسببت في حادث، ما مسؤوليتي المدنية والتأمين الإلزامي؟")
assert any(x.startswith("legis-67-1976") for x in c)
print("  ✓ سؤال الحادث/المسؤولية المدنية يستحضر مواد المرور")
print("  === تمّ =====")
PY2
echo '=== تم: _traffic_ids محايدَ الفرع (الغلاف) — قانون المرور يُستحضَر لأسئلة الترخيص/التأمين المدنية أيضًا — تطبيقيٌّ فقط ==='
"""
(H / "run_trafficfix.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_trafficfix.sh && sha256sum run_trafficfix.sh"
(H / "DEPLOY_trafficfix.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_trafficfix.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; app sha embedded")
r = subprocess.run(["bash", "-n", str(H / "run_trafficfix.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
