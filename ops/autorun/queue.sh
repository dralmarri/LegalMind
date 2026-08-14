#!/bin/bash
# أمر آلي 28: اختبار API /api/browse مباشرة من الخادم (نفس ما تطلبه الواجهة بالضبط)
# + منع أي تخزين مؤقت لملفات التقرير نهائياً لقطع الشك
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

echo "== منع التخزين المؤقت لملفات التقارير نهائياً =="
cat > /etc/nginx/conf.d/no-cache-reports.conf <<'EOF'
location ~ ^/(review|status)-[a-z0-9]+\.txt$ {
    root /var/www/legalmind-v3;
    add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0" always;
    add_header Pragma "no-cache" always;
    if_modified_since off;
    etag off;
}
EOF
nginx -t && systemctl reload nginx && echo "أُضيف منع التخزين المؤقت ✓"

echo ""
echo "== تسجيل دخول تجريبي للحصول على جلسة صالحة =="
PW=$(cat /root/legalmind-admin-password.txt 2>/dev/null | tail -1 | awk '{print $NF}')
CODE=$(curl -s -o /tmp/lg.json -w '%{http_code}' -c /tmp/lmck2 -X POST http://127.0.0.1:8088/api/login \
  -H 'Content-Type: application/json' -d "{\"username\":\"dralmarri\",\"password\":\"$PW\"}")
echo "رمز تسجيل الدخول: $CODE"

echo ""
echo "== استدعاء /api/browse تماماً كما تفعله الواجهة (kind=laws, b=تجاري) =="
curl -s -b /tmp/lmck2 "http://127.0.0.1:8088/api/browse?kind=laws&b=%D8%AA%D8%AC%D8%A7%D8%B1%D9%8A" \
  -o /tmp/browse.json -w "\nرمز HTTP: %{http_code}\n"
echo ""
echo "-- محتوى الاستجابة الفعلية (خام) --"
cat /tmp/browse.json
echo ""
echo ""
echo "-- عدد البطاقات في الاستجابة (عدّ مباشر) --"
python3 -c "
import json
d = json.load(open('/tmp/browse.json'))
groups = d.get('groups', [])
print('عدد البطاقات:', len(groups))
for g in groups:
    print(' -', g.get('name') or g.get('key'), '|', g.get('count'))
"

rm -f /tmp/lmck2 /tmp/lg.json /tmp/browse.json

{
  echo "=== اختبار API الحقيقي مباشرة + منع التخزين المؤقت — $(date -u +%F' '%T) UTC ==="
  echo "(هذا الرابط نفسه الآن بلا أي تخزين مؤقت — النتيجة أعلاه في سجل status هي الحاسمة)"
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== اكتمل الاختبار المباشر — النتيجة في هذا السجل أعلاه ====="
