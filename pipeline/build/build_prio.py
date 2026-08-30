#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط: تصحيحُ أولوية الترتيب في حزم الاستحضار — «الخاصُّ يقيّد العامّ» ترتيبًا.
متى نطق محفّزٌ متخصّص (مرور/بيئة/بلدية/إعلام إلكتروني — وبواباتُه ضيّقة) تصدّرت موادُّه النواةَ العامّة
للفرع بدل أن تُذيَّل خلفها. الرصد الذي أوجبه: في سؤال ترخيص موقعٍ إخباريّ كانت المعرّفات 18 الأولى (صاحبة
الدرجة 0.85) كلَّها من الإجراءات الجزائية 17/1960، ومواد 20/1981 في الترتيب 104-116 بدرجة صفر فتُقتطع عند
امتلاء ميزانية السياق. + تصديرُ جسر القضاء الإداري داخل محفّز الإعلام (بعد نواته مباشرةً لا في ذيله).
الاختبار هنا يقيس «الترتيب» لا مجرّد «الوجود». نسخةٌ احتياطية + استرجاعٌ تلقائيّ."""
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
TMP=/tmp/prio_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
grep -q "«الخاصُّ يقيّد العامّ» — ترتيبًا لا حكمًا فحسب" "$TMP/app.py" && echo "موجود: تصحيح الأولوية" || {{ echo "خطأ"; exit 1; }}
echo "== قياسٌ قبل النشر (النسخة العاملة حاليًّا) =="
"$PYA" - <<'PYB'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
q="أنشأت شركة شخص واحد وأريد ترخيص موقع إخباري إلكتروني، ما المستندات وكم تستغرق الوزارة للرد وإذا رفضت هل أتظلم وما الكفالة ومدة الترخيص وإذا شغلت الموقع قبل الترخيص ما العقوبة وأي محكمة تختص؟"
b=list(m._draft_bundles("استشارة",q,[],None,None))
pos=lambda p:[i for i,o in enumerate(b) if o.startswith(p)]
print("   قبل: إجمالي=%d | 8/2016 أوّل موضع=%s | 20/1981 أوّل موضع=%s"%(
    len(b), (pos("legis-8-2016") or ["—"])[0], (pos("legis-20-1981") or ["—"])[0]))
PYB
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.prio"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.prio" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: الترتيب لا الوجود =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
HI = 18   # نافذة الدرجة العالية في المستهلك (_bscore = 0.85 if _bi < 18)
def bundle(q): return list(m._draft_bundles("استشارة",q,[],None,None))
def first(b,pfx):
    for i,o in enumerate(b):
        if o.startswith(pfx): return i
    return None

q1="أنشأت شركة شخص واحد وأريد ترخيص موقع إخباري إلكتروني، ما المستندات وكم تستغرق الوزارة للرد وإذا رفضت هل أتظلم وما الكفالة ومدة الترخيص وإذا شغلت الموقع قبل الترخيص ما العقوبة وأي محكمة تختص؟"
b=bundle(q1)
e,a = first(b,"legis-8-2016"), first(b,"legis-20-1981")
print("   بعد: إجمالي=%d | 8/2016 أوّل موضع=%s | 20/1981 أوّل موضع=%s"%(len(b),e,a))
assert e is not None and e < HI, "القانون الخاصّ 8/2016 لم يتصدّر (موضع %s)"%e
assert a is not None and a < HI, "جسر القضاء الإداري لم يتصدّر (موضع %s)"%a
for n in ("m5","m6","m7","m8"):
    i=b.index("legis-20-1981-"+n) if ("legis-20-1981-"+n) in b else None
    assert i is not None and i < HI, "20/1981 %s خارج نافذة الأولوية (موضع %s)"%(n,i)
print("   ✓ الخاصّ (8/2016 + اللائحة) وجسرُ الطعن (20/1981 م5/م6/م7/م8) كلُّها داخل نافذة الدرجة 0.85")
r=first(b,"regl-8-2016"); print("   ✓ اللائحة 100/2016 أوّل موضع =",r)
assert r is not None and r < 45, "اللائحة تأخّرت كثيرًا (موضع %s)"%r

# لا انحدار (1): سؤال مروريّ ⇒ المرور يتصدّر ولا يتسرّب الإعلام
b2=bundle("تعرّضت لحادث سيارة وأُصبت بعجز وسيارة الطرف الآخر مؤمَّنة، فما تعويضي والمسؤولية المدنية؟")
t=first(b2,"legis-67-1976"); assert t is not None and t < HI, "المرور لم يتصدّر (موضع %s)"%t
assert first(b2,"legis-8-2016") is None and first(b2,"regl-8-2016") is None
print("   ✓ لا انحدار: المرور يتصدّر (موضع %d) ولا تسرّب لعائلة الإعلام"%t)

# لا انحدار (2): سؤال جزائيّ محض بلا محفّز متخصّص ⇒ النواة العامّة تتصدّر كالسابق
b3=bundle("ما عقوبة جريمة الرشوة للموظف العام في القانون الكويتي؟")
assert not any(o.startswith(("legis-67-1976","legis-42-2014","legis-33-2016","legis-8-2016")) for o in b3[:HI]), \
    "محفّزٌ متخصّص نطق خطأً في سؤالٍ جزائيّ محض"
print("   ✓ لا انحدار: السؤال الجزائيّ المحض يحتفظ بنواته العامّة في الصدارة")

# لا انحدار (3): العقوبة المجرّدة في الإعلام لا تجرّ الإداري
b4=bundle("ما عقوبة إنشاء موقع إلكتروني إخباري بدون ترخيص وهل يجوز حجبه؟")
assert first(b4,"legis-20-1981") is None, "تسرّب القضاء الإداري لسؤال عقوبةٍ مجرّد"
assert first(b4,"legis-8-2016") is not None and first(b4,"legis-8-2016") < HI
print("   ✓ لا انحدار: العقوبة المجرّدة ⇒ 8/2016 يتصدّر بلا جرِّ الإداري")
print("   === تمّ =====")
PY2
echo '=== تم: تصحيح أولوية الترتيب (الخاصُّ قبل العامّ) + تصدير جسر القضاء الإداري — تطبيقيٌّ فقط ==='
"""
(H / "run_prio.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_prio.sh && sha256sum run_prio.sh"
(H / "DEPLOY_prio.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_prio.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK")
r = subprocess.run(["bash", "-n", str(H / "run_prio.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(oneliner))
