#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ المرسوم بقانون 19/2012 (حماية الوحدة الوطنية): مُدخِل + JSON (5 مواد) + app.py (حزمة + مصنّف
+ إدراج 19/2012 في رسم الديباجات). إدخال + إعادة فهرسة + رسم الديباجات + خريطة + نشر + اختبار وظيفيّ."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
ing = H/"ingest_natunity.py"; js = H/"law19_2012_parsed.json"; px = H/"preamble_xref.py"
b_ing,b_js,b_app,b_px = enc(ing),enc(js),enc(APP),enc(px)
s_ing,s_js,s_app,s_px = sha(ing),sha(js),sha(APP),sha(px)
SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/natunity_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_natunity.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law19_2012_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_natunity.py" "$TMP/law19_2012_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_natunity.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json; d=json.load(open('$TMP/law19_2012_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==5 and [int(k[1:]) for k in d['order']]==list(range(1,6)); c=' '.join(a.values())+' '+d['preamble_text']; assert chr(0xFFFD) not in c and 'خارج إقليم دولة الكويت' in a['m1']; print('19/2012 json OK: 5 مواد، م1 كامل')"
grep -q "legis-19-2012" "$TMP/app.py" && echo "حزمة الوحدة الوطنية موجودة" || {{ echo "خطأ"; exit 1; }}
cd /opt/LegalMind
echo "== إدخال 19/2012 =="; "$PYA" "$TMP/ingest_natunity.py" "$TMP/law19_2012_parsed.json"
echo "== إعادة الفهرسة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== رسم الديباجات =="; cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py; "$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "محدّث"
echo "== خريطة =="; "$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "محدّثة" || echo "تنبيه"
echo "== نشر app.py =="; cp -f "$APP" "$APP.bak.natunity"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.natunity" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q,b=None): return set(m._draft_bundles("استشارة",q,[],None,b))
br=m._resolve_branch(None, m._draft_norm_ar("جريمة إثارة الفتن الطائفية وخطاب الكراهية"))
print("  التصنيف (الوحدة الوطنية ⇒):", br); assert "جزاي" in m._draft_norm_ar(br)
a=ids("عقوبة إثارة الفتنة الطائفية والتحريض على كراهية فئة من المجتمع ونشر أفكار عنصرية")
assert all(("legis-19-2012-m%d"%n) in a for n in (1,2,3)); print("  ✓ حزمة الوحدة الوطنية (م1/م2/م3)")
d=ids("ما القوانين المتصلة بالقانون 19 لسنة 2012 لحماية الوحدة الوطنية؟","استشارة")
assert "legis-19-2012-preamble" in d and any(x in d for x in ("legis-16-1960-preamble","legis-17-1960-preamble")); print("  ✓ رسم الديباجات 19/2012")
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-19-2012-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects"); tot=cur.fetchone()[0]
assert n==6; print("  ✓ العدّ: 19/2012 =",n,"| الإجمالي =",tot)
print("  === تمّ =====")
PY2
echo '=== تم: إدخال المرسوم بقانون 19/2012 لحماية الوحدة الوطنية — 6 كائنات + حزمة + مصنّف + رسم ديباجات ==='
"""
(H/"run_natunity.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + "' | base64 -d | gunzip > run_natunity.sh && sha256sum run_natunity.sh"
(H/"DEPLOY_natunity.txt").write_text(oneliner+"\n", encoding="utf-8")
print("app sha:", s_app, "| run sha:", hashlib.sha256(SH.encode()).hexdigest())
