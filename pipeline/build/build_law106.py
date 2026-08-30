#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني نشرَ قانون مكافحة غسل الأموال وتمويل الإرهاب 106/2013: مُدخِل + JSON نظيف (مُنظَّف آليًّا من
تلفٍ حتميّ) + app.py (بـ6 حزم + محفّز _aml_ids + إشارات مصنّف). إدخال + إعادة فهرسة + خريطة + اختبار."""
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
TMP=/tmp/law106_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law106.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law106_2013_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"
sha256sum "$TMP/ingest_law106.py" "$TMP/law106_2013_parsed.json" "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_law106.py',encoding='utf-8').read()); print('ingest OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/law106_2013_parsed.json',encoding='utf-8')); assert len(d['articles'])==46, len(d['articles']); assert chr(0xFFFD) not in json.dumps(d,ensure_ascii=False); print('json OK: مواد',len(d['articles']),'+ لا محارف بديلة')"
grep -q "legis-106-2013" "$TMP/app.py" && echo "حزم 106/2013 موجودة" || {{ echo "خطأ"; exit 1; }}
grep -q "_aml_ids" "$TMP/app.py" && echo "محفّز غسل الأموال موجود" || {{ echo "خطأ"; exit 1; }}
cd /opt/LegalMind
echo "== إدخال (تجريبي) =="; "$PYA" "$TMP/ingest_law106.py" "$TMP/law106_2013_parsed.json" --dry-run | head -6
echo "== إدخال (فعلي) =="; "$PYA" "$TMP/ingest_law106.py" "$TMP/law106_2013_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law106"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law106" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ (حزم غسل الأموال + المصنّف + المحفّز) =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
det=m._resolve_branch(None, m._draft_norm_ar("متهم بغسل أموال متحصلة من جريمة اتجار وقُدّم للنيابة"))
print("  تصنيف «غسل الأموال»:",det); assert det=="جزائي","المصنّف لم يوجّه للجزائي"
ids=m._draft_bundles("استشارة","متهم بغسل الأموال المتحصلة من جريمة، ما العقوبة وهل تصادر الأموال",[],None,"جزائي")
need=[("legis-106-2013-m2","جريمة غسل الأموال"),("legis-106-2013-m28","عقوبة الغسل ≤10 سنوات"),
      ("legis-106-2013-m29","عقوبة التمويل ≤15 سنة"),("legis-106-2013-m30","التشديد"),
      ("legis-106-2013-m32","الشخص الاعتباري"),("legis-106-2013-m40","المصادرة")]
for k,lbl in need:
    print("  "+lbl+" ("+k+"):", k in ids)
assert all(k in ids for k,_ in need), "بعض مواد 106/2013 الحاكمة غائبة!"
n=m._draft_bundles("استشارة","عقد إيجار شقة",[],None,"مدني")
assert not [i for i in n if i.startswith("legis-106-2013")], "تفعيل زائف!"
print("  ✓ حزم غسل الأموال فعّالة (م2/م28/م29/م30/م32/م40)، والمصنّف يوجّه للجزائي")
PY2
echo '=== تم: إدخال قانون مكافحة غسل الأموال وتمويل الإرهاب 106/2013 — 47 كائنًا + 6 حزم + محفّز (نُظّف آليًّا) ==='
"""
(H / "run_law106.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law106.sh && sha256sum run_law106.sh"
(H / "DEPLOY_law106.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app)
print("run_law106.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
