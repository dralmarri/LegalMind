#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ قانون بلدية الكويت 33/2016: مُدخِل + JSON (53 مادة + ديباجة، منقولةٌ برمجيًّا من DOCX نظيف) + app.py
(محفّز _municipality_ids المُوجَّه بالباب محايدَ الفرع + تعميمُ الجسر المدنيّ على المرور 67/1976 [الفعل الضار
م227+ لأسئلة تعويض الحوادث] + إشارات المصنّف + إدراج 33/2016 في رسم الديباجات). إدخال + فهرسة + رسم ديباجات
+ خريطة + نشر + اختبار وظيفيّ. الفرع «إداري». نسخةٌ احتياطية + استرجاع."""
import base64, gzip, hashlib, pathlib, subprocess
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")


def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


ingest = H / "ingest_law33_2016.py"; js = H / "law33_2016_parsed.json"; px = H / "preamble_xref.py"
b_ing, b_js, b_app, b_px = enc(ingest), enc(js), enc(APP), enc(px)
s_ing, s_js, s_app, s_px = sha(ingest), sha(js), sha(APP), sha(px)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law33_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law33_2016.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law33_2016_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_law33_2016.py" "$TMP/law33_2016_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law33_2016.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json,re; d=json.load(open('$TMP/law33_2016_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==53; nums=[int(re.match(r'm(\\\\d+)',k).group(1)) for k in d['order']]; assert nums==list(range(1,54)); c=' '.join(a.values())+' '+d['preamble_text']; assert chr(0xFFFD) not in c and '_' not in c and not re.findall(r'\\\\)\\\\s*[0-9]+\\\\s*\\\\(', c); assert 'المجلس البلدي' in a['m1'] and 'هيئة عامة مستقلة' in a['m2']; print('33/2016 json OK: 53 مادة متسلسلة، لا � ولا _ ولا أقواس معكوسة')"
for tok in legis-33-2016 _municipality_ids _MUNI_KEYS; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
grep -q "جسرُ الشريعة العامة: التعويضُ عن حوادث المركبات" "$TMP/app.py" && echo "موجود: تعميم الجسر المدني على المرور" || {{ echo "خطأ: جسر المرور المدني"; exit 1; }}
cd /opt/LegalMind
echo "== إدخال 33/2016 (فعلي) =="; "$PYA" "$TMP/ingest_law33_2016.py" "$TMP/law33_2016_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم الديباجات =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "رسم الديباجات محدّث"
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law33"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law33" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q): return set(m._draft_bundles("استشارة",q,[],None,None))
a=ids("ما عقوبة مخالفة اشتراطات البناء البلدية وإزالتها على نفقة المخالف والتظلّم منها؟")
assert any(("legis-33-2016-m%d"%n) in a for n in range(38,45)), "مخالفات البلدية لم تُستحضَر"
print("  ✓ المخالفات والعقوبات البلدية (الباب الثالث م38-م44)")
b=ids("ما اختصاصات المجلس البلدي وشروط عضويته؟")
assert any(("legis-33-2016-m%d"%n) in b for n in range(4,31))
print("  ✓ المجلس البلدي واختصاصاته (الباب الأول م4-م30)")
# تعميم الجسر المدني على المرور:
c=ids("سيارة صدمتني وأصابتني، ما التعويض عن الحادث والمسؤولية المدنية؟")
assert any(("legis-67-1980-m%d"%n) in c for n in range(227,235)), "جسر المرور المدني لم يعمل"
assert "legis-67-1976-m6" in c
print("  ✓ تعميم الجسر المدني على المرور: الفعل الضار (67/1980 م227+) مع تأمين المركبة (م6)")
d=ids("ما القوانين المتصلة بقانون بلدية الكويت 33 لسنة 2016؟")
assert "legis-33-2016-preamble" in d
print("  ✓ رسم الديباجات 33/2016 | ديباجات متصلة:", len([x for x in d if x.endswith('-preamble')]))
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-33-2016-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects"); tot=cur.fetchone()[0]
assert n==54
print("  ✓ العدّ: 33/2016 =",n,"| الإجمالي =",tot)
print("  === تمّ =====")
PY2
echo '=== تم: إدخال قانون بلدية الكويت 33/2016 — 54 كائنًا + محفّز _municipality_ids + تعميم الجسر المدني على المرور + مصنّف + رسم ديباجات ==='
"""
(H / "run_law33_2016.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law33_2016.sh && sha256sum run_law33_2016.sh"
(H / "DEPLOY_law33_2016.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app); print("px sha:", s_px)
print("run_law33_2016.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; 4 shas embedded")
r = subprocess.run(["bash", "-n", str(H / "run_law33_2016.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
