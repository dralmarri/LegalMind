#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ القانون 35/1985 (جرائم المفرقعات): مُدخِل + JSON (11 مادة + ديباجة) + app.py (محفّز _explosives_ids
كاملًا + جسر الإرهاب + حزمة + إشارات المصنّف + إدراج 35/1985 في رسم الديباجات). إدخال + إعادة فهرسة
+ رسم الديباجات + خريطة + نشر + اختبار وظيفيّ. الفرع «جزائي». نسخةٌ احتياطية + استرجاعٌ تلقائيّ."""
import base64, gzip, hashlib, pathlib, subprocess
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")


def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


ingest = H / "ingest_law35.py"; js = H / "law35_1985_parsed.json"; px = H / "preamble_xref.py"
b_ing, b_js, b_app, b_px = enc(ingest), enc(js), enc(APP), enc(px)
s_ing, s_js, s_app, s_px = sha(ingest), sha(js), sha(APP), sha(px)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law35_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law35.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law35_1985_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_law35.py" "$TMP/law35_1985_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law35.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json; d=json.load(open('$TMP/law35_1985_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==11 and [int(k[1:]) for k in d['order']]==list(range(1,12)); c=' '.join(a.values())+' '+d['preamble_text']; assert chr(0xFFFD) not in c and '_' not in c; assert 'الإعدام' in a['m1'] and 'أموالهم' in a['m2'] and 'ارتكابها' in a['m5'] and 'محكمة أمن الدولة' in a['m9']; print('35/1985 json OK: 11 مادة متسلسلة، تصويبات OCR مطبّقة، لا � ولا _')"
for tok in legis-35-1985 _explosives_ids _EXPLOSIVES_KEYS; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
cd /opt/LegalMind
echo "== إدخال 35/1985 (فعلي) =="; "$PYA" "$TMP/ingest_law35.py" "$TMP/law35_1985_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم الديباجات =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "رسم الديباجات محدّث"
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law35"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law35" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q): return set(m._draft_bundles("استشارة",q,[],None,None))
br=m._resolve_branch(None, m._draft_norm_ar("عقوبة إحراز المفرقعات والاتجار بها بغير ترخيص"))
print("  التصنيف (المفرقعات ⇒):", br); assert "جزاي" in m._draft_norm_ar(br)
a=ids("ما عقوبة إحراز المفرقعات وصنعها والاتجار بها بغير ترخيص واختصاص محكمة أمن الدولة؟")
assert all(("legis-35-1985-m%d"%n) in a for n in range(1,12)), [n for n in range(1,12) if ("legis-35-1985-m%d"%n) not in a]
print("  ✓ جرائم المفرقعات كاملًا (م1-م11)")
b=ids("استعمل مفرقعات بقصد إشاعة الذعر وتفجير مبنى")
assert "legis-35-1985-m1" in b and any(x.startswith("legis-47-2026") for x in b)
print("  ✓ جسر الإرهاب: المفرقعات لإشاعة الذعر ⇒ نواة 47/2026")
d=ids("ما القوانين المتصلة بقانون المفرقعات 35 لسنة 1985؟")
assert "legis-35-1985-preamble" in d
print("  ✓ رسم الديباجات 35/1985")
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-35-1985-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-35-1985-m1'"); t1=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects"); tot=cur.fetchone()[0]
assert n==12 and "الإعدام" in t1
print("  ✓ العدّ: 35/1985 =",n,"| م1 «الإعدام» | الإجمالي =",tot)
print("  === تمّ =====")
PY2
echo '=== تم: إدخال القانون 35/1985 لجرائم المفرقعات — 12 كائنًا + محفّز كامل + جسر الإرهاب + مصنّف + رسم ديباجات ==='
"""
(H / "run_law35.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law35.sh && sha256sum run_law35.sh"
(H / "DEPLOY_law35.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app); print("px sha:", s_px)
print("run_law35.sh sha:", hashlib.sha256(SH.encode()).hexdigest())

# ---- round-trip self-verify ----
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; 4 shas embedded")
r = subprocess.run(["bash", "-n", str(H / "run_law35.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
