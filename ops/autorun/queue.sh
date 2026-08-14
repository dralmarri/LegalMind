#!/bin/bash
# أمر آلي 23: إصلاح عطل typo_fixer (نفس فئة خطأ 'str' has no attribute 'get') + استئناف الجدولتين الدائمتين
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

echo "== إصلاح عطل typo_fixer.py (تنقية عناصر غير سليمة من رد النموذج) =="
python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
p = "/opt/LegalMind/tools/typo_fixer.py"
src = open(p, encoding="utf-8").read()

OLD = '''            for blk in res.get("content", []):
                if blk.get("type") == "tool_use":
                    return blk["input"].get("fixes", [])
            return []'''
NEW = '''            for blk in res.get("content", []):
                if blk.get("type") == "tool_use":
                    raw = blk["input"].get("fixes", [])
                    clean = [x for x in raw if isinstance(x, dict)]
                    if len(clean) != len(raw):
                        print("    تجاهلت %d عنصراً غير سليم النوع" % (len(raw) - len(clean)), flush=True)
                    return clean
            return []'''
if OLD in src:
    src = src.replace(OLD, NEW, 1)
    open(p, "w", encoding="utf-8").write(src)
    print("أُصلح ✓")
else:
    print("مُصلح مسبقاً أو الكود مختلف — تحقق يدوي لاحقاً")
PYEOF
/opt/LegalMind/.venv/bin/python -m py_compile /opt/LegalMind/tools/typo_fixer.py && echo "الكود سليم ✓"

echo ""
echo "== استئناف الجدولتين الدائمتين =="
cat > /etc/cron.d/legalmind-autoreview <<'EOF'
*/20 * * * * root flock -n /var/lock/lmreview.lock /opt/LegalMind/tools/run_reviewer.sh >> /root/reviewer.log 2>&1
EOF
chmod 644 /etc/cron.d/legalmind-autoreview
echo "خدمة المراجعة الدورية (كل 20 دقيقة) مفعّلة ✓"

cat > /etc/cron.d/legalmind-typofix <<'EOF'
7,37 * * * * root flock -n /var/lock/lmtypofix.lock /opt/LegalMind/tools/run_typo_fixer.sh >> /root/typofix.log 2>&1
EOF
chmod 644 /etc/cron.d/legalmind-typofix
echo "خدمة التنظيف الطباعي (كل 30 دقيقة) مفعّلة ✓"

echo ""
echo "== تشغيل تجريبي فوري لكل منهما للتأكد من عدم وجود عطل =="
timeout 200 /opt/LegalMind/tools/run_reviewer.sh > /root/reviewer-resume-test.log 2>&1 || true
echo "-- المراجعة الدورية --"
tail -15 /root/reviewer-resume-test.log

timeout 200 /opt/LegalMind/tools/run_typo_fixer.sh > /root/typofix-resume-test.log 2>&1 || true
echo "-- التنظيف الطباعي --"
tail -15 /root/typofix-resume-test.log

{
  echo "=== استئناف الخدمتين التلقائيتين — $(date -u +%F' '%T) UTC ==="
  echo "المراجعة الدورية: كل 20 دقيقة | التنظيف الطباعي: كل 30 دقيقة"
  echo "الطابور الحالي صغير جداً (~230 عنصراً فقط) — استهلاك متوقع منخفض من الآن فصاعداً"
  echo ""
  echo "-- اختبار المراجعة الدورية --"
  cat /root/reviewer-resume-test.log
  echo ""
  echo "-- اختبار التنظيف الطباعي --"
  cat /root/typofix-resume-test.log
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشرت نتيجة الاستئناف ====="
