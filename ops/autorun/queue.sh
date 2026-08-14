#!/bin/bash
# أمر آلي 25: السياق الكامل لآلية التجميع الحقيقية (GEXPR) — قراءة فقط، صفر تكلفة
set -e

{
  echo "=== السياق الكامل لآلية تجميع بطاقات القوانين — $(date -u +%F' '%T) UTC ==="
  echo ""
  echo "----- السطور 5550-5660 كاملة من app.py -----"
  sed -n '5550,5660p' /opt/LegalMind/admin/app.py
  echo ""
  echo "----- تعريف GEXPR في أي مكان بالملف -----"
  grep -n "GEXPR" /opt/LegalMind/admin/app.py
  echo ""
  echo "----- أقرب دالة/مسار (route) قبل هذه السطور -----"
  awk 'NR<=5591 && /^def |@app\.(get|post)/{ln=NR; txt=$0} END{}' /opt/LegalMind/admin/app.py
  grep -n "^def \|@app\.get\|@app\.post" /opt/LegalMind/admin/app.py | awk -F: '$1<5591' | tail -5
  echo ""
  echo "----- تحقق مباشر: تشغيل استعلام مطابق لما في الكود على كتاب أسواق المال -----"
  set -a; source /opt/LegalMind/deploy/.env; set +a
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
    "SELECT coalesce(metadata->>'title','') AS meta_title, count(*) FROM knowledge_objects
     WHERE metadata->>'title' ILIKE '%اسواق-المال%' OR metadata->>'title' ILIKE '%اسواق المال%'
     GROUP BY 1 ORDER BY 2 DESC LIMIT 25;"
  echo ""
  echo "----- نفس الاستعلام لكتاب موجود في العرض حالياً (تعريفات) -----"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
    "SELECT id, title, branch, topic, metadata->>'title' AS meta_title, metadata->>'law_ref' AS law_ref
     FROM knowledge_objects WHERE title ILIKE '%تعريف%' AND branch='تجاري' LIMIT 3;"
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشر السياق الكامل ====="
