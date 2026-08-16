#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط: توسيعُ الجسر المدنيّ في محفّز المرور — تعويضُ الإصابة الجسدية في حوادث المركبات يرتكز
على م247 (عناصر الضرر) وم248 (الدية الشرعية للإصابة) والتزامِ المؤمِّن م800/م801 في القانون المدني 67/1980،
إضافةً إلى الفعل الضار العام (م227-234). المدنيُّ مُدخَلٌ سلفًا (لا فهرسة). يتحقّق السكربتُ من وجود هذه المواد
في القاعدة قبل الاعتماد عليها. نسخةٌ احتياطية + استرجاعٌ تلقائيّ."""
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
TMP=/tmp/trafficcivil_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
grep -q "نواةُ تعويض الإصابة الجسدية في الحوادث" "$TMP/app.py" && echo "موجود: توسيع الجسر المدني للمرور (م247/م248/م800)" || {{ echo "خطأ"; exit 1; }}
echo "== تحقّق: مواد التعويض/التأمين المدنية مُدخَلة فعلًا =="
"$PYA" - <<'PYCHK'
import os, psycopg
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT id,left(original_text,55) FROM knowledge_objects WHERE id IN ('legis-67-1980-m247','legis-67-1980-m248','legis-67-1980-m800','legis-67-1980-m801') ORDER BY id")
    rows=cur.fetchall()
got=[r[0] for r in rows]
for want in ('legis-67-1980-m247','legis-67-1980-m248','legis-67-1980-m800','legis-67-1980-m801'):
    assert want in got, "مفقودة: %s"%want
for r in rows: print("   ",r[0],":",r[1])
print("  ✓ مواد التعويض (م247/م248) والتأمين (م800/م801) مُدخَلةٌ في القاعدة")
PYCHK
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.trafficcivil"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.trafficcivil" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
a=set(m._draft_bundles("استشارة","تعرّضت لحادث سيارة وأُصبت بعجز، وسيارة الطرف الآخر مؤمَّنة، فما تعويضي والمسؤولية المدنية؟",[],None,None))
for n in (227,228,247,248,800,801):
    assert ("legis-67-1980-m%d"%n) in a, "م%d غائبة"%n
assert "legis-67-1976-m6" in a, "تأمين المركبة (م6) لم يُستحضَر على «مؤمَّنة»"
print("  ✓ حادث مروري: تأمين المركبة (م6، يُطلَق على «مؤمَّنة») + الفعل الضار (م227/م228)")
print("    + تعويض الإصابة (م247/م248 الدية) + التزام المؤمِّن وحلوله (م800/م801) — كلّها معًا")
# لا انحدار: العقوبة المجرّدة لا تجرّ المدني
b=set(m._draft_bundles("استشارة","ما عقوبة تجاوز الإشارة الحمراء؟",[],None,None))
assert not any(("legis-67-1980-m%d"%n) in b for n in (227,248)) and "legis-67-1976-m33-mukarrar" in b
print("  ✓ لا انحدار: سؤال العقوبة لا يجرّ المدني، والعقوبات المرورية سليمة")
print("  === تمّ =====")
PY2
echo '=== تم: توسيع الجسر المدني للمرور — تعويض الإصابة (م247/م248) والتأمين (م800/م801) مع الفعل الضار — تطبيقيٌّ فقط ==='
"""
(H / "run_trafficcivil.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_trafficcivil.sh && sha256sum run_trafficcivil.sh"
(H / "DEPLOY_trafficcivil.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_trafficcivil.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; app sha embedded")
r = subprocess.run(["bash", "-n", str(H / "run_trafficcivil.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
