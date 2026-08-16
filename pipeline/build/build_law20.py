#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ القانون 20/2019 (النظام الموحد الخليجي لمكافحة الغش التجاري): مُدخِل + JSON (18 مادة + 4 إصدار)
+ app.py (حزمتان جزائيتان + إشارات المصنّف + إدراج 20/2019 في رسم الديباجات) + إعادة بناء رسم الديباجات.
إدخال + إعادة فهرسة + خريطة + نشر app + اختبار وظيفيّ. النصّ مُتحقَّقٌ من صور الجريدة الرسمية."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ingest = H / "ingest_law20.py"; js = H / "law20_2019_parsed.json"; px = H / "preamble_xref.py"
b_ing, b_js, b_app, b_px = enc(ingest), enc(js), enc(APP), enc(px)
s_ing, s_js, s_app, s_px = sha(ingest), sha(js), sha(APP), sha(px)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law20_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law20.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law20_2019_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_law20.py" "$TMP/law20_2019_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law20.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json; d=json.load(open('$TMP/law20_2019_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==18 and [int(k[1:]) for k in d['order']]==list(range(1,19)); assert len(d['issuance'])==4; c=' '.join(list(a.values())+list(d['issuance'].values()))+' '+d['preamble_text']; assert chr(0xFFFD) not in c and '_' not in c; import re; assert all(v.count(chr(40))==v.count(chr(41)) for v in a.values()); print('json OK: 18 مادة + 4 إصدار، أقواس متوازنة، لا � ولا _')"
grep -q "legis-20-2019" "$TMP/app.py" && echo "حزم الغش التجاري موجودة" || {{ echo "خطأ"; exit 1; }}
cd /opt/LegalMind
echo "== إدخال 20/2019 (فعلي) =="; "$PYA" "$TMP/ingest_law20.py" "$TMP/law20_2019_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم علاقات الديباجات =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "رسم الديباجات محدّث"
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law20"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law20" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q,b=None): return set(m._draft_bundles("استشارة",q,[],None,b))
# التصنيف: سؤال غش تجاري بلا فرعٍ صريح ⇒ جزائي
br=m._resolve_branch(None, m._draft_norm_ar("ما عقوبة بيع بضائع مغشوشة والغش التجاري؟"))
print("  التصنيف (غش تجاري ⇒):", br); assert "جزاي" in m._draft_norm_ar(br) or "جزائ" in br
# الحزم: العقوبات + الحظر
a=ids("عقوبة الغش التجاري ومصادرة البضائع المغشوشة والعود، وحظر بيع البضائع الفاسدة")
need=["legis-20-2019-m2","legis-20-2019-m11","legis-20-2019-m12","legis-20-2019-m15"]
print("  حزم الغش (م2/م11/م12/م15):", all(k in a for k in need)); assert all(k in a for k in need)
# رسم الديباجات: 20/2019 يستحضر قوانينه المتّصلة المُدخَلة
d=ids("ما القوانين المتصلة بالقانون رقم 20 لسنة 2019 لمكافحة الغش التجاري؟","استشارة")
rel=sorted(x for x in d if x.endswith("-preamble"))
print("  ديباجات متّصلة:", rel[:8])
assert "legis-20-2019-preamble" in d and any(x in d for x in ("legis-16-1960-preamble","legis-17-1960-preamble")), "رسم ديباجات 20 لم يعمل"
# سلامة النصّ: م11 أقواس صحيحة، عدّ الكائنات 23
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-20-2019-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-20-2019-m11'"); t11=cur.fetchone()[0]
ok=("(السجن)" in t11 and "(5000)" in t11 and t11.count("(")==t11.count(")"))
print("  كائنات 20/2019:", n, "| م11 أقواس سليمة:", ok)
assert n==23 and ok
print("  ✓ 20/2019: التصنيف + الحزم + رسم الديباجات + سلامة النصّ — تمّ")
PY2
echo '=== تم: إدخال القانون 20/2019 لمكافحة الغش التجاري — 23 كائنًا + حزمتان + إشارات مصنّف + رسم ديباجات ==='
"""
(H / "run_law20.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law20.sh && sha256sum run_law20.sh"
(H / "DEPLOY_law20.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app); print("px sha:", s_px)
print("run_law20.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
