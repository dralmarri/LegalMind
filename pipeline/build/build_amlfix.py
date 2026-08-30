#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ مُجمَّع: (تصحيح) إعادة إدخال 106/2013 بعد تنظيف الحروف الساقطة في 4 مواد إجرائية (م5/م10/م14/م15)
+ (أ) محفّز التزامات المؤسسات المالية وحظر إفصاح التنبيه (م5-م15/م34-م36) + (ب) تعميم جسر الجريمة الأصلية
(سرقة/نصب/خيانة أمانة/تزوير من 16/1960). إعادة إدخال + إعادة فهرسة + خريطة + نشر app + اختبار وظيفيّ."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ingest = H / "ingest_law106.py"; js = H / "law106_2013_parsed.json"
b_ing, b_js, b_app = enc(ingest), enc(js), enc(APP)
s_ing, s_js, s_app = sha(ingest), sha(js), sha(APP)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/amlfix_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law106.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law106_2013_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"
sha256sum "$TMP/ingest_law106.py" "$TMP/law106_2013_parsed.json" "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_law106.py',encoding='utf-8').read()); print('ingest OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/law106_2013_parsed.json',encoding='utf-8')); assert len(d['articles'])==46, len(d['articles']); b=json.dumps(d,ensure_ascii=False); assert chr(0xFFFD) not in b; assert '_' not in b; print('json OK: مواد',len(d['articles']),'— لا � ولا _')"
grep -q "_aml_bank_ids" "$TMP/app.py" && echo "محفّز التزامات المؤسسات موجود" || {{ echo "خطأ"; exit 1; }}
cd /opt/LegalMind
echo "== إعادة إدخال 106/2013 المُصحَّح (م5/م10/م14/م15) =="; "$PYA" "$TMP/ingest_law106.py" "$TMP/law106_2013_parsed.json"
echo "== إعادة الفهرسة الكاملة (لتحديث متجهات المواد المُصحَّحة) =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.amlfix"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.amlfix" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
# (أ) حظر إفصاح التنبيه + التزامات المؤسسات (بلا عبارة «غسل الأموال» صراحةً)
ids=m._draft_bundles("استشارة","هل يجوز للبنك تحذير العميل بأنه تم الإخطار عن معاملته المشبوهة؟ وما حكم الاحتفاظ بالسجلات؟",[],None,"جزائي")
need_a=["legis-106-2013-m12","legis-106-2013-m13","legis-106-2013-m35"]
print("  (أ) حظر التنبيه/الالتزامات:", {{k:(k in ids) for k in need_a}})
assert all(k in ids for k in need_a), "عنقود حظر التنبيه غائب!"
# (ب) تعميم الجريمة الأصلية: نصب/احتيال/تزوير من 16/1960
ids2=m._draft_bundles("استشارة","متهم بغسل أموال متحصلة من جرائم نصب واحتيال وتزوير محررات",[],None,"جزائي")
need_b=["legis-106-2013-m2","legis-16-1960-m231","legis-16-1960-m257"]
print("  (ب) جسر النصب/التزوير:", {{k:(k in ids2) for k in need_b}})
assert all(k in ids2 for k in need_b), "جسر النصب/التزوير غائب!"
# سرقة/خيانة أمانة
ids3=m._draft_bundles("استشارة","غسل عائدات سرقة وخيانة أمانة",[],None,"جزائي")
print("  (ب) جسر السرقة/خيانة الأمانة:", {{k:(k in ids3) for k in ("legis-16-1960-m217","legis-16-1960-m240")}})
assert "legis-16-1960-m217" in ids3, "جسر السرقة غائب!"
# لا تفعيل زائف: نصب بلا غسل لا يستدعي الجسر (لكن قد تستدعيه حزمة الجزاء العامة — نتحقق من عدم استدعاء 106)
ids4=m._draft_bundles("استشارة","جريمة نصب واحتيال بلا أي غسل أموال",[],None,"جزائي")
print("  عدم تفعيل غسل لجريمةٍ مجرّدة:", "legis-106-2013-m2" not in ids4)
# سلامة النصّ المُصحَّح: م14 يذكر «معايير» و«خبرة» و«بتوفير» بلا حروف ساقطة
import json, psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as c, c.cursor() as cur:
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-106-2013-m14'")
    t14=cur.fetchone()[0]
ok14=("معايير" in t14 and "خبرة" in t14 and "بتوفير" in t14 and "معاير" not in t14 and "خرة " not in t14)
print("  م14 مُصحَّح (معايير/خبرة/بتوفير، لا حروف ساقطة):", ok14)
assert ok14, "بقي تلفٌ في م14!"
print("  ✓ التصحيح + المحفّز + الجسر المُعمَّم يعملون")
PY2
echo '=== تم: تصحيح 106/2013 (4 مواد) + محفّز التزامات المؤسسات/حظر التنبيه + تعميم جسر الجريمة الأصلية ==='
"""
(H / "run_amlfix.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_amlfix.sh && sha256sum run_amlfix.sh"
(H / "DEPLOY_amlfix.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app)
print("run_amlfix.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
