#!/bin/bash
# أمر آلي 24: تشخيص لماذا لا تظهر الكتب المُصحَّحة في عرض "القوانين" كبطاقات منفصلة
# قراءة فقط من الكود والقاعدة، صفر تكلفة
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

echo "===== (1) البحث عن كود عرض بطاقات 'القوانين' في app.py ====="
grep -n "publication\|law_ref\|/api/documents\|/api/laws\|/api/library" /opt/LegalMind/admin/app.py | head -40

echo ""
echo "===== (2) البحث عن التجميع الفعلي (GROUP BY) لهذا العرض ====="
grep -n "GROUP BY\|group by" /opt/LegalMind/admin/app.py | head -20

echo ""
echo "===== (3) عيّنة من metadata لكائن من كتاب موجود فعلاً في العرض (كتاب التعريفات) ====="
docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
  "SELECT id, title, object_type, metadata FROM knowledge_objects
   WHERE metadata->>'publication' ILIKE '%تعريفات%' LIMIT 1;"

echo ""
echo "===== (4) عيّنة من metadata لكائن من الكتاب الخامس (المُصحَّح حديثاً) ====="
docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
  "SELECT k.id, k.title, k.object_type, k.metadata
   FROM knowledge_objects k JOIN sources s ON s.source_key = k.source_key
   WHERE s.file_name ILIKE '%الكتاب-الخامس-اسواق%' LIMIT 1;"

echo ""
echo "===== (5) كل القيم الفريدة لحقل publication في القاعدة حالياً ====="
docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
  "SELECT metadata->>'publication' AS publication, count(*)
   FROM knowledge_objects WHERE metadata->>'publication' IS NOT NULL
   GROUP BY 1 ORDER BY 2 DESC LIMIT 20;"

echo ""
echo "===== (6) نص الدالة المسؤولة عن /api/documents أو ما يعادلها (استخراج كامل) ====="
sed -n '/def.*documents/,/^def /p' /opt/LegalMind/admin/app.py | head -80

{
  echo "=== تشخيص عرض بطاقات القوانين — $(date -u +%F' '%T) UTC ==="
  echo ""
  echo "(1) كود العرض:"
  grep -n "publication\|law_ref\|/api/documents\|/api/laws\|/api/library" /opt/LegalMind/admin/app.py | head -40
  echo ""
  echo "(2) التجميع:"
  grep -n "GROUP BY\|group by" /opt/LegalMind/admin/app.py | head -20
  echo ""
  echo "(3) عيّنة كتاب موجود في العرض (تعريفات):"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
    "SELECT id, title, object_type, metadata FROM knowledge_objects WHERE metadata->>'publication' ILIKE '%تعريفات%' LIMIT 1;"
  echo ""
  echo "(4) عيّنة الكتاب الخامس المُصحَّح:"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
    "SELECT k.id, k.title, k.object_type, k.metadata FROM knowledge_objects k
     JOIN sources s ON s.source_key = k.source_key WHERE s.file_name ILIKE '%الكتاب-الخامس-اسواق%' LIMIT 1;"
  echo ""
  echo "(5) قيم publication الحالية:"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
    "SELECT metadata->>'publication' AS publication, count(*) FROM knowledge_objects
     WHERE metadata->>'publication' IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 20;"
  echo ""
  echo "(6) دالة /api/documents:"
  sed -n '/def.*documents/,/^def /p' /opt/LegalMind/admin/app.py | head -80
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشر التشخيص ====="
