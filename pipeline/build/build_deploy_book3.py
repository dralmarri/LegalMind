#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني سكربت نشر مكتفٍ ذاتيًا للكتاب الثالث + أمر التسليم أحادي السطر (بلا SFTP)."""
import base64, gzip, hashlib, json, pathlib

HERE = pathlib.Path(__file__).parent
ING  = (HERE / "ingest_book3.py").read_text(encoding="utf-8")
JSN  = (HERE / "book3_articles.json").read_text(encoding="utf-8")

def gz_b64(s: str) -> str:
    return base64.b64encode(gzip.compress(s.encode("utf-8"), 9)).decode("ascii")

ing_b64 = gz_b64(ING)
jsn_b64 = gz_b64(JSN)
ing_sha = hashlib.sha256(ING.encode("utf-8")).hexdigest()
jsn_sha = hashlib.sha256(JSN.encode("utf-8")).hexdigest()

# تحقّق من صحّة الـJSON قبل البناء
d = json.loads(JSN)
n_art = len(d["articles"]); n_anx = len(d["annexes"])

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
TMP=/tmp/b3_deploy
mkdir -p "$TMP"

printf '%s' '{ing_b64}' | base64 -d | gunzip > "$TMP/ingest_book3.py"
printf '%s' '{jsn_b64}' | base64 -d | gunzip > "$TMP/book3_articles.json"

echo "== SHA256 (يجب أن تطابق) =="
echo "ingest_book3.py المتوقع: {ing_sha}"
echo "book3_articles.json المتوقع: {jsn_sha}"
sha256sum "$TMP/ingest_book3.py" "$TMP/book3_articles.json"

echo "== تحقّق البنية =="
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_book3.py',encoding='utf-8').read()); print('python OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/book3_articles.json',encoding='utf-8')); assert len(d['articles'])=={n_art} and len(d['annexes'])=={n_anx}; print('json OK: مواد',len(d['articles']),'| ملاحق',len(d['annexes']))"

cd /opt/LegalMind

echo "== تقرير تجريبي (dry-run) =="
"$PYA" "$TMP/ingest_book3.py" "$TMP/book3_articles.json" --dry-run

echo "== الإدخال الفعلي =="
"$PYA" "$TMP/ingest_book3.py" "$TMP/book3_articles.json"

echo "== إعادة الفهرسة (تطبع الاتساق postgres_objects == qdrant_points) =="
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex

echo "== عدّ كائنات الكتاب الثالث في postgres =="
"$PYA" -c "import psycopg,os; dsn=os.getenv('DATABASE_URL') or 'postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind'; cur=psycopg.connect(dsn).cursor(); cur.execute(\\"select count(*) from knowledge_objects where id like 'lreg-7-2010-k3-%'\\"); print('كائنات k3:', cur.fetchone()[0])"

echo '=== تم: الكتاب الثالث (إنفاذ القانون) — {n_art} مادة + {n_anx} ملاحق ==='
"""

sh_path = HERE / "run_book3_full.sh"
sh_path.write_text(SH, encoding="utf-8")
sh_sha = hashlib.sha256(SH.encode("utf-8")).hexdigest()

# أمر التسليم أحادي السطر: يعيد بناء السكربت من gzip+base64، ثم يطبع الـSHA
delivery_b64 = base64.b64encode(gzip.compress(SH.encode("utf-8"), 9)).decode("ascii")
one_liner = (f"printf '%s' '{delivery_b64}' | base64 -d | gunzip > run_book3_full.sh "
             f"&& sha256sum run_book3_full.sh")

txt_path = HERE / "DEPLOY_book3.txt"
txt_path.write_text(one_liner + "\n", encoding="utf-8")

print("== حجم الحمولات ==")
print(f"ingest_book3.py: {len(ING)} حرف | gzip+b64 {len(ing_b64)}")
print(f"book3_articles.json: {len(JSN)} حرف | gzip+b64 {len(jsn_b64)}")
print(f"run_book3_full.sh: {len(SH)} حرف | SHA256 {sh_sha}")
print(f"أمر التسليم (سطر واحد): {len(one_liner)} حرف")
print(f"\nSHA المتوقع لـ run_book3_full.sh (بعد اللصق يجب أن يطبع):\n  {sh_sha}")
print(f"\nكُتب: {sh_path}\nكُتب: {txt_path}")
