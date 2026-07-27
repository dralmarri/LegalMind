#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني نشرَ اللائحة التنفيذية لغسل الأموال (37/2013): مُدخِل + JSON + app.py (بحزمتين + توسيع محفّز
_aml_ids ليشمل مواد اللائحة). إدخال + إعادة فهرسة + خريطة + اختبار وظيفيّ."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ingest = H / "ingest_amlreg.py"; js = H / "amlreg_parsed.json"
b_ing, b_js, b_app = enc(ingest), enc(js), enc(APP)
s_ing, s_js, s_app = sha(ingest), sha(js), sha(APP)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/amlreg_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_amlreg.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/amlreg_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"
sha256sum "$TMP/ingest_amlreg.py" "$TMP/amlreg_parsed.json" "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_amlreg.py',encoding='utf-8').read()); print('ingest OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/amlreg_parsed.json',encoding='utf-8')); assert len(d['articles'])==26, len(d['articles']); assert chr(0xFFFD) not in json.dumps(d,ensure_ascii=False); print('json OK: مواد',len(d['articles']))"
grep -q "regl-106-2013" "$TMP/app.py" && echo "حزم اللائحة موجودة" || {{ echo "خطأ"; exit 1; }}
cd /opt/LegalMind
echo "== إدخال (فعلي) =="; "$PYA" "$TMP/ingest_amlreg.py" "$TMP/amlreg_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.amlreg"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.amlreg" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ (اللائحة + المحفّز) =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
ids=m._draft_bundles("استشارة","ما تدابير العناية الواجبة تجاه الشخص المعرض سياسياً والحد المعتمد للتحقق من هوية العميل في مكافحة غسل الأموال",[],None,"جزائي")
need=[("regl-106-2013-m5","تحديد الهوية"),("regl-106-2013-m6","الحد المعتمد 3 آلاف"),
      ("regl-106-2013-m7","الشخص المعرض سياسياً"),("regl-106-2013-m16","الإخطار عن العمليات المشبوهة"),
      ("legis-106-2013-m2","جريمة غسل الأموال (القانون)")]
for k,lbl in need:
    print("  "+lbl+" ("+k+"):", k in ids)
assert all(k in ids for k,_ in need), "بعض مواد اللائحة/القانون غائبة!"
print("  ✓ اللائحة التنفيذية تُستحضَر مع القانون (م5/م6/م7/م16 + قانون م2)")
PY2
echo '=== تم: إدخال اللائحة التنفيذية لغسل الأموال 37/2013 — 27 كائنًا + حزمتان + توسيع المحفّز ==='
"""
(H / "run_amlreg.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_amlreg.sh && sha256sum run_amlreg.sh"
(H / "DEPLOY_amlreg.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app)
print("run_amlreg.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
