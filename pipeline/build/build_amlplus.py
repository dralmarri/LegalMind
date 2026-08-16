#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ مُجمَّع (يُغني عن amlfix): (تصحيح) إعادة إدخال 106/2013 بعد تنظيف 4 مواد إجرائية + إثراء الديباجة
بسند الإصدار الحقيقيّ + (أ) محفّز التزامات المؤسسات/حظر التنبيه + (ب) تعميم جسر الجريمة الأصلية (16/1960)
+ (ج١) جسرٌ عكسيّ (جريمة أصلية+قرينة ماليّة⇒غسل) + (ج٢) تفعيل رسم الديباجات في الاسترجاع.
إعادة إدخال + إعادة فهرسة + إعادة بناء رسم الديباجات + خريطة + نشر app + اختبار وظيفيّ شامل."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ingest = H / "ingest_law106.py"; js = H / "law106_2013_parsed.json"; px = H / "preamble_xref.py"
b_ing, b_js, b_app, b_px = enc(ingest), enc(js), enc(APP), enc(px)
s_ing, s_js, s_app, s_px = sha(ingest), sha(js), sha(APP), sha(px)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/amlplus_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law106.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law106_2013_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_law106.py" "$TMP/law106_2013_parsed.json" "$TMP/app.py" "$TMP/preamble_xref.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_law106.py',encoding='utf-8').read()); print('ingest OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/preamble_xref.py',encoding='utf-8').read()); print('px OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/law106_2013_parsed.json',encoding='utf-8')); assert len(d['articles'])==46, len(d['articles']); b=json.dumps(d,ensure_ascii=False); assert chr(0xFFFD) not in b; assert '_' not in b; print('json OK: مواد',len(d['articles']),'— لا � ولا _')"
for tok in _aml_bank_ids _reverse_predicate_ids _preamble_related_ids _draft_bundles_inner; do
  grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok مفقود"; exit 1; }}
done
cd /opt/LegalMind
echo "== إعادة إدخال 106/2013 المُصحَّح + الديباجة المُثراة =="; "$PYA" "$TMP/ingest_law106.py" "$TMP/law106_2013_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم علاقات الديباجات (بعد إثراء ديباجة 106) =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.amlplus"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.amlplus" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ شامل =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def has(q,branch="جزائي"): return set(m._draft_bundles("استشارة",q,[],None,branch))
# (أ) حظر إفصاح التنبيه + التزامات المؤسسات
a=has("هل يجوز للبنك تحذير العميل بأنه تم الإخطار عن معاملته المشبوهة؟ وما حكم الاحتفاظ بالسجلات؟")
print("  (أ) حظر التنبيه/الالتزامات m12/m13/m35:", all(("legis-106-2013-"+x) in a for x in ("m12","m13","m35")))
assert all(("legis-106-2013-"+x) in a for x in ("m12","m13","m35"))
# (ب) جسر الجريمة الأصلية المُعمَّم: نصب/تزوير + سرقة/خيانة أمانة
b=has("متهم بغسل أموال متحصلة من جرائم نصب واحتيال وتزوير محررات")
print("  (ب) نصب/تزوير 16/1960 m231/m257:", "legis-16-1960-m231" in b and "legis-16-1960-m257" in b)
assert "legis-16-1960-m231" in b and "legis-16-1960-m257" in b
b2=has("غسل عائدات سرقة وخيانة أمانة")
print("  (ب) سرقة/خيانة أمانة 16/1960 m217/m240:", "legis-16-1960-m217" in b2 and "legis-16-1960-m240" in b2)
assert "legis-16-1960-m217" in b2 and "legis-16-1960-m240" in b2
# (ج١) الجسر العكسيّ: جريمة أصلية + قرينة ماليّة ⇒ 106 م2/م28 ؛ ولا يُفعَّل لجريمةٍ بلا قرينة ماليّة
c=has("حقق المتهم عائدات ضخمة من الاتجار بالمخدرات وأخفى الأموال")
print("  (ج١) عكسيّ: مخدرات+قرينة ماليّة ⇒ 106 م2/م28:", "legis-106-2013-m2" in c and "legis-106-2013-m28" in c)
assert "legis-106-2013-m2" in c and "legis-106-2013-m28" in c
c2=has("عقوبة تعاطي المخدرات للحدث")
print("  (ج١) لا تفعيل عكسيّ لتعاطٍ بلا قرينة ماليّة:", "legis-106-2013-m2" not in c2)
assert "legis-106-2013-m2" not in c2
# (ج٢) رسم الديباجات: سؤالٌ يسمّي 106/2013 ⇒ يستحضر ديباجاتِ قوانين متّصلة مُدخَلة (16/1960، 1/1993، 7/2010…)
d=has("ما القوانين المتصلة بالقانون رقم 106 لسنة 2013 في شأن غسل الأموال؟","استشارة")
rel=[x for x in d if x.endswith("-preamble")]
print("  (ج٢) ديباجات متّصلة مُستحضَرة:", sorted(rel)[:8])
assert "legis-106-2013-preamble" in d, "ديباجة القانون المحوريّ غائبة!"
assert any(x in d for x in ("legis-16-1960-preamble","legis-1-1993-preamble","legis-7-2010-preamble")), "لم تُستحضَر ديباجاتُ القوانين المتّصلة!"
# سلامة النصّ المُصحَّح
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-106-2013-m14'"); t14=cur.fetchone()[0]
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-106-2013-preamble'"); tp=cur.fetchone()[0]
ok14=("معايير" in t14 and "خبرة" in t14 and "بتوفير" in t14 and "معاير" not in t14)
okp=("سند الإصدار" in tp and "رقم 16 لسنة 1960" in tp)
print("  م14 مُصحَّح:", ok14, "| الديباجة مُثراة بسند الإصدار:", okp)
assert ok14 and okp
print("  ✓ التصحيح + (أ) + (ب) + (ج١) الجسر العكسيّ + (ج٢) رسم الديباجات — كلّها تعمل")
PY2
echo '=== تم: تصحيح 106/2013 + محفّز الالتزامات/حظر التنبيه + تعميم جسر الجريمة الأصلية + جسرٌ عكسيّ + تفعيل رسم الديباجات ==='
"""
(H / "run_amlplus.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_amlplus.sh && sha256sum run_amlplus.sh"
(H / "DEPLOY_amlplus.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app); print("px sha:", s_px)
print("run_amlplus.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
