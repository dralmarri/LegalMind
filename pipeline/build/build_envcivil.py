#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط: جسرُ الشريعة العامة في محفّز البيئة — سؤالُ المسؤولية المدنية البيئية (م160 «مع عدم
الإخلال بأي قانون آخر») يحتاج القواعدَ العامةَ للمسؤولية التقصيرية (الفعل الضار) في القانون المدني 67/1980
(م227 فما بعد) أساسًا تكميليًّا؛ فنقرنها بجسر المسؤولية البيئية. المدنيُّ مُدخَلٌ سلفًا (لا فهرسة). يتحقّق
السكربتُ من وجود مواد المدنيّ في القاعدة قبل الاعتماد عليها. نسخةٌ احتياطية + استرجاعٌ تلقائيّ."""
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
TMP=/tmp/envcivil_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
grep -q "جسرُ الشريعة العامة" "$TMP/app.py" && echo "موجود: جسر الشريعة العامة (المدني 67/1980)" || {{ echo "خطأ"; exit 1; }}
echo "== تحقّق: مواد المدني التقصيرية مُدخَلة فعلًا =="
"$PYA" - <<'PYCHK'
import os, psycopg
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT id,left(original_text,60) FROM knowledge_objects WHERE id IN ('legis-67-1980-m227','legis-67-1980-m228','legis-67-1980-m231') ORDER BY id")
    rows=cur.fetchall()
assert len(rows)==3, "مواد المدني 227/228/231 غير موجودة! %r"%rows
for i,t in rows: print("   ",i,":",t)
print("  ✓ مواد المسؤولية التقصيرية (67/1980) مُدخَلةٌ في القاعدة")
PYCHK
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.envcivil"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.envcivil" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
a=set(m._draft_bundles("استشارة","مصنع ألقى نفايات خطرة في جون الكويت، ما المسؤولية المدنية والتعويض عن الأضرار البيئية؟",[],None,None))
assert "legis-42-2014-m160" in a, "م160 غائبة"
civ=sorted(x for x in a if x.startswith("legis-67-1980-m22") or x.startswith("legis-67-1980-m23"))
assert any(("legis-67-1980-m%d"%n) in a for n in range(227,235)), "الشريعة العامة (الفعل الضار) لم تُستحضَر!"
print("  ✓ جسر الشريعة العامة: 42/2014 م160/م161 + القانون المدني 67/1980 (الفعل الضار م227+) معًا")
print("    المدني المُستحضَر:", civ[:6])
# لا انحدار
assert "legis-42-2014-m131" in m._draft_bundles("استشارة","عقوبة إلقاء النفايات الخطرة",[],None,None)
print("  ✓ لا انحدار: عقوبة النفايات الخطرة (م131) سليمة")
print("  === تمّ =====")
PY2
echo '=== تم: جسر الشريعة العامة — المسؤولية البيئية (42/2014 م160) تُقرَن بالفعل الضار المدني (67/1980 م227+) تكميلًا — تطبيقيٌّ فقط ==='
"""
(H / "run_envcivil.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_envcivil.sh && sha256sum run_envcivil.sh"
(H / "DEPLOY_envcivil.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_envcivil.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; app sha embedded")
r = subprocess.run(["bash", "-n", str(H / "run_envcivil.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
