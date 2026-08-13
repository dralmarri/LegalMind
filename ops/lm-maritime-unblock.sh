#!/bin/bash
# حذف سجل مصدر القانون البحري العالق ودفعات المكرر ثم إعادة الملف للطابور مع الرؤية القسرية
set -e
echo "== حذف سجلات المصدر العالقة =="
docker exec legalmind-postgres psql -U legalmind -d legalmind -c "DELETE FROM sources WHERE file_name LIKE '%بحري%' OR title LIKE '%البحرية%';"
echo "== حذف دفعات المكرر =="
docker exec legalmind-postgres psql -U legalmind -d legalmind -c "DELETE FROM ingestion_batches WHERE status='duplicate' AND report->>'file' LIKE '%بحري%';"
echo "== إعادة الملف للطابور =="
if [ -f "/opt/legalmind-ingest/inbox/قانون-التجارة-البحرية.pdf" ]; then
  echo "الملف ما زال في الطابور — لا حاجة للنسخ"
else
  F=$(ls -t /opt/legalmind-ingest/archive/*بحري* 2>/dev/null | grep -v json | head -1)
  echo "من الأرشيف: $F"
  [ -z "$F" ] && { echo "!! لم أجد الملف"; exit 1; }
  cp "$F" "/opt/legalmind-ingest/inbox/قانون-التجارة-البحرية.pdf"
fi
cat > "/opt/legalmind-ingest/inbox/قانون-التجارة-البحرية.pdf.json" <<'MJSON'
{"force_vision": true, "source_type": "legislation", "title": "قانون التجارة البحرية الكويتي", "branch": "تجاري", "topic": "النقل"}
MJSON
echo "دخل الطابور بالرؤية القسرية — الحارس الخلفي سيلتقطه عند الاكتمال"
echo "تابع: قسم الطابور في الرئيسية + tail -10 /root/maritime-final.log"
