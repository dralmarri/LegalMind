#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني سكربت نشرٍ يحقن محرّر «التعديل داخل البطاقة» في واجهة البحث الثابتة
/var/www/legalmind-v3/index.html (وهي SPA يخدمها nginx مباشرةً على admin.soutaladalah.com).
لا يمسّ app.py؛ الحقن يستدعي /api/object و/api/reindex عبر بروكسي nginx بمصادقة المتصفّح المخزّنة.
فكرة الإدراج تُنفَّذ بـ Python على الخادم: نسخة احتياطية → إزالة أيّ حقنٍ سابق بين العلامتين → إدراج قبل </body>."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
SNIP = (H / "incard_edit.html").read_text(encoding="utf-8")
snip_sha = hashlib.sha256(SNIP.encode()).hexdigest()
b64 = base64.b64encode(gzip.compress(SNIP.encode(), 9)).decode()

# مُدرِج بايثون يُكتب على الخادم ويعمل على الملف الحقيقي (يتعامل مع HTML مبنيّ/مصغَّر)
INSERTER = r'''
import sys, re, pathlib
target = pathlib.Path("/var/www/legalmind-v3/index.html")
snip = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
html = target.read_text(encoding="utf-8")
# أزل أيّ حقنٍ سابق بين العلامتين حتى يكون التشغيل قابلًا للتكرار
html = re.sub(r"<!--legalmind-incard-edit-->.*?<!--/legalmind-incard-edit-->\s*",
              "", html, flags=re.S)
if "</body>" in html:
    html = html.replace("</body>", snip + "\n</body>", 1)
else:
    html = html + "\n" + snip
target.write_text(html, encoding="utf-8")
print("طول الملف بعد الحقن:", len(html))
print("العلامة موجودة:", "legalmind-incard-edit" in html)
'''

SH = f"""#!/usr/bin/env bash
set -euo pipefail
TARGET=/var/www/legalmind-v3/index.html
TMP=/tmp/incard_deploy; mkdir -p "$TMP"
printf '%s' '{b64}' | base64 -d | gunzip > "$TMP/incard_edit.html"
echo "== SHA256 مقتطف الحقن =="
echo "المتوقع: {snip_sha}"
sha256sum "$TMP/incard_edit.html"
[ -f "$TARGET" ] || {{ echo "خطأ: $TARGET غير موجود"; exit 1; }}
cp -f "$TARGET" "$TARGET.bak.incard.$(date +%s)"
echo "نسخة احتياطية محفوظة."
cat > "$TMP/insert.py" <<'PYEOF'
{INSERTER}
PYEOF
python3 "$TMP/insert.py" "$TMP/incard_edit.html"
# تحقّق نهائي
grep -q "legalmind-incard-edit" "$TARGET" && echo "✓ الحقن مثبّت في $TARGET" || {{ echo "فشل الحقن"; exit 1; }}
grep -c "legalmind-incard-edit" "$TARGET" | grep -q '^2$' && echo "✓ نسخة واحدة (علامتا فتح/إغلاق)" || echo "تنبيه: عدد العلامات غير متوقّع"
echo '=== تم: زرّ التعديل داخل البطاقة مثبّت في واجهة البحث (لا حاجة لإعادة تشغيل خدمة) ==='
echo 'حدّث الصفحة في المتصفّح بـ Ctrl+Shift+R لتجاوز التخزين المؤقّت.'
"""
sh_sha = hashlib.sha256(SH.encode()).hexdigest()
(H / "run_incard.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_incard.sh && sha256sum run_incard.sh"
(H / "DEPLOY_incard.txt").write_text(oneliner + "\n", encoding="utf-8")
print("مقتطف الحقن SHA256:", snip_sha)
print("run_incard.sh SHA256:", sh_sha)
print("طول المقتطف:", len(SNIP), "حرف")
