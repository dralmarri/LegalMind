import base64,gzip,hashlib,json,pathlib
H=pathlib.Path(__file__).parent
ING=(H/"ingest_lab4.py").read_text(encoding="utf-8"); JSN=(H/"lab4_parsed.json").read_text(encoding="utf-8")
def gz(s): return base64.b64encode(gzip.compress(s.encode(),9)).decode()
ib,jb=gz(ING),gz(JSN); ish=hashlib.sha256(ING.encode()).hexdigest(); jsh=hashlib.sha256(JSN.encode()).hexdigest()
na=len(json.loads(JSN)["articles"])
SH=f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
TMP=/tmp/lab4_deploy; mkdir -p "$TMP"
printf '%s' '{ib}' | base64 -d | gunzip > "$TMP/ingest_lab4.py"
printf '%s' '{jb}' | base64 -d | gunzip > "$TMP/lab4_parsed.json"
echo "== SHA256 =="; echo "ingest المتوقع: {ish}"; echo "json المتوقع: {jsh}"
sha256sum "$TMP/ingest_lab4.py" "$TMP/lab4_parsed.json"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_lab4.py',encoding='utf-8').read()); print('py OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/lab4_parsed.json',encoding='utf-8')); assert len(d['articles'])=={na}; print('json OK: مواد',len(d['articles']))"
cd /opt/LegalMind
"$PYA" "$TMP/ingest_lab4.py" "$TMP/lab4_parsed.json" --dry-run
"$PYA" "$TMP/ingest_lab4.py" "$TMP/lab4_parsed.json"
echo "== إعادة الفهرسة (deploy/.env) =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
"$PYA" -c "import psycopg,os; dsn=os.getenv('DATABASE_URL') or 'postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind'; c=psycopg.connect(dsn).cursor(); c.execute(\\"select count(*) from knowledge_objects where id like 'legis-6-2010-%'\\"); print('كائنات 6/2010:', c.fetchone()[0])"
echo '=== تم: القانون 6/2010 (العمل في القطاع الأهلي) — 150 مادة + ديباجة (فرع عمل) ==='
"""
(H/"run_lab4_full.sh").write_text(SH,encoding="utf-8")
ssh=hashlib.sha256(SH.encode()).hexdigest()
one=f"printf '%s' '{gz(SH)}' | base64 -d | gunzip > run_lab4_full.sh && sha256sum run_lab4_full.sh"
(H/"DEPLOY_lab4.txt").write_text(one+"\n",encoding="utf-8")
print("run_lab4_full.sh SHA256:",ssh)
print("one-liner chars:",len(one))
