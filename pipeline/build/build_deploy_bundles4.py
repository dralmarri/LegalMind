#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني سكربت نشر حزم استرجاع الكتاب الرابع (تحديث app.py + إعادة تشغيل الخدمة)."""
import base64, gzip, hashlib, pathlib

APP = pathlib.Path("/tmp/app_patched.py").read_text(encoding="utf-8")
app_b64 = base64.b64encode(gzip.compress(APP.encode("utf-8"), 9)).decode("ascii")
app_sha = hashlib.sha256(APP.encode("utf-8")).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/b4_deploy
mkdir -p "$TMP"

printf '%s' '{app_b64}' | base64 -d | gunzip > "$TMP/app.py"

echo "== SHA256 (يجب أن يطابق المتوقع) =="
echo "app.py المتوقع: {app_sha}"
sha256sum "$TMP/app.py"

echo "== تحقّق البنية =="
python3 -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('python OK')"
grep -q "_CMAREG4_BUNDLES" "$TMP/app.py" && echo "حزم ك3 موجودة" || {{ echo "خطأ: حزم ك3 غير موجودة"; exit 1; }}
grep -c "for _name, keys, sfx in _CMAREG4_BUNDLES" "$TMP/app.py" | grep -q '^1$' && echo "الربط في _draft_bundles موجود" || {{ echo "خطأ: الربط غير موجود"; exit 1; }}

echo "== نسخة احتياطية للحالي =="
cp -f "$APP" "$APP.bak.book4" && echo "احتُفظ بـ $APP.bak.book4"

echo "== تركيب النسخة الجديدة =="
cp -f "$TMP/app.py" "$APP"

echo "== إعادة تشغيل الخدمة =="
systemctl restart legalmind-admin
sleep 3
systemctl is-active legalmind-admin && echo "الخدمة نشطة" || {{ echo "تحذير: الخدمة غير نشطة — استرجاع النسخة الاحتياطية"; cp -f "$APP.bak.book4" "$APP"; systemctl restart legalmind-admin; exit 1; }}

echo '=== تم: حزم استرجاع الكتاب الرابع (10 حزم، 81 معرّفًا) نشطة ==='
"""

sh_path = pathlib.Path(__file__).parent / "run_book4_bundles.sh"
sh_path.write_text(SH, encoding="utf-8")
sh_sha = hashlib.sha256(SH.encode("utf-8")).hexdigest()

delivery_b64 = base64.b64encode(gzip.compress(SH.encode("utf-8"), 9)).decode("ascii")
one_liner = (f"printf '%s' '{delivery_b64}' | base64 -d | gunzip > run_book4_bundles.sh "
             f"&& sha256sum run_book4_bundles.sh")
txt_path = pathlib.Path(__file__).parent / "DEPLOY_book4_bundles.txt"
txt_path.write_text(one_liner + "\n", encoding="utf-8")

print(f"app.py: {len(APP)} حرف | SHA256 {app_sha}")
print(f"run_book4_bundles.sh: {len(SH)} حرف | SHA256 {sh_sha}")
print(f"أمر التسليم: {len(one_liner)} حرف")
print(f"\nSHA المتوقع لـ run_book4_bundles.sh:\n  {sh_sha}")
print(f"\nكُتب: {sh_path}\nكُتب: {txt_path}")
