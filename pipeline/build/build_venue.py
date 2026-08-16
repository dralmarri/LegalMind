#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط: جسرُ الاختصاص وتقدير قيمة الدعوى (المرافعات 38/1980) + إصلاحان مرافقان.

(1) **جسرُ الاختصاص.** بلغ النموذجُ الاختصاصَ في دعوى عقارية **قياسًا** على م833 مدنيّ (وهي في دعوى
    القسمة)، وقواعدُ الاختصاص من النظام العام لا تثبت بقياس. ومعاينةُ المرافعات كشفت أنّه لا بابَ
    اختصاصٍ محلّيًّا فيه أصلًا (الكويت وحدةٌ قضائية)، وإنّما: الدوليّ م23-م28، والنوعيّ والقيميّ
    م29-م36، وتقديرُ القيمة م37-م44. فالمسارُ الصحيح: م40 (دعوى صحّة العقد بقيمة المتعاقد عليه) ⇐
    م39 (الدعوى العقارية بقيمة العقار) ⇐ م29 (نصابُ الجزئية) ⇐ م34 (فما جاوزه فللكلية)، وم42 في
    دعاوى صحّة التوقيع والتزوير. والبوّابةُ اقترانيّة مع منعٍ صريح للتسرّب الجزائيّ (اختصاصُه في
    الإجراءات الجزائية 17/1960 لا في المرافعات).

(2) **إصلاحُ فائضٍ في محفّز 20/2014:** كان سؤالُ التوقيع يجرّ م18-م25 جملةً، فتُقحَم موادُّ مزوّدي
    خدمات التصديق وترخيصِهم (م22-م25) بلا سؤال وتبتلع أربعةَ مواضعَ من نافذة الصدارة. فصارت م18-م21
    للتوقيع، وم22-م25 لا تُستحضَر إلّا بذكر المزوّد أو جهة التصديق أو الاعتماد.

(3) **إصلاحُ مطابقةٍ في محفّز 5/1959:** مفتاحُ «قيم» (القوامة) كان يلتقط «قيمته» بالمطابقة السابقة
    (بلا حدٍّ في آخر الكلمة) فيشعل عنقودَ الولاية والوصاية م33-م43 ويبتلع أحدَ عشرَ موضعًا. صار
    العنقودُ يُطابَق بحدَّي الكلمة — وهو نفسُ العلاج الذي طُبّق سابقًا على مفاتيح الجزاء القصيرة.

الاختبارُ يقيس الترتيب لا الوجود. نسخةٌ احتياطية + استرجاعٌ تلقائيّ.
"""
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
TMP=/tmp/venue_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
grep -q "def _venue_ids" "$TMP/app.py" && echo "موجود: محفّز الاختصاص" || {{ echo "خطأ"; exit 1; }}
[ "$(grep -c '_venue_ids' "$TMP/app.py")" -ge 2 ] && echo "موجود: النداء في الغلاف" || {{ echo "خطأ: غيرُ موصول"; exit 1; }}
grep -q "«قيم» تلتقط «قيمته»" "$TMP/app.py" && echo "موجود: إصلاحُ المطابقة" || {{ echo "خطأ"; exit 1; }}
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.venue"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.venue" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: الترتيب لا الوجود =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
HI = 18
def bundle(q): return list(m._draft_bundles("استشارة",q,[],None,None))
def need(b,oid,lbl):
    i = b.index(oid) if oid in b else None
    assert i is not None and i < HI, "%s: %s خارج نافذة الأولوية (موضع %s)"%(lbl,oid,i)
    return i

# (1) اختصاصٌ عقاريٌّ صريح ⇒ سلسلةُ الاستدلال كاملةً
b=bundle("أي محكمة تختص بدعوى صحة ونفاذ عقد بيع عقار قيمته مائة ألف دينار؟")
print("   الصدارة: %s"%", ".join(o.replace("legis-","") for o in b[:14]))
for oid in ("legis-38-1980-m40","legis-38-1980-m39","legis-38-1980-m29","legis-38-1980-m34"):
    print("      %-18s موضع %d"%(oid.replace("legis-",""), need(b,oid,"الاختصاص العقاريّ")))
assert not [o for o in b if o.startswith("legis-5-1959-m33")], "عنقودُ الولاية نطق خطأً على «قيمته»"
print("   ✓ سلسلةُ الاستدلال (م40⇐م39⇐م29⇐م34) داخل النافذة، وعنقودُ الولاية لم ينطق")

# (2) دعوى صحّة توقيع ⇒ م42 وم37
b2=bundle("أريد رفع دعوى صحة توقيع على ورقة عرفية، فأي محكمة تختص وكيف تُقدَّر قيمة الدعوى؟")
for oid in ("legis-38-1980-m42","legis-38-1980-m37","legis-38-1980-m34"):
    need(b2,oid,"صحّةُ التوقيع")
print("   ✓ دعوى صحّة التوقيع: م42/م37/م34 في الصدارة")

# (3) الجسرُ الإلكترونيّ ⇒ اتّسعت النافذة بعد إصلاح الفائض
b3=bundle("بعتُ نصيبي في قسيمةٍ سكنية لابن عمّي بموجب اتفاقٍ وقّعناه بالتوقيع الإلكترونيّ عبر البريد، "
          "وقبض جزءًا من الثمن، والآن يرفض الحضور إلى دائرة التسجيل العقاري ويقول إنّ العقد لم يُسجَّل "
          "فلا قيمة له. هل الملكيةُ انتقلت إليّ؟ وما دعواي؟")
for oid in ("legis-5-1959-m7","legis-5-1959-m17","legis-5-1959-m11-mukarrar-1",
            "legis-20-2014-m2","legis-20-2014-m3","legis-20-2014-m18","legis-20-2014-m19",
            "legis-20-2014-m20"):
    need(b3,oid,"الجسرُ الإلكترونيّ")
print("   ✓ الجسرُ الإلكترونيّ: النواةُ العقارية وحجّيةُ التوقيع (م18-م20) كلُّها داخل النافذة")

# (4) صمتٌ واجب — لا يتسرّب المرافعاتُ ولا العقاريُّ إلى ما ليس منهما
for q,lbl in (("ما عقوبةُ السرقة من منزلٍ مسكونٍ ليلًا؟","سرقة"),
              ("أي محكمة تختص بجريمة الرشوة؟","رشوة"),
              ("ما شروطُ الترخيص لمزاولة أعمال البثّ المرئي والمسموع؟","بثّ"),
              ("هل يجوز فصلُ العامل أثناء إجازته المرضية؟","عمل"),
              ("زوجي هجرني منذ سنة، فهل لي طلبُ التفريق للضرر؟","أحوال")):
    bb=bundle(q)
    for pfx,nm in (("legis-5-1959","العقاريّ"),):
        leak=[o for o in bb if o.startswith(pfx)]
        assert not leak, "تسرّبُ %s في سؤال %s: %s"%(nm,lbl,leak[:3])
print("   ✓ صمتٌ واجب: لا تسرّبَ عقاريًّا في خمسة أسئلةٍ أجنبية، ولا اختصاصَ مرافعاتٍ في الجزائيّ")

# (5) لا انحدار: مكتسباتُ النشرات السابقة
b5=bundle("اشتريتُ أرضًا بعقدٍ عرفيٍّ ولم أسجّله، ثمّ باعها البائعُ لغيري وسجّلها. لمن تكون الملكية؟")
for oid in ("legis-5-1959-m7","legis-5-1959-m8","legis-5-1959-m14"):
    need(b5,oid,"العقد العرفيّ")
b6=bundle("أنشأت شركة شخص واحد وأريد ترخيص موقع إخباري إلكتروني، ما المستندات وكم تستغرق الوزارة "
          "للرد وإذا رفضت هل أتظلم وما الكفالة ومدة الترخيص وإذا شغلت الموقع قبل الترخيص ما العقوبة "
          "وأي محكمة تختص؟")
e=[i for i,o in enumerate(b6) if o.startswith("legis-8-2016")]
a=[i for i,o in enumerate(b6) if o.startswith("legis-20-1981")]
assert e and e[0] < HI and a and a[0] < HI, "انحدار: 8/2016=%s 20/1981=%s"%(e[:1],a[:1])
print("   ✓ لا انحدار: العقدُ العرفيّ باقٍ، و8/2016 موضع %d و20/1981 موضع %d"%(e[0],a[0]))
print("   === تمّ =====")
PY2
echo '=== تم: جسرُ الاختصاص 38/1980 + إصلاحُ فائض 20/2014 + إصلاحُ مطابقة 5/1959 — تطبيقيٌّ فقط ==='
"""

(H / "run_venue.sh").write_text(SH, encoding="utf-8")
oneliner = ("printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() +
            "' | base64 -d | gunzip > run_venue.sh && bash run_venue.sh")
(H / "DEPLOY_venue.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
assert gzip.decompress(base64.b64decode(oneliner.split("'")[3])) == SH.encode(), "round-trip mismatch!"
print("round-trip OK")
r = subprocess.run(["bash", "-n", str(H / "run_venue.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(oneliner))
