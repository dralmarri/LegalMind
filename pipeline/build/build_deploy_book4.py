#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني سكربت نشر مكتفٍ ذاتيًا للكتاب الرابع + أمر التسليم أحادي السطر (بلا SFTP).
يصحّح مشكلة الكتاب الثالث: يُحمّل ملف البيئة deploy/.env قبل إعادة الفهرسة."""
import base64, gzip, hashlib, json, pathlib

HERE = pathlib.Path(__file__).parent
ING  = (HERE / "ingest_book4.py").read_text(encoding="utf-8")
JSN  = (HERE / "book4_articles.json").read_text(encoding="utf-8")

def gz_b64(s: str) -> str:
    return base64.b64encode(gzip.compress(s.encode("utf-8"), 9)).decode("ascii")

ing_b64 = gz_b64(ING); jsn_b64 = gz_b64(JSN)
ing_sha = hashlib.sha256(ING.encode("utf-8")).hexdigest()
jsn_sha = hashlib.sha256(JSN.encode("utf-8")).hexdigest()
d = json.loads(JSN); n_art = len(d["articles"]); n_anx = len(d["annexes"])

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
TMP=/tmp/b4_deploy
mkdir -p "$TMP"

printf '%s' '{ing_b64}' | base64 -d | gunzip > "$TMP/ingest_book4.py"
printf '%s' '{jsn_b64}' | base64 -d | gunzip > "$TMP/book4_articles.json"

echo "== SHA256 (يجب أن تطابق) =="
echo "ingest_book4.py المتوقع: {ing_sha}"
echo "book4_articles.json المتوقع: {jsn_sha}"
sha256sum "$TMP/ingest_book4.py" "$TMP/book4_articles.json"

echo "== تحقّق البنية =="
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_book4.py',encoding='utf-8').read()); print('python OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/book4_articles.json',encoding='utf-8')); assert len(d['articles'])=={n_art} and len(d['annexes'])=={n_anx}; print('json OK: مواد',len(d['articles']),'| ملاحق',len(d['annexes']))"

cd /opt/LegalMind

echo "== تقرير تجريبي (dry-run) =="
"$PYA" "$TMP/ingest_book4.py" "$TMP/book4_articles.json" --dry-run

echo "== الإدخال الفعلي =="
"$PYA" "$TMP/ingest_book4.py" "$TMP/book4_articles.json"

echo "== إعادة الفهرسة (مع تحميل ملف البيئة deploy/.env) =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex

echo "== عدّ كائنات الكتاب الرابع في postgres =="
"$PYA" -c "import psycopg,os; dsn=os.getenv('DATABASE_URL') or 'postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind'; cur=psycopg.connect(dsn).cursor(); cur.execute(\\"select count(*) from knowledge_objects where id like 'lreg-7-2010-k4-%'\\"); print('كائنات k4:', cur.fetchone()[0])"

echo '=== تم: الكتاب الرابع (بورصات الأوراق المالية ووكالات المقاصة) — {n_art} مادة + {n_anx} ملاحق ==='
"""

sh_path = HERE / "run_book4_full.sh"
sh_path.write_text(SH, encoding="utf-8")
sh_sha = hashlib.sha256(SH.encode("utf-8")).hexdigest()

delivery_b64 = base64.b64encode(gzip.compress(SH.encode("utf-8"), 9)).decode("ascii")
one_liner = (f"printf '%s' '{delivery_b64}' | base64 -d | gunzip > run_book4_full.sh "
             f"&& sha256sum run_book4_full.sh")
txt_path = HERE / "DEPLOY_book4.txt"
txt_path.write_text(one_liner + "\n", encoding="utf-8")

print(f"ingest_book4.py: {len(ING)} حرف | gzip+b64 {len(ing_b64)}")
print(f"book4_articles.json: {len(JSN)} حرف | gzip+b64 {len(jsn_b64)}")
print(f"run_book4_full.sh: {len(SH)} حرف | SHA256 {sh_sha}")
print(f"أمر التسليم (سطر واحد): {len(one_liner)} حرف")
print(f"\nSHA المتوقع لـ run_book4_full.sh:\n  {sh_sha}")
print(f"\nكُتب: {sh_path}\nكُتب: {txt_path}")
