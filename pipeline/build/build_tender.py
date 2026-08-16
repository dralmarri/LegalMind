#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ حِزم الاستحضار للقانون 49/2016 (تطبيقيٌّ فقط — لا يمسّ القاعدة ولا يحتاج reindex).

يُنشَر **بعد** DEPLOY_law49_2016.txt، لأنّ الحِزمَ قوائمُ معرّفات: ما لم تكن الكائناتُ في القاعدة
سقطت عند الجلب فصار الفحصُ كاذبًا.

الغرضُ المحدَّد: «الخاصُّ يقيّد العامّ» في مسألةٍ إجرائيةٍ لا تحتمل الخطأ. فالنواةُ العامّة
(20/1981) تُنبئ صاحبَ منازعةِ العقد الإداريّ أنّ الاستئناف يليه تمييزٌ فوق ثلاثين ألف دينار
(م14 مكرر). و49/2016 م79 تقول في المناقصات خلافَ ذلك: حكمُ دائرة الاستئناف المتخصّصة **باتّ
لا يجوز الطعن فيه بأيّ طريق**. فمن أجاب بالعامّ أضاع ميعادًا لا يُستدرَك، ومن أجاب بالخاصّ
أصاب. ولذا يتصدّر محفّزُ 49/2016 محفّزَ الاختصاص العامّ في ترتيب الغلاف.
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
TMP=/tmp/tender_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
for s in "_tender_ids" "_TENDER_STRONG" "_TENDER_TERM" "legis-49-2016-" "_AR_DIAC" "توسعة الإحالات بين القوانين"; do
  grep -q "$s" "$TMP/app.py" || {{ echo "خطأ: مفقود $s"; exit 1; }}
done
echo "علاماتُ السلامة موجودة"

echo
echo "== شرطٌ سابق: كائناتُ 49/2016 مُدخَلة =="
"$PYA" - <<'PY0'
import os, psycopg, sys
dsn = os.getenv('DATABASE_URL') or 'postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind'
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("select count(*) from knowledge_objects where id like 'legis-49-2016-%'")
    n = cur.fetchone()[0]
    print('كائنات 49/2016:', n)
    if n != 99:
        print('أوقف: شغّل DEPLOY_law49_2016.txt أوّلًا (المتوقّع 99).'); sys.exit(1)
PY0

echo
echo "== قياسٌ قبل النشر =="
"$PYA" - <<'PYB'
import sys; sys.path.insert(0, "/opt/LegalMind")
from admin import app as m
q = ("شركتنا تقدّمت بعطاء في مناقصة عامة طرحتها وزارة الأشغال ورُسيت على غيرنا. تظلّمنا فرُفض، "
     "فأين نرفع الدعوى؟ وهل حكمُ الاستئناف قابلٌ للتمييز؟")
b = list(m._draft_bundles("استشارة", q, [], None, None))
pos = lambda o: (b.index(o) if o in b else None)
print("   إجمالي=%d" % len(b))
for o in ("legis-49-2016-m79", "legis-49-2016-m78", "legis-49-2016-m77", "legis-20-1981-m2"):
    print("      %-22s موضع %s" % (o.replace("legis-", ""), pos(o)))
PYB

echo
echo "== النشر =="
cp -f "$APP" "$APP.bak.tender"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.tender" "$APP"; systemctl restart legalmind-admin; exit 1; }}

echo "== تحقّقٌ وظيفيّ: الترتيبُ لا الوجود =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0, "/opt/LegalMind")
from admin import app as m
HI = 18
B = lambda q: list(m._draft_bundles("استشارة", q, [], None, None))


def need(b, oid, lbl):
    i = b.index(oid) if oid in b else None
    assert i is not None and i < HI, "%s: %s خارج نافذة الأولوية (موضع %s)" % (lbl, oid, i)
    return i


q1 = ("شركتنا تقدّمت بعطاء في مناقصة عامة طرحتها وزارة الأشغال ورُسيت على غيرنا. تظلّمنا فرُفض، "
      "فأين نرفع الدعوى؟ وهل حكمُ الاستئناف قابلٌ للتمييز؟")
b = B(q1)
print("   إجمالي=%d | الصدارة: %s" % (len(b), ", ".join(o.replace("legis-", "") for o in b[:14])))
for oid in ("legis-49-2016-m77", "legis-49-2016-m78", "legis-49-2016-m79",
            "legis-49-2016-m2", "legis-20-1981-m2"):
    print("      %-22s موضع %d" % (oid.replace("legis-", ""), need(b, oid, "خصومةُ المناقصة")))
assert b.index("legis-49-2016-m79") < b.index("legis-20-1981-m2"), \\
    "الخاصُّ لم يتصدّر العامّ: م79 بعد م2 من 20/1981"
print("   ✓ م79 (الحكمُ الباتّ) تتصدّر النواةَ العامّة — «الخاصُّ يقيّد العامّ» ترتيبًا")

for q, oids, lbl in (
    ("صادرت الجهة صاحبة الشأن تأميننا النهائي في مقاولة الأشغال بعد فسخ العقد، فهل يجوز؟",
     ("legis-49-2016-m65", "legis-49-2016-m70"), "مصادرةُ التأمين"),
    ("شركة أجنبية تريد التقدّم لمناقصة في الكويت، هل تحتاج وكيلًا محلّيًا وسجلًا تجاريًا؟",
     ("legis-49-2016-m31", "legis-49-2016-m24"), "المتعاقدُ الأجنبيّ"),
    ("هل يجوز للجهاز إصدار أمر تغييري بالزيادة يتجاوز 5% من قيمة عقد المقاولة؟",
     ("legis-49-2016-m74", "legis-49-2016-m76"), "الأوامرُ التغييرية"),
    ("ما نسبة أفضلية المنتج المحلي والمشروعات الصغيرة والمتوسطة في المناقصات؟",
     ("legis-49-2016-m62", "legis-49-2016-m87"), "الأفضلية"),
    ("هل يسري قانون المناقصات على مشتريات مؤسسة البترول الكويتية من مشتقات النفط؟",
     ("legis-49-2016-m2", "legis-49-2016-m3"), "نطاقُ السريان")):
    bb = B(q)
    print("   %s: %s" % (lbl, " | ".join("%s=%d" % (o.replace("legis-49-2016-", "م"), need(bb, o, lbl))
                                        for o in oids)))
print("   ✓ العناقيدُ الخمسة داخل النافذة")

print("   == لا انحدار ==")
b2 = B("شركتي وقّعت عقد توريد مع وزارة الأشغال العامة ثمّ أوقفت الوزارة الصرف. أين أرفع دعواي؟")
need(b2, "legis-20-1981-m2", "العقدُ الإداريّ")
print("      ✓ نواةُ القضاء الإداريّ باقيةٌ في منازعة العقد الإداريّ (م2 موضع %d)"
      % b2.index("legis-20-1981-m2"))
b3 = B("أي محكمة تختص بدعوى تعويض ضد وزارة الصحة عن خطأ طبي أصابني؟")
need(b3, "legis-38-1980-m34", "الخطأُ الطبّيّ")
assert not [o for o in b3 if o.startswith("legis-49-2016")], "تسرّبٌ مناقصاتيّ في الخطأ الطبّيّ"
print("      ✓ الخطأُ الطبّيّ لم يُحوَّل ولم يتسرّب إليه 49/2016")
b4 = B("بعتُ نصيبي في قسيمةٍ سكنية بتوقيعٍ إلكترونيّ وأنكر المشتري، هل انتقلت الملكية؟ وما دعواي؟")
for oid in ("legis-5-1959-m7", "legis-20-2014-m2"):
    need(b4, oid, "الجسرُ العقاريّ")
print("      ✓ الجسرُ العقاريُّ الإلكترونيّ سليم")
for q, lbl in (("ما عقوبةُ السرقة من منزلٍ مسكونٍ ليلًا؟", "سرقة"),
               ("هل يجوز فصلُ العامل أثناء إجازته المرضية؟", "عمل"),
               ("زوجي هجرني منذ سنة، فهل لي طلبُ التفريق للضرر؟", "أحوال")):
    leak = [o for o in B(q) if o.startswith("legis-49-2016")]
    assert not leak, "تسرّبٌ مناقصاتيّ في سؤال %s: %s" % (lbl, leak[:4])
print("      ✓ الصمتُ الواجب باقٍ في الجزائيّ والعمل والأحوال")
print("   === تمّ =====")
PY2
echo '=== تم: حِزمُ المناقصات العامة 49/2016 — تطبيقيٌّ فقط، لا يمسّ القاعدة ==='
"""

(H / "run_tender.sh").write_text(SH, encoding="utf-8")
one = ("printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() +
       "' | base64 -d | gunzip > run_tender.sh && bash run_tender.sh")
(H / "DEPLOY_tender.txt").write_text(one + "\n", encoding="utf-8")
assert gzip.decompress(base64.b64decode(one.split("'")[3])) == SH.encode(), "round-trip mismatch!"
print("app sha:", s_app)
print("run_tender.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
r = subprocess.run(["bash", "-n", str(H / "run_tender.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(one))
