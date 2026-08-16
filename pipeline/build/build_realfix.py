#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط: إلحاقُ عنقود صحف الدعاوى العقارية بوضع «المعاملة الإلكترونية» في محفّز 5/1959.

الرصدُ الموجِب: في جواب «بيع الحصّة العقارية بتوقيعٍ إلكترونيّ» أعلن النموذجُ أنّ سندَ التأشير بصحيفة
دعوى صحّة التعاقد «لم يرد في السياق المرفق فتُراجع نصوصُه» — والسندُ مُدخَلٌ في القاعدة: م11 مكرر (1)
من 5/1959 «يجب تسجيل صحف دعاوى استحقاق أيّ حقٍّ من الحقوق العينية العقارية أو التأشير…»، وم11 مكرر (3)
في أثره تجاه الغير. والسببُ تصميميّ لا محتوائيّ: كان وضعُ «المعاملة الإلكترونية» يختصر نفسه إلى سبع
موادّ حمايةً لنافذة الصدارة، فأسقط العنقودَ ولو نطق السؤالُ بالخصومة. فصار الاختصارُ حاجبًا لا موفّرًا.

والعلاجُ مشروط: يُلحَق العنقودُ (أربعُ موادّ) متى نطق السؤالُ بدعوى أو إنكارٍ أو امتناعٍ أو أثرٍ تجاه
الغير — فيبقى المجموعُ إحدى عشرة مادةً و20/2014 م2/م3/م18/م19/م20 كلُّها داخل نافذة الدرجة العالية.
وسؤالُ المعاملة الإلكترونية المجرّد من الخصومة يبقى على نواته السبع كما كان.

ويطبع السكربتُ قبل ذلك — قراءةً فقط — بحثًا عن قاعدة الاختصاص المحلّيّ في الدعاوى العقارية بالمرافعات
38/1980، لأنّ النموذج بلغ الاختصاص قياسًا على م833 مدنيّ، والاختصاصُ لا يُقاس.
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
TMP=/tmp/realfix_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
grep -q "فكان الاختصارُ حاجبًا لا موفّرًا" "$TMP/app.py" && echo "موجود: إلحاقُ عنقود صحف الدعاوى" || {{ echo "خطأ"; exit 1; }}

echo
echo "== معاينةٌ (قراءةٌ فقط): أين قاعدةُ الاختصاص المحلّيّ العقاريّ في المرافعات 38/1980؟ =="
"$PYA" - <<'PYQ'
import os, re, psycopg
dsn = os.getenv('DATABASE_URL') or 'postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind'
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT id,original_text FROM knowledge_objects WHERE id LIKE 'legis-38-1980-%' "
                "AND (original_text LIKE '%%يقع في دائرتها%%' OR original_text LIKE '%%يقع في دائرته%%' "
                "     OR original_text LIKE '%%الاختصاص المحلي%%' OR original_text LIKE '%%موطن المدعى عليه%%')")
    rows = cur.fetchall()
    key = lambda r: int(re.search(r"m(\\d+)", r[0]).group(1)) if re.search(r"m(\\d+)", r[0]) else 10**6
    rows.sort(key=key)
    print("موادُّ الاختصاص المحلّيّ: %d" % len(rows))
    for oid, t in rows[:12]:
        print("\\n### %s\\n%s" % (oid, re.sub(r"\\s+", " ", t).strip()[:300]))
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-38-1980-%'")
    print("\\nإجمالي كائنات المرافعات 38/1980 =", cur.fetchone()[0])
PYQ

echo
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.realfix"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.realfix" "$APP"; systemctl restart legalmind-admin; exit 1; }}
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

q1=("بعتُ نصيبي في قسيمةٍ سكنية لابن عمّي بموجب اتفاقٍ وقّعناه بالتوقيع الإلكترونيّ عبر البريد، "
    "وقبض جزءًا من الثمن، والآن يرفض الحضور إلى دائرة التسجيل العقاري ويقول إنّ العقد لم يُسجَّل "
    "فلا قيمة له. هل الملكيةُ انتقلت إليّ؟ وما دعواي؟")
b=bundle(q1)
print("   إجمالي=%d | الصدارة: %s"%(len(b),", ".join(o.replace("legis-","") for o in b[:13])))
for oid in ("legis-5-1959-m7","legis-5-1959-m17","legis-5-1959-m29",
            "legis-5-1959-m11-mukarrar-1","legis-5-1959-m11-mukarrar-3",
            "legis-20-2014-m2","legis-20-2014-m3","legis-20-2014-m18","legis-20-2014-m19"):
    print("      %-26s موضع %d"%(oid.replace("legis-",""), need(b,oid,"الخصومة العقارية")))
print("   ✓ سندُ التأشير (م11 مكرر) صار داخل النافذة مع نواة الانعقاد وحجّية التوقيع")

# لا انحدار (1): سؤالٌ إلكترونيٌّ عقاريٌّ بلا خصومة ⇒ النواةُ السبع كما كانت، بلا عنقودِ الدعاوى
b2=bundle("هل يصحّ توقيع عقد بيع عقارٍ بتوقيعٍ إلكترونيّ؟")
mk=[o for o in b2 if "mukarrar" in o and o.startswith("legis-5-1959")]
assert not mk, "عنقودُ الدعاوى نطق بلا خصومة: %s"%mk
for oid in ("legis-5-1959-m7","legis-20-2014-m2","legis-20-2014-m3"):
    need(b2,oid,"بلا خصومة")
print("   ✓ لا انحدار: السؤالُ المجرّد من الخصومة يبقى على نواته السبع")

# لا انحدار (2): مكتسباتُ النشرة السابقة
b3=bundle("اشتريتُ أرضًا بعقدٍ عرفيٍّ ولم أسجّله، ثمّ باعها البائعُ لغيري وسجّلها. لمن تكون الملكية؟")
for oid in ("legis-5-1959-m7","legis-5-1959-m8","legis-5-1959-m14"):
    need(b3,oid,"العقد العرفيّ")
b4=bundle("ما إجراءاتُ تسجيل حقّ الإرث في عقارات التركة؟")
for oid in ("legis-5-1959-m10","legis-5-1959-m20","legis-5-1959-m21"):
    need(b4,oid,"الإرث")
print("   ✓ لا انحدار: العقدُ العرفيّ وتسجيلُ الإرث كما كانا")

# لا انحدار (3): الصمتُ الواجب باقٍ
for q,lbl in (("ما عقوبةُ السرقة من منزلٍ مسكونٍ ليلًا؟","سرقة"),
              ("هل يجوز فصلُ العامل أثناء إجازته المرضية؟","عمل"),
              ("زوجي هجرني منذ سنة، فهل لي طلبُ التفريق للضرر؟","أحوال")):
    leak=[o for o in bundle(q) if o.startswith("legis-5-1959")]
    assert not leak, "تسرّبٌ عقاريّ في سؤال %s: %s"%(lbl,leak[:4])
print("   ✓ لا انحدار: الصمتُ الواجب باقٍ")
print("   === تمّ =====")
PY2
echo '=== تم: إلحاقُ عنقود صحف الدعاوى العقارية — تطبيقيٌّ فقط، لا يمسّ القاعدة ولا يحتاج reindex ==='
"""

(H / "run_realfix.sh").write_text(SH, encoding="utf-8")
oneliner = ("printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() +
            "' | base64 -d | gunzip > run_realfix.sh && bash run_realfix.sh")
(H / "DEPLOY_realfix.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_realfix.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
assert gzip.decompress(base64.b64decode(oneliner.split("'")[3])) == SH.encode(), "round-trip mismatch!"
print("round-trip OK")
r = subprocess.run(["bash", "-n", str(H / "run_realfix.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(oneliner))
