#!/bin/bash
# اعتماد جماعي لمواد قانون التجارة البحرية (الدفعة ذات 252 كائناً) بعد فحص المستخدم لعينة منها
set -e
BID=$(docker exec legalmind-postgres psql -U legalmind -d legalmind -Atc "SELECT batch_id FROM ingestion_batches WHERE object_count=252 AND status='completed' ORDER BY started_at DESC LIMIT 1;")
echo "الدفعة: $BID"
if [ -z "$BID" ]; then echo "!! لم أجد الدفعة — أخبر كلود"; exit 1; fi
docker exec legalmind-postgres psql -U legalmind -d legalmind -c "UPDATE knowledge_objects SET verification_status='operationally_accepted', authority_status='human_verified_authority', usable_as_citation=true, updated_at=now() WHERE metadata->>'batch_id'='$BID' AND verification_status='machine_pending_human';"
echo "== المتبقي في قائمة المراجعة الآن =="
docker exec legalmind-postgres psql -U legalmind -d legalmind -Atc "SELECT count(*) FROM knowledge_objects WHERE verification_status='machine_pending_human';"
echo "تم الاعتماد الجماعي — مواد القانون البحري أصبحت معتمدة وقابلة للاستشهاد"
