import base64,gzip,hashlib,json,pathlib
H=pathlib.Path(__file__).parent
ING=(H/"ingest_adm11.py").read_text(encoding="utf-8"); JSN=(H/"adm11_parsed.json").read_text(encoding="utf-8")
def gz(s): return base64.b64encode(gzip.compress(s.encode(),9)).decode()
ib,jb=gz(ING),gz(JSN); ish=hashlib.sha256(ING.encode()).hexdigest(); jsh=hashlib.sha256(JSN.encode()).hexdigest()
na=len(json.loads(JSN)["articles"])
SH=f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
TMP=/tmp/adm11_deploy; mkdir -p "$TMP"
printf '%s' '{ib}' | base64 -d | gunzip > "$TMP/ingest_adm11.py"
printf '%s' '{jb}' | base64 -d | gunzip > "$TMP/adm11_parsed.json"
echo "== SHA256 =="; echo "ingest المتوقع: {ish}"; echo "json المتوقع: {jsh}"
sha256sum "$TMP/ingest_adm11.py" "$TMP/adm11_parsed.json"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_adm11.py',encoding='utf-8').read()); print('py OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/adm11_parsed.json',encoding='utf-8')); assert len(d['articles'])=={na}; print('json OK: مواد',len(d['articles']))"
cd /opt/LegalMind
"$PYA" "$TMP/ingest_adm11.py" "$TMP/adm11_parsed.json" --dry-run
"$PYA" "$TMP/ingest_adm11.py" "$TMP/adm11_parsed.json"
echo "== إعادة الفهرسة (deploy/.env) =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
"$PYA" -c "import psycopg,os; dsn=os.getenv('DATABASE_URL') or 'postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind'; c=psycopg.connect(dsn).cursor(); c.execute(\\"select count(*) from knowledge_objects where id like 'legis-42-1964-%'\\"); print('كائنات 42/1964:', c.fetchone()[0])"
echo '=== تم: القانون 42/1964 بشأن تنظيم مهنة المحاماة — مادتا إصدار + 44 مادة (منها 4 مكرر و4 ملغاة) + ديباجة (فرع إداري) ==='
"""
(H/"run_adm11_full.sh").write_text(SH,encoding="utf-8")
one=f"printf '%s' '{gz(SH)}' | base64 -d | gunzip > run_adm11_full.sh && sha256sum run_adm11_full.sh"
(H/"DEPLOY_adm11.txt").write_text(one+"\n",encoding="utf-8")
print("run_adm11_full.sh SHA256:",hashlib.sha256(SH.encode()).hexdigest())

APP=pathlib.Path("/tmp/app_patched.py").read_text(encoding="utf-8")
app_b64=base64.b64encode(gzip.compress(APP.encode(),9)).decode(); app_sha=hashlib.sha256(APP.encode()).hexdigest()
SH2=f"""#!/usr/bin/env bash
set -euo pipefail
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/adm11_deploy; mkdir -p "$TMP"
printf '%s' '{app_b64}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app.py المتوقع: {app_sha}"; sha256sum "$TMP/app.py"
python3 -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('python OK')"
grep -q "legis-42-1964-m46" "$TMP/app.py" && echo "حزم المحاماة 42/1964 موجودة" || {{ echo "خطأ: 42/1964"; exit 1; }}
grep -q "legis-10-2020-t2025" "$TMP/app.py" && echo "حزم التوثيق 10/2020 سليمة" || {{ echo "خطأ: 10/2020"; exit 1; }}
grep -q "legis-23-1990-m74" "$TMP/app.py" && echo "حزم تنظيم القضاء سليمة" || {{ echo "خطأ: 23/1990"; exit 1; }}
grep -q "def _admin_core" "$TMP/app.py" && echo "نواة 20/1981 سليمة" || {{ echo "خطأ: 20/1981"; exit 1; }}
grep -q "_AR_DIAC" "$TMP/app.py" && echo "تطبيع إزالة التشكيل مفعّل" || {{ echo "خطأ: _AR_DIAC"; exit 1; }}
cp -f "$APP" "$APP.bak.adm11" && echo "احتُفظ بـ $APP.bak.adm11"
cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin && echo "الخدمة نشطة" || {{ echo "استرجاع"; cp -f "$APP.bak.adm11" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo '=== تم: حزم قانون تنظيم مهنة المحاماة 42/1964 نشطة ==='
"""
(H/"run_adm11_bundles.sh").write_text(SH2,encoding="utf-8")
one2=f"printf '%s' '{gz(SH2)}' | base64 -d | gunzip > run_adm11_bundles.sh && sha256sum run_adm11_bundles.sh"
(H/"DEPLOY_adm11_bundles.txt").write_text(one2+"\n",encoding="utf-8")
print("app.py SHA256:",app_sha)
print("run_adm11_bundles.sh SHA256:",hashlib.sha256(SH2.encode()).hexdigest())
