#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ القانون 88/1995 (محاكمة الوزراء): مُدخِل + JSON (16 مادة، م14 ملغاة) + app.py (حزمة الوزراء
+ إشارات المصنّف + إدراج 88/1995 في رسم الديباجات) — ويحمل app أيضًا آخرَ إصلاحات الاسترجاع (جسر الآداب
16/1960، وتوسيع مفاتيح الاتجار). إدخال + إعادة فهرسة + رسم الديباجات + خريطة + نشر + اختبار وظيفيّ."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ingest = H / "ingest_law88.py"; js = H / "law88_1995_parsed.json"; px = H / "preamble_xref.py"
b_ing, b_js, b_app, b_px = enc(ingest), enc(js), enc(APP), enc(px)
s_ing, s_js, s_app, s_px = sha(ingest), sha(js), sha(APP), sha(px)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law88_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law88.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law88_1995_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_law88.py" "$TMP/law88_1995_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law88.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json; d=json.load(open('$TMP/law88_1995_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==17 and 'm6-mukarrar' in a; c=' '.join(a.values())+' '+d['preamble_text']; assert chr(0xFFFD) not in c and '_' not in c and 'ُيُ' not in c; assert a['m14'].strip()=='ملغاة' and 'يُعاقب' in a['m2'] and 'التظلم' in a['m6-mukarrar']; print('88/1995 json OK: 17 مادة (+م6مكرر)، م14 ملغاة، م2 يُعاقب، لا � ولا ُيُ')"
for tok in legis-88-1995 _minister_ids _morality_ids _trafficking_ids; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
cd /opt/LegalMind
echo "== إدخال 88/1995 (فعلي) =="; "$PYA" "$TMP/ingest_law88.py" "$TMP/law88_1995_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم الديباجات =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "رسم الديباجات محدّث"
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law88"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law88" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q,b=None): return set(m._draft_bundles("استشارة",q,[],None,b))
# التصنيف + حزمة الوزراء
br=m._resolve_branch(None, m._draft_norm_ar("إجراءات محاكمة وزير عن جريمة في وظيفته"))
print("  التصنيف (محاكمة الوزراء ⇒):", br); assert "جزاي" in m._draft_norm_ar(br)
a=ids("ما إجراءات محاكمة الوزراء ولجنة التحقيق والمحكمة الخاصة وجرائم الوزير والتظلم من الحفظ؟")
assert all(("legis-88-1995-m%d"%n) in a for n in (1,2,3,11)) and "legis-88-1995-m6-mukarrar" in a
print("  ✓ محاكمة الوزراء كاملًا (م1/م2/م3/م11 + م6مكرر التظلّم)")
# رسم الديباجات: 88/1995 يستحضر قوانينه المتّصلة المُدخَلة
d=ids("ما القوانين المتصلة بالقانون 88 لسنة 1995 لمحاكمة الوزراء؟","استشارة")
rel=sorted(x for x in d if x.endswith("-preamble"))
print("  ديباجات متّصلة:", rel[:8])
assert "legis-88-1995-preamble" in d and any(x in d for x in ("legis-16-1960-preamble","legis-17-1960-preamble","legis-31-1970-preamble")), "رسم ديباجات 88 لم يعمل"
# باقي الإصلاحات حيّة: جسر الآداب + الاتجار بالنساء
assert "legis-16-1960-m201" in ids("الاتجار بالأشخاص للاستغلال الجنسي وإكراههن على الدعارة"); print("  ✓ جسر الآداب 16/1960 حيّ")
# سلامة النصّ والعدّ
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-88-1995-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-88-1995-m2'"); t2=cur.fetchone()[0]
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-88-1995-m14'"); t14=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects"); tot=cur.fetchone()[0]
assert n==18 and "يُعاقب" in t2 and t14.strip()=="ملغاة"
print("  ✓ العدّ: 88/1995 =",n,"(بم6مكرر) | م2 «يُعاقب» | م14 «ملغاة» | الإجمالي =",tot)
print("  === تمّ =====")
PY2
echo '=== تم: إدخال القانون 88/1995 لمحاكمة الوزراء — 17 كائنًا + حزمة + مصنّف + رسم ديباجات (مع حمل جسر الآداب) ==='
"""
(H / "run_law88.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law88.sh && sha256sum run_law88.sh"
(H / "DEPLOY_law88.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app); print("px sha:", s_px)
print("run_law88.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
