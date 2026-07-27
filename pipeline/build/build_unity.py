#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط: جسرُ حماية الوحدة الوطنية (19/2012) في عائلة النشر. المرسومُ بقانون مُدخَلٌ سلفًا
(6 كائنات: م1 الحظر، م2 العقوبات، م3 الشخص الاعتباري، م4 الإعفاء، م5 التنفيذ + ديباجة) لكنّ مفاتيحه في
حزم الفرع تشترط عباراتٍ مركّبةً («الفتنة القبلية») فتفوتها الصيغُ الطبيعية («خلافٌ قبليّ»)، فوصل السؤالُ
بلا نصوصه. والأثرُ قانونيّ لا شكليّ: م21/11 من المطبوعات تحظر إثارة الفتن الطائفية والقبلية بغرامة
3000-10000 (م27/3)، بينما يجرّم 19/2012 الفعلَ ذاتَه بعقوبةٍ أشدّ — وم27 تُصرّح بـ«عدم الإخلال بأيّ عقوبة
أشدّ». فعرضُ الأخفّ وحدَه تضليل. يتحقّق السكربت من وجود المواد في القاعدة قبل الاعتماد عليها."""
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
TMP=/tmp/unity_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
for tok in _unity_ids _UNITY_KEYS; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
echo "== تحقّق: مواد 19/2012 مُدخَلةٌ فعلًا =="
"$PYA" - <<'PYCHK'
import os, psycopg
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
want=["legis-19-2012-m%d"%n for n in (1,2,3,4)]
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT id,left(original_text,150) FROM knowledge_objects WHERE id = ANY(%s) ORDER BY id",(want,))
    rows=cur.fetchall()
got=[r[0] for r in rows]
for w in want: assert w in got, "مفقودة: %s"%w
for r in rows: print("   ",r[0],"::",r[1].replace(chr(10)," "))
print("  ✓ مواد الوحدة الوطنية (م1-م4) مُدخَلةٌ في القاعدة")
PYCHK
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.unity"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.unity" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: الترتيب لا الوجود =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
HI = 18
def bundle(q): return list(m._draft_bundles("استشارة",q,[],None,None))
def at(b,o): return b.index(o) if o in b else None

q="موقعي الإخباري الإلكتروني نشر مقالًا انتقد قاضيًا بعبارات لاذعة، وآخر عن خلاف قبلي. ما المحظورات التي خالفتها وما عقوبتها؟ وهل يمكن حجب الموقع؟ وأي محكمة تختص؟"
a=bundle(q)
for o in ("legis-8-2016-m18","legis-3-2006-m21","legis-3-2006-m27","legis-19-2012-m1","legis-19-2012-m2",
          "legis-8-2016-m19","legis-8-2016-m22"):
    i=at(a,o); assert i is not None and i < HI, "%s خارج نافذة الأولوية (%s)"%(o,i)
print("  ✓ سؤال الاختبار: الإحالة (م18) + المحظور (م21) + عقوبته (م27) + العقوبة الأشدّ (19/2012 م1/م2)")
print("    + الحجب (8/2016 م19) + دائرة الجنايات (م22) — كلُّها متصدّرة")
b=bundle("نشرت الصحيفة مقالًا طائفيًا يحض على كراهية فئة، ما العقوبة؟")
for o in ("legis-3-2006-m21","legis-19-2012-m2"):
    assert at(b,o) is not None and at(b,o) < HI
print("  ✓ الصحيفة الورقية: المحظور (م21) + العقوبة الأشدّ (19/2012 م2)")
# لا انحدار: محظورٌ لا صلةَ له بالفتنة لا يجرّ 19/2012
c=bundle("نشر الموقع الإلكتروني مقالًا فيه انتقاد لأمير البلاد، ما العقوبة؟")
assert not any(x.startswith("legis-19-2012") for x in c), "تسرّبت الوحدة الوطنية إلى محظورٍ لا صلةَ له بها"
assert at(c,"legis-3-2006-m20") is not None and at(c,"legis-3-2006-m27") is not None
print("  ✓ لا انحدار: نقد الأمير ⇒ م20 وعقوبتها (م27) بلا جرِّ الوحدة الوطنية")
for lbl,q2 in (("المرور","ما عقوبة القيادة برخصة سيارة منتهية؟"),
               ("الرشوة","ما عقوبة جريمة الرشوة للموظف العام؟")):
    r=bundle(q2)
    assert not any(x.startswith(("legis-3-2006","legis-8-2016")) for x in r), "تسرّبت عائلة النشر إلى %s"%lbl
print("  ✓ لا تسرّب: المرور والرشوة")
print("  === تمّ =====")
PY2
echo '=== تم: جسر حماية الوحدة الوطنية (19/2012) في عائلة النشر — تطبيقيٌّ فقط ==='
"""
(H / "run_unity.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_unity.sh && sha256sum run_unity.sh"
(H / "DEPLOY_unity.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_unity.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK")
r = subprocess.run(["bash", "-n", str(H / "run_unity.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(oneliner))
