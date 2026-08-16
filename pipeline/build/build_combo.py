#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ مُجمَّع (يُغني عن DEPLOY_law20) لقانونين جزائيين معًا بإعادة فهرسةٍ واحدة:
  • 20/2019 النظام الموحد الخليجي لمكافحة الغش التجاري (18 مادة + 4 إصدار).
  • 91/2013 مكافحة الاتجار بالأشخاص وتهريب المهاجرين (14 مادة، مع ملاحظة عدم دستورية جزءٍ من م13).
app.py: حزم الغش التجاري + حزم الاتجار بالأشخاص + جسر الجريمة الأصلية (الاتجار⇒غسل) + إشارات المصنّف
+ إدراج القانونين في رسم الديباجات. إدخال + إعادة فهرسة + رسم الديباجات + خريطة + نشر + اختبار وظيفيّ."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

F = {"ing20": H / "ingest_law20.py", "js20": H / "law20_2019_parsed.json",
     "ing91": H / "ingest_law91.py", "js91": H / "law91_2013_parsed.json",
     "app": APP, "px": H / "preamble_xref.py"}
B = {k: enc(v) for k, v in F.items()}
S = {k: sha(v) for k, v in F.items()}

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/combo_deploy; mkdir -p "$TMP"
printf '%s' '{B["ing20"]}' | base64 -d | gunzip > "$TMP/ingest_law20.py"
printf '%s' '{B["js20"]}'  | base64 -d | gunzip > "$TMP/law20_2019_parsed.json"
printf '%s' '{B["ing91"]}' | base64 -d | gunzip > "$TMP/ingest_law91.py"
printf '%s' '{B["js91"]}'  | base64 -d | gunzip > "$TMP/law91_2013_parsed.json"
printf '%s' '{B["app"]}'   | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{B["px"]}'    | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="
echo "ing20 {S['ing20']}"; echo "js20 {S['js20']}"; echo "ing91 {S['ing91']}"; echo "js91 {S['js91']}"; echo "app {S['app']}"; echo "px {S['px']}"
sha256sum "$TMP/ingest_law20.py" "$TMP/law20_2019_parsed.json" "$TMP/ingest_law91.py" "$TMP/law91_2013_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law20.py ingest_law91.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json; d=json.load(open('$TMP/law20_2019_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==18 and len(d['issuance'])==4; c=' '.join(list(a.values())+list(d['issuance'].values()))+' '+d['preamble_text']; assert chr(0xFFFD) not in c and '_' not in c and all(v.count(chr(40))==v.count(chr(41)) for v in a.values()); print('20/2019 json OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/law91_2013_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==14 and [int(k[1:]) for k in d['order']]==list(range(1,15)); c=' '.join(a.values())+' '+d['preamble_text']; assert chr(0xFFFD) not in c and '_' not in c; assert 'المحكمة الدستورية' in a['m13'] and 'الطعن رقم 7 لسنة 2018' in a['m13']; print('91/2013 json OK: م13 + ملاحظة الدستورية')"
for tok in legis-20-2019 legis-91-2013; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
cd /opt/LegalMind
echo "== إدخال 20/2019 =="; "$PYA" "$TMP/ingest_law20.py" "$TMP/law20_2019_parsed.json"
echo "== إدخال 91/2013 =="; "$PYA" "$TMP/ingest_law91.py" "$TMP/law91_2013_parsed.json"
echo "== إعادة الفهرسة الكاملة (مرّة واحدة) =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم الديباجات =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "رسم الديباجات محدّث"
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.combo"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.combo" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q,b=None): return set(m._draft_bundles("استشارة",q,[],None,b))
# 20/2019 الغش التجاري
a=ids("عقوبة الغش التجاري ومصادرة البضائع المغشوشة والعود وحظر بيع البضائع الفاسدة")
assert all(("legis-20-2019-m%d"%n) in a for n in (2,11,12,15)); print("  ✓ حزم الغش التجاري 20/2019")
# 91/2013 الاتجار بالأشخاص
b=ids("عقوبة الاتجار بالأشخاص وتهريب المهاجرين ومصادرة العائدات وحماية المجني عليه")
assert all(("legis-91-2013-m%d"%n) in b for n in (2,3,5,12)); print("  ✓ حزم الاتجار بالأشخاص 91/2013")
# جسر الجريمة الأصلية: غسل عائدات الاتجار ⇒ 91/2013 + 106/2013
c=ids("غسل أموال متحصلة من الاتجار بالأشخاص وتهريب المهاجرين")
assert "legis-91-2013-m2" in c and "legis-106-2013-m2" in c; print("  ✓ جسر الاتجار⇒غسل (91 + 106)")
# التصنيف التلقائيّ
assert "جزاي" in m._draft_norm_ar(m._resolve_branch(None, m._draft_norm_ar("الاتجار بالأشخاص")))
assert "جزاي" in m._draft_norm_ar(m._resolve_branch(None, m._draft_norm_ar("الغش التجاري وبضائع مغشوشة"))); print("  ✓ التصنيف (الاتجار/الغش ⇒ جزائي)")
# رسم الديباجات
d20=ids("ما القوانين المتصلة بالقانون 20 لسنة 2019 لمكافحة الغش التجاري؟","استشارة")
d91=ids("ما القوانين المتصلة بالقانون 91 لسنة 2013 لمكافحة الاتجار بالأشخاص؟","استشارة")
assert "legis-20-2019-preamble" in d20 and "legis-91-2013-preamble" in d91; print("  ✓ رسم الديباجات للقانونين")
# سلامة النصّ + العدّ
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-20-2019-%%'"); n20=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-91-2013-%%'"); n91=cur.fetchone()[0]
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-20-2019-m11'"); t=cur.fetchone()[0]
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-91-2013-m13'"); t13=cur.fetchone()[0]
assert n20==23 and n91==15 and "(السجن)" in t and "المحكمة الدستورية" in t13
print("  ✓ العدّ: 20/2019 =",n20,"| 91/2013 =",n91,"| م11 أقواس سليمة | م13 ملاحظة الدستورية محفوظة")
print("  === تمّ =====")
PY2
echo '=== تم: إدخال 20/2019 (الغش التجاري) + 91/2013 (الاتجار بالأشخاص) — حزم + جسر الجريمة الأصلية + رسم ديباجات (إعادة فهرسة واحدة) ==='
"""
(H / "run_combo.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_combo.sh && sha256sum run_combo.sh"
(H / "DEPLOY_combo.txt").write_text(oneliner + "\n", encoding="utf-8")
for k, v in S.items():
    print("%s sha: %s" % (k, v))
print("run_combo.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
