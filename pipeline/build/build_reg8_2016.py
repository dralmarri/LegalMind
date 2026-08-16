#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ اللائحة التنفيذية 100/2016 (رفيقةُ قانون تنظيم الإعلام الإلكتروني 8/2016): مُدخِل (22 كائنًا: ديباجة +
مادتا إصدار + 19 مادة، منقولةٌ حرفًا بحرف من صور الجريدة) + app.py (توسيعُ محفّز _emedia_ids ليُلحق مواد
اللائحة بعناقيد القانون: الترخيص/الكفالة/التجديد/النقل/الإلغاء رم7-رم18، والاستطلاعات رم6، والدعم رم4).
إدخال + إعادة فهرسة + رسم ديباجات + نشر + تحقّق وظيفيّ. نسخةٌ احتياطية + استرجاعٌ تلقائيّ."""
import base64, gzip, hashlib, pathlib, subprocess
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")


def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


ingest = H / "ingest_reg8_2016.py"
b_ing, b_app = enc(ingest), enc(APP)
s_ing, s_app = sha(ingest), sha(APP)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/reg8_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_reg8_2016.py"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "app: {s_app}"
sha256sum "$TMP/ingest_reg8_2016.py" "$TMP/app.py"
for f in ingest_reg8_2016.py app.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
for tok in regl-8-2016 _emedia_ids "R % 12" "R % 6"; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
cd /opt/LegalMind
echo "== إدخال اللائحة 100/2016 (فعليّ) =="; "$PYA" "$TMP/ingest_reg8_2016.py"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم الديباجات =="
"$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null 2>&1 && echo "رسم الديباجات محدّث" || echo "تنبيه: تعذّر تحديث رسم الديباجات"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.reg8"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.reg8" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q): return set(m._draft_bundles("استشارة",q,[],None,None))
a=ids("ما قيمة الكفالة المالية اللازمة لترخيص موقع إلكتروني إخباري وما مدة الترخيص وكيف يُجدَّد؟")
assert "regl-8-2016-m12" in a and "regl-8-2016-m15" in a, "الكفالة/المدة من اللائحة لم تُستحضَر"
assert "legis-8-2016-m6" in a, "الترخيص من القانون لم يُستحضَر"
print("  ✓ الكفالة 500 دينار (رم12) + مدة 10 سنوات والتجديد (رم15) + الترخيص القانوني (م6)")
b=ids("هل يجوز لموقع إلكتروني إجراء استطلاع رأي حول انتخابات مجلس الأمة؟")
assert "regl-8-2016-m6" in b, "ضوابط الاستطلاعات (رم6) لم تُستحضَر"
print("  ✓ ضوابط استطلاعات الرأي (رم6) — تنفرد بها اللائحة")
c=ids("ما إجراءات نقل ترخيص الوسيلة الإعلامية الإلكترونية للورثة وإلغاؤه؟")
assert "regl-8-2016-m16" in c and "regl-8-2016-m18" in c, "النقل/الإلغاء الإجرائيّ (رم16/رم18) لم يُستحضَر"
print("  ✓ نقل الترخيص للورثة (رم16) وإلغاؤه (رم18)")
# إصلاح بوابة الاختصاص في القانون 8/2016 (كان الاختبار السابق يسقط على «أي محكمة تختص»):
e=ids("أي محكمة تختص بنظر جريمة إنشاء موقع إلكتروني بدون ترخيص؟ وما العقوبة وهل يجوز الحجب؟")
assert "legis-8-2016-m22" in e and "legis-8-2016-m19" in e, "الاختصاص (م22)/العقوبة (م19) لم تُستحضَر"
print("  ✓ إصلاح بوابة الاختصاص: دائرة الجنايات (م22) + العقوبة والحجب (م19) على «أي محكمة تختص»")
# لا انحدار: سؤالٌ مروريّ لا يجرّ اللائحة الإعلامية
d=ids("ما عقوبة القيادة برخصة سيارة منتهية؟")
assert not any(x.startswith("regl-8-2016") for x in d), "تسرّبت اللائحة الإعلامية لسؤال مروريّ"
print("  ✓ لا انحدار: سؤال المرور لا يجرّ لائحة الإعلام الإلكتروني")
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'regl-8-2016-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects"); tot=cur.fetchone()[0]
assert n==22, "عدد كائنات اللائحة = %s (المتوقع 22)"%n
print("  ✓ العدّ: اللائحة 100/2016 =",n,"| الإجمالي =",tot)
print("  === تمّ =====")
PY2
echo '=== تم: إدخال اللائحة التنفيذية 100/2016 (رفيقةُ 8/2016) — 22 كائنًا + توسيع محفّز _emedia_ids ==='
"""
(H / "run_reg8_2016.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_reg8_2016.sh && sha256sum run_reg8_2016.sh"
(H / "DEPLOY_reg8_2016.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("app sha:", s_app)
print("run_reg8_2016.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; 2 shas embedded")
r = subprocess.run(["bash", "-n", str(H / "run_reg8_2016.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
