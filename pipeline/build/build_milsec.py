#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ تطبيقيٌّ فقط (بلا إدخال/فهرسة): يُضيف مساعِد الاسترجاع `_milsec_ids` للمرسوم بقانون 13/2026
(تأمين المصالح العليا للجهات العسكرية) كي تنجو مادةُ العقوبة م25 — التي تحمل عقوبةَ إفشاء الأسرار
(مخالفة م5: حبسٌ حتى 5 سنوات + غرامة 5-10 آلاف، مدفونةً في ذيلها) وعقوبةَ المناطق المحمية (م8/م11/م12)
— مع بقيّة الفصل الخامس (م26 الإشاعات، م27 إضرار المكلّف، م28 مضاعفة الحرب، م30 اختصاص النيابة).
المحتوى مُدخَلٌ سلفًا (35 كائنًا) فلا حاجة لإعادة فهرسة. نسخةٌ احتياطيةٌ + استرجاعٌ تلقائيّ + اختبارٌ وظيفيّ."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")


def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


b_app, s_app = enc(APP), sha(APP)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/milsec_deploy; mkdir -p "$TMP"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app: {s_app}"; sha256sum "$TMP/app.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('app.py OK')"
for tok in _milsec_ids _MILSEC_KEYS legis-13-2026; do grep -q "$tok" "$TMP/app.py" && echo "موجود: $tok" || {{ echo "خطأ: $tok"; exit 1; }}; done
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.milsec"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.milsec" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
def ids(q): return set(m._draft_bundles("استشارة",q,[],None,None))
a=ids("ما عقوبة إفشاء سرٍّ عسكريّ من أسرار الدفاع أو دخول منطقة عسكرية محظورة؟")
need=[25,5,26,27,28,30]
assert all(("legis-13-2026-m%d"%n) in a for n in need), [n for n in need if ("legis-13-2026-m%d"%n) not in a]
print("  ✓ عقوبات 13/2026 تُستحضَر: م5(السرية)+م25(عقوبتها)+م26+م27+م28+م30")
b=ids("إفشاء الأسرار العسكرية والوثائق العسكرية السرية")
assert "legis-13-2026-m25" in b and "legis-13-2026-m5" in b
print("  ✓ الاستعلام عن الأسرار وحده يُظهر م25 (عقوبة إفشاء م5)")
# سلامة النصّ في القاعدة: م25 تحمل فعلًا عقوبة مخالفة م5
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-13-2026-m25'"); t=cur.fetchone()[0]
assert "المادة (5)" in t and "خمس سنوات" in t, "م25 لا تحمل عقوبة م5!"
print("  ✓ م25 تحمل عقوبة مخالفة م5 (حتى 5 سنوات) — مؤكَّدٌ من القاعدة")
print("  === تمّ =====")
PY2
echo '=== تم: مساعِد _milsec_ids — سدُّ ثغرة استرجاع عقوبات 13/2026 (م25 عقوبة إفشاء الأسرار م5) — تطبيقيٌّ فقط ==='
"""
(H / "run_milsec.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_milsec.sh && sha256sum run_milsec.sh"
(H / "DEPLOY_milsec.txt").write_text(oneliner + "\n", encoding="utf-8")
print("app sha:", s_app)
print("run_milsec.sh sha:", hashlib.sha256(SH.encode()).hexdigest())

# ---- round-trip self-verify ----
import subprocess, tempfile, os
dec = gzip.decompress(base64.b64decode(oneliner.split("'")[3]))
assert dec == SH.encode(), "round-trip mismatch!"
print("round-trip OK; app sha embedded:", s_app[:16], "…")
r = subprocess.run(["bash", "-n", str(H / "run_milsec.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
