#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ قانون حماية البيئة 42/2014: مُدخِل + JSON (182 مادة + ديباجة، منقولةٌ برمجيًّا من DOCX نظيف) + app.py
(محفّز _environment_ids المُوجَّه بالباب محايدَ الفرع + إشارات المصنّف + إدراج 42/2014 في رسم الديباجات).
إدخال + إعادة فهرسة + رسم الديباجات + خريطة + نشر + اختبار وظيفيّ. الفرع «إداري». نسخةٌ احتياطية + استرجاع."""
import base64, gzip, hashlib, pathlib, subprocess
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")


def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


ingest = H / "ingest_law42.py"; js = H / "law42_2014_parsed.json"; px = H / "preamble_xref.py"
b_ing, b_js, b_app, b_px = enc(ingest), enc(js), enc(APP), enc(px)
s_ing, s_js, s_app, s_px = sha(ingest), sha(js), sha(APP), sha(px)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law42_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law42.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law42_2014_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_law42.py" "$TMP/law42_2014_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law42.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json,re; d=json.load(open('$TMP/law42_2014_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==182 and 'm143-mukarrar' in a; nums={{int(re.match(r'm(\\\\d+)',k).group(1)) for k in d['order']}}; assert set(range(1,182)).issubset(nums); c=' '.join(a.values())+' '+d['preamble_text']; assert chr(0xFFFD) not in c and '_' not in c; import re as r2; assert not r2.findall(r'\\\\)\\\\s*[0-9]+\\\\s*\\\\(', c); assert 'يعاقب' in a['m143'] and 'الهيئة العامة للبيئة' in a['m1']; print('42/2014 json OK: 182 مادة (+م143مكرر)، متسلسلة، لا � ولا _ ولا أقواس معكوسة')"
for tok in legis-42-2014 _environment_ids _ENV_KEYS; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
cd /opt/LegalMind
echo "== إدخال 42/2014 (فعلي) =="; "$PYA" "$TMP/ingest_law42.py" "$TMP/law42_2014_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم الديباجات =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "رسم الديباجات محدّث"
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law42"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law42" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q): return set(m._draft_bundles("استشارة",q,[],None,None))
# محايدُ الفرع: أسئلة البيئة تتوزّع إداري/جزائي/مدني — والمحفّز يعمل في الغلاف
a=ids("ما عقوبة إلقاء النفايات الخطرة وتلويث البيئة البرية؟")
assert any(("legis-42-2014-m%d"%n) in a for n in range(128,158)), "عقوبات البيئة لم تُستحضَر"
assert "legis-42-2014-m1" in a
print("  ✓ العقوبات البيئية (الباب السابع م128+) تُستحضَر")
b=ids("ما التعويض عن الأضرار البيئية والمسؤولية المدنية عن التلوث؟")
assert any(("legis-42-2014-m%d"%n) in b for n in range(158,168)), "المسؤولية المدنية البيئية لم تُستحضَر"
print("  ✓ المسؤولية المدنية والتعويض البيئي (الباب الثامن م158-م167)")
c=ids("ما اختصاصات الهيئة العامة للبيئة والمجلس الأعلى للبيئة؟")
assert all(("legis-42-2014-m%d"%n) in c for n in (4,6)), "إدارة شؤون البيئة لم تُستحضَر"
print("  ✓ إدارة شؤون البيئة (الهيئة/المجلس م4-م15)")
d=ids("ما القوانين المتصلة بقانون حماية البيئة 42 لسنة 2014؟")
assert "legis-42-2014-preamble" in d
rel=sorted(x for x in d if x.endswith("-preamble"))
print("  ✓ رسم الديباجات 42/2014 | ديباجات متصلة:", len(rel))
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-42-2014-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-42-2014-%%-mukarrar'"); nk=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects"); tot=cur.fetchone()[0]
assert n==183 and nk==1
print("  ✓ العدّ: 42/2014 =",n,"(+م143مكرر) | الإجمالي =",tot)
print("  === تمّ =====")
PY2
echo '=== تم: إدخال قانون حماية البيئة 42/2014 — 183 كائنًا (182 مادة) + محفّز _environment_ids المُوجَّه بالباب محايدَ الفرع + مصنّف + رسم ديباجات ==='
"""
(H / "run_law42.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law42.sh && sha256sum run_law42.sh"
(H / "DEPLOY_law42.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app); print("px sha:", s_px)
print("run_law42.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; 4 shas embedded")
r = subprocess.run(["bash", "-n", str(H / "run_law42.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
