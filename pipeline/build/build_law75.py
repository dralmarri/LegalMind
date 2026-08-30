#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ إدخالِ القانون 75/2019 (حقوق المؤلف والحقوق المجاورة): 52 كائنًا (ديباجة + م1-م51).

النسخةُ الثانية — بعد مقابلةِ النصّ على صورِ صفحاتٍ من «الكويت اليوم» ع1455:
  (أ) استُكمل التاريخُ الميلاديّ «الموافق 23 يوليو 2019 م» موسومًا بمصدره.
  (ب) فُصلت ترويسةُ «أحكام ختامية» عن ذيل م47 — فالعقوباتُ م41–م47 لا م41–م48.
  (ج) سُجّل خلافُ الشاهدين في موضعين ولم يُغيَّر النصّ فيهما.

النشرةُ ذاتيةُ التشغيل: تُفكّ ثمّ تُنفَّذ. البيئةُ تُصدَّر في أوّل سطرٍ قبل أيّ اتصالٍ بالقاعدة،
ولا كلمةَ مرورٍ في المتن. وتتحقّق قبل الكتابة (بصمةٌ + فحصُ بناءٍ + معاينةٌ جافّة)، وتقيس بعد
الإدخال، وتعيد بناء خريطة الإحالات كي يلتقط النظامُ إلغاءَ 22/2016 و64/1999.
"""
import base64, gzip, hashlib, json, pathlib, subprocess

H = pathlib.Path(__file__).parent
ING = (H / "ingest_law75_2019.py").read_text(encoding="utf-8")
JSN = (H / "law75_2019_parsed.json").read_text(encoding="utf-8")
XB = (H / "xref_build.py").read_text(encoding="utf-8")

gz = lambda s: base64.b64encode(gzip.compress(s.encode(), 9)).decode()
sh = lambda s: hashlib.sha256(s.encode()).hexdigest()
D = json.loads(JSN)
NA = len(D["articles"])
assert NA == 51, NA
assert "أحكام ختامية" not in D["articles"]["47"]["text"]
assert D["articles"]["48"]["fasl"] == "أحكام ختامية"
assert "الموافق 23 يوليو 2019 م" in D["issuance"]
assert len(D["subheadings"]) == 6
assert not any(D["articles"][k]["text"].rstrip().endswith(("الحقوق الأدبية", "الحقوق المالية"))
               for k in D["order"])

SH = f"""#!/usr/bin/env bash
set -euo pipefail
if [ -r /opt/LegalMind/deploy/.env ]; then set -a; . /opt/LegalMind/deploy/.env; set +a; fi
[ -n "${{DATABASE_URL:-}}" ] || {{ echo "خطأ: DATABASE_URL غير مضبوط — راجِع deploy/.env"; exit 1; }}
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
TMP=/tmp/law75_deploy; mkdir -p "$TMP"
printf '%s' '{gz(ING)}' | base64 -d | gunzip > "$TMP/ingest_law75_2019.py"
printf '%s' '{gz(JSN)}' | base64 -d | gunzip > "$TMP/law75_2019_parsed.json"
echo "== SHA256 =="
echo "ingest المتوقع: {sh(ING)}"
echo "json   المتوقع: {sh(JSN)}"
sha256sum "$TMP/ingest_law75_2019.py" "$TMP/law75_2019_parsed.json"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_law75_2019.py',encoding='utf-8').read()); print('py OK')"
"$PYA" - <<'PYCHK'
import json
d = json.load(open('/tmp/law75_deploy/law75_2019_parsed.json', encoding='utf-8'))
assert len(d['articles']) == {NA} == len(d['order']), len(d['articles'])
# الترويسةُ ليست متنًا، والقسمُ الختاميُّ قائمٌ بذاته
assert 'أحكام ختامية' not in d['articles']['47']['text'], 'ترويسةٌ باقيةٌ في م47'
assert len(d['subheadings']) == 6, 'العناوينُ الفرعية %d' % len(d['subheadings'])
for k in ('5','8','15','16','21','22'):
    assert not d['articles'][k]['text'].rstrip().endswith(('الحقوق الأدبية','الحقوق المالية')), \
        'م%s ذيلُها عنوان' % k
assert all(d['articles'][k]['fasl'] == 'أحكام ختامية' for k in ('48','49','50','51'))
assert d['articles']['47']['fasl'] == 'الفصل الثاني — العقوبات'
# ما أفادته صورةُ الجريدة
assert 'الموافق 23 يوليو 2019 م' in d['issuance'], 'التاريخُ الميلاديّ مفقود'
assert 'يُلغى القانون رقم 22 لسنة 2016' in d['articles']['49']['text']
assert 'بالمادتين 31 ، 32' in d['articles']['41']['text'], 'ربطُ العقوبة بالاستثناء'
assert len(d['gazette_divergences']) == 2 and len(d['structural_splits']) == 1
print('json OK: مواد', len(d['articles']), '| أبواب/فصول', len(d['structure']),
      '| خلافٌ مسجَّل', len(d['gazette_divergences']))
PYCHK

echo
echo "== قبل الإدخال =="
"$PYA" - <<'PY0'
import os, psycopg
with psycopg.connect(os.environ['DATABASE_URL']) as cx, cx.cursor() as cur:
    cur.execute("select count(*) from knowledge_objects where id like 'legis-75-2019-%'")
    print('كائنات 75/2019 قبل:', cur.fetchone()[0])
    cur.execute("select count(*) from knowledge_objects")
    print('إجمالي القاعدة قبل:', cur.fetchone()[0])
PY0

cd /opt/LegalMind
echo
echo "== معاينةٌ جافّة =="
"$PYA" "$TMP/ingest_law75_2019.py" "$TMP/law75_2019_parsed.json" --dry-run
echo
echo "== الإدخال =="
"$PYA" "$TMP/ingest_law75_2019.py" "$TMP/law75_2019_parsed.json"

echo
echo "== إعادة الفهرسة =="
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex

echo
echo "== بعد الإدخال =="
"$PYA" - <<'PY1'
import os, psycopg
with psycopg.connect(os.environ['DATABASE_URL']) as cx, cx.cursor() as cur:
    cur.execute("select count(*) from knowledge_objects where id like 'legis-75-2019-%'")
    n = cur.fetchone()[0]; print('كائنات 75/2019 بعد:', n)
    assert n == 52, 'العدد غير متوقّع: %d' % n
    cur.execute("select count(*) from knowledge_objects where branch='تجاري'")
    print('إجمالي الفرع التجاري:', cur.fetchone()[0])
    cur.execute("select count(*) from knowledge_objects "
                "where id like 'legis-75-2019-m%' and (metadata->>'penal')::bool")
    p = cur.fetchone()[0]; print('موادُّ العقوبات الموسومة:', p)
    assert p == 7, 'العقوباتُ م41-م47 سبعٌ لا %d' % p
    cur.execute("select metadata->>'fasl', count(*) from knowledge_objects "
                "where id like 'legis-75-2019-m%' group by 1 order by 2 desc")
    for s, c in cur.fetchall():
        print('   %-58s %d' % (s or '—', c))
    cur.execute("select original_text from knowledge_objects where id='legis-75-2019-preamble'")
    t = cur.fetchone()[0]
    for needle, lbl in (('الموافق 23 يوليو 2019 م', 'التاريخُ الميلاديّ'),
                        ('الكويت اليوم', 'بيانُ الجريدة'),
                        ('لم يُقابَل على الجريدة', 'التنبيهُ في المتن')):
        assert needle in t, 'الديباجة: %s مفقود' % lbl
        print('   ✓', lbl)
    cur.execute("select left(original_text,150) from knowledge_objects where id='legis-75-2019-m49'")
    print('\\n### م49 (الإلغاء)\\n%s…' % cur.fetchone()[0].replace(chr(10), ' '))
PY1

echo
echo "== إعادة بناء خريطة الإحالات =="
printf '%s' '{gz(XB)}' | base64 -d | gunzip > /opt/LegalMind/admin/xref_build.py
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل التشغيل"; exit 1; }}
echo '=== تم: قانون حقوق المؤلف والحقوق المجاورة 75/2019 — 52 كائنًا + فهرسة + خريطة إحالات ==='
"""

(H / "run_law75.sh").write_text(SH, encoding="utf-8")
one = ("printf '%s' '" + gz(SH) +
       "' | base64 -d | gunzip > run_law75.sh && bash run_law75.sh")
(H / "DEPLOY_law75.txt").write_text(one + "\n", encoding="utf-8")

assert gzip.decompress(base64.b64decode(one.split("'")[3])) == SH.encode(), "round-trip mismatch!"
print("ingest sha:", sh(ING))
print("json   sha:", sh(JSN))
print("run_law75.sh sha:", sh(SH))
r = subprocess.run(["bash", "-n", str(H / "run_law75.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(one))
