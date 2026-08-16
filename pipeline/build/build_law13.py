#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني نشرَ قانون الأسلحة والذخائر 13/1991: مُدخِل + JSON نظيف + app.py (بحزم أسلحة + محفّز _weapons_ids
+ إشارات مصنّف). إدخال + إعادة فهرسة كاملة + خريطة إحالات + نشر app.py + اختبار وظيفيّ."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ingest = H / "ingest_law13.py"; js = H / "law13_parsed.json"
b_ing, b_js, b_app = enc(ingest), enc(js), enc(APP)
s_ing, s_js, s_app = sha(ingest), sha(js), sha(APP)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law13_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law13.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law13_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"
sha256sum "$TMP/ingest_law13.py" "$TMP/law13_parsed.json" "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_law13.py',encoding='utf-8').read()); print('ingest OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/law13_parsed.json',encoding='utf-8')); assert len(d['articles'])==32, len(d['articles']); assert chr(0xFFFD) not in json.dumps(d,ensure_ascii=False); print('json OK: كائنات',len(d['articles']),'+ لا محارف بديلة')"
grep -q "legis-13-1991" "$TMP/app.py" && echo "حزم 13/1991 موجودة" || {{ echo "خطأ"; exit 1; }}
grep -q "_weapons_ids" "$TMP/app.py" && echo "محفّز الأسلحة موجود" || {{ echo "خطأ"; exit 1; }}
cd /opt/LegalMind
echo "== إدخال (تجريبي) =="; "$PYA" "$TMP/ingest_law13.py" "$TMP/law13_parsed.json" --dry-run | head -8
echo "== إدخال (فعلي) =="; "$PYA" "$TMP/ingest_law13.py" "$TMP/law13_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law13"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law13" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ (حزم الأسلحة + المصنّف + المكرر) =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
det=m._resolve_branch(None, m._draft_norm_ar("ضبط شخص يحوز سلاحاً غير مرخص ما العقوبة المقررة"))
print("  تصنيف «حيازة سلاح غير مرخص»:",det); assert det=="جزائي","المصنّف لم يوجّه للجزائي"
ids=m._draft_bundles("استشارة","شخص ضُبط يحوز مسدساً غير مرخص وأسلحة بيضاء وقام بإيقاع الروع في مكان عام، ما العقوبات والمصادرة",[],None,"جزائي")
need=[("legis-13-1991-m2","حظر الحيازة بلا ترخيص"),("legis-13-1991-m21","عقوبة الحيازة"),
      ("legis-13-1991-m21-mukarrar","عقوبة الأسلحة البيضاء/الهوائية"),
      ("legis-13-1991-m22-mukarrar","جريمة إيقاع الروع"),("legis-13-1991-m1","التعريفات")]
for k,lbl in need:
    print("  "+lbl+" ("+k+"):", k in ids)
assert all(k in ids for k,_ in need), "بعض مواد الأسلحة الحاكمة غائبة!"
print("  ✓ حزم الأسلحة فعّالة، والمكرّرات (م21/م22 مكرر) حاضرة، والمصنّف يوجّه للجزائي")
PY2
echo '=== تم: إدخال قانون الأسلحة والذخائر 13/1991 — 33 كائنًا + 4 حزم + محفّز المكرر + إشارات مصنّف ==='
"""
(H / "run_law13.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law13.sh && sha256sum run_law13.sh"
(H / "DEPLOY_law13.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app)
print("run_law13.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
