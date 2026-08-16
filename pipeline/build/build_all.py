#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ واحدٌ مُجمَّع يُغني عن amlplus وlaw47 معًا (إعادة فهرسةٌ واحدة، بلا ترتيبٍ ملزِم):
  • تصحيح 106/2013 (تنظيف م5/م10/م14/م15 + إثراء الديباجة بسند الإصدار) — إعادة إدخال idempotent.
  • إدخال المرسوم بقانون 47/2026 (مكافحة جرائم الإرهاب) — 32 كائنًا.
  • app.py: محفّز الالتزامات/حظر التنبيه + تعميم جسر الجريمة الأصلية + الجسر العكسيّ + رسم الديباجات
    + محفّز الإرهاب _terrorism_ids + جسر تمويل الإرهاب 47⇄106 + 5 حزم إرهاب + إشارات المصنّف.
  • إعادة بناء رسم الديباجات (يربط 47 و106 المُثراة بشبكتهما) + خريطة الإحالات + اختبار وظيفيّ شامل."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

F = {"ing106": H / "ingest_law106.py", "js106": H / "law106_2013_parsed.json",
     "ing47": H / "ingest_law47.py", "js47": H / "law47_2026_parsed.json",
     "app": APP, "px": H / "preamble_xref.py"}
B = {k: enc(v) for k, v in F.items()}
S = {k: sha(v) for k, v in F.items()}

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/all_deploy; mkdir -p "$TMP"
printf '%s' '{B["ing106"]}' | base64 -d | gunzip > "$TMP/ingest_law106.py"
printf '%s' '{B["js106"]}'  | base64 -d | gunzip > "$TMP/law106_2013_parsed.json"
printf '%s' '{B["ing47"]}'  | base64 -d | gunzip > "$TMP/ingest_law47.py"
printf '%s' '{B["js47"]}'   | base64 -d | gunzip > "$TMP/law47_2026_parsed.json"
printf '%s' '{B["app"]}'    | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{B["px"]}'     | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 المتوقّعة =="
echo "ing106: {S['ing106']}"; echo "js106: {S['js106']}"; echo "ing47: {S['ing47']}"
echo "js47: {S['js47']}"; echo "app: {S['app']}"; echo "px: {S['px']}"
sha256sum "$TMP/ingest_law106.py" "$TMP/law106_2013_parsed.json" "$TMP/ingest_law47.py" "$TMP/law47_2026_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law106.py ingest_law47.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json; d=json.load(open('$TMP/law106_2013_parsed.json',encoding='utf-8')); assert len(d['articles'])==46; c=' '.join(v['text'] for v in d['articles'].values())+' '+d.get('preamble_text',''); assert chr(0xFFFD) not in c and '_' not in c; print('106 json OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/law47_2026_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==31 and [int(k[1:]) for k in d['order']]==list(range(1,32)); assert 'كل فعل أو تهديد يؤدي' in a['m1']['text']; c=' '.join(v['text'] for v in a.values())+' '+d.get('preamble_text',''); assert chr(0xFFFD) not in c and '_' not in c; print('47 json OK: م1 مُصحَّح')"
for tok in _aml_bank_ids _reverse_predicate_ids _preamble_related_ids _terrorism_ids legis-47-2026; do
  grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok مفقود"; exit 1; }}
done
cd /opt/LegalMind
echo "== إعادة إدخال 106/2013 المُصحَّح =="; "$PYA" "$TMP/ingest_law106.py" "$TMP/law106_2013_parsed.json"
echo "== إدخال 47/2026 (فعلي) =="; "$PYA" "$TMP/ingest_law47.py" "$TMP/law47_2026_parsed.json"
echo "== إعادة الفهرسة الكاملة (مرّة واحدة) =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم علاقات الديباجات =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.all"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.all" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ شامل =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q,b="جزائي"): return set(m._draft_bundles("استشارة",q,[],None,b))
# 106: حظر التنبيه + الجريمة الأصلية المُعمَّمة
a=ids("هل يجوز للبنك تحذير العميل بأنه تم الإخطار عن معاملته المشبوهة؟ وحكم الاحتفاظ بالسجلات؟")
assert all(("legis-106-2013-"+x) in a for x in ("m12","m13","m35")); print("  ✓ 106 حظر التنبيه")
b=ids("غسل أموال متحصلة من نصب واحتيال وتزوير محررات")
assert "legis-16-1960-m231" in b and "legis-16-1960-m257" in b; print("  ✓ جسر النصب/التزوير")
# 47: نواة الإرهاب + جسر التمويل
c=ids("عقوبة إنشاء وإدارة تنظيم إرهابي، وهل تتقادم؟")
assert all(("legis-47-2026-"+x) in c for x in ("m1","m7","m12","m28","m29")); print("  ✓ نواة الإرهاب 47/2026")
d=ids("متهم بتمويل الإرهاب وجمع أموال لتنظيم إرهابي")
assert "legis-47-2026-m1" in d and "legis-106-2013-m3" in d and "legis-106-2013-m29" in d; print("  ✓ جسر تمويل الإرهاب 47⇄106")
# رسم الديباجات: 47 و106 يستحضران قوانينهما المتّصلة
e=ids("ما القوانين المتصلة بالمرسوم بقانون رقم 47 لسنة 2026 لمكافحة الإرهاب؟","استشارة")
assert "legis-47-2026-preamble" in e and any(x in e for x in ("legis-106-2013-preamble","legis-13-1991-preamble","legis-111-2015-preamble")); print("  ✓ رسم ديباجات 47")
f=ids("ما القوانين المتصلة بالقانون رقم 106 لسنة 2013؟","استشارة")
assert "legis-106-2013-preamble" in f and any(x in f for x in ("legis-16-1960-preamble","legis-1-1993-preamble")); print("  ✓ رسم ديباجات 106")
# سلامة القاعدة
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-47-2026-%%'"); n47=cur.fetchone()[0]
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-47-2026-m1'"); t1=cur.fetchone()[0]
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-106-2013-m14'"); t14=cur.fetchone()[0]
assert n47==32 and "كل فعل أو تهديد" in t1 and "معايير" in t14 and "معاير" not in t14
print("  ✓ 47/2026: 32 كائنًا، م1«تهديد» | 106 م14 مُصحَّح")
print("  === كلّ التحقّقات نجحت ===")
PY2
echo '=== تم: تصحيح 106/2013 + إدخال 47/2026 مكافحة الإرهاب + كل المحفّزات والجسور ورسم الديباجات (إعادة فهرسة واحدة) ==='
"""
(H / "run_all.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_all.sh && sha256sum run_all.sh"
(H / "DEPLOY_all.txt").write_text(oneliner + "\n", encoding="utf-8")
for k, v in S.items():
    print("%s sha: %s" % (k, v))
print("run_all.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
