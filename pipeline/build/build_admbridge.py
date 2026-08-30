#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط (لا إدخال ولا فهرسة): جسرُ القضاء الإداري في عائلة الإعلام الإلكتروني — رفضُ الترخيص أو
إلغاؤه أو سحبُه قرارٌ إداريّ، والتظلّمُ إلى الوزير مرحلةٌ سابقة لا نهايةُ الطريق؛ فيُستحضَر مسارُ الطعن في
القانون 20/1981 (م7 ميعاد الستين يومًا، م8 التظلّم، م5 ولاية الإلغاء، م6 وقف التنفيذ، م12/م14 الاستئناف)
ولو صُنّف السؤالُ جزائيًّا. + توسيعُ بوابة _EMEDIA_KEYS للصيغ الإضافية (موقعي/وسيلتي/موقع إخباري).
يطبع السكربتُ نصَّ م7/م8 من 20/1981 للتدقيق. نسخةٌ احتياطية + استرجاعٌ تلقائيّ."""
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
TMP=/tmp/admbridge_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
grep -q "جسرُ القضاء الإداري (20/1981)" "$TMP/app.py" && echo "موجود: جسر القضاء الإداري" || {{ echo "خطأ"; exit 1; }}
echo "== تحقّق: مواد الطعن الإداري مُدخَلةٌ فعلًا + تدقيقُ سلامة نصّها =="
"$PYA" - <<'PYCHK'
import os, psycopg
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
want=["legis-20-1981-m1","legis-20-1981-m2","legis-20-1981-m5","legis-20-1981-m6","legis-20-1981-m7",
      "legis-20-1981-m8","legis-20-1981-m9","legis-20-1981-m11","legis-20-1981-m12","legis-20-1981-m12mkr",
      "legis-20-1981-m14","legis-20-1981-m14mkr","legis-20-1981-m15"]
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT id,original_text FROM knowledge_objects WHERE id = ANY(%s)", (want,))
    rows=dict(cur.fetchall())
missing=[w for w in want if w not in rows]
assert not missing, "مواد غائبة: %s"%missing
print("  ✓ مواد نواة القضاء الإداري (13) مُدخَلةٌ كلُّها")
print("\\n  --- م7 (ميعاد دعوى الإلغاء) ---"); print("  "+rows["legis-20-1981-m7"].replace(chr(10)," ")[:420])
print("\\n  --- م8 (شروط قبول طلبات الإلغاء/التظلّم) ---"); print("  "+rows["legis-20-1981-m8"].replace(chr(10)," ")[:420])
bad=[k for k,v in rows.items() if chr(0xFFFD) in v]
print("\\n  محارف بديلة �:", bad or "لا")
PYCHK
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.admbridge"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.admbridge" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q): return set(m._draft_bundles("استشارة",q,[],None,None))
a=ids("رُفض طلب ترخيص موقعي الإلكتروني الإخباري، وتظلمتُ فرُفض التظلم، فهل أطعن أمام القضاء وما الميعاد؟")
for n in ("m5","m6","m7","m8"):
    assert ("legis-20-1981-"+n) in a, "%s غائبة"%n
assert "legis-8-2016-m11" in a, "قرار الوزير (م11) غائب"
print("  ✓ رفض الترخيص: قرار الوزير (م11) + ولاية الإلغاء (م5) ووقف التنفيذ (م6) وميعاد الستين يومًا (م7) والتظلّم (م8)")
b=ids("ألغت الوزارة ترخيص وسيلتي الإعلامية الإلكترونية وسحبته، ما موقفي القانوني؟")
assert "legis-20-1981-m7" in b and "legis-20-1981-m12" in b
print("  ✓ الإلغاء/السحب: مسار الطعن والاستئناف (م7/م12) — ولو صُنّف السؤال جزائيًّا")
c=ids("ما المستندات المطلوبة لترخيص موقع إخباري وكم تستغرق الوزارة للرد وإذا رفضت هل أتظلم وما الكفالة ومدة الترخيص وما عقوبة التشغيل بلا ترخيص وأي محكمة تختص؟")
for want in ("legis-8-2016-m19","legis-8-2016-m22","regl-8-2016-m12","regl-8-2016-m15","legis-20-1981-m7"):
    assert want in c, "%s غائبة عن السؤال المركّب"%want
print("  ✓ السؤال المركّب: العقوبة (م19) + الاختصاص (م22) + الكفالة (رم12) + التجديد (رم15) + الطعن (20/1981 م7)")
# لا انحدار: العقوبة المجرّدة وشروط المدير لا تجرّان الإداري
for q in ("ما عقوبة إنشاء موقع إلكتروني إخباري بدون ترخيص وهل يجوز حجبه؟",
          "ما شروط المدير المسؤول لموقع إلكتروني؟"):
    r=ids(q)
    assert not any(x.startswith("legis-20-1981") for x in r), "تسرّب الإداري إلى: %s"%q
print("  ✓ لا انحدار: العقوبة المجرّدة وشروط المدير لا تجرّان القضاء الإداري")
# لا تسرّب لعائلاتٍ أخرى
d=ids("ما عقوبة القيادة برخصة سيارة منتهية؟")
assert not any(x.startswith("legis-8-2016") or x.startswith("regl-8-2016") for x in d)
print("  ✓ لا تسرّب: سؤال المرور لا يجرّ عائلة الإعلام الإلكتروني")
print("  === تمّ =====")
PY2
echo '=== تم: جسر القضاء الإداري (20/1981) لعائلة الإعلام الإلكتروني + توسيع بوابة الاستحضار — تطبيقيٌّ فقط ==='
"""
(H / "run_admbridge.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_admbridge.sh && sha256sum run_admbridge.sh"
(H / "DEPLOY_admbridge.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_admbridge.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; app sha embedded")
r = subprocess.run(["bash", "-n", str(H / "run_admbridge.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
