#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني نشرَ القانون 25/1996 (الكشف عن العمولات في عقود الدولة): مُدخِل + JSON نظيف + app.py
(بحزمة استرجاع جديدة). خطوات الخادم: تحقّق البصمات/الصياغة/عدد المواد → إدخال (تجريبي ثمّ فعلي)
→ إعادة فهرسة كاملة (من الطرفية، بلا مهلة nginx) → تحديث خريطة الإحالات → نشر app.py + إعادة تشغيل
+ اختبار وظيفيّ يتأكّد من تفعيل حزمة 25/1996 في الفرع الجزائي."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ingest = H / "ingest_law25.py"
js = H / "law25_parsed.json"

b_ing, b_js, b_app = enc(ingest), enc(js), enc(APP)
s_ing, s_js, s_app = sha(ingest), sha(js), sha(APP)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law25_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law25.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law25_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="
echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"
sha256sum "$TMP/ingest_law25.py" "$TMP/law25_parsed.json" "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_law25.py',encoding='utf-8').read()); print('ingest OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/law25_parsed.json',encoding='utf-8')); assert len(d['articles'])==7, len(d['articles']); print('json OK: مواد',len(d['articles']))"
grep -q "legis-25-1996" "$TMP/app.py" && echo "حزمة 25/1996 موجودة في app.py" || {{ echo "خطأ: الحزمة مفقودة"; exit 1; }}
cd /opt/LegalMind
echo "== إدخال (تجريبي) =="
"$PYA" "$TMP/ingest_law25.py" "$TMP/law25_parsed.json" --dry-run
echo "== إدخال (فعلي) =="
"$PYA" "$TMP/ingest_law25.py" "$TMP/law25_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null && echo "خريطة محدّثة" || echo "تنبيه: تعذّر تحديث الخريطة"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law25"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law25" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ (تفعيل حزمة 25/1996 في الفرع الجزائي) =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
facts="شركة تعاقدت مع وزارة على عقد توريد ودفعت عمولة لوسيط ولم تكشف عنها في العقد"
ids=m._draft_bundles("استشارة",facts,[],None,"جزائي")
n=len([i for i in ids if i.startswith("legis-25-1996")])
print("  مواد 25/1996 المستحضَرة:",n,"->",[i for i in ids if i.startswith("legis-25-1996")])
assert n>=7, "الحزمة لم تُفعَّل!"
print("  ✓ الحزمة فعّالة")
PY2
echo '=== تم: إدخال القانون 25/1996 (الكشف عن العمولات في عقود الدولة) + حزمة استرجاع جزائية ==='
"""
(H / "run_law25.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law25.sh && sha256sum run_law25.sh"
(H / "DEPLOY_law25.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing)
print("json   sha:", s_js)
print("app    sha:", s_app)
print("run_law25.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
