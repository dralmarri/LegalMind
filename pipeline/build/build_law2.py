#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني نشرَ القانون 2/2016 (هيئة مكافحة الفساد + الذمة المالية): مُدخِل + JSON نظيف + app.py
(بخمس حزم استرجاع). خطوات الخادم: تحقّق البصمات/الصياغة/عدد المواد → إدخال (تجريبي ثمّ فعلي)
→ إعادة فهرسة كاملة → تحديث خريطة الإحالات (تُغلق إحالة م59/م60 من 31/1970 إلى م22)
→ نشر app.py + إعادة تشغيل + اختبار وظيفيّ يتأكّد من تفعيل الحزم واستحضار م22."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ingest = H / "ingest_law2.py"
js = H / "law2_parsed.json"
b_ing, b_js, b_app = enc(ingest), enc(js), enc(APP)
s_ing, s_js, s_app = sha(ingest), sha(js), sha(APP)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law2_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law2.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law2_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="
echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"
sha256sum "$TMP/ingest_law2.py" "$TMP/law2_parsed.json" "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_law2.py',encoding='utf-8').read()); print('ingest OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/law2_parsed.json',encoding='utf-8')); assert len(d['articles'])==65, len(d['articles']); print('json OK: مواد',len(d['articles']))"
"$PYA" -c "import json; d=json.load(open('$TMP/law2_parsed.json',encoding='utf-8')); t=d['articles']['m45']['text']; assert '15، 16، 26، 29، 34' in t, 'تصحيح م45 مفقود'; assert chr(0xFFFD) not in json.dumps(d,ensure_ascii=False), 'محرف بديل متبقٍّ'; print('م45 مصحّحة + لا محارف بديلة')"
grep -q "legis-2-2016" "$TMP/app.py" && echo "حزم 2/2016 موجودة في app.py" || {{ echo "خطأ: الحزم مفقودة"; exit 1; }}
cd /opt/LegalMind
echo "== إدخال (تجريبي) =="
"$PYA" "$TMP/ingest_law2.py" "$TMP/law2_parsed.json" --dry-run
echo "== إدخال (فعلي) =="
"$PYA" "$TMP/ingest_law2.py" "$TMP/law2_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== خريطة الإحالات (تُغلق 31/1970 م59/م60 → 2/2016 م22) =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json 2>/dev/null | grep -E "legis-2-2016|إجمالي|محفوظة" || echo "(تعذّر عرض تفاصيل الخريطة)"
"$PYA" -c "import json; m=json.load(open('/opt/LegalMind/admin/xref_map.json',encoding='utf-8')); hits=[s for s,t in m.items() if any('legis-2-2016' in x for x in t)]; print('مصادر تُحيل إلى 2/2016:', hits[:10] or 'لا')"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law2"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law2" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ (تفعيل حزم 2/2016 في الفرع الجزائي) =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
for facts in [
  "موظف عام لم يقدم إقرار الذمة المالية للهيئة العامة لمكافحة الفساد",
  "شخص أبلغ عن جريمة فساد ويطلب الحماية من هيئة نزاهة"]:
    ids=m._draft_bundles("استشارة",facts,[],None,"جزائي")
    n=[i for i in ids if i.startswith("legis-2-2016")]
    print("  «"+facts[:40]+"…» → مواد 2/2016:", len(n), "| م22:", "legis-2-2016-m22" in ids)
    assert "legis-2-2016-m22" in ids, "م22 لم تُستحضَر!"
print("  ✓ الحزم فعّالة وم22 حاضرة")
PY2
echo '=== تم: إدخال القانون 2/2016 (هيئة مكافحة الفساد + الذمة المالية) + 5 حزم + إغلاق إحالة 31/1970 ==='
"""
(H / "run_law2.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law2.sh && sha256sum run_law2.sh"
(H / "DEPLOY_law2.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing)
print("json   sha:", s_js)
print("app    sha:", s_app)
print("run_law2.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
