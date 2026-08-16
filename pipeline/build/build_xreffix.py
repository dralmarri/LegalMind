#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرٌ خفيف: يُحدّث xref_build.py ليتحمّل الأقواس المنقلبة اتجاهيًّا (bidi) حول الأرقام
«) 22 (» / «) 2(»، فتُغلق إحالة م59/م60 من 31/1970 إلى م22 من 2/2016 (وأمثالها).
لا إدخال ولا إعادة فهرسة. خطوات: نشر xref_build.py → إعادة توليد xref_map.json →
إعادة تشغيل الخدمة (لأنّ _XREF يُحمَّل عند الإقلاع) → تحقّق من وجود الحواف الجديدة."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
XB = H / "xref_build.py"
b_xb = base64.b64encode(gzip.compress(XB.read_bytes(), 9)).decode()
s_xb = hashlib.sha256(XB.read_bytes()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
XB=/opt/LegalMind/admin/xref_build.py
MAP=/opt/LegalMind/admin/xref_map.json
TMP=/tmp/xreffix_deploy; mkdir -p "$TMP"
printf '%s' '{b_xb}' | base64 -d | gunzip > "$TMP/xref_build.py"
echo "== SHA256 xref_build.py =="; echo "المتوقع: {s_xb}"; sha256sum "$TMP/xref_build.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/xref_build.py',encoding='utf-8').read()); print('xref_build OK')"
cp -f "$XB" "$XB.bak.xreffix" 2>/dev/null || true
cp -f "$TMP/xref_build.py" "$XB"
echo "== إعادة توليد خريطة الإحالات =="
"$PYA" "$XB" --out "$MAP" 2>/dev/null | grep -E "إجمالي الحواف|مصادر لها إحالات" || true
echo "== تحقّق: حواف 31/1970 → 2/2016 =="
"$PYA" - <<'PY2'
import json
m=json.load(open("/opt/LegalMind/admin/xref_map.json",encoding="utf-8"))
for src in ("legis-31-1970-m59","legis-31-1970-m60"):
    tgts=m.get(src,[])
    print("  "+src+" -> "+str(tgts))
srcs=[s for s,t in m.items() if any("legis-2-2016" in x for x in t)]
print("  مصادر تُحيل إلى 2/2016:", srcs or "لا")
for s in ("legis-31-1970-m59","legis-31-1970-m60"):
    assert "legis-2-2016-m22" in m.get(s,[]), s+" لم تُغلق إحالته!"
print("  ✓ أُغلقت إحالة م59 وم60 معًا → م22 من 2/2016")
PY2
echo "== إعادة تشغيل الخدمة (تحميل _XREF الجديد) =="
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin >/dev/null && echo "الخدمة نشطة" || {{ echo "فشل"; exit 1; }}
echo '=== تم: أُغلقت إحالات الأقواس المنقلبة (31/1970 م59/م60 → 2/2016 م22) ==='
"""
(H / "run_xreffix.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_xreffix.sh && sha256sum run_xreffix.sh"
(H / "DEPLOY_xreffix.txt").write_text(oneliner + "\n", encoding="utf-8")
print("xref_build.py sha:", s_xb)
print("run_xreffix.sh sha:", hashlib.sha256(SH.encode()).hexdigest())
