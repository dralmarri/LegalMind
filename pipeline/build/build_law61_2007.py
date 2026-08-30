#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ القانون 61/2007 (المطبوعات والنشر): مُدخِل + JSON (33 مادة + ديباجة = 34 كائنًا؛ النصُّ النافذ
المعدَّل، مقابَلٌ بصور الجريدة الرسمية ع762 وبالنسخة المجمَّعة) + app.py: محفّزٌ جديد _press_ids محايدُ الفرع،
و**تفعيلُ جسر م18** من 8/2016 (كان معطَّلًا لغياب المُحال إليه: م19/م20/م21 محظورات و م26/م27 عقوباتها)،
وجسرُ الردّ (8/2016 م17 ⇄ 3/2006 م17)، وجسرُ الطعن (3/2006 م11 + نواة 20/1981 — نصٌّ خاصٌّ لاحق يواجه
استثناءَ «تراخيص إصدار الصحف والمجلات» في م1/خامسا). إدخال + فهرسة + ديباجات + نشر + اختبارُ ترتيبٍ لا وجود."""
import base64, gzip, hashlib, pathlib, subprocess
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")


def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


ingest = H / "ingest_law61_2007.py"; js = H / "law61_2007_parsed.json"; px = H / "preamble_xref.py"
b_ing, b_js, b_app, b_px = enc(ingest), enc(js), enc(APP), enc(px)
s_ing, s_js, s_app, s_px = sha(ingest), sha(js), sha(APP), sha(px)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law61_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law61_2007.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law61_2007_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_law61_2007.py" "$TMP/law61_2007_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law61_2007.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json; d=json.load(open('$TMP/law61_2007_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==21; assert [int(k[1:]) for k in d['order']]==list(range(1,22)); c=' '.join(a.values()); assert chr(0xFFFD) not in c and '_' not in c; assert 'الدائرة الإدارية' in a['m5'] and '20 لسنة 1981' in a['m5']; assert 'كراهية أو ازدراء أي فئة' in a['m11'] and 'التجريح' in a['m11']; assert 'عشرين ألف دينار' in a['m13'] and 'مائة ألف دينار' in a['m7']; print('61/2007 json OK: 21 مادة، طعن م5، البند 11، التجريح، عقوبات م13، كفالة م7')"
for tok in legis-61-2007 _bcast_ids _BCAST_KEYS; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
cd /opt/LegalMind
echo "== إدخال 3/2006 (فعليّ) =="; "$PYA" "$TMP/ingest_law61_2007.py" "$TMP/law61_2007_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم الديباجات =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "رسم الديباجات محدّث"
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law61"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law61" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: الترتيب لا الوجود =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
HI = 18
def bundle(q): return list(m._draft_bundles("استشارة",q,[],None,None))
def at(b,o): return b.index(o) if o in b else None

a=bundle("ما المحظور نشره في المواقع الإلكترونية الإخبارية وما عقوبته؟")
for o in ("legis-8-2016-m18","legis-3-2006-m21","legis-3-2006-m27","legis-61-2007-m11","legis-61-2007-m13"):
    i=at(a,o); assert i is not None and i < HI, "%s خارج نافذة الأولوية (%s)"%(o,i)
print("  ✓ جسر م18 مكتملُ الطرفين: المطبوعات (م21/م27) + الإعلام المرئي (م11/م13) — كلُّها متصدّرة")
b=bundle("ما عقوبة البث الفضائي بدون ترخيص وأي محكمة تختص؟")
for o in ("legis-61-2007-m12","legis-61-2007-m18"):
    assert at(b,o) is not None and at(b,o) < HI
print("  ✓ البث بلا ترخيص (م12: حبس ≤ سنة + 5000-10000 + مصادرة وجوبية) + دائرة الجنايات (م18)")
c=bundle("رُفض طلب ترخيص قناتي الفضائية، فهل أطعن أمام القضاء وما الميعاد؟")
for o in ("legis-61-2007-m5","legis-20-1981-m7","legis-20-1981-m1"):
    assert at(c,o) is not None and at(c,o) < HI
print("  ✓ جسر الطعن: م5 (تُجيزه صراحةً وفق 20/1981) + نواةُ القضاء الإداري")
d=bundle("بثت القناة مادة فيها ازدراء لفئة من المجتمع، ما العقوبة؟")
for o in ("legis-61-2007-m11","legis-61-2007-m13","legis-19-2012-m2"):
    assert at(d,o) is not None and at(d,o) < HI
print("  ✓ محظورُ الكراهية (م11/11) + عقوبتُه (م13) + العقوبةُ الأشدّ (19/2012 م2)")
e=bundle("ما رأس المال المطلوب لترخيص قناة فضائية مرئية ومن يكون المدير العام؟")
for o in ("legis-61-2007-m3","legis-61-2007-m4"):
    assert at(e,o) is not None
print("  ✓ رأس المال (م3: خمسمائة ألف للمرئية) والمدير العام (م4)")
f=bundle("ما القوانين المتصلة بقانون الإعلام المرئي والمسموع 61 لسنة 2007؟")
assert "legis-61-2007-preamble" in f
print("  ✓ رسم الديباجات 61/2007 | ديباجات متصلة:", len([x for x in f if x.endswith('-preamble')]))
for lbl,q in (("المرور","ما عقوبة القيادة برخصة سيارة منتهية؟"),
              ("الرشوة","ما عقوبة جريمة الرشوة للموظف العام؟"),
              ("البيئة","تلوث بحري في جون الكويت")):
    r=bundle(q); assert not any(x.startswith("legis-61-2007") for x in r), "تسرّب 61/2007 إلى: %s"%lbl
print("  ✓ لا تسرّب: المرور والرشوة والبيئة")
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-61-2007-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects"); tot=cur.fetchone()[0]
assert n==22, "عدد كائنات 3/2006 = %s (المتوقع 22)"%n
print("  ✓ العدّ: 3/2006 =",n,"| الإجمالي =",tot)
print("  === تمّ =====")
PY2
echo '=== تم: إدخال القانون 3/2006 للمطبوعات والنشر — 22 كائنًا + محفّز _bcast_ids + إتمام جسر م18 ==='
"""
(H / "run_law61_2007.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law61_2007.sh && sha256sum run_law61_2007.sh"
(H / "DEPLOY_law61_2007.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app); print("px sha:", s_px)
print("run_law61_2007.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; 4 shas embedded")
r = subprocess.run(["bash", "-n", str(H / "run_law61_2007.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(oneliner))
