import base64,gzip,hashlib,pathlib
APP=pathlib.Path("/tmp/app_patched.py").read_text(encoding="utf-8")
app_b64=base64.b64encode(gzip.compress(APP.encode(),9)).decode(); app_sha=hashlib.sha256(APP.encode()).hexdigest()
SH=f"""#!/usr/bin/env bash
set -euo pipefail
APP=/opt/LegalMind/admin/app.py
TMP=/tmp/lab5_deploy; mkdir -p "$TMP"
printf '%s' '{app_b64}' | base64 -d | gunzip > "$TMP/app.py"
echo "== SHA256 =="; echo "app.py المتوقع: {app_sha}"; sha256sum "$TMP/app.py"
python3 -c "import ast; ast.parse(open('$TMP/app.py',encoding='utf-8').read()); print('python OK')"
grep -q "_LAB5_BUNDLES = \\[" "$TMP/app.py" && echo "حزم 28/1969 موجودة" || {{ echo "خطأ: حزم 28/1969 غير موجودة"; exit 1; }}
grep -c "for _name, keys, sfx in _LAB5_BUNDLES" "$TMP/app.py" | grep -q '^1$' && echo "الربط موجود" || {{ echo "خطأ: الربط غير موجود"; exit 1; }}
grep -q "_LAB4_BUNDLES = \\[" "$TMP/app.py" && echo "حزم 6/2010 سليمة" || {{ echo "خطأ: 6/2010 مفقود"; exit 1; }}
grep -q "for _name, keys, sfx in _LABOR_BUNDLES" "$TMP/app.py" && echo "حزم 68/2015 سليمة" || {{ echo "خطأ: 68/2015 مفقود"; exit 1; }}
cp -f "$APP" "$APP.bak.lab5" && echo "احتُفظ بـ $APP.bak.lab5"
cp -f "$TMP/app.py" "$APP"
systemctl restart legalmind-admin; sleep 3
systemctl is-active legalmind-admin && echo "الخدمة نشطة" || {{ echo "تحذير: استرجاع"; cp -f "$APP.bak.lab5" "$APP"; systemctl restart legalmind-admin; exit 1; }}
echo '=== تم: حزم استرجاع القانون 28/1969 (العمل في قطاع الأعمال النفطية — 6 حزم، بوابة النفط) نشطة ==='
"""
(pathlib.Path(__file__).parent/"run_lab5_bundles.sh").write_text(SH,encoding="utf-8")
one=f"printf '%s' '{base64.b64encode(gzip.compress(SH.encode(),9)).decode()}' | base64 -d | gunzip > run_lab5_bundles.sh && sha256sum run_lab5_bundles.sh"
(pathlib.Path(__file__).parent/"DEPLOY_lab5_bundles.txt").write_text(one+"\n",encoding="utf-8")
print("app.py SHA256:",app_sha)
print("run_lab5_bundles.sh SHA256:",hashlib.sha256(SH.encode()).hexdigest())
