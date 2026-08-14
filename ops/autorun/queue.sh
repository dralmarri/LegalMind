#!/bin/bash
# أمر آلي 11: تصحيح استهداف الملف — البحث السابق التقط "الكتاب الخامس عشر" خطأً بدل "السابع عشر"
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

echo "== إيقاف المعالجة الخاطئة الجارية (كتاب 15) =="
pkill -f "table_reader.py.*الخامس-عشر" 2>/dev/null && echo "أُوقفت ✓" || echo "لم تكن تعمل أو انتهت مسبقاً"
sleep 2

echo ""
echo "== تنظيف أي بقايا أُدرجت خطأً من كتاب 15 عبر القارئ الجدولي =="
docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
  "DELETE FROM knowledge_objects WHERE id LIKE 'TBL-الكتاب-الخامس%';"

echo ""
echo "== تحديد الملف الصحيح بدقة (الاسم الحرفي المؤكد من سجل sources) =="
EXACT="/opt/legalmind-ingest/archive/BATCH-20260813-223443-937A1650__الكتاب-السابع-عشر-اسواق-المال.pdf"
if [ -f "$EXACT" ]; then
  SRC="$EXACT"
else
  SRC=$(find /opt/legalmind-ingest/archive -iname "*السابع-عشر-اسواق-المال*.pdf" ! -iname "*.json" | head -1)
fi
echo "الملف المستهدف: ${SRC:-غير موجود}"

if [ -z "$SRC" ]; then
  echo "تعذر إيجاد الملف بالاسم الدقيق — القائمة الكاملة لملفات أسواق المال في الأرشيف:"
  find /opt/legalmind-ingest/archive -iname "*اسواق-المال*.pdf" ! -iname "*.json" -exec ls -la {} \;
  { echo "=== تعذر تحديد الملف — يلزم توضيحك ==="; 
    find /opt/legalmind-ingest/archive -iname "*اسواق-المال*.pdf" ! -iname "*.json" -exec basename {} \;
  } > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
  exit 0
fi

FNAME=$(basename "$SRC" | sed 's/^BATCH-[0-9-]*__//')
cp -a "$SRC" "/opt/legalmind-ingest/inbox/${FNAME}"
echo "نُسخ إلى صندوق الإدخال: $FNAME"

nohup /opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/table_reader.py \
  "/opt/legalmind-ingest/inbox/${FNAME}" "تجاري" "أسواق المال" \
  > /root/tables-reingest2.log 2>&1 &
echo "انطلقت القراءة الجدولية للملف الصحيح في الخلفية"

sleep 25
{
  echo "=== تصحيح الاستهداف — $(date -u +%F' '%T) UTC ==="
  echo "الملف الصحيح المستهدف: $FNAME"
  echo ""
  echo "-- سطور أولية من السجل --"
  tail -25 /root/tables-reingest2.log 2>/dev/null
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== دُفع التصحيح ====="
