#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ مُجمَّع لـ53/2026: (تصحيح) إعادة إدخال النصّ النظيف المنقول من صور الجريدة (26 كائنًا، معرّفات
مطابقة ⇒ تحديث) + app.py (حزمتا النسب/تصحيح الأسماء + إشارات المصنّف + رسم الديباجات) + إعادة بناء رسم
الديباجات. إعادة إدخال + إعادة فهرسة + خريطة + نشر app + اختبار وظيفيّ (سلامة النصّ + الحزم + الرسم)."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
APP = pathlib.Path("/tmp/app_patched.py")

def enc(p): return base64.b64encode(gzip.compress(pathlib.Path(p).read_bytes(), 9)).decode()
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

ingest = H / "ingest_law53.py"; px = H / "preamble_xref.py"
b_ing, b_app, b_px = enc(ingest), enc(APP), enc(px)
s_ing, s_app, s_px = sha(ingest), sha(APP), sha(px)

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/law53fix_deploy; mkdir -p "$TMP"
printf '%s' '{b_ing}' | base64 -d | gunzip > "$TMP/ingest_law53.py"
printf '%s' '{b_app}' | base64 -d | gunzip > "$TMP/app.py"
printf '%s' '{b_px}'  | base64 -d | gunzip > "$TMP/preamble_xref.py"
echo "== SHA256 =="; echo "ingest: {s_ing}"; echo "app: {s_app}"; echo "px: {s_px}"
sha256sum "$TMP/ingest_law53.py" "$TMP/app.py" "$TMP/preamble_xref.py"
for f in ingest_law53.py app.py preamble_xref.py; do
  "$PYA" -c "import ast; ast.parse(open('$TMP/$f',encoding='utf-8').read()); print('$f OK')"
done
grep -q "legis-53-2026" "$TMP/app.py" && echo "حزم 53/2026 موجودة" || {{ echo "خطأ"; exit 1; }}
"$PYA" "$TMP/ingest_law53.py" --dry-run | grep -E "إجمالي|بديلة|مضاعف|فارغة|مكرّره|مكرّرة"
cd /opt/LegalMind
echo "== إعادة إدخال 53/2026 (نصّ نظيف، تحديث) =="; "$PYA" "$TMP/ingest_law53.py"
echo "== إعادة الفهرسة الكاملة =="
set -a; . /opt/LegalMind/deploy/.env; set +a
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PYE" -m engine.legalmind_engine reindex
echo "== إعادة بناء رسم علاقات الديباجات =="
cp -f "$TMP/preamble_xref.py" /opt/LegalMind/admin/preamble_xref.py
"$PYA" /opt/LegalMind/admin/preamble_xref.py >/dev/null && echo "رسم الديباجات محدّث"
echo "== خريطة الإحالات =="
"$PYA" /opt/LegalMind/admin/xref_build.py --out /opt/LegalMind/admin/xref_map.json >/dev/null 2>&1 && echo "خريطة محدّثة" || echo "تنبيه: تعذّر التحديث"
echo "== نشر app.py =="
cp -f "$APP" "$APP.bak.law53fix"; cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل — استرجاع"; cp -f "$APP.bak.law53fix" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo "== تحقّق وظيفيّ =="
"$PYA" - <<'PY2'
import sys; sys.path.insert(0,"/opt/LegalMind")
from admin import app as m
import psycopg, os
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
# سلامة النصّ المُصحَّح: م5 «يكون» لا «بكون»، م10 «قُدِّم» سليمة، لا تنوين مضاعف، عدّ الكائنات 26
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE 'legis-53-2026-%%'"); n=cur.fetchone()[0]
    cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-53-2026-m5'"); t5=cur.fetchone()[0]
    cur.execute("SELECT string_agg(original_text,' ') FROM knowledge_objects WHERE id LIKE 'legis-53-2026-%%'"); allt=cur.fetchone()[0]
print("  كائنات 53/2026:", n, "| م5 «يكون للجنة»:", "يكون للجنة" in t5, "| لا «بكون»:", "بكون" not in t5)
print("  لا تنوين مضاعف (اًً):", "اًً" not in allt, "| لا محرف بديل:", chr(0xFFFD) not in allt)
assert n==26 and "يكون للجنة" in t5 and "بكون" not in t5 and "اًً" not in allt and chr(0xFFFD) not in allt
# الحزم: النسب + تصحيح الأسماء (فرع الأحوال)
def ids(q,b=None): return set(m._draft_bundles("استشارة",q,[],None,b))
a=ids("دعوى إثبات النسب غير المباشر ونفيه أمام لجنة دعاوى النسب")
assert all(("legis-53-2026-m%d"%k) in a for k in (1,4,8,14,18)), "حزمة النسب ناقصة"; print("  ✓ حزمة النسب")
b=ids("طلب تصحيح الاسم الشخصي وتغيير اللقب")
assert all(("legis-53-2026-m%d"%k) in b for k in (11,12,15,17)), "حزمة تصحيح الأسماء ناقصة"; print("  ✓ حزمة تصحيح الأسماء")
# رسم الديباجات: 53/2026 يستحضر قوانينه المتّصلة المُدخَلة
d=ids("ما القوانين المتصلة بالمرسوم بقانون رقم 53 لسنة 2026 لدعاوى النسب؟","أحوال شخصية")
assert "legis-53-2026-preamble" in d and any(x in d for x in ("legis-111-2015-preamble","legis-124-2019-preamble","legis-51-1984-preamble","legis-12-2015-preamble")), "رسم الديباجات 53 لم يعمل"
print("  ✓ رسم الديباجات 53/2026")
print("  === 53/2026: نصٌّ نظيف + حزمتان + رسم ديباجات — تمّ ===")
PY2
echo '=== تم: تصحيح نصّ 53/2026 (نقل نظيف من الجريدة) + حزمتا النسب/تصحيح الأسماء + رسم الديباجات ==='
"""
(H / "run_law53fix.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_law53fix.sh && sha256sum run_law53fix.sh"
(H / "DEPLOY_law53fix.txt").write_text(oneliner + "\n", encoding="utf-8")
print("ingest sha:", s_ing); print("app sha:", s_app); print("px sha:", s_px)
print("run_law53fix.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
