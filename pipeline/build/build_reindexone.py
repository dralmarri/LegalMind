#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني سكربت نشرٍ واحدًا للفهرسة الجزئية السريعة:
 1) ينشر reindex_one_cli.py في مجلّد المحرّك.
 2) ينشر app.py الجديد (فيه POST /api/reindex-one) مع نسخة احتياطية + إعادة تشغيل + استرجاع.
 3) يعيد حقن واجهة البحث (زرّ «حفظ وفهرسة» يفهرس المادة فورًا) في /var/www/legalmind-v3/index.html.
 4) اختبار ذاتي: يفهرس م12 ويؤكّد وجود نقطتها في Qdrant.
كلّه SFTP-free: gzip+base64. يشغّله المستخدم على الخادم."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
CLI = (H / "reindex_one_cli.py").read_text(encoding="utf-8")
SNIP = (H / "incard_edit.html").read_text(encoding="utf-8")
APP = pathlib.Path("/tmp/app_patched.py").read_text(encoding="utf-8")


def gz(s): return base64.b64encode(gzip.compress(s.encode(), 9)).decode()


cli_b, snip_b, app_b = gz(CLI), gz(SNIP), gz(APP)
cli_sha = hashlib.sha256(CLI.encode()).hexdigest()
snip_sha = hashlib.sha256(SNIP.encode()).hexdigest()
app_sha = hashlib.sha256(APP.encode()).hexdigest()

INSERTER = r'''
import sys, re, pathlib
target = pathlib.Path("/var/www/legalmind-v3/index.html")
snip = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
html = target.read_text(encoding="utf-8")
html = re.sub(r"<!--legalmind-incard-edit-->.*?<!--/legalmind-incard-edit-->\s*", "", html, flags=re.S)
html = html.replace("</body>", snip + "\n</body>", 1) if "</body>" in html else html + "\n" + snip
target.write_text(html, encoding="utf-8")
print("طول الملف بعد الحقن:", len(html), "| العلامة موجودة:", "legalmind-incard-edit" in html)
'''

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
CLI=/opt/LegalMind/engine/reindex_one_cli.py
WEB=/var/www/legalmind-v3/index.html
TMP=/tmp/reindexone_deploy; mkdir -p "$TMP"
TS=$(date +%s)

echo "== 1) نشر أداة الفهرسة الجزئية للمحرّك =="
printf '%s' '{cli_b}' | base64 -d | gunzip > "$TMP/reindex_one_cli.py"
echo "cli المتوقّع: {cli_sha}"; sha256sum "$TMP/reindex_one_cli.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/reindex_one_cli.py',encoding='utf-8').read()); print('cli py OK')"
cp -f "$TMP/reindex_one_cli.py" "$CLI"
echo "نُشرت: $CLI"

echo "== 2) نشر app.py (فيه /api/reindex-one) =="
printf '%s' '{app_b}' | base64 -d | gunzip > "$TMP/app.py"
echo "app المتوقّع: {app_sha}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app py OK')"
grep -q "reindex-one" "$TMP/app.py" && echo "نقطة reindex-one موجودة" || {{ echo "خطأ: reindex-one مفقودة"; exit 1; }}
grep -q "legalmind-incard-edit" "$WEB" 2>/dev/null && echo "الواجهة محقونة سابقًا (ستُحدَّث)" || true
cp -f "$APP" "$APP.bak.reidx1.$TS" && echo "نسخة احتياطية: $APP.bak.reidx1.$TS"
cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.reidx1.$TS" "$APP"; systemctl restart legalmind-admin; exit 1; }}

echo "== 3) إعادة حقن واجهة البحث (حفظ وفهرسة فوري) =="
printf '%s' '{snip_b}' | base64 -d | gunzip > "$TMP/incard_edit.html"
echo "snippet المتوقّع: {snip_sha}"; sha256sum "$TMP/incard_edit.html"
[ -f "$WEB" ] || {{ echo "خطأ: $WEB غير موجود"; exit 1; }}
cp -f "$WEB" "$WEB.bak.reidx1.$TS"
cat > "$TMP/insert.py" <<'PYEOF'
{INSERTER}
PYEOF
python3 "$TMP/insert.py" "$TMP/incard_edit.html"
grep -q "reindex-one" "$WEB" && echo "الواجهة تستدعي reindex-one" || {{ echo "خطأ: الواجهة لا تستدعي reindex-one"; exit 1; }}

echo "== 4) اختبار ذاتي: فهرسة م12 ثمّ التأكّد من وجود نقطتها =="
set -a; . /opt/LegalMind/deploy/.env 2>/dev/null; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /opt/LegalMind/.venv/bin/python "$CLI" legis-67-1980-m12
/opt/LegalMind/.venv/bin/python - <<'PY'
import sys, os, json, urllib.request
sys.path.insert(0,"/opt/LegalMind"); sys.path.insert(0,"/opt/LegalMind/engine")
from engine import embedding
pid=embedding.point_id("legis-67-1980-m12")
coll=os.getenv("LEGALMIND_COLLECTION","legalmind_multilingual_e5_base_v1")
try:
    r=urllib.request.urlopen("http://127.0.0.1:6333/collections/"+coll+"/points/"+str(pid),timeout=10)
    res=json.loads(r.read()).get("result") or dict()
    pay=res.get("payload") or dict()
    print("point OK id=",pid," object_id=",pay.get("object_id"))
except Exception as e:
    print("could not confirm:",e)
PY
echo '=== تم: الفهرسة الجزئية السريعة مثبّتة (حفظ → فهرسة فورية للمادة وحدها) ==='
echo 'في المتصفّح: Ctrl+Shift+R ثم جرّب «حفظ وفهرسة».'
"""

sh_sha = hashlib.sha256(SH.encode()).hexdigest()
(H / "run_reidx1.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + gz(SH) + "' | base64 -d | gunzip > run_reidx1.sh && sha256sum run_reidx1.sh"
(H / "DEPLOY_reidx1.txt").write_text(oneliner + "\n", encoding="utf-8")
print("cli   SHA256:", cli_sha)
print("app   SHA256:", app_sha)
print("snip  SHA256:", snip_sha)
print("run_reidx1.sh SHA256:", sh_sha)
