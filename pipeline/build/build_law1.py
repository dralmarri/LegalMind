#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني نشرَ قانون حماية الأموال العامة 1/1993: مُدخِل + JSON نظيف + app.py (بـ6 حزم مال عام + محفّز
_publicfunds_ids + إشارات مصنّف). إدخال + إعادة فهرسة كاملة + خريطة إحالات + نشر app.py + اختبار وظيفيّ."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ingest = H / "ingest_law1.py"; js = H / "law1_1993_parsed.json"
b_ing, b_js, b_app = enc(ingest), enc(js), enc(APP)
s_ing, s_js, s_app = sha(ingest), sha(js), sha(APP)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law1_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law1.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law1_1993_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"
sha256sum "$TMP/ingest_law1.py" "$TMP/law1_1993_parsed.json" "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_law1.py',encoding='utf-8').read()); print('ingest OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/law1_1993_parsed.json',encoding='utf-8')); assert len(d['articles'])==33, len(d['articles']); assert chr(0xFFFD) not in json.dumps(d,ensure_ascii=False); print('json OK: كائنات',len(d['articles']),'+ لا محارف بديلة')"
grep -q "legis-1-1993" "$TMP/app.py" && echo "حزم 1/1993 موجودة" || {{ echo "خطأ"; exit 1; }}
grep -q "_publicfunds_ids" "$TMP/app.py" && echo "محفّز المال العام موجود" || {{ echo "خطأ"; exit 1; }}
cd /opt/LegalMind
echo "== إدخال (تجريبي) =="; "$PYA" "$TMP/ingest_law1.py" "$TMP/law1_1993_parsed.json" --dry-run | head -8
echo "== إدخال (فعلي) =="; "$PYA" "$TMP/ingest_law1.py" "$TMP/law1_1993_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law1"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law1" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ (حزم المال العام + المصنّف + م21 مكرر) =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
det=m._resolve_branch(None, m._draft_norm_ar("موظف عام اختلس أموالا من المال العام وقُدّم للنيابة"))
print("  تصنيف «اختلاس المال العام»:",det); assert det=="جزائي","المصنّف لم يوجّه للجزائي"
ids=m._draft_bundles("استشارة","موظف عام اختلس أموالا عامة مسلمة إليه بسبب وظيفته، ما العقوبة وهل تسقط الدعوى بالتقادم وما حكم رد المال",[],None,"جزائي")
need=[("legis-1-1993-m9","الاختلاس"),("legis-1-1993-m16","العزل والرد وغرامة الضعف"),
      ("legis-1-1993-m21-mukarrar","عدم سقوط الدعوى بالتقادم"),("legis-1-1993-m22","رد المال رغم الانقضاء")]
for k,lbl in need:
    print("  "+lbl+" ("+k+"):", k in ids)
assert all(k in ids for k,_ in need), "بعض مواد المال العام الحاكمة غائبة!"
print("  ✓ حزم المال العام فعّالة، وم21 مكرر (عدم التقادم) حاضرة، والمصنّف يوجّه للجزائي")
PY2
echo '=== تم: إدخال قانون حماية الأموال العامة 1/1993 — 34 كائنًا + 6 حزم + محفّظ عدم التقادم + إشارات مصنّف ==='
"""
(H / "run_law1.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law1.sh && sha256sum run_law1.sh"
(H / "DEPLOY_law1.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app)
print("run_law1.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
