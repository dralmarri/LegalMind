#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط: منعُ جسر الاختصاص من توجيه منازعات العقد الإداريّ إلى المحاكم العادية.

الرصدُ الموجِب ظهر عرَضًا في معاينة تصحيح م2 من 20/1981، إذ قرأنا نصَّها كاملًا: «تختصّ **وحدها**
بنظر المنازعات التي تنشأ بين الجهات الإدارية والمتعاقد الآخر في عقود الالتزام والأشغال العامة
والتوريد أو أيّ عقد إداريّ». وكان جسرُ الاختصاص المنشورُ للتوّ يوجّه صاحبَ هذه المنازعة إلى
المحكمة الكلية بم29/م34 من المرافعات — وهو خطأٌ يُبطل الإجراء لا مجرّد نقصٍ في الاستحضار.
قيس فقُطع في أربعة أسئلةٍ من أربعة.

والبوّابةُ مضبوطةٌ بدرجتين: ألفاظٌ لا تحتمل غيرَ العقد الإداريّ (عقد التزام، أشغال عامة، توريد،
مناقصة، امتياز مرفق) تُشعلها وحدَها؛ وذكرُ الجهة (وزارة، بلدية، الدولة) لا يكفي إلّا مقترنًا بلفظ
تعاقد — وإلّا حُوّلت دعوى التعويض عن خطأٍ طبّيّ ضدّ وزارة الصحة إلى القضاء الإداريّ، وهي مسؤوليةٌ
تقصيريةٌ من اختصاص المحاكم العادية. والتحويلُ إلى نواة 20/1981 لا إلى الصمت — فالسؤالُ يُجاب لا يُهمَل.
"""
import base64, gzip, hashlib, pathlib, subprocess

H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/admvenue_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
grep -q "_VENUE_ADM_ONLY" "$TMP/app.py" && echo "موجود: بوّابةُ العقد الإداريّ" || {{ echo "خطأ"; exit 1; }}
echo "== قياسٌ قبل النشر =="
"$PYA" - <<'PYB'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
q="تعاقدت مع وزارة الأشغال العامة على عقد توريد وامتنعت عن صرف المستحقات، فأي محكمة تختص بدعواي؟"
b=list(m._draft_bundles("استشارة",q,[],None,None))
p=[i for i,o in enumerate(b) if o.startswith("legis-38-1980-m34")]
a=[i for i,o in enumerate(b) if o.startswith("legis-20-1981")]
print("   قبل: م34 مرافعات موضع=%s | 20/1981 أوّل موضع=%s"%((p or ["—"])[0],(a or ["—"])[0]))
PYB
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.admvenue"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.admvenue" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
HI = 18
def bundle(q): return list(m._draft_bundles("استشارة",q,[],None,None))
def first(b,pfx):
    for i,o in enumerate(b):
        if o.startswith(pfx): return i
    return None

print("   -- منازعةُ العقد الإداريّ ⇒ الدائرة الإدارية، ولا تُوجَّه إلى المرافعات --")
for q in ("تعاقدت مع وزارة الأشغال العامة على عقد توريد وامتنعت عن صرف المستحقات، فأي محكمة تختص بدعواي؟",
          "لدي عقد التزام مع جهة إدارية ونشأ نزاع حول تنفيذه، ما المحكمة المختصة؟",
          "أي محكمة تختص بمنازعة عقد أشغال عامة مع الدولة؟",
          "شركتي فازت بمناقصة حكومية ثم أُلغي العقد إداريًا، أين أرفع الدعوى؟"):
    b=bundle(q); a=first(b,"legis-20-1981"); v=first(b,"legis-38-1980-m34")
    assert a is not None and a < HI, "20/1981 لم يتصدّر (موضع %s) في: %s"%(a,q[:40])
    assert v is None or v >= HI, "م34 مرافعات في نافذة الصدارة (موضع %s) — توجيهٌ خاطئ"%v
    print("      ✓ 20/1981 موضع %-2d | م34 مرافعات: %s"%(a, "غائب" if v is None else "خارج النافذة (%d)"%v))

print("   -- ما ليس عقدًا إداريًّا يبقى في المرافعات --")
for q,lbl in (("أي محكمة تختص بدعوى تعويض ضد وزارة الصحة عن خطأ طبي أصابني؟","خطأ طبّيّ"),
              ("أي محكمة تختص بدعوى صحة ونفاذ عقد بيع عقار قيمته مائة ألف دينار؟","بيعُ عقار"),
              ("أريد رفع دعوى صحة توقيع على ورقة عرفية، فأي محكمة تختص؟","صحّةُ توقيع")):
    b=bundle(q); v=first(b,"legis-38-1980-m34")
    assert v is not None and v < HI, "%s: م34 مرافعات خارج النافذة (موضع %s)"%(lbl,v)
    print("      ✓ %-12s م34 مرافعات موضع %d"%(lbl,v))

print("   -- لا انحدار --")
b=bundle("بعتُ نصيبي في قسيمةٍ سكنية لابن عمّي بموجب اتفاقٍ وقّعناه بالتوقيع الإلكترونيّ عبر البريد، "
         "وقبض جزءًا من الثمن، والآن يرفض الحضور إلى دائرة التسجيل العقاري ويقول إنّ العقد لم يُسجَّل "
         "فلا قيمة له. هل الملكيةُ انتقلت إليّ؟ وما دعواي؟")
for oid in ("legis-5-1959-m7","legis-5-1959-m11-mukarrar-1","legis-20-2014-m2","legis-20-2014-m3"):
    i=b.index(oid) if oid in b else None
    assert i is not None and i < HI, "انحدار: %s موضع %s"%(oid,i)
b2=bundle("أنشأت شركة شخص واحد وأريد ترخيص موقع إخباري إلكتروني، ما المستندات وإذا رفضت هل أتظلم "
          "وإذا شغلت الموقع قبل الترخيص ما العقوبة وأي محكمة تختص؟")
e,a2 = first(b2,"legis-8-2016"), first(b2,"legis-20-1981")
assert e is not None and e < HI and a2 is not None and a2 < HI, "انحدار الإعلام: %s %s"%(e,a2)
assert not [o for o in bundle("ما عقوبةُ السرقة من منزلٍ مسكونٍ ليلًا؟") if o.startswith("legis-5-1959")]
print("      ✓ الجسرُ العقاريّ الإلكترونيّ، والإعلامُ (8/2016 موضع %d، 20/1981 موضع %d)، والصمتُ الواجب"%(e,a2))
print("   === تمّ =====")
PY2
echo '=== تم: منعُ توجيه منازعات العقد الإداريّ إلى المحاكم العادية — تطبيقيٌّ فقط ==='
"""

(H / "run_admvenue.sh").write_text(SH, encoding="utf-8")
one = ("printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() +
       "' | base64 -d | gunzip > run_admvenue.sh && bash run_admvenue.sh")
(H / "DEPLOY_admvenue.txt").write_text(one + "\n", encoding="utf-8")
assert gzip.decompress(base64.b64decode(one.split("'")[3])) == SH.encode(), "round-trip mismatch!"
print("app sha:", s_app); print("round-trip OK")
r = subprocess.run(["bash", "-n", str(H / "run_admvenue.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(one))
