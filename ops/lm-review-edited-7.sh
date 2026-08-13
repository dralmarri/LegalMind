#!/bin/bash
# مراجعة التعديلات اليدوية السبعة أيضاً مقابل صفحات المصدر — تنطلق تلقائياً بعد انتهاء المراجعة الرئيسية
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
import re
src = open("/root/auto_review.py", encoding="utf-8").read()
new = re.sub(r"verification_status='machine_pending_human'\s*AND coalesce\(metadata->>'human_edited',''\) <> 'true'",
             "metadata->>'human_edited'='true'", src)
assert new != src, "لم أجد الشرط المتوقع في auto_review.py"
open("/root/auto_review_edited.py", "w", encoding="utf-8").write(new)
print("جُهّزت نسخة المراجعة الخاصة بالتعديلات اليدوية ✓")
PYEOF

cat > /root/run_edited_review.sh <<'EOF'
#!/bin/bash
# انتظر انتهاء المراجعة الرئيسية ثم راجع المواد المعدلة يدوياً
while pgrep -f "python /root/auto_review.py" > /dev/null; do sleep 30; done
/opt/LegalMind/.venv/bin/python /root/auto_review_edited.py
EOF
chmod +x /root/run_edited_review.sh
nohup /root/run_edited_review.sh > /root/auto-review-edited.log 2>&1 &
echo "ستنطلق مراجعة التعديلات السبعة تلقائياً فور انتهاء الجولة الرئيسية"
echo "تابع: tail -15 /root/auto-review-edited.log"
