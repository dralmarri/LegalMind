#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ المرسوم بقانون 13/2026 (تأمين المصالح العليا للجهات العسكرية): مُدخِل + JSON (34 مادة/6 فصول)
+ app.py (بندلان + مصنّف + رسم ديباجات). إدخال + إعادة فهرسة + رسم الديباجات + خريطة + نشر + اختبار."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")
def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
ing=H/"ingest_law13_2026.py"; js=H/"law13_2026_parsed.json"; px=H/"preamble_xref.py"
b_ing,b_js,b_app,b_px=enc(ing),enc(js),enc(APP),enc(px); s_ing,s_js,s_app,s_px=sha(ing),sha(js),sha(APP),sha(px)
SH=f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/mil13_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law13_2026.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law13_2026_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_law13_2026.py" "$TMP/law13_2026_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law13_2026.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json,re; d=json.load(open('$TMP/law13_2026_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==34 and [int(k[1:]) for k in d['order']]==list(range(1,35)); c=' '.join(a.values())+' '+d['preamble_text']; assert chr(0xFFFD) not in c and '_' not in c and not re.search(r'\)\s*[0-9]\s*\(',c); print('13/2026 json OK: 34 مادة، أقواس مصوّبة، لا � ولا _')"
grep -q "legis-13-2026" "$TMP/app.py" && echo "بندلا الجهات العسكرية موجودان" || {{ echo "خطأ"; exit 1; }}
cd /opt/LegalMind
echo "== إدخال 13/2026 =="; "$PYA" "$TMP/ingest_law13_2026.py" "$TMP/law13_2026_parsed.json"
echo "== إعادة الفهرسة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== رسم الديباجات =="; cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py; "$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "محدّث"
echo "== خريطة =="; "$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "محدّثة" || echo "تنبيه"
echo "== نشر app.py =="; cp -f "$APP" "$APP.bak.mil13"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.mil13" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q,b=None): return set(m._draft_bundles("استشارة",q,[],None,b))
br=m._resolve_branch(None, m._draft_norm_ar("عقوبة إفشاء الأسرار العسكرية والاعتداء على الجهات العسكرية"))
print("  التصنيف (الجهات العسكرية ⇒):", br); assert "جزاي" in m._draft_norm_ar(br)
a=ids("عقوبة إفشاء الأسرار العسكرية والاعتداء على المصالح العليا للجهات العسكرية والمناطق المحمية والنشاط المعادي")
cov=[n for n in (1,10,25,32,34) if ("legis-13-2026-m%d"%n) in a]
print("  تغطية الحزمتين (م1/م10/م25/م32/م34):", cov)
assert all(("legis-13-2026-m%d"%n) in a for n in (1,10,25,32,34)), "الحزم لا تغطّي القانون كاملًا (بم العقوبات)"
d=ids("ما القوانين المتصلة بالمرسوم بقانون رقم 13 لسنة 2026 لتأمين الجهات العسكرية؟","استشارة")
assert "legis-13-2026-preamble" in d and any(x in d for x in ("legis-16-1960-preamble","legis-17-1960-preamble")); print("  ✓ رسم الديباجات 13/2026")
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-13-2026-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects"); tot=cur.fetchone()[0]
assert n==35; print("  ✓ العدّ: 13/2026 =",n,"| الإجمالي =",tot)
print("  === تمّ =====")
PY2
echo '=== تم: إدخال المرسوم بقانون 13/2026 لتأمين المصالح العليا للجهات العسكرية — 35 كائنًا + بندلان + مصنّف + رسم ديباجات ==='
"""
(H/"run_mil13.sh").write_text(SH, encoding="utf-8")
oneliner="printf '%s' '"+base64.b64encode(gzip.compress(SH.encode(),9)).decode()+"' | base64 -d | gunzip > run_mil13.sh && sha256sum run_mil13.sh"
(H/"DEPLOY_mil13.txt").write_text(oneliner+"\n", encoding="utf-8")
print("app sha:", s_app, "| run sha:", hashlib.sha256(SH.encode()).hexdigest())
