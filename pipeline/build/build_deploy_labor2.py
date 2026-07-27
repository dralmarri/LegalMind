import base64,gzip,hashlib,json,pathlib
H=pathlib.Path(__file__).parent
ING=(H/"ingest_labor2.py").read_text(encoding="utf-8"); JSN=(H/"labor2_parsed.json").read_text(encoding="utf-8")
def gz(s): return base64.b64encode(gzip.compress(s.encode(),9)).decode()
ib,jb=gz(ING),gz(JSN); ish=hashlib.sha256(ING.encode()).hexdigest(); jsh=hashlib.sha256(JSN.encode()).hexdigest()
na=len(json.loads(JSN)["articles"])
SH=f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
TMP=/tmp/labor2_deploy; mkdir -p "$TMP"
printf '%s' '{ib}' | base64 -d | gunzip > "$TMP/ingest_labor2.py"
printf '%s' '{jb}' | base64 -d | gunzip > "$TMP/labor2_parsed.json"
echo "== SHA256 =="; echo "ingest المتوقع: {ish}"; echo "json المتوقع: {jsh}"
sha256sum "$TMP/ingest_labor2.py" "$TMP/labor2_parsed.json"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_labor2.py',encoding='utf-8').read()); print('py OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/labor2_parsed.json',encoding='utf-8')); assert len(d['articles'])=={na}; print('json OK: مواد',len(d['articles']))"
cd /opt/LegalMind
"$PYA" "$TMP/ingest_labor2.py" "$TMP/labor2_parsed.json" --dry-run
"$PYA" "$TMP/ingest_labor2.py" "$TMP/labor2_parsed.json"
echo "== إعادة الفهرسة (deploy/.env) =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
"$PYA" -c "import psycopg,os; dsn=os.getenv('DATABASE_URL') or 'postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind'; c=psycopg.connect(dsn).cursor(); c.execute(\\"select count(*) from knowledge_objects where id like 'legis-46-1987-%'\\"); print('كائنات 46/1987:', c.fetchone()[0])"
echo '=== تم: المرسوم بقانون 46/1987 (إنشاء الدائرة العمالية) — 5 مواد + ديباجة (فرع عمل) ==='
"""
(H/"run_labor2_full.sh").write_text(SH,encoding="utf-8")
ssh=hashlib.sha256(SH.encode()).hexdigest()
one=f"printf '%s' '{gz(SH)}' | base64 -d | gunzip > run_labor2_full.sh && sha256sum run_labor2_full.sh"
(H/"DEPLOY_labor2.txt").write_text(one+"\n",encoding="utf-8")
print("run_labor2_full.sh SHA256:",ssh)
