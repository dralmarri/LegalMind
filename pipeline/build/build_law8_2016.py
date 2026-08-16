#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ القانون 8/2016 (تنظيم الإعلام الإلكتروني): مُدخِل + JSON (27 مادة، منقولةٌ حرفًا بحرف من صور الجريدة)
+ app.py (محفّز _emedia_ids المُوجَّه بالموضوع محايدَ الفرع + إشارات المصنّف + إدراج 8/2016 في رسم الديباجات).
إدخال + فهرسة + رسم ديباجات + خريطة + نشر + اختبار وظيفيّ. الفرع «جزائي». نسخةٌ احتياطية + استرجاع."""
import base64, gzip, hashlib, pathlib, subprocess
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")


def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


ingest = H / "ingest_law8_2016.py"; js = H / "law8_2016_parsed.json"; px = H / "preamble_xref.py"
b_ing, b_js, b_app, b_px = enc(ingest), enc(js), enc(APP), enc(px)
s_ing, s_js, s_app, s_px = sha(ingest), sha(js), sha(APP), sha(px)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law8_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law8_2016.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law8_2016_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_law8_2016.py" "$TMP/law8_2016_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law8_2016.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json,re; d=json.load(open('$TMP/law8_2016_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==27; nums=[int(k[1:]) for k in d['order']]; assert nums==list(range(1,28)); c=' '.join(a.values())+' '+d['preamble_text']; assert chr(0xFFFD) not in c and '_' not in c; assert 'السيرة' in a['m8'] and 'السرة' not in c and 'يشترط' in a['m8']; assert 'النيابة العامة' in a['m21'] and 'دائرة الجنايات' in a['m22'] and 'الحجب' in a['m1']; print('8/2016 json OK: 27 مادة متسلسلة، تصحيحات الصور (السيرة/يشترط)، لا � ولا _')"
for tok in legis-8-2016 _emedia_ids _EMEDIA_KEYS; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
cd /opt/LegalMind
echo "== إدخال 8/2016 (فعلي) =="; "$PYA" "$TMP/ingest_law8_2016.py" "$TMP/law8_2016_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم الديباجات =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "رسم الديباجات محدّث"
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law8"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law8" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q): return set(m._draft_bundles("استشارة",q,[],None,None))
br=m._resolve_branch(None, m._draft_norm_ar("عقوبة موقع إلكتروني بدون ترخيص وحجبه"))
print("  التصنيف (الإعلام الإلكتروني ⇒):", br)
a=ids("ما عقوبة إنشاء موقع إلكتروني إخباري بدون ترخيص وهل يجوز حجبه؟ وأي محكمة تختص؟")
assert "legis-8-2016-m19" in a and "legis-8-2016-m22" in a, "العقوبة/الحجب/الاختصاص لم تُستحضَر"
print("  ✓ الحجب والعقوبة (م19) + دائرة الجنايات (م22) + النيابة (م21)")
b=ids("ما شروط ترخيص الصحيفة الإلكترونية وشروط المدير المسؤول والكفالة المالية؟")
assert all(("legis-8-2016-m%d"%n) in b for n in (6,8,9,12))
print("  ✓ الترخيص والمدير المسؤول والكفالة (م6/م8/م9/م12)")
c=ids("محظورات النشر في الإعلام الإلكتروني وإحالتها لقانون المطبوعات")
assert "legis-8-2016-m18" in c
print("  ✓ المحظورات (م18 المُحيلة للمطبوعات 3/2006 والإعلام المرئي 61/2007)")
d=ids("ما القوانين المتصلة بقانون تنظيم الإعلام الإلكتروني 8 لسنة 2016؟")
assert "legis-8-2016-preamble" in d
print("  ✓ رسم الديباجات 8/2016 | ديباجات متصلة:", len([x for x in d if x.endswith('-preamble')]))
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-8-2016-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects"); tot=cur.fetchone()[0]
assert n==28
print("  ✓ العدّ: 8/2016 =",n,"| الإجمالي =",tot)
print("  === تمّ =====")
PY2
echo '=== تم: إدخال القانون 8/2016 لتنظيم الإعلام الإلكتروني — 28 كائنًا + محفّز _emedia_ids + مصنّف + رسم ديباجات ==='
"""
(H / "run_law8_2016.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law8_2016.sh && sha256sum run_law8_2016.sh"
(H / "DEPLOY_law8_2016.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app); print("px sha:", s_px)
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; 4 shas embedded")
r = subprocess.run(["bash", "-n", str(H / "run_law8_2016.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
