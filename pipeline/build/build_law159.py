#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني نشرَ قانون مكافحة المخدرات 159/2025 (المواد فقط، دون الجداول): مُدخِل + JSON + app.py
(بـ9 حزم مخدرات + محفّز _drugs_ids + إشارات مصنّف). إدخال + إعادة فهرسة + خريطة إحالات + اختبار وظيفيّ."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ingest = H / "ingest_law159.py"; js = H / "law159_2025_parsed.json"
b_ing, b_js, b_app = enc(ingest), enc(js), enc(APP)
s_ing, s_js, s_app = sha(ingest), sha(js), sha(APP)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law159_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law159.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law159_2025_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"
sha256sum "$TMP/ingest_law159.py" "$TMP/law159_2025_parsed.json" "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_law159.py',encoding='utf-8').read()); print('ingest OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/law159_2025_parsed.json',encoding='utf-8')); assert len(d['articles'])==85, len(d['articles']); assert chr(0xFFFD) not in json.dumps(d,ensure_ascii=False); print('json OK: مواد',len(d['articles']),'+ لا محارف بديلة')"
grep -q "legis-159-2025" "$TMP/app.py" && echo "حزم 159/2025 موجودة" || {{ echo "خطأ"; exit 1; }}
grep -q "_drugs_ids" "$TMP/app.py" && echo "محفّز المخدرات موجود" || {{ echo "خطأ"; exit 1; }}
cd /opt/LegalMind
echo "== إدخال (تجريبي) =="; "$PYA" "$TMP/ingest_law159.py" "$TMP/law159_2025_parsed.json" --dry-run | head -6
echo "== إدخال (فعلي) =="; "$PYA" "$TMP/ingest_law159.py" "$TMP/law159_2025_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law159"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law159" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ (حزم المخدرات + المصنّف + المحفّز) =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
det=m._resolve_branch(None, m._draft_norm_ar("شخص ضُبط بحوزته كمية من الحشيش بقصد الاتجار وقُدّم للنيابة"))
print("  تصنيف «اتجار بالحشيش»:",det); assert det=="جزائي","المصنّف لم يوجّه للجزائي"
ids=m._draft_bundles("استشارة","شخص ضُبط بحوزته مادة مخدرة (حشيش) بقصد الاتجار، ما العقوبة وهل تسقط بالتقادم وهل يُودع للعلاج",[],None,"جزائي")
need=[("legis-159-2025-m42","الاتجار/الجلب — الإعدام أو المؤبد"),("legis-159-2025-m43","الحيازة بقصد الاتجار"),
      ("legis-159-2025-m44","الظروف المشددة — الإعدام"),("legis-159-2025-m49","التعاطي/الاستعمال الشخصي"),
      ("legis-159-2025-m64","بديل الإيداع للعلاج"),("legis-159-2025-m74","عدم سقوط الدعوى بالتقادم (م46/47)")]
for k,lbl in need:
    print("  "+lbl+" ("+k+"):", k in ids)
assert all(k in ids for k,_ in need), "بعض مواد المخدرات الحاكمة غائبة!"
# لا تفعيل زائف
n=m._draft_bundles("استشارة","عقد إيجار شقة سكنية",[],None,"مدني")
assert not [i for i in n if i.startswith("legis-159-2025")], "تفعيل زائف على الإيجار!"
print("  ✓ حزم المخدرات فعّالة (م42-م49 + بدائل العلاج + عدم التقادم)، والمصنّف يوجّه للجزائي")
PY2
echo '=== تم: إدخال قانون مكافحة المخدرات 159/2025 (المواد م1-م84) — 86 كائنًا + 9 حزم + محفّز — دون الجداول ==='
"""
(H / "run_law159.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law159.sh && sha256sum run_law159.sh"
(H / "DEPLOY_law159.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app)
print("run_law159.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
