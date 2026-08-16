#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ قانون المرور 67/1976: مُدخِل + JSON (59 مادة + ديباجة، منقولةٌ من صور الجريدة) + app.py (محفّز
_traffic_ids المُوجَّه بالباب + إشارات المصنّف + إدراج 67/1976 في رسم الديباجات). إدخال + إعادة فهرسة
+ رسم الديباجات + خريطة + نشر + اختبار وظيفيّ. الفرع «جزائي». نسخةٌ احتياطية + استرجاعٌ تلقائيّ."""
import base64, gzip, hashlib, pathlib, subprocess
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")


def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


ingest = H / "ingest_law67.py"; js = H / "law67_1976_parsed.json"; px = H / "preamble_xref.py"
b_ing, b_js, b_app, b_px = enc(ingest), enc(js), enc(APP), enc(px)
s_ing, s_js, s_app, s_px = sha(ingest), sha(js), sha(APP), sha(px)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law67_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law67.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law67_1976_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_law67.py" "$TMP/law67_1976_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law67.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json,re; d=json.load(open('$TMP/law67_1976_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==59; nums=[int(re.match(r'm(\\\\d+)',k).group(1)) for k in d['order']]; assert set(range(1,51)).issubset(set(nums)); c=' '.join(a.values())+' '+d['preamble_text']; assert chr(0xFFFD) not in c and '_' not in c; assert '[[' not in c; assert 'المادة (34)' in a['m41'] and 'المادة (43)' not in a['m41'] and '(24، 42، 42 مكرر، 43)' in a['m41']; assert 'تحت تأثير' in a['m38'] and 'خدمة المجتمع' in a['m39-mukarrar']; print('67/1976 json OK: 59 مادة (م1-م50 + 9 مكرر)، م41 مصوّبة، لا � ولا _ ولا التباس')"
for tok in legis-67-1976 _traffic_ids _TRAFFIC_KEYS; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
cd /opt/LegalMind
echo "== إدخال 67/1976 (فعلي) =="; "$PYA" "$TMP/ingest_law67.py" "$TMP/law67_1976_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم الديباجات =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "رسم الديباجات محدّث"
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law67"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law67" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q): return set(m._draft_bundles("استشارة",q,[],None,None))
br=m._resolve_branch(None, m._draft_norm_ar("ما عقوبة القيادة تحت تأثير الخمر في قانون المرور"))
print("  التصنيف (المرور ⇒):", br); assert "جزاي" in m._draft_norm_ar(br)
a=ids("ما عقوبة القيادة تحت تأثير المسكر أو المخدر في قانون المرور وهل تُسحب الرخصة؟")
assert "legis-67-1976-m38" in a and "legis-67-1976-m44" in a, "عقوبة القيادة تحت التأثير لم تُستحضَر"
print("  ✓ القيادة تحت التأثير (م38 + م44 القبض)")
b=ids("كيف أرخّص سيارة وما هو التأمين الإلزامي من المسئولية المدنية؟")
assert all(("legis-67-1976-m%d"%n) in b for n in (4,5,6)), "الترخيص/التأمين لم يُستحضَر"
print("  ✓ الترخيص والتأمين (م4/م5/م6)")
c=ids("ما شروط قبول الصلح في مخالفات المرور ونظام نقاط المخالفات؟")
assert "legis-67-1976-m41" in c and "legis-67-1976-m42-mukarrar" in c
print("  ✓ الصلح ونظام النقاط (م41 + م42مكرر)")
d=ids("ما القوانين المتصلة بقانون المرور 67 لسنة 1976؟")
assert "legis-67-1976-preamble" in d
print("  ✓ رسم الديباجات 67/1976")
# إصلاحٌ راكب: توسيعُ مفاتيح 51/2026 — الاستعلام الذي فشل في نشرة 51/2026 صار يُطلق الحزمة
e=ids("أي محكمة تختص بنظر جرائم أمن الدولة والأعمال الإرهابية وكيف يُستأنف حكمها؟")
assert all(("legis-51-2026-m%d"%n) in e for n in range(1,8)), "إصلاح 51/2026 لم يعمل!"
print("  ✓ إصلاح 51/2026: «أي محكمة تختص بنظر جرائم أمن الدولة» يُطلق الدوائر المتخصصة (م1-م7)")
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-67-1976-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-67-1976-%%-mukarrar'"); nk=cur.fetchone()[0]
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-67-1976-m41'"); t41=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects"); tot=cur.fetchone()[0]
assert n==60 and nk==9 and "(24، 42، 42 مكرر، 43)" in t41
print("  ✓ العدّ: 67/1976 =",n,"(9 مكرر) | م41 مرجعها مصوّب | الإجمالي =",tot)
print("  === تمّ =====")
PY2
echo '=== تم: إدخال قانون المرور 67/1976 — 60 كائنًا (59 مادة) + محفّز _traffic_ids المُوجَّه بالباب + مصنّف + رسم ديباجات ==='
"""
(H / "run_law67.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law67.sh && sha256sum run_law67.sh"
(H / "DEPLOY_law67.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app); print("px sha:", s_px)
print("run_law67.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; 4 shas embedded")
r = subprocess.run(["bash", "-n", str(H / "run_law67.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
