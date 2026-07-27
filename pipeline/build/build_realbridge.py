#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط: جسرُ التسجيل العقاري 5/1959 — محفّزٌ محايدُ الفرع في الغلاف.

الرصدُ الموجِب: قانونُ التسجيل العقاري مُدخَلٌ كاملًا (72 كائنًا) وله ثماني حزمٍ في
`_REGISTRATION_BUNDLES`، غير أنّه لا يُستحضَر عمليًّا لقيدين: الكتلةُ كلُّها مشروطةٌ بفرعٍ
«مدني/تجاري»، ومفاتيحُها مركّبةٌ تُطابَق بالاحتواء الحرفيّ («اثبات اصل الملكيه»، «تسجيل عقد
البيع») فلا ينطقها السؤالُ الطبيعيّ. فظهر الأثرُ في جوابٍ عن بيع عقارٍ بتوقيعٍ إلكترونيّ:
تحفّظ النموذجُ بأنّ «نصوص قانون التسجيل العقاري غير مرفقة» — وهي فجوةُ استحضارٍ لا فجوةُ محتوى.

والجسرُ يصل ما وصله المشرّع: 20/2014 (م2/م3 بنصّهما بعد المرسوم بقانون 148/2025) تُنشئ الالتزامَ
من المعاملة الإلكترونية، وم7 من 5/1959 تحبسه عند حدّه — «ويترتّب على عدم التسجيل أنّ الحقوق
المذكورة لا تنشأ ولا تنتقل ولا تتغيّر ولا تزول، لا بين ذوي الشأن ولا بالنسبة إلى غيرهم. ولا يكون
للتصرّفات غير المسجَّلة من الآثار سوى الالتزامات الشخصية بين ذوي الشأن». فالبيعُ ينعقد ويُلزم
شخصيًّا، والملكيةُ لا تنتقل — وم17 (التحريرُ بمعرفة موظّفي الدائرة) وم29/م30 (التصديقُ الحضوريّ
بشاهدين واستيثاقٌ شفويّ) تُفسّران لماذا لا يقوم البريدُ الموقَّعُ إلكترونيًّا مقامَ محرَّر التسجيل.

الاختبارُ يقيس **الترتيب** لا الوجود (نافذةُ الدرجة العالية = 18). نسخةٌ احتياطية + استرجاعٌ تلقائيّ.
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
TMP=/tmp/realbridge_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
grep -q "def _realty_ids" "$TMP/app.py" && echo "موجود: محفّز التسجيل العقاري" || {{ echo "خطأ: المحفّز مفقود"; exit 1; }}
[ "$(grep -c '_realty_ids' "$TMP/app.py")" -ge 2 ] && echo "موجود: النداء في الغلاف" || {{ echo "خطأ: المحفّز غيرُ موصولٍ بالغلاف"; exit 1; }}
echo "== قياسٌ قبل النشر (النسخة العاملة حاليًّا) =="
"$PYA" - <<'PYB'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
q=("اتفقتُ مع شريكي على بيع حصّته في عقارٍ عبر البريد الإلكتروني بتوقيعٍ إلكترونيّ، "
   "وأنكر الآن الاتفاق. هل ينعقد البيع؟ وهل التوقيع حجّة عليه؟")
b=list(m._draft_bundles("استشارة",q,[],None,None))
p=[i for i,o in enumerate(b) if o.startswith("legis-5-1959")]
print("   قبل: إجمالي=%d | 5/1959 أوّل موضع=%s | عددُ موادّه=%d"%(len(b),(p or ["—"])[0],len(p)))
PYB
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.realbridge"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.realbridge" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: الترتيب لا الوجود =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
HI = 18   # نافذة الدرجة العالية في المستهلك (_bscore = 0.85 if _bi < 18)
def bundle(q): return list(m._draft_bundles("استشارة",q,[],None,None))
def at(b,oid): return b.index(oid) if oid in b else None
def need(b,oid,lbl):
    i=at(b,oid)
    assert i is not None and i < HI, "%s: %s خارج نافذة الأولوية (موضع %s)"%(lbl,oid,i)
    return i

# (1) الجسرُ الأصليّ: معاملةٌ إلكترونية على عقار
q1=("اتفقتُ مع شريكي على بيع حصّته في عقارٍ عبر البريد الإلكتروني بتوقيعٍ إلكترونيّ، "
    "وأنكر الآن الاتفاق. هل ينعقد البيع؟ وهل التوقيع حجّة عليه؟")
b=bundle(q1)
print("   بعد: إجمالي=%d | الصدارة: %s"%(len(b),", ".join(o.replace("legis-","") for o in b[:9])))
for oid in ("legis-5-1959-m7","legis-5-1959-m17","legis-5-1959-m29","legis-5-1959-m30",
            "legis-20-2014-m2","legis-20-2014-m3"):
    print("      %-22s موضع %d"%(oid.replace("legis-",""), need(b,oid,"الجسر")))
print("   ✓ انعقادُ التصرّف (20/2014) وأثرُ عدم التسجيل (5/1959 م7) في نافذةٍ واحدة")

# (2) عقدٌ عرفيّ غيرُ مسجَّل ⇒ م7 وم8 وم14
b2=bundle("اشتريتُ أرضًا بعقدٍ عرفيٍّ ولم أسجّله، ثمّ باعها البائعُ لغيري وسجّلها. لمن تكون الملكية؟")
for oid in ("legis-5-1959-m7","legis-5-1959-m8","legis-5-1959-m14"):
    need(b2,oid,"العقد العرفيّ")
print("   ✓ العقدُ العرفيّ غيرُ المسجَّل: م7/م8/م14 في الصدارة (إجمالي=%d)"%len(b2))

# (3) تسجيلُ حقّ الإرث
b3=bundle("ما إجراءاتُ تسجيل حقّ الإرث في عقارات التركة؟")
for oid in ("legis-5-1959-m7","legis-5-1959-m10","legis-5-1959-m20","legis-5-1959-m21"):
    need(b3,oid,"الإرث")
print("   ✓ تسجيلُ حقّ الإرث: م7/م10/م20/م21 في الصدارة (إجمالي=%d)"%len(b3))

# (4) صحفُ الدعاوى العقارية والتأشير
b4=bundle("رفعتُ دعوى استحقاقٍ على عقار، فهل تُسجَّل صحيفةُ الدعوى؟ وما أثرُ التأشير على الغير؟")
for n in (1,3):
    need(b4,"legis-5-1959-m11-mukarrar-%d"%n,"صحف الدعاوى")
print("   ✓ صحفُ الدعاوى: م11 مكرر (1) و(3) في الصدارة")

# (5) صمتٌ واجب — لا يتسرّب القانونُ العقاريّ إلى ما ليس منه
for q,lbl in (("ما عقوبةُ السرقة من منزلٍ مسكونٍ ليلًا؟","سرقة"),
              ("هل يجوز فصلُ العامل أثناء إجازته المرضية؟","عمل"),
              ("ما مدّةُ الطعن بالتمييز في الأحكام الجزائية؟","تمييز"),
              ("زوجي هجرني منذ سنة، فهل لي طلبُ التفريق للضرر؟","أحوال"),
              ("ما شروطُ الترخيص لمزاولة أعمال البثّ المرئي والمسموع؟","بثّ")):
    bb=bundle(q)
    leak=[o for o in bb if o.startswith("legis-5-1959")]
    assert not leak, "تسرّبٌ عقاريّ في سؤال %s: %s"%(lbl,leak[:4])
print("   ✓ صمتٌ واجب في خمسة أسئلةٍ أجنبية عن التسجيل العقاري")

# (6) لا انحدار: مكتسباتُ النشرات السابقة باقية
b6=bundle("أنشأت شركة شخص واحد وأريد ترخيص موقع إخباري إلكتروني، ما المستندات وكم تستغرق "
          "الوزارة للرد وإذا رفضت هل أتظلم وما الكفالة ومدة الترخيص وإذا شغلت الموقع قبل "
          "الترخيص ما العقوبة وأي محكمة تختص؟")
e=[i for i,o in enumerate(b6) if o.startswith("legis-8-2016")]
a=[i for i,o in enumerate(b6) if o.startswith("legis-20-1981")]
assert e and e[0] < HI and a and a[0] < HI, "انحدار: 8/2016=%s 20/1981=%s"%(e[:1],a[:1])
assert not [o for o in b6 if o.startswith("legis-5-1959")], "تسرّبٌ عقاريّ في سؤال الإعلام"
print("   ✓ لا انحدار: 8/2016 موضع %d و20/1981 موضع %d"%(e[0],a[0]))

b7=bundle("ما عقوبة جريمة الرشوة للموظف العام في القانون الكويتي؟")
assert not [o for o in b7 if o.startswith("legis-5-1959")], "تسرّبٌ عقاريّ في سؤال الرشوة"
assert any(o.startswith("legis-16-1960") for o in b7[:HI]), "انحدار: عائلةُ الجزاء لم تتصدّر"
print("   ✓ لا انحدار: عائلةُ الجزاء تحتفظ بصدارتها")
print("   === تمّ =====")
PY2
echo '=== تم: جسرُ التسجيل العقاري 5/1959 (محايدُ الفرع) — تطبيقيٌّ فقط، لا يمسّ القاعدة ولا يحتاج reindex ==='
"""

(H / "run_realbridge.sh").write_text(SH, encoding="utf-8")
oneliner = ("printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() +
            "' | base64 -d | gunzip > run_realbridge.sh && bash run_realbridge.sh")
(H / "DEPLOY_realbridge.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_realbridge.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK")
r = subprocess.run(["bash", "-n", str(H / "run_realbridge.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(oneliner))
