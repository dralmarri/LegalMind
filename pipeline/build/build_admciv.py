#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط: وصلُ الشريعة العامة للعقد بنواة القضاء الإداريّ في منازعة العقد الإداريّ.

الرصدُ الموجِب: في جواب «عقد التوريد مع وزارة الأشغال» أصاب النظامُ الاختصاصَ والمواعيدَ الإجرائية،
ثمّ أعلن صراحةً أنّ نصَّ **مدّة عدم سماع الدعوى التعاقدية** «غيرُ مرفق». وهو مُدخَلٌ في القاعدة:
م438 من المدنيّ «لا تُسمع عند الإنكار الدعوى بحقٍّ من الحقوق الشخصية بمضيّ خمس عشرة سنة». بل إنّ
م448 من الفصل نفسِه (الانقطاع) قد وصلته واستشهد بها — فوصلته حلقةُ الانقطاع دون حلقة المدّة.

والوصلُ واجبٌ بحكم النصّ لا بالاستحسان: م15 من 20/1981 تُحيل فيما لم يرد فيه نصّ، وولايةُ «القضاء
الكامل» في م2 دعوى موضوعٍ لا إلغاء — فتحكمها القواعدُ العامة للعقد والمدّة، لا ميعادُ الستّين يومًا.
فتُلحق: م196 (قوّةُ العقد)، م197 (حسنُ النية في التنفيذ)، م438 (المدّة العامة)، م448 (الانقطاع
بالمطالبة القضائية ولو أمام محكمةٍ غير مختصّة)، م300 (تقديرُ التعويض عند خلوّ العقد منه).

وتُسقَط م12 مكرر من نواة الإداريّ في هذا المسار وحده (خاصّةٌ بالتأديب لا شأن لها بالعقد)، فيبقى
المجموعُ سبعةَ عشرَ داخل نافذة الدرجة العالية. لا مساسَ بالقاعدة ولا حاجةَ إلى reindex.
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
TMP=/tmp/admciv_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
grep -q "_ADM_CIVIL_CORE" "$TMP/app.py" && echo "موجود: الشريعةُ العامة للعقد" || {{ echo "خطأ"; exit 1; }}
echo "== قياسٌ قبل النشر =="
"$PYA" - <<'PYB'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
q=("شركتي وقّعت عقد توريد مع وزارة الأشغال العامة، ونفّذنا 80% من الكمّيات، ثمّ أوقفت الوزارة "
   "الصرف وأنذرتنا بسحب العمل. أين أرفع دعواي؟ وما المواعيد التي يجب أن أنتبه لها؟")
b=list(m._draft_bundles("استشارة",q,[],None,None))
p=[i for i,o in enumerate(b) if o=="legis-67-1980-m438"]
print("   قبل: م438 (مدّةُ عدم السماع) موضع=%s | إجمالي=%d"%((p or ["غائب"])[0],len(b)))
PYB
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.admciv"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.admciv" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: الترتيب لا الوجود =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
HI = 18
def bundle(q): return list(m._draft_bundles("استشارة",q,[],None,None))
def need(b,oid,lbl):
    i = b.index(oid) if oid in b else None
    assert i is not None and i < HI, "%s: %s خارج النافذة (موضع %s)"%(lbl,oid,i)
    return i

q=("شركتي وقّعت عقد توريد مع وزارة الأشغال العامة، ونفّذنا 80% من الكمّيات، ثمّ أوقفت الوزارة "
   "الصرف وأنذرتنا بسحب العمل. أين أرفع دعواي؟ وما المواعيد التي يجب أن أنتبه لها؟ وهل أستطيع "
   "وقف قرار السحب قبل الفصل في الموضوع؟")
b=bundle(q)
print("   الصدارة: %s"%", ".join(o.replace("legis-","") for o in b[:17]))
for oid,lbl in (("legis-20-1981-m2","الاختصاصُ والقضاءُ الكامل"),
                ("legis-20-1981-m6","وقفُ التنفيذ"),
                ("legis-20-1981-m7","ميعادُ الإلغاء"),
                ("legis-20-1981-m8","التظلّمُ الوجوبيّ (لنفيه)"),
                ("legis-20-1981-m15","الإحالةُ التكميلية"),
                ("legis-67-1980-m438","مدّةُ عدم سماع الدعوى"),
                ("legis-67-1980-m448","انقطاعُ المدّة"),
                ("legis-67-1980-m197","حسنُ النية"),
                ("legis-67-1980-m300","تقديرُ التعويض")):
    print("      %-22s موضع %-2d  (%s)"%(oid.replace("legis-",""), need(b,oid,"العقدُ الإداريّ"), lbl))
assert "legis-20-1981-m12mkr" not in b[:HI], "م12 مكرر (تأديبية) تزاحم في نافذة العقد"
v=[i for i,o in enumerate(b) if o.startswith("legis-38-1980-m34")]
assert not v or v[0] >= HI, "م34 مرافعات في الصدارة — توجيهٌ خاطئ (موضع %s)"%v[:1]
print("   ✓ الاختصاصُ والمواعيدُ الإجرائية والمدّةُ الموضوعية في نافذةٍ واحدة، بلا توجيهٍ خاطئ")

print("   -- لا انحدار --")
for qq,lbl in (("أي محكمة تختص بدعوى تعويض ضد وزارة الصحة عن خطأ طبي أصابني؟","خطأ طبّيّ"),
               ("أي محكمة تختص بدعوى صحة ونفاذ عقد بيع عقار قيمته مائة ألف دينار؟","بيعُ عقار")):
    bb=bundle(qq); i=[k for k,o in enumerate(bb) if o=="legis-38-1980-m34"]
    assert i and i[0] < HI, "%s: م34 مرافعات خارج النافذة"%lbl
    print("      ✓ %-10s م34 مرافعات موضع %d"%(lbl,i[0]))
b3=bundle("بعتُ نصيبي في قسيمةٍ سكنية بتوقيعٍ إلكترونيّ وأنكر المشتري، هل انتقلت الملكية؟ وما دعواي؟")
for oid in ("legis-5-1959-m7","legis-20-2014-m2","legis-20-2014-m3"):
    need(b3,oid,"الجسرُ العقاريّ")
assert not [o for o in bundle("ما عقوبةُ السرقة من منزلٍ مسكونٍ ليلًا؟") if o.startswith(("legis-5-1959","legis-38-1980-m34"))]
b4=bundle("أنشأت شركة وأريد ترخيص موقع إخباري إلكتروني، وإذا رفضت الوزارة هل أتظلم وأي محكمة تختص؟")
assert any(o.startswith("legis-8-2016") for o in b4[:HI]), "انحدارُ عائلة الإعلام"
print("      ✓ الجسرُ العقاريُّ الإلكترونيّ، والصمتُ الواجب، وعائلةُ الإعلام")
print("   === تمّ =====")
PY2
echo '=== تم: وصلُ الشريعة العامة للعقد بنواة القضاء الإداريّ — تطبيقيٌّ فقط ==='
"""

(H / "run_admciv.sh").write_text(SH, encoding="utf-8")
one = ("printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() +
       "' | base64 -d | gunzip > run_admciv.sh && bash run_admciv.sh")
(H / "DEPLOY_admciv.txt").write_text(one + "\n", encoding="utf-8")
assert gzip.decompress(base64.b64decode(one.split("'")[3])) == SH.encode(), "round-trip mismatch!"
print("app sha:", s_app); print("round-trip OK")
r = subprocess.run(["bash", "-n", str(H / "run_admciv.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(one))
