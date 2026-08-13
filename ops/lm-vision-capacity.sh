#!/bin/bash
# رفع سقف الرد وتصغير دفعات الرؤية + إعادة إطلاق إصلاح القانون البحري
set -e
pkill -f maritime_repair.py 2>/dev/null || true
python3 - <<'PYEOF'
p = "/opt/LegalMind/engine/claude_reader.py"
src = open(p, encoding="utf-8").read()
src = src.replace("def _call(blocks, max_tokens=32000):", "def _call(blocks, max_tokens=60000):", 1)
src = src.replace("def _split_pdf(path, max_pages=30):", "def _split_pdf(path, max_pages=15):", 1)
open(p, "w", encoding="utf-8").write(src)
import re
mt = re.search(r"def _call\(blocks, max_tokens=(\d+)\)", src).group(1)
mp = re.search(r"def _split_pdf\(path, max_pages=(\d+)\)", src).group(1)
print("سقف الرد:", mt, "| صفحات الدفعة:", mp)
PYEOF
/opt/LegalMind/.venv/bin/python -m py_compile /opt/LegalMind/engine/claude_reader.py
systemctl restart legalmind-ingest
echo "== إعادة إطلاق الإصلاح بالسعة الجديدة =="
BID=$(docker exec legalmind-postgres psql -U legalmind -d legalmind -Atc "SELECT batch_id FROM ingestion_batches WHERE object_count=252 AND status='completed' ORDER BY started_at DESC LIMIT 1;")
F=$(ls /opt/legalmind-ingest/archive/${BID}__*.pdf 2>/dev/null | head -1)
if [ -z "$F" ]; then F=$(ls -t /opt/legalmind-ingest/archive/*البحري* 2>/dev/null | head -1); fi
if [ -z "$BID" ] || [ -z "$F" ]; then echo "!! لم أجد الدفعة أو الملف"; exit 1; fi
set -a; source /opt/LegalMind/deploy/.env; set +a
nohup /opt/LegalMind/.venv/bin/python /opt/LegalMind/engine/maritime_repair.py "$BID" "$F" > /root/maritime-repair.log 2>&1 &
echo "انطلق (15 دفعة × 15 صفحة — نحو 15-20 دقيقة)"
echo "تابعه: tail -20 /root/maritime-repair.log"
