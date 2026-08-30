#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني سكربت نشرٍ يحقن «سجلّ الاستشارات والصحف» في واجهة الصياغة الثابتة
/var/www/legalmind-v3/index.html (SPA يخدمها nginx على admin.soutaladalah.com).
لا يمسّ app.py؛ الحقن يعترض /api/draft في المتصفّح ويحفظ كلّ استشارة/صياغة في localStorage
ليعود إليها المستخدم متى شاء (زرّ عائم + لوحة سجلّ + عرض تفصيلي). قابل لإعادة التشغيل (بين علامتين).
الإدراج بايثون على الخادم: نسخة احتياطية → إزالة أيّ حقنٍ سابق بين العلامتين → إدراج قبل </body>."""
import base64, gzip, hashlib, pathlib
H = pathlib.Path(__file__).parent
SNIP = (H / "draft_history.html").read_text(encoding="utf-8")
snip_sha = hashlib.sha256(SNIP.encode()).hexdigest()
b64 = base64.b64encode(gzip.compress(SNIP.encode(), 9)).decode()

INSERTER = r'''
import sys, re, pathlib
target = pathlib.Path("/var/www/legalmind-v3/index.html")
snip = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
html = target.read_text(encoding="utf-8")
# أزل أيّ حقنٍ سابق بين العلامتين حتى يكون التشغيل قابلًا للتكرار
html = re.sub(r"<!--legalmind-draft-history-->.*?<!--/legalmind-draft-history-->\s*",
              "", html, flags=re.S)
if "</body>" in html:
    html = html.replace("</body>", snip + "\n</body>", 1)
else:
    html = html + "\n" + snip
target.write_text(html, encoding="utf-8")
print("طول الملف بعد الحقن:", len(html))
print("العلامة موجودة:", "legalmind-draft-history" in html)
'''

SH = f"""#!/usr/bin/env bash
set -euo pipefail
TARGET=/var/www/legalmind-v3/index.html
TMP=/tmp/drafthist_deploy; mkdir -p "$TMP"
printf '%s' '{b64}' | base64 -d | gunzip > "$TMP/draft_history.html"
echo "== SHA256 مقتطف الحقن =="
echo "المتوقع: {snip_sha}"
sha256sum "$TMP/draft_history.html"
[ -f "$TARGET" ] || {{ echo "خطأ: $TARGET غير موجود"; exit 1; }}
cp -f "$TARGET" "$TARGET.bak.drafthist.$(date +%s)"
echo "نسخة احتياطية محفوظة."
cat > "$TMP/insert.py" <<'PYEOF'
{INSERTER}
PYEOF
python3 "$TMP/insert.py" "$TMP/draft_history.html"
# تحقّق نهائي
grep -q "legalmind-draft-history" "$TARGET" && echo "✓ الحقن مثبّت في $TARGET" || {{ echo "فشل الحقن"; exit 1; }}
[ "$(grep -c -E '<!--/?legalmind-draft-history-->' "$TARGET")" = "2" ] && echo "✓ نسخة واحدة (علامتا فتح/إغلاق)" || echo "تنبيه: عدد العلامات غير متوقّع"
echo '=== تم: سجلّ الاستشارات والصحف مثبّت في الواجهة (لا حاجة لإعادة تشغيل خدمة) ==='
echo 'حدّث الصفحة في المتصفّح بـ Ctrl+Shift+R لتجاوز التخزين المؤقّت.'
"""
sh_sha = hashlib.sha256(SH.encode()).hexdigest()
(H / "run_drafthist.sh").write_text(SH, encoding="utf-8")
oneliner = "printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() + \
           "' | base64 -d | gunzip > run_drafthist.sh && sha256sum run_drafthist.sh"
(H / "DEPLOY_drafthist.txt").write_text(oneliner + "\n", encoding="utf-8")
print("مقتطف الحقن SHA256:", snip_sha)
print("run_drafthist.sh SHA256:", sh_sha)
print("طول المقتطف:", len(SNIP), "حرف")
