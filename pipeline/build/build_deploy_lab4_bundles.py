#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشر حزم استرجاع القانون 6/2010 (العمل في القطاع الأهلي) — تحديث app.py + إعادة تشغيل الخدمة."""
import base64, gzip, hashlib, pathlib
APP = pathlib.Path("/tmp/app_patched.py").read_text(encoding="utf-8")
app_b64 = base64.b64encode(gzip.compress(APP.encode("utf-8"), 9)).decode("ascii")
app_sha = hashlib.sha256(APP.encode("utf-8")).hexdigest()
SH = f"""#!/usr/bin/env bash
set -euo pipefail
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/lab4_deploy
mkdir -p "$TMP"
printf '%s' '{app_b64}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 (يجب أن يطابق المتوقع) =="
echo "app.py المتوقع: {app_sha}"
sha256sum "$TMP/app.py"
echo "== تحقّق البنية =="
python3 -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('python OK')"
grep -q "_LAB4_BUNDLES = \\[" "$TMP/app.py" && echo "حزم 6/2010 موجودة" || {{ echo "خطأ: حزم 6/2010 غير موجودة"; exit 1; }}
grep -c "for _name, keys, sfx in _LAB4_BUNDLES" "$TMP/app.py" | grep -q '^1$' && echo "الربط في _draft_bundles موجود" || {{ echo "خطأ: الربط غير موجود"; exit 1; }}
grep -q "_LABOR19_BUNDLES = \\[" "$TMP/app.py" && echo "حزم 19/2000 سليمة" || {{ echo "خطأ: حزم 19/2000 مفقودة"; exit 1; }}
grep -q "for _name, keys, sfx in _LABOR_BUNDLES" "$TMP/app.py" && echo "حزم العمالة المنزلية 68/2015 سليمة" || {{ echo "خطأ: حزم 68/2015 مفقودة"; exit 1; }}
echo "== نسخة احتياطية للحالي =="
cp -f "$APP" "$APP.bak.lab4" && echo "احتُفظ بـ $APP.bak.lab4"
echo "== تركيب النسخة الجديدة =="
cp -f "$TMP/app.py" "$APP"
echo "== إعادة تشغيل الخدمة =="
systemctl restart legalmind-admin
sleep 3
systemctl is-active legalmind-admin && echo "الخدمة نشطة" || {{ echo "تحذير: الخدمة غير نشطة — استرجاع النسخة الاحتياطية"; cp -f "$APP.bak.lab4" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo '=== تم: حزم استرجاع القانون 6/2010 (العمل في القطاع الأهلي — 18 حزمة، فرع عمل، مقيَّدة بغير المنزلي) نشطة ==='
"""
sh_path = pathlib.Path(__file__).parent / "run_lab4_bundles.sh"
sh_path.write_text(SH, encoding="utf-8")
sh_sha = hashlib.sha256(SH.encode("utf-8")).hexdigest()
delivery_b64 = base64.b64encode(gzip.compress(SH.encode("utf-8"), 9)).decode("ascii")
one_liner = (f"printf '%s' '{delivery_b64}' | base64 -d | gunzip > run_lab4_bundles.sh "
             f"&& sha256sum run_lab4_bundles.sh")
(pathlib.Path(__file__).parent / "DEPLOY_lab4_bundles.txt").write_text(one_liner + "\n", encoding="utf-8")
print(f"app.py SHA256: {app_sha}")
print(f"run_lab4_bundles.sh SHA256: {sh_sha}")
print(f"one-liner chars: {len(one_liner)}")
