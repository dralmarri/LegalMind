#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ المرسوم بقانون 51/2026 (تخصيص دوائر جزائية لجرائم أمن الدولة والإرهاب): مُدخِل + JSON (7 مواد
+ ديباجة) + app.py (محفّز _statesec_court_ids كاملًا + جسر 47/2026 + حزمة + إشارات المصنّف + إدراج
51/2026 في رسم الديباجات). إدخال + إعادة فهرسة + رسم الديباجات + خريطة + نشر + اختبار وظيفيّ. الفرع «جزائي»."""
import base64, gzip, hashlib, pathlib, subprocess
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")


def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


ingest = H / "ingest_law51.py"; js = H / "law51_2026_parsed.json"; px = H / "preamble_xref.py"
b_ing, b_js, b_app, b_px = enc(ingest), enc(js), enc(APP), enc(px)
s_ing, s_js, s_app, s_px = sha(ingest), sha(js), sha(APP), sha(px)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law51_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law51.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law51_2026_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_law51.py" "$TMP/law51_2026_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law51.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json; d=json.load(open('$TMP/law51_2026_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==7 and [int(k[1:]) for k in d['order']]==list(range(1,8)); c=' '.join(a.values())+' '+d['preamble_text']; assert chr(0xFFFD) not in c and '_' not in c; import re; assert not re.findall(r'\\)\\s*[0-9]+\\s*\\(', c); assert 'محكمة الكلية' in a['m1'] and 'نهائياً' in a['m2'] and 'يُلغى' in a['m6']; print('51/2026 json OK: 7 مواد متسلسلة، أقواس مصوّبة، حركات مجموعة، لا � ولا _')"
for tok in legis-51-2026 _statesec_court_ids _STATESEC_COURT_KEYS; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
cd /opt/LegalMind
echo "== إدخال 51/2026 (فعلي) =="; "$PYA" "$TMP/ingest_law51.py" "$TMP/law51_2026_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم الديباجات =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "رسم الديباجات محدّث"
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law51"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law51" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q): return set(m._draft_bundles("استشارة",q,[],None,None))
br=m._resolve_branch(None, m._draft_norm_ar("أي محكمة تنظر جرائم أمن الدولة والإرهاب"))
print("  التصنيف (الدوائر الجزائية ⇒):", br); assert "جزاي" in m._draft_norm_ar(br)
a=ids("أي محكمة تختص بنظر جرائم أمن الدولة والأعمال الإرهابية وكيف يُستأنف حكمها؟")
assert all(("legis-51-2026-m%d"%n) in a for n in range(1,8)), [n for n in range(1,8) if ("legis-51-2026-m%d"%n) not in a]
print("  ✓ تخصيص الدوائر الجزائية كاملًا (م1-م7)")
assert any(x.startswith("legis-47-2026") for x in a)
print("  ✓ جسر 47/2026 (تعريف/نطاق/تشديد الإرهاب) مع سؤال المحكمة")
d=ids("ما القوانين المتصلة بالمرسوم بقانون 51 لسنة 2026؟")
assert "legis-51-2026-preamble" in d
print("  ✓ رسم الديباجات 51/2026")
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-51-2026-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-51-2026-m2'"); t2=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects"); tot=cur.fetchone()[0]
assert n==8 and "نهائي" in t2
print("  ✓ العدّ: 51/2026 =",n,"| م2 «نهائياً» | الإجمالي =",tot)
print("  === تمّ =====")
PY2
echo '=== تم: إدخال المرسوم بقانون 51/2026 لتخصيص الدوائر الجزائية — 8 كائنات + محفّز كامل + جسر 47/2026 + مصنّف + رسم ديباجات ==='
"""
(H / "run_law51.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law51.sh && sha256sum run_law51.sh"
(H / "DEPLOY_law51.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app); print("px sha:", s_px)
print("run_law51.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; 4 shas embedded")
r = subprocess.run(["bash", "-n", str(H / "run_law51.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
