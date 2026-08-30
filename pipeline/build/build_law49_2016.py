#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ إدخالِ القانون 49/2016 (المناقصات العامة): 99 كائنًا (ديباجة + م1-م97 + م62 مكرر).

النشرةُ ذاتيةُ التشغيل: تُفكّ ثمّ تُنفَّذ، فلا يقع خطأ «No such file». وهي تتحقّق قبل الكتابة
(بصمةٌ + فحصُ بناءٍ + معاينةٌ جافّة)، وتقيس بعد الإدخال، وتعيد بناء خريطة الإحالات آليًّا كي
يلتقط النظامُ إحالاتِ 49/2016 إلى 20/1981 و38/1980 و20/2014 و30/1964 وغيرِها.
"""
import base64, gzip, hashlib, json, pathlib, subprocess

H = pathlib.Path(__file__).parent
ING = (H / "ingest_law49_2016.py").read_text(encoding="utf-8")
JSN = (H / "law49_2016_parsed.json").read_text(encoding="utf-8")
XB = (H / "xref_build.py").read_text(encoding="utf-8")

gz = lambda s: base64.b64encode(gzip.compress(s.encode(), 9)).decode()
sh = lambda s: hashlib.sha256(s.encode()).hexdigest()
NA = len(json.loads(JSN)["articles"])
assert NA == 98, NA

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
TMP=/tmp/law49_deploy; mkdir -p "$TMP"
printf '%s' '{gz(ING)}' | base64 -d | gunzip > "$TMP/ingest_law49_2016.py"
printf '%s' '{gz(JSN)}' | base64 -d | gunzip > "$TMP/law49_2016_parsed.json"
echo "== SHA256 =="
echo "ingest المتوقع: {sh(ING)}"
echo "json   المتوقع: {sh(JSN)}"
sha256sum "$TMP/ingest_law49_2016.py" "$TMP/law49_2016_parsed.json"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_law49_2016.py',encoding='utf-8').read()); print('py OK')"
"$PYA" - <<'PYCHK'
import json
d = json.load(open('/tmp/law49_deploy/law49_2016_parsed.json', encoding='utf-8'))
assert len(d['articles']) == {NA}, len(d['articles'])
assert len(d['order']) == {NA}
assert 'm62-mukarrar' in d['articles'] and 'm97' in d['articles']
am = d['amendments']
assert am['m31']['amendment_status'].endswith('1/2024')
assert '(37) لسنة 1964' in d['articles']['m94']['text']
assert 'يتظلم أمام لجنة التصنيف' in d['articles']['m27']['text']
assert d['articles']['m86']['bab'] == 'الباب العاشر' and d['articles']['m86']['fasl'] is None
print('json OK: مواد', len(d['articles']), '| معدَّلة', len(am))
PYCHK

echo
echo "== قبل الإدخال =="
"$PYA" - <<'PY0'
import os, psycopg
dsn = os.getenv('DATABASE_URL') or 'postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind'
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("select count(*) from knowledge_objects where id like 'legis-49-2016-%'")
    print('كائنات 49/2016 قبل:', cur.fetchone()[0])
    cur.execute("select count(*) from knowledge_objects")
    print('إجمالي القاعدة قبل:', cur.fetchone()[0])
PY0

cd /opt/LegalMind
echo
echo "== معاينةٌ جافّة =="
"$PYA" "$TMP/ingest_law49_2016.py" "$TMP/law49_2016_parsed.json" --dry-run
echo
echo "== الإدخال =="
"$PYA" "$TMP/ingest_law49_2016.py" "$TMP/law49_2016_parsed.json"

echo
echo "== إعادة الفهرسة (البيئة من deploy/.env) =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex

echo
echo "== بعد الإدخال =="
"$PYA" - <<'PY1'
import os, psycopg
dsn = os.getenv('DATABASE_URL') or 'postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind'
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("select count(*) from knowledge_objects where id like 'legis-49-2016-%'")
    n = cur.fetchone()[0]; print('كائنات 49/2016 بعد:', n)
    assert n == 99, 'العدد غير متوقّع: %d' % n
    cur.execute("select count(*) from knowledge_objects where branch='إداري'")
    print("إجمالي الفرع الإداري:", cur.fetchone()[0])
    cur.execute("select metadata->>'amendment_status', count(*) from knowledge_objects "
                "where id like 'legis-49-2016-m%' group by 1 order by 2 desc")
    for s, c in cur.fetchall():
        print('   %-46s %d' % (s, c))
    cur.execute("select id,left(original_text,110) from knowledge_objects "
                "where id in ('legis-49-2016-m31','legis-49-2016-m79','legis-49-2016-m62-mukarrar')")
    for i, t in cur.fetchall():
        print('\\n### %s\\n%s…' % (i, t.replace(chr(10), ' ')))
PY1

echo
echo "== إعادة بناء خريطة الإحالات =="
printf '%s' '{gz(XB)}' | base64 -d | gunzip > /opt/LegalMind/admin/xref_build.py
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل التشغيل"; exit 1; }}
echo '=== تم: قانون المناقصات العامة 49/2016 — 99 كائنًا + فهرسة + خريطة إحالات ==='
"""

(H / "run_law49_2016.sh").write_text(SH, encoding="utf-8")
one = ("printf '%s' '" + gz(SH) +
       "' | base64 -d | gunzip > run_law49_2016.sh && bash run_law49_2016.sh")
(H / "DEPLOY_law49_2016.txt").write_text(one + "\n", encoding="utf-8")

assert gzip.decompress(base64.b64decode(one.split("'")[3])) == SH.encode(), "round-trip mismatch!"
print("ingest sha:", sh(ING))
print("json   sha:", sh(JSN))
print("run_law49_2016.sh sha:", sh(SH))
r = subprocess.run(["bash", "-n", str(H / "run_law49_2016.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(one))
