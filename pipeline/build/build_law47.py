#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ المرسوم بقانون 47/2026 (مكافحة جرائم الإرهاب): مُدخِل + JSON (31 مادة) + app.py (محفّز _terrorism_ids
+ جسر تمويل الإرهاب 47⇄106 + 5 حزم + إشارات المصنّف + إدراج 47/2026 في رسم الديباجات) + إعادة بناء رسم
الديباجات (يربط 47 تلقائيًّا بـ106/2013، 13/1991، 111/2015، 2/2016…). إدخال + إعادة فهرسة + خريطة + اختبار."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ingest = H / "ingest_law47.py"; js = H / "law47_2026_parsed.json"; px = H / "preamble_xref.py"
b_ing, b_js, b_app, b_px = enc(ingest), enc(js), enc(APP), enc(px)
s_ing, s_js, s_app, s_px = sha(ingest), sha(js), sha(APP), sha(px)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law47_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law47.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law47_2026_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_law47.py" "$TMP/law47_2026_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_law47.py',encoding='utf-8').read()); print('ingest OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/preamble_xref.py',encoding='utf-8').read()); print('px OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/law47_2026_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==31, len(a); ks=[int(k[1:]) for k in d['order']]; assert ks==list(range(1,32)), 'not sequential'; b=json.dumps(d,ensure_ascii=False); assert chr(0xFFFD) not in b and '_' not in b; assert 'كل فعل أو تهديد يؤدي' in a['m1']['text'], 'تصويب م1 مفقود'; print('json OK: 31 مادة متسلسلة، م1 مُصحَّح، لا � ولا _')"
for tok in _terrorism_ids legis-47-2026; do
  grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok مفقود"; exit 1; }}
done
cd /opt/LegalMind
echo "== إدخال 47/2026 (فعلي) =="; "$PYA" "$TMP/ingest_law47.py" "$TMP/law47_2026_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم علاقات الديباجات (يُدرج 47/2026) =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law47"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law47" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q,b=None): return set(m._draft_bundles("استشارة",q,[],None,b))
# التصنيف التلقائيّ: سؤال إرهاب بلا فرعٍ صريح ⇒ جزائي
br=m._resolve_branch(None, m._draft_norm_ar("ما عقوبة إنشاء تنظيم إرهابي وإدارته؟"))
print("  التصنيف التلقائيّ (إرهاب⇒جزائي):", br)
# نواة جرائم الإرهاب
a=ids("ما عقوبة من أنشأ أو أدار تنظيماً إرهابياً؟ وهل تتقادم الجريمة؟")
need=["legis-47-2026-m1","legis-47-2026-m7","legis-47-2026-m12","legis-47-2026-m28","legis-47-2026-m29"]
print("  نواة الإرهاب (م1/م7/م12/م28/م29):", all(k in a for k in need))
assert all(k in a for k in need)
# جسر تمويل الإرهاب: 47/2026 ⇄ 106/2013 (م3 التجريم، م29 العقوبة)
b=ids("متهم بتمويل الإرهاب وجمع أموال لتنظيم إرهابي")
print("  جسر التمويل (47 + 106 م3/م29):", "legis-47-2026-m1" in b and "legis-106-2013-m3" in b and "legis-106-2013-m29" in b)
assert "legis-106-2013-m3" in b and "legis-106-2013-m29" in b
# الخطورة الإرهابية والتدابير الوقائية
c=ids("إجراءات الخطورة الإرهابية وإخضاع الشخص لبرنامج إعادة التأهيل والتدابير الوقائية")
print("  الخطورة/التأهيل (م17/م18/م19):", all(("legis-47-2026-"+x) in c for x in ("m18","m19")))
assert "legis-47-2026-m19" in c
# رسم الديباجات: سؤالٌ يسمّي 47/2026 ⇒ يستحضر ديباجاتِ قوانين متّصلة مُدخَلة (106/2013، 13/1991، 111/2015…)
d=ids("ما القوانين المتصلة بالمرسوم بقانون رقم 47 لسنة 2026 في شأن مكافحة جرائم الإرهاب؟")
rel=sorted(x for x in d if x.endswith("-preamble"))
print("  ديباجات متّصلة:", rel[:8])
assert "legis-47-2026-preamble" in d, "ديباجة القانون المحوريّ غائبة!"
assert any(x in d for x in ("legis-106-2013-preamble","legis-13-1991-preamble","legis-111-2015-preamble")), "لم تُستحضَر القوانين المتّصلة!"
# سلامة القاعدة وتصحيح م1
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-47-2026-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-47-2026-m1'"); t1=cur.fetchone()[0]
print("  كائنات 47/2026:", n, "| م1 «تهديد» لا «تحديد»:", ("كل فعل أو تهديد" in t1 and "أو تحديد يؤدي" not in t1))
assert n==32 and "كل فعل أو تهديد" in t1
print("  ✓ 47/2026: التصنيف + النواة + جسر التمويل + الخطورة + رسم الديباجات — كلّها تعمل")
PY2
echo '=== تم: إدخال المرسوم بقانون 47/2026 مكافحة جرائم الإرهاب — 32 كائنًا + محفّز + جسر تمويل + 5 حزم + رسم ديباجات ==='
"""
(H / "run_law47.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law47.sh && sha256sum run_law47.sh"
(H / "DEPLOY_law47.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app); print("px sha:", s_px)
print("run_law47.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
