#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ مُجمَّع (يُغني عن DEPLOY_combo) بإعادة فهرسةٍ واحدة:
  • 91/2013 مكافحة الاتجار بالأشخاص وتهريب المهاجرين (14 مادة + ملاحظة دستورية م13).
  • اللائحة التنفيذية لمكافحة الغش التجاري 106/2021 (regl-20-2019، 18 مادة + 3 إصدار).
  • إصلاح فجوة استرجاع الغش التجاري: _fraud_ids يستحضر القانون 20/2019 كاملًا (بعقوباته م10-م18) + لائحته
    على أيّ مصطلحٍ محوريّ (حزم النطاق كانت تفوّت العقوبات لخصوصية مفاتيحها).
إدخال + إعادة فهرسة + رسم الديباجات + خريطة + نشر app + اختبار وظيفيّ. (20/2019 الأمّ مُدخَلٌ سلفًا — 8191.)"""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

F = {"ing91": H / "ingest_law91.py", "js91": H / "law91_2013_parsed.json",
     "ingR": H / "ingest_reg20.py", "app": APP, "px": H / "preamble_xref.py"}
B = {k: enc(v) for k, v in F.items()}
S = {k: sha(v) for k, v in F.items()}

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/final_deploy; mkdir -p "$TMP"
printf '%s' '{B["ing91"]}' | base64 -d | gunzip > "$TMP/ingest_law91.py"
printf '%s' '{B["js91"]}'  | base64 -d | gunzip > "$TMP/law91_2013_parsed.json"
printf '%s' '{B["ingR"]}'  | base64 -d | gunzip > "$TMP/ingest_reg20.py"
printf '%s' '{B["app"]}'   | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{B["px"]}'    | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="
echo "ing91 {S['ing91']}"; echo "js91 {S['js91']}"; echo "ingR {S['ingR']}"; echo "app {S['app']}"; echo "px {S['px']}"
sha256sum "$TMP/ingest_law91.py" "$TMP/law91_2013_parsed.json" "$TMP/ingest_reg20.py" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law91.py ingest_reg20.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
"$PYA" -c "import json; d=json.load(open('$TMP/law91_2013_parsed.json',encoding='utf-8')); a=d['articles']; assert len(a)==14 and [int(k[1:]) for k in d['order']]==list(range(1,15)); c=' '.join(a.values())+' '+d['preamble_text']; assert chr(0xFFFD) not in c and '_' not in c; assert 'المحكمة الدستورية' in a['m13']; print('91/2013 json OK')"
"$PYA" "$TMP/ingest_reg20.py" --dry-run | grep -E "إجمالي|بديلة|فارغة|مكرّرة"
for tok in _fraud_ids regl-20-2019 legis-91-2013; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
cd /opt/LegalMind
echo "== إدخال 91/2013 =="; "$PYA" "$TMP/ingest_law91.py" "$TMP/law91_2013_parsed.json"
echo "== إدخال اللائحة التنفيذية 106/2021 (regl-20-2019) =="; "$PYA" "$TMP/ingest_reg20.py"
echo "== إعادة الفهرسة الكاملة (مرّة واحدة) =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم الديباجات =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "رسم الديباجات محدّث"
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.final"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.final" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q,b=None): return set(m._draft_bundles("استشارة",q,[],None,b))
# إصلاح فجوة الغش التجاري: العقوبات (م10-م18) تظهر الآن بالصياغة الطبيعية للسؤال + اللائحة
a=ids("ما الجرائم والعقوبات المقررة في الغش التجاري، وأثر الموازين والملصقات المزيّفة، وحكم العَود، ومصادرة البضائع المغشوشة؟")
need=["legis-20-2019-m11","legis-20-2019-m12","legis-20-2019-m13","legis-20-2019-m15","regl-20-2019-m5","regl-20-2019-m14","regl-20-2019-m18"]
print("  إصلاح الغش (عقوبات القانون + إجراءات اللائحة):", {{k:(k in a) for k in need}})
assert all(k in a for k in need), "فجوة الغش لم تُغلَق!"
# 91/2013 الاتجار بالأشخاص + جسر الغسل
b=ids("عقوبة الاتجار بالأشخاص وتهريب المهاجرين ومصادرة العائدات وحماية المجني عليه")
assert all(("legis-91-2013-m%d"%n) in b for n in (2,3,5,12)); print("  ✓ حزم الاتجار بالأشخاص 91/2013")
c=ids("غسل أموال متحصلة من الاتجار بالأشخاص")
assert "legis-91-2013-m2" in c and "legis-106-2013-m2" in c; print("  ✓ جسر الاتجار⇒غسل")
# إصلاح فجوة حماية المجني عليهم: م12 يظهر لسؤال التدابير (كان يُقصّ من حزمة النطاق المتأخّرة)
v=ids("ما التدابير الواجبة تجاه المجني عليهن في الاتجار بالأشخاص؟ الإيواء والرعاية والإعادة الآمنة")
assert "legis-91-2013-m12" in v and "legis-91-2013-m4" in v; print("  ✓ حماية المجني عليهم (م12) تظهر")
# العدّ وسلامة النصّ
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-91-2013-%%'"); n91=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'regl-20-2019-%%'"); nr=cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects"); tot=cur.fetchone()[0]
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='regl-20-2019-m18'"); t18=cur.fetchone()[0]
assert n91==15 and nr==22 and "تحريز كل عينة" in t18
print("  ✓ العدّ: 91/2013 =",n91,"| اللائحة regl-20-2019 =",nr,"| الإجمالي =",tot)
print("  === تمّ =====")
PY2
echo '=== تم: 91/2013 (الاتجار بالأشخاص) + لائحة الغش التجاري 106/2021 + إصلاح فجوة عقوبات الغش (إعادة فهرسة واحدة) ==='
"""
(H / "run_final.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_final.sh && sha256sum run_final.sh"
(H / "DEPLOY_final.txt").write_text(oneliner + "\n", encoding="utf-8")
for k, v in S.items():
    print("%s sha: %s" % (k, v))
print("run_final.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
