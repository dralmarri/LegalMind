#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني سكربت نشر قانون العمالة المنزلية 68/2015 + أمر تسليم أحادي السطر (بلا SFTP).
يُحمّل deploy/.env قبل إعادة الفهرسة."""
import base64, gzip, hashlib, json, pathlib

HERE = pathlib.Path(__file__).parent
ING  = (HERE / "ingest_labor.py").read_text(encoding="utf-8")
JSN  = (HERE / "labor_parsed.json").read_text(encoding="utf-8")

def gz(s): return base64.b64encode(gzip.compress(s.encode("utf-8"), 9)).decode("ascii")

ing_b64, jsn_b64 = gz(ING), gz(JSN)
ing_sha = hashlib.sha256(ING.encode()).hexdigest()
jsn_sha = hashlib.sha256(JSN.encode()).hexdigest()
d = json.loads(JSN); n_art = len(d["articles"])

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
TMP=/tmp/labor_deploy
mkdir -p "$TMP"

printf '%s' '{ing_b64}' | base64 -d | gunzip > "$TMP/ingest_labor.py"
printf '%s' '{jsn_b64}' | base64 -d | gunzip > "$TMP/labor_parsed.json"

echo "== SHA256 (يجب أن تطابق) =="
echo "ingest_labor.py المتوقع: {ing_sha}"
echo "labor_parsed.json المتوقع: {jsn_sha}"
sha256sum "$TMP/ingest_labor.py" "$TMP/labor_parsed.json"

echo "== تحقّق البنية =="
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_labor.py',encoding='utf-8').read()); print('python OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/labor_parsed.json',encoding='utf-8')); assert len(d['articles'])=={n_art}; print('json OK: مواد',len(d['articles']))"

cd /opt/LegalMind

echo "== تقرير تجريبي =="
"$PYA" "$TMP/ingest_labor.py" "$TMP/labor_parsed.json" --dry-run

echo "== الإدخال الفعلي =="
"$PYA" "$TMP/ingest_labor.py" "$TMP/labor_parsed.json"

echo "== إعادة الفهرسة (مع تحميل deploy/.env) =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex

echo "== عدّ كائنات القانون =="
"$PYA" -c "import psycopg,os; dsn=os.getenv('DATABASE_URL') or 'postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind'; cur=psycopg.connect(dsn).cursor(); cur.execute(\\"select count(*) from knowledge_objects where id like 'legis-68-2015-%'\\"); print('كائنات القانون 68/2015:', cur.fetchone()[0])"

echo '=== تم: قانون العمالة المنزلية 68/2015 — 54 مادة + ديباجة (الفرع: عمل) ==='
"""

sh_path = HERE / "run_labor_full.sh"
sh_path.write_text(SH, encoding="utf-8")
sh_sha = hashlib.sha256(SH.encode()).hexdigest()
delivery = gz(SH)
one = (f"printf '%s' '{delivery}' | base64 -d | gunzip > run_labor_full.sh "
       f"&& sha256sum run_labor_full.sh")
(HERE / "DEPLOY_labor.txt").write_text(one + "\n", encoding="utf-8")

print(f"ingest_labor.py: {len(ING)} | json: {len(JSN)}")
print(f"run_labor_full.sh SHA256: {sh_sha}")
print(f"delivery one-liner: {len(one)} chars")
print(f"\nSHA المتوقع:\n  {sh_sha}")
