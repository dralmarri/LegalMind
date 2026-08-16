#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ حِزم الاستحضار للقانون 75/2019 (تطبيقيٌّ فقط — لا يمسّ القاعدة ولا يحتاج reindex).

يُنشَر **بعد** DEPLOY_law75.txt، لأنّ الحِزمَ قوائمُ معرّفات: ما لم تكن الكائناتُ في القاعدة
سقطت عند الجلب فصار الفحصُ كاذبًا. ولذلك يبدأ بشرطٍ سابقٍ يعدّ 52 كائنًا ويقف إن نقصت.

الغرضُ المحدَّد — **الاستثناءُ قبل العقوبة**: م41 تنصّ صراحةً على أنّ عقوباتِ الفصل تُطبَّق
«دون الإخلال بالاستثناءات الواردة بالمادتين 31، 32». فمن أفتى بالحبس والغرامة ولم يعرض
النازلةَ على م31–م33 (النسخُ للاستعمال الشخصيّ، والاقتباسُ، والاستعمالُ التعليميّ والبحثيّ،
ورخصُ الترجمة والنسخ) **جرّم فعلًا مباحًا** — وهو أفدحُ من العكس، لأنّ الأوّل يُخيف بريئًا
ويورّطه في صلحٍ لا يلزمه.
ويليه م42: النيابةُ العامة **دون غيرها** بالتحقيق والتصرّف والادّعاء، ودائرةُ الجنايات
بالمحكمة الكلية بالنظر. فمن قصد المحكمة الجزئية أو رفع جنحةً مباشرةً أخطأ بابَ الخصومة.
"""
import base64, gzip, hashlib, pathlib, subprocess

H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
b_app = base64.b64encode(gzip.compress(APP.read_bytes(), 9)).decode()
s_app = hashlib.sha256(APP.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
if [ -r /opt/LegalMind/deploy/.env ]; then set -a; . /opt/LegalMind/deploy/.env; set +a; fi
[ -n "${{DATABASE_URL:-}}" ] || {{ echo "خطأ: DATABASE_URL غير مضبوط"; exit 1; }}
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/copyright_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app المتوقع: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
for s in "_copyright_ids" "_CR_STRONG" "_CR_OBJ" "_CR_ACT" "legis-75-2019-" \\
         "_tender_ids" "_infoaccess_ids" "_AR_DIAC"; do
  grep -q "$s" "$TMP/app.py" || {{ echo "خطأ: مفقود $s"; exit 1; }}
done
echo "علاماتُ السلامة موجودة"

echo
echo "== شرطٌ سابق: كائناتُ 75/2019 مُدخَلة بالنسخة المقابَلة على الجريدة =="
"$PYA" - <<'PY0'
import os, psycopg, sys
with psycopg.connect(os.environ['DATABASE_URL']) as cx, cx.cursor() as cur:
    cur.execute("select count(*) from knowledge_objects where id like 'legis-75-2019-%'")
    n = cur.fetchone()[0]; print('كائنات 75/2019:', n)
    if n != 52:
        print('أوقف: شغّل DEPLOY_law75.txt أوّلًا (المتوقّع 52).'); sys.exit(1)
    cur.execute("select count(*) from knowledge_objects "
                "where id like 'legis-75-2019-m%' and (metadata->>'penal')::bool")
    p = cur.fetchone()[0]
    if p != 7:
        print('أوقف: العقوباتُ %d لا 7 — القاعدةُ فيها النسخةُ القديمة قبل فصل «أحكام ختامية».' % p)
        sys.exit(1)
    print('العقوباتُ الموسومة: 7 ✓ (النسخةُ المقابَلة)')
PY0

echo
echo "== قياسٌ قبل النشر =="
"$PYA" - <<'PYB'
import sys; sys.path.insert(0, "/opt/LegalMind")
from admin import app as m
q = ("عميلي ناشرٌ صوّر فصولًا من كتابٍ مترجمٍ ووزّعها على طلبته بلا إذن المؤلف، "
     "ورُفعت عليه شكوى. ما عقوبته؟ وهل له دفعٌ يُعفيه؟")
b = list(m._draft_bundles("استشارة", q, [], None, None))
pos = lambda o: (b.index(o) if o in b else None)
print("   إجمالي=%d" % len(b))
for o in ("legis-75-2019-m41", "legis-75-2019-m31", "legis-75-2019-m32",
          "legis-75-2019-m43", "legis-75-2019-m42"):
    print("      %-22s موضع %s" % (o.replace("legis-", ""), pos(o)))
PYB

echo
echo "== النشر =="
cp -f "$APP" "$APP.bak.copyright"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.copyright" "$APP"; systemctl restart legalmind-admin; exit 1; }}

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


q1 = ("عميلي ناشرٌ صوّر فصولًا من كتابٍ مترجمٍ ووزّعها على طلبته بلا إذن المؤلف، "
      "ورُفعت عليه شكوى. ما عقوبته؟ وهل له دفعٌ يُعفيه؟")
b = B(q1)
print("   إجمالي=%d | الصدارة: %s" % (len(b), ", ".join(o.replace("legis-", "") for o in b[:14])))
i41 = need(b, "legis-75-2019-m41", "الاعتداء")
i31 = need(b, "legis-75-2019-m31", "الاعتداء")
i32 = need(b, "legis-75-2019-m32", "الاعتداء")
i43 = need(b, "legis-75-2019-m43", "الاعتداء")
i42 = need(b, "legis-75-2019-m42", "الاعتداء")
for lbl, i in (("م41 الربط", i41), ("م31 الاستثناء", i31), ("م32", i32),
               ("م42 النيابة", i42), ("م43 العقوبة", i43)):
    print("      %-16s موضع %d" % (lbl, i))
assert i41 < i31 < i43 and i32 < i43, \\
    "الاستثناءُ لم يتقدّم العقوبة: م41=%d م31=%d م32=%d م43=%d" % (i41, i31, i32, i43)
print("   ✓ م41 ← م31/م32 ← م43 — العقوبةُ لا تُفتى قبل عرض الاستثناء")

for q, oids, lbl in (
    ("هل يجوز تصوير فصلٍ من مصنَّفٍ لأغراض التدريس الجامعي والبحث العلمي بلا إذن المؤلف؟",
     ("legis-75-2019-m31", "legis-75-2019-m32", "legis-75-2019-m33"), "الاستعمالُ التعليميّ"),
    ("ما مدة حماية حقوق المؤلف المالية بعد وفاته؟ ومتى يصير المصنَّف ملكًا عامًّا؟",
     ("legis-75-2019-m23", "legis-75-2019-m22"), "مدةُ الحماية"),
    ("محلٌّ يبيع أجهزة فكّ تشفير القنوات المشفّرة، ما الجريمة وما العقوبة؟",
     ("legis-75-2019-m44", "legis-75-2019-m41"), "التحايلُ التكنولوجيّ"),
    ("أريد وقف نشر مصنَّفي المعتدى عليه فورًا وضبط النسخ لدى المطبعة، ما السبيل؟",
     ("legis-75-2019-m35", "legis-75-2019-m36"), "الإجراءُ التحفظيّ"),
    ("أودعتُ مصنَّفي لدى المكتبة الوطنية، فهل يثبت لي الملك قطعًا في نزاعٍ على الملكية؟",
     ("legis-75-2019-m38", "legis-75-2019-m40"), "قرينةُ الإيداع"),
    ("منتج تسجيلات صوتية يمنع إذاعةً من بثّ تسجيلاته، ما حقوقه المجاورة؟",
     ("legis-75-2019-m19", "legis-75-2019-m20"), "الحقوقُ المجاورة"),
    ("صمّمتُ شعارًا لشركةٍ وأنا موظّفٌ لديها بعقد عمل، لمن تعود حقوق التأليف؟",
     ("legis-75-2019-m27", "legis-75-2019-m25"), "المصنفُ لحساب الغير"),
    ("هل تحمي حقوقُ المؤلف الأفكارَ المجرّدة والنصوصَ التشريعية والأخبار؟",
     ("legis-75-2019-m4", "legis-75-2019-m3"), "ما لا يُحمى"),
    ("هل ما زال القانون 22 لسنة 2016 في شأن حقوق المؤلف ساريًا؟",
     ("legis-75-2019-m49",), "الإلغاء")):
    bb = B(q)
    print("   %-22s %s" % (lbl, " | ".join(
        "%s=%d" % (o.replace("legis-75-2019-", "م"), need(bb, o, lbl)) for o in oids)))
print("   ✓ العناقيدُ التسعة داخل النافذة")

print("   == لا انحدار ==")
for q, oid, lbl in (
    ("شركتنا تقدّمت بعطاء في مناقصة عامة ورُسيت على غيرنا، تظلّمنا فرُفض، فأين نرفع الدعوى؟",
     "legis-49-2016-m79", "المناقصات"),
    ("طلبتُ من الوزارة نسخةً من مستند يخصّني فرفضت، ماذا أفعل؟",
     "legis-12-2020-m13", "حقُّ الاطلاع"),
    ("أي محكمة تختص بدعوى تعويض ضد وزارة الصحة عن خطأ طبي أصابني؟",
     "legis-38-1980-m34", "الخطأُ الطبّيّ")):
    bb = B(q)
    print("      ✓ %-14s %s موضع %d" % (lbl, oid.replace("legis-", ""), need(bb, oid, lbl)))

for q, lbl in (("ما عقوبةُ السرقة من منزلٍ مسكونٍ ليلًا؟", "سرقة"),
               ("هل يجوز فصلُ العامل أثناء إجازته المرضية؟", "عمل"),
               ("زوجي هجرني منذ سنة، فهل لي طلبُ التفريق للضرر؟", "أحوال"),
               ("ما شروط قيد بيانات الشركة في السجل التجاري ونشر الملخص؟", "سجل تجاري"),
               ("اشتريتُ أرضًا بعقدٍ عرفيٍّ ولم أسجّله", "عقار"),
               ("كتبتُ إقرارًا بالدين ونشرته على الواتساب، هل يُحتجّ به؟", "إقرار بدين")):
    leak = [o for o in B(q) if o.startswith("legis-75-2019")]
    assert not leak, "تسرُّبُ حقوق المؤلف في سؤال %s: %s" % (lbl, leak[:4])
print("      ✓ الصمتُ الواجب باقٍ في الجزائيّ والعمل والأحوال والتجاريّ والعقار")
print("   === تمّ =====")
PY2
echo '=== تم: حِزمُ حقوق المؤلف والحقوق المجاورة 75/2019 — تطبيقيٌّ فقط، لا يمسّ القاعدة ==='
"""

(H / "run_copyright.sh").write_text(SH, encoding="utf-8")
one = ("printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() +
       "' | base64 -d | gunzip > run_copyright.sh && bash run_copyright.sh")
(H / "DEPLOY_copyright.txt").write_text(one + "\n", encoding="utf-8")
assert gzip.decompress(base64.b64decode(one.split("'")[3])) == SH.encode(), "round-trip mismatch!"
print("app sha:", s_app)
print("run_copyright.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
r = subprocess.run(["bash", "-n", str(H / "run_copyright.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(one))
