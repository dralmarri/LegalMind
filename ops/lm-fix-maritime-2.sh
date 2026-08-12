#!/bin/bash
# حذف سجل مصدر القانون البحري العالق (سبب "مكرر") وإعادة الملف للطابور
set -e
echo "== حذف سجل المصدر العالق =="
docker exec legalmind-postgres psql -U legalmind -d legalmind -c "DELETE FROM sources WHERE first_batch_id='BATCH-20260812-185021-22A9E664';"
echo "== حذف دفعات (مكرر) الخاصة بالملف =="
docker exec legalmind-postgres psql -U legalmind -d legalmind -c "DELETE FROM ingestion_batches WHERE status='duplicate' AND report->>'file' LIKE '%البحري%';"
echo "== إعادة الملف من الأرشيف للطابور =="
F=$(ls -t /opt/legalmind-ingest/archive/ | grep "البحري" | head -1)
echo "الملف: $F"
if [ -n "$F" ]; then
  cp "/opt/legalmind-ingest/archive/$F" "/opt/legalmind-ingest/inbox/قانون-التجارة-البحرية.pdf"
  echo "أُعيد للطابور — تابع الأجزاء من مركز المصادر (10-15 دقيقة)"
else
  echo "!! لم أجد الملف في الأرشيف — أخبر كلود"
fi
