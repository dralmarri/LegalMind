#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ القانون 3/2006 (المطبوعات والنشر): مُدخِل + JSON (33 مادة + ديباجة = 34 كائنًا؛ النصُّ النافذ
المعدَّل، مقابَلٌ بصور الجريدة الرسمية ع762 وبالنسخة المجمَّعة) + app.py: محفّزٌ جديد _press_ids محايدُ الفرع،
و**تفعيلُ جسر م18** من 8/2016 (كان معطَّلًا لغياب المُحال إليه: م19/م20/م21 محظورات و م26/م27 عقوباتها)،
وجسرُ الردّ (8/2016 م17 ⇄ 3/2006 م17)، وجسرُ الطعن (3/2006 م11 + نواة 20/1981 — نصٌّ خاصٌّ لاحق يواجه
استثناءَ «تراخيص إصدار الصحف والمجلات» في م1/خامسا). إدخال + فهرسة + ديباجات + نشر + اختبارُ ترتيبٍ لا وجود."""
import base64, gzip, hashlib, pathlib, subprocess
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")


def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


ingest = H / "ingest_law3_2006.py"; js = H / "law3_2006_parsed.json"; px = H / "preamble_xref.py"
b_ing, b_js, b_app, b_px = enc(ingest), enc(js), enc(APP), enc(px)
s_ing, s_js, s_app, s_px = sha(ingest), sha(js), sha(APP), sha(px)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law3_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law3_2006.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law3_2006_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_law3_2006.py" "$TMP/law3_2006_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law3_2006.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json; d=json.load(open('$TMP/law3_2006_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==33; assert [int(k[1:]) for k in d['order']]==list(range(1,34)); c=' '.join(a.values()); assert chr(0xFFFD) not in c and ')))' not in c; assert 'المواقع أو الوسائل الإعلامية الإلكترونية' in a['m2']; assert 'الدائرة الإدارية' in a['m11'] and '20 لسنة 1981' in a['m11']; assert 'خمسة آلاف دينار' in a['m27'] and 'مائة ألف دينار' in a['m12']; print('3/2006 json OK: 33 مادة متسلسلة، جسر م2 الإلكتروني، طعن م11، أرقام م27/م12')"
for tok in legis-3-2006 _press_ids _PRESS_KEYS; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
cd /opt/LegalMind
echo "== إدخال 3/2006 (فعليّ) =="; "$PYA" "$TMP/ingest_law3_2006.py" "$TMP/law3_2006_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم الديباجات =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "رسم الديباجات محدّث"
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law3"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law3" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ: الترتيب لا الوجود =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
HI = 18
def bundle(q): return list(m._draft_bundles("استشارة",q,[],None,None))
def at(b,o): return b.index(o) if o in b else None

a=bundle("ما المحظور نشره في المواقع الإلكترونية الإخبارية وما عقوبته؟")
for o in ("legis-8-2016-m18","legis-3-2006-m19","legis-3-2006-m21","legis-3-2006-m27"):
    i=at(a,o); assert i is not None and i < HI, "%s خارج نافذة الأولوية (%s)"%(o,i)
print("  ✓ جسر م18 مُفعَّل: الإحالة (8/2016 م18) + محظورات المطبوعات (م19/م21) + عقوباتها (م27) — كلُّها متصدّرة")
b=bundle("رُفض طلب ترخيص صحيفتي اليومية، فهل أطعن أمام القضاء وما الميعاد؟")
for o in ("legis-3-2006-m11","legis-20-1981-m7","legis-20-1981-m1"):
    i=at(b,o); assert i is not None and i < HI, "%s خارج النافذة (%s)"%(o,i)
print("  ✓ جسر الطعن: م11 (تُجيزه صراحةً) + م1 من 20/1981 (وفيها استثناء تراخيص الصحف) + م7 (الميعاد)")
c=bundle("نشرت الصحيفة مقالًا فيه تحقير للدستور، ما العقوبة وأي محكمة؟")
for o in ("legis-3-2006-m21","legis-3-2006-m27","legis-3-2006-m24"):
    assert at(c,o) is not None and at(c,o) < HI
print("  ✓ المحظورات (م21) + العقوبة (م27) + دائرة الجنايات (م24)")
d=bundle("ما شروط ترخيص مطبعة ودار نشر وترجمة؟")
assert at(d,"legis-3-2006-m3") is not None
print("  ✓ تراخيص المطابع ودور النشر (م3)")
e=bundle("ما القوانين المتصلة بقانون المطبوعات والنشر 3 لسنة 2006؟")
assert "legis-3-2006-preamble" in e
print("  ✓ رسم الديباجات 3/2006 | ديباجات متصلة:", len([x for x in e if x.endswith('-preamble')]))
for lbl,q in (("المرور","ما عقوبة القيادة برخصة سيارة منتهية؟"),
              ("الرشوة","ما عقوبة جريمة الرشوة للموظف العام؟")):
    r=bundle(q); assert not any(x.startswith("legis-3-2006") for x in r), "تسرّب المطبوعات إلى: %s"%lbl
print("  ✓ لا تسرّب: المرور والرشوة لا يجرّان قانون المطبوعات")
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-3-2006-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects"); tot=cur.fetchone()[0]
assert n==34, "عدد كائنات 3/2006 = %s (المتوقع 34)"%n
print("  ✓ العدّ: 3/2006 =",n,"| الإجمالي =",tot)
print("  === تمّ =====")
PY2
echo '=== تم: إدخال القانون 3/2006 للمطبوعات والنشر — 34 كائنًا + محفّز _press_ids + تفعيل جسر م18 ==='
"""
(H / "run_law3_2006.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law3_2006.sh && sha256sum run_law3_2006.sh"
(H / "DEPLOY_law3_2006.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app); print("px sha:", s_px)
print("run_law3_2006.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; 4 shas embedded")
r = subprocess.run(["bash", "-n", str(H / "run_law3_2006.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(oneliner))
