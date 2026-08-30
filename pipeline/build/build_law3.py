#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني نشرَ القانون 21/2015 (حقوق الطفل): مُدخِل + JSON نظيف + app.py (بعشر حزم استرجاع، فرع جزائي).
خطوات الخادم: تحقّق البصمات/الصياغة/عدد المواد (97) → إدخال (تجريبي ثمّ فعلي) → إعادة فهرسة كاملة
→ تحديث خريطة الإحالات → نشر app.py + إعادة تشغيل + اختبار وظيفيّ (تفعيل حزم الطفل واستحضار العقوبات)."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ingest = H / "ingest_law3.py"; js = H / "law3_parsed.json"
b_ing, b_js, b_app = enc(ingest), enc(js), enc(APP)
s_ing, s_js, s_app = sha(ingest), sha(js), sha(APP)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law3_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law3.py"
printf '%s' '{b_js}'  | base64 -d | gunzip > "$TMP/law3_parsed.json"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="
echo "ingest: {s_ing}"; echo "json: {s_js}"; echo "app: {s_app}"
sha256sum "$TMP/ingest_law3.py" "$TMP/law3_parsed.json" "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/ingest_law3.py',encoding='utf-8').read()); print('ingest OK')"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app OK')"
"$PYA" -c "import json; d=json.load(open('$TMP/law3_parsed.json',encoding='utf-8')); assert len(d['articles'])==97, len(d['articles']); assert chr(0xFFFD) not in json.dumps(d,ensure_ascii=False); print('json OK: مواد',len(d['articles']),'+ لا محارف بديلة')"
grep -q "legis-21-2015" "$TMP/app.py" && echo "حزم 21/2015 موجودة في app.py" || {{ echo "خطأ: الحزم مفقودة"; exit 1; }}
cd /opt/LegalMind
echo "== إدخال (تجريبي) =="
"$PYA" "$TMP/ingest_law3.py" "$TMP/law3_parsed.json" --dry-run
echo "== إدخال (فعلي) =="
"$PYA" "$TMP/ingest_law3.py" "$TMP/law3_parsed.json"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر تحديث الخريطة"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law3"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law3" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ (تفعيل حزم الطفل في الفرعين: جزائي + أحوال) =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
# الفرع الجزائي: العقوبات والحماية والعمل
for facts,need in [("رجل اعتدى بالضرب على طفل وأصابه ما العقوبة","legis-21-2015-m94"),
                   ("صاحب محل شغّل طفلا عمره 12 سنة هل يعاقب","legis-21-2015-m85"),
                   ("طفل معرض للخطر بسبب إهمال والديه ما دور مراكز حماية الطفولة","legis-21-2015-m77")]:
    ids=m._draft_bundles("استشارة",facts,[],None,"جزائي")
    n=[i for i in ids if i.startswith("legis-21-2015")]
    print("  [جزائي] «"+facts[:30]+"…» → مواد 21/2015:", len(n), "| "+need+":", need in ids)
    assert n, "لم تُفعَّل أيّ حزمة طفل في الفرع الجزائي!"
# الفرع الأحوال: الحقوق والنسب (مزدوج مثل العنف الأسري)
ids=m._draft_bundles("استشارة","نسب الطفل وحقه في الاسم وإثبات بنوته لوالديه",[],None,"أحوال شخصية")
n=[i for i in ids if i.startswith("legis-21-2015")]
print("  [أحوال] «نسب الطفل وحقه في الاسم…» → مواد 21/2015:", len(n))
assert n, "لم تُفعَّل حزم الطفل في فرع الأحوال!"
print("  ✓ حزم حقوق الطفل فعّالة في الفرعين")
# الجسر الأسريّ–الجزائيّ
def _has(ids,p): return [i for i in ids if i.startswith(p)]
V="زوج يضرب زوجته أمام أطفالها ويهددها بالقتل"
jz=m._draft_bundles("استشارة",V,[],None,"جزائي")
print("  [الجسر/جزائي] جرائم 16/1960:",len(_has(jz,"legis-16-1960")),"| آثار أسرية 51/1984:",len(_has(jz,"legis-51-1984")))
assert _has(jz,"legis-51-1984"), "الجسر: الفرع الجزائيّ لم يجلب الآثار الأسرية!"
ah=m._draft_bundles("استشارة",V,[],None,"أحوال شخصية")
print("  [الجسر/أحوال] جرائم 16/1960:",len(_has(ah,"legis-16-1960")),"| أحوال 51/1984:",len(_has(ah,"legis-51-1984")))
assert "legis-16-1960-m160" in ah, "الجسر: فرع الأحوال لم يجلب جريمة الضرب (م160)!"
rb=m._draft_bundles("استشارة","موظف قبل رشوة",[],None,"جزائي")
assert not _has(rb,"legis-51-1984"), "الجسر اشتعل خطأً على قضية رشوة!"
print("  ✓ الجسر الأسريّ–الجزائيّ يصل الفرعين ولا يشتعل على غير النِّزاع الأسريّ")
PY2
echo '=== تم: 21/2015 (حقوق الطفل) + توصيل مزدوج + الجسر الأسريّ–الجزائيّ ==='
"""
(H / "run_law3.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law3.sh && sha256sum run_law3.sh"
(H / "DEPLOY_law3.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("json sha:", s_js); print("app sha:", s_app)
print("run_law3.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
