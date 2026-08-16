import base64,gzip,hashlib,json,pathlib
H=pathlib.Path(__file__).parent
ING=(H/"ingest_adm3.py").read_text(encoding="utf-8"); JSN=(H/"adm3_parsed.json").read_text(encoding="utf-8")
def gz(s): return base64.b64encode(gzip.compress(s.encode(),9)).decode()
ib,jb=gz(ING),gz(JSN); ish=hashlib.sha256(ING.encode()).hexdigest(); jsh=hashlib.sha256(JSN.encode()).hexdigest()
na=len(json.loads(JSN)["articles"])
SH=f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
TMP=/tmp/adm3_deploy; mkdir -p "$TMP"
printf '%s' '{ib}' | base64 -d | gunzip > "$TMP/ingest_adm3.py"
printf '%s' '{jb}' | base64 -d | gunzip > "$TMP/adm3_parsed.json"
echo "== SHA256 =="; echo "ingest المتوقع: {ish}"; echo "json المتوقع: {jsh}"
sha256sum "$TMP/ingest_adm3.py" "$TMP/adm3_parsed.json"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_adm3.py',encoding='utf-8').read()); print('py OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/adm3_parsed.json',encoding='utf-8')); assert len(d['articles'])=={na}; print('json OK: مواد',len(d['articles']))"
cd /opt/LegalMind
"$PYA" "$TMP/ingest_adm3.py" "$TMP/adm3_parsed.json" --dry-run
"$PYA" "$TMP/ingest_adm3.py" "$TMP/adm3_parsed.json"
echo "== إعادة الفهرسة (deploy/.env) =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
"$PYA" -c "import psycopg,os; dsn=os.getenv('DATABASE_URL') or 'postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind'; c=psycopg.connect(dsn).cursor(); c.execute(\\"select count(*) from knowledge_objects where id like 'legis-15-1979-%'\\"); print('كائنات 15/1979:', c.fetchone()[0])"
echo '=== تم: القانون 15/1979 (الخدمة المدنية) — 40 مادة + مكرران + ديباجة (فرع إداري) ==='
"""
(H/"run_adm3_full.sh").write_text(SH,encoding="utf-8")
one=f"printf '%s' '{gz(SH)}' | base64 -d | gunzip > run_adm3_full.sh && sha256sum run_adm3_full.sh"
(H/"DEPLOY_adm3.txt").write_text(one+"\n",encoding="utf-8")
print("run_adm3_full.sh SHA256:",hashlib.sha256(SH.encode()).hexdigest())

APP=pathlib.Path("/tmp/app_patched.py").read_text(encoding="utf-8")
app_b64=base64.b64encode(gzip.compress(APP.encode(),9)).decode(); app_sha=hashlib.sha256(APP.encode()).hexdigest()
SH2=f"""#!/usr/bin/env bash
set -euo pipefail
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/adm3_deploy; mkdir -p "$TMP"
printf '%s' '{app_b64}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app.py المتوقع: {app_sha}"; sha256sum "$TMP/app.py"
python3 -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('python OK')"
grep -q "_CIVSERVICE_BUNDLES = " "$TMP/app.py" && echo "حزم 15/1979 موجودة" || {{ echo "خطأ: _admin_core"; exit 1; }}
grep -q "for _name, keys, sfx in _CIVSERVICE_BUNDLES" "$TMP/app.py" && echo "الربط موجود" || {{ echo "خطأ: الربط الإداري"; exit 1; }}
grep -q "def _admin_core" "$TMP/app.py" && echo "نواة 20/1981 سليمة" || {{ echo "خطأ: إعاقة+إداري"; exit 1; }}
grep -q "_DISABILITY_BUNDLES = \\[" "$TMP/app.py" && echo "حزم 8/2010 سليمة" || {{ echo "خطأ: 8/2010"; exit 1; }}
grep -q "_LAB4_BUNDLES = \\[" "$TMP/app.py" && echo "حزم 6/2010 سليمة" || {{ echo "خطأ: 6/2010"; exit 1; }}
cp -f "$APP" "$APP.bak.adm3" && echo "احتُفظ بـ $APP.bak.adm3"
cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin && echo "الخدمة نشطة" || {{ echo "استرجاع"; cp -f "$APP.bak.adm3" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo '=== تم: نواة القضاء الإداري (15/1979) + توجيه الفرع الإداري نشطة ==='
"""
(H/"run_adm3_bundles.sh").write_text(SH2,encoding="utf-8")
one2=f"printf '%s' '{gz(SH2)}' | base64 -d | gunzip > run_adm3_bundles.sh && sha256sum run_adm3_bundles.sh"
(H/"DEPLOY_adm3_bundles.txt").write_text(one2+"\n",encoding="utf-8")
print("app.py SHA256:",app_sha)
print("run_adm3_bundles.sh SHA256:",hashlib.sha256(SH2.encode()).hexdigest())
