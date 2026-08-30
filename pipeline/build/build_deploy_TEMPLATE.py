"""قالب بناء نشر إدخال قانون + حزم، مع إعادة بناء خريطة الإحالات آليًّا في نهاية الإدخال.
للاستخدام: انسخه إلى build_deploy_admN.py واستبدل الوسوم [[...]] بقيم القانون، ثم شغّله.
يتطلّب في نفس المجلد: ingest_admN.py، admN_parsed.json، xref_build.py، و /tmp/app_patched.py."""
import base64,gzip,hashlib,json,pathlib
H=pathlib.Path(__file__).parent
TAG="[[TAG]]"          # مثال: adm13
PREFIX="[[PREFIX]]"    # مثال: legis-17-1960
DONE_MSG="[[DONE]]"    # مثال: 'قانون الإجراءات والمحاكمات الجزائية 17/1960'
SENTINEL="[[SENTINEL]]"  # مثال: legis-17-1960-m230  (معرّف يتحقّق منه نشر الحزم)

ING=(H/f"ingest_{TAG}.py").read_text(encoding="utf-8"); JSN=(H/f"{TAG}_parsed.json").read_text(encoding="utf-8")
XB=(H/"xref_build.py").read_text(encoding="utf-8")
def gz(s): return base64.b64encode(gzip.compress(s.encode(),9)).decode()
ib,jb,xbb=gz(ING),gz(JSN),gz(XB)
ish=hashlib.sha256(ING.encode()).hexdigest(); jsh=hashlib.sha256(JSN.encode()).hexdigest()
na=len(json.loads(JSN)["articles"])

SH=f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
TMP=/tmp/{TAG}_deploy; mkdir -p "$TMP"
printf '%s' '{ib}' | base64 -d | gunzip > "$TMP/ingest_{TAG}.py"
printf '%s' '{jb}' | base64 -d | gunzip > "$TMP/{TAG}_parsed.json"
echo "== SHA256 =="; echo "ingest المتوقع: {ish}"; echo "json المتوقع: {jsh}"
sha256sum "$TMP/ingest_{TAG}.py" "$TMP/{TAG}_parsed.json"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_{TAG}.py',encoding='utf-8').read()); print('py OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/{TAG}_parsed.json',encoding='utf-8')); assert len(d['articles'])=={na}; print('json OK: مواد',len(d['articles']))"
cd /opt/LegalMind
"$PYA" "$TMP/ingest_{TAG}.py" "$TMP/{TAG}_parsed.json" --dry-run
"$PYA" "$TMP/ingest_{TAG}.py" "$TMP/{TAG}_parsed.json"
echo "== إعادة الفهرسة (deploy/.env) =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
"$PYA" -c "import psycopg,os; dsn=os.getenv('DATABASE_URL') or 'postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind'; c=psycopg.connect(dsn).cursor(); c.execute(\\"select count(*) from knowledge_objects where id like '{PREFIX}-%'\\"); print('كائنات {PREFIX}:', c.fetchone()[0])"
echo "== إعادة بناء خريطة الإحالات بين القوانين (تلقائيًّا) =="
printf '%s' '{xbb}' | base64 -d | gunzip > /opt/LegalMind/admin/xref_build.py
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json
systemctl restart legalmind-admin; sleep 2
systemctl is-active legalmind-admin && echo "الخدمة نشطة (خريطة الإحالات محدّثة)" || {{ echo "فشل التشغيل"; exit 1; }}
echo '=== تم: {DONE_MSG} — إدخال + فهرسة + تحديث خريطة الإحالات ==='
"""
(H/f"run_{TAG}_full.sh").write_text(SH,encoding="utf-8")
(H/f"DEPLOY_{TAG}.txt").write_text(f"printf '%s' '{gz(SH)}' | base64 -d | gunzip > run_{TAG}_full.sh && sha256sum run_{TAG}_full.sh\n")
print(f"run_{TAG}_full.sh SHA256:",hashlib.sha256(SH.encode()).hexdigest())

APP=pathlib.Path("/tmp/app_patched.py").read_text(encoding="utf-8")
app_b64=gz(APP); app_sha=hashlib.sha256(APP.encode()).hexdigest()
SH2=f"""#!/usr/bin/env bash
set -euo pipefail
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/{TAG}_deploy; mkdir -p "$TMP"
printf '%s' '{app_b64}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app.py المتوقع: {app_sha}"; sha256sum "$TMP/app.py"
python3 -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('python OK')"
grep -q "{SENTINEL}" "$TMP/app.py" && echo "حزم {DONE_MSG} موجودة" || {{ echo "خطأ: sentinel"; exit 1; }}
grep -q "توسعة الإحالات بين القوانين" "$TMP/app.py" && echo "توسعة الإحالات سليمة" || {{ echo "خطأ: xref"; exit 1; }}
grep -q "_AR_DIAC" "$TMP/app.py" && echo "تطبيع إزالة التشكيل مفعّل" || {{ echo "خطأ: _AR_DIAC"; exit 1; }}
cp -f "$APP" "$APP.bak.{TAG}" && echo "احتُفظ بـ $APP.bak.{TAG}"
cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin && echo "الخدمة نشطة" || {{ echo "استرجاع"; cp -f "$APP.bak.{TAG}" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo '=== تم: حزم {DONE_MSG} نشطة ==='
"""
(H/f"run_{TAG}_bundles.sh").write_text(SH2,encoding="utf-8")
(H/f"DEPLOY_{TAG}_bundles.txt").write_text(f"printf '%s' '{gz(SH2)}' | base64 -d | gunzip > run_{TAG}_bundles.sh && sha256sum run_{TAG}_bundles.sh\n")
print("app.py SHA256:",app_sha)
print(f"run_{TAG}_bundles.sh SHA256:",hashlib.sha256(SH2.encode()).hexdigest())
