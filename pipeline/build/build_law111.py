#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني نشرَ قانون الأحداث 111/2015: مُدخِل + JSON نظيف + app.py (بخمس حزم أحداث + إشارات مصنّف).
إدخال + إعادة فهرسة كاملة + خريطة إحالات + نشر app.py + اختبار وظيفيّ (تفعيل حزم الأحداث)."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ingest = H / "ingest_law111.py"; js = H / "law111_parsed.json"
b_ing, b_js, b_app = enc(ingest), enc(js), enc(APP)
s_ing, s_js, s_app = sha(ingest), sha(js), sha(APP)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law111_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law111.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law111_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"
sha256sum "$TMP/ingest_law111.py" "$TMP/law111_parsed.json" "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_law111.py',encoding='utf-8').read()); print('ingest OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/law111_parsed.json',encoding='utf-8')); assert len(d['articles'])==73, len(d['articles']); assert chr(0xFFFD) not in json.dumps(d,ensure_ascii=False); print('json OK: كائنات',len(d['articles']),'+ لا محارف بديلة')"
grep -q "legis-111-2015" "$TMP/app.py" && echo "حزم 111/2015 موجودة" || {{ echo "خطأ"; exit 1; }}
cd /opt/LegalMind
echo "== إدخال (تجريبي) =="; "$PYA" "$TMP/ingest_law111.py" "$TMP/law111_parsed.json" --dry-run | head -6
echo "== إدخال (فعلي) =="; "$PYA" "$TMP/ingest_law111.py" "$TMP/law111_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law111"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law111" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ (حزم الأحداث + المصنّف) =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
# المصنّف يوجّه سؤال الأحداث إلى الفرع الجزائيّ
det=m._resolve_branch(None, m._draft_norm_ar("حدث عمره 16 سنة ارتكب سرقة وقُدّم لمحكمة الأحداث"))
print("  تصنيف «حدث ارتكب سرقة»:",det)
assert det=="جزائي", "المصنّف لم يوجّه سؤال الأحداث للجزائي"
for facts,need in [("حدث عمره 16 ارتكب سرقة ما التدابير والعقوبة","legis-111-2015-m15"),
                   ("محاكمة حدث أمام محكمة الأحداث والطعن","legis-111-2015-m33"),
                   ("الحبس الاحتياطي للحدث","legis-111-2015-m18")]:
    ids=m._draft_bundles("استشارة",facts,[],None,"جزائي")
    n=[i for i in ids if i.startswith("legis-111-2015")]
    print("  «"+facts[:34]+"…» → مواد 111/2015:",len(n),"|",need+":",need in ids)
    assert n, "لم تُفعَّل حزم الأحداث!"
print("  ✓ حزم الأحداث فعّالة والمصنّف يوجّه للجزائي")
PY2
echo '=== تم: إدخال القانون 111/2015 (الأحداث) — 74 كائنًا + 5 حزم + إشارات مصنّف ==='
"""
(H / "run_law111.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law111.sh && sha256sum run_law111.sh"
(H / "DEPLOY_law111.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app)
print("run_law111.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
