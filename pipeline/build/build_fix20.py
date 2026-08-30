#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ إصلاحِ تلفِ النقل في القانون 20/1981: تصحيحاتٌ مستهدَفة حتميّةٌ فقط (23 موضعًا في 8 مواد)، كلٌّ مسنَدٌ
إلى تناقضٍ داخليّ أو إلى النصّ الأصليّ 1981 أو إلى استحالةٍ نحوية. تحديثٌ في مكانه (لا يتغيّر عددُ الكائنات
= 8654) + إعادة فهرسة. ويطبع نصَّ م1 وم2 كاملًا لإقفال التدقيق (لم يَصِلا بعد). لا تغييرَ في app.py."""
import base64, gzip, hashlib, pathlib, subprocess
H = pathlib.Path(__file__).parent


def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


fx = H / "fix_20_1981.py"
b_fx, s_fx = enc(fx), sha(fx)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
TMP=/tmp/fix20_deploy; mkdir -p "$TMP"
printf '%s' '{b_fx}' | base64 -d | gunzip > "$TMP/fix_20_1981.py"
echo "== SHA256 =="; echo "fix: {s_fx}"; sha256sum "$TMP/fix_20_1981.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/fix_20_1981.py',encoding='utf-8').read()); print('fix_20_1981.py OK')"
cd /opt/LegalMind
echo "== معاينةٌ قبل الكتابة (dry-run) =="
"$PYA" "$TMP/fix_20_1981.py" --dry-run
echo
echo "== التطبيق الفعليّ =="
"$PYA" "$TMP/fix_20_1981.py"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== تحقّق: النصوص بعد الإصلاح =="
"$PYA" - <<'PY2'
import os, psycopg
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
ids=["legis-20-1981-m%s"%s for s in ("1","2","3","4","5","8","10","12mkr","14","14mkr")]
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT id,original_text FROM knowledge_objects WHERE id = ANY(%s)",(ids,))
    d=dict(cur.fetchall())
    cur.execute("SELECT count(*) FROM knowledge_objects"); tot=cur.fetchone()[0]
bad=[]
for frag,oid in [("ولاية قضاة الإلغاء","legis-20-1981-m1"),("يقدمها ذو الشأن","legis-20-1981-m1"),("تنظيم إلقاء","legis-20-1981-m3"),("اتخخاذه","legis-20-1981-m4"),
                 ("البنود: وثالثا","legis-20-1981-m5"),("الصادرة كم مجالس","legis-20-1981-m8"),
                 ("صرخت","legis-20-1981-m10"),("مرفوعا من المحكمة","legis-20-1981-m14"),
                 (") 1 (","legis-20-1981-m12mkr")]:
    if frag in d.get(oid,""): bad.append((oid,frag))
assert not bad, "بقايا تلف: %s"%bad
for frag,oid in [("ولاية قضاء الإلغاء","legis-20-1981-m1"),("تراخيص إصدار الصحف","legis-20-1981-m1"),("تنظيم القضاء","legis-20-1981-m3"),("البنود: ثانيا وثالثا","legis-20-1981-m5"),
                 ("الصادرة من مجالس","legis-20-1981-m8"),("صرّحت","legis-20-1981-m10"),
                 ("الطعن على أن يكون","legis-20-1981-m10"),("مرفوعا من الحكومة","legis-20-1981-m14"),
                 ("المادة (1)","legis-20-1981-m12mkr")]:
    assert frag in d.get(oid,""), "التصحيح لم يثبت: %s في %s"%(frag,oid)
print("  ✓ كلّ التصحيحات ثابتة ولا بقايا تلف")
print("  ✓ الإجمالي =",tot,"(ثابتٌ — تحديثٌ في مكانه)")
print("\\n  ===== نصّ م1 وم2 للتدقيق =====")
for oid in ("legis-20-1981-m1","legis-20-1981-m2"):
    print("\\n--- %s ---"%oid); print(d.get(oid,"(مفقودة)"))
print("\\n  ===== م5 وم14 بعد الإصلاح =====")
for oid in ("legis-20-1981-m5","legis-20-1981-m14"):
    print("\\n--- %s ---"%oid); print(d.get(oid,"")[:600])
PY2
echo "== تحقّق وظيفيّ: الجسر ما زال يعمل =="
"$PYA" - <<'PY3'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
a=set(m._draft_bundles("استشارة","رُفض طلب ترخيص موقعي الإلكتروني الإخباري وتظلمتُ فرُفض، فهل أطعن وما الميعاد؟",[],None,None))
for n in ("m1","m5","m6","m7","m8"):
    assert ("legis-20-1981-"+n) in a, "%s غائبة"%n
print("  ✓ جسر القضاء الإداري سليم بعد الإصلاح (م1/م5/م6/م7/م8)")
PY3
echo '=== تم: إصلاح تلف النقل في 20/1981 — 23 موضعًا في 8 مواد، تحديثٌ في مكانه + إعادة فهرسة ==='
"""
(H / "run_fix20.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_fix20.sh && sha256sum run_fix20.sh"
(H / "DEPLOY_fix20.txt").write_text(oneliner + "\n", encoding="utf-8")
print("fix sha:", s_fx)
print("run_fix20.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK")
r = subprocess.run(["bash", "-n", str(H / "run_fix20.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(oneliner))
