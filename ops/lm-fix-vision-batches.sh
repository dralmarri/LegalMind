#!/bin/bash
# تصغير دفعات الرؤية إلى 30 صفحة + تمتين الدمج + إعادة إطلاق إصلاح القانون البحري
set -e
python3 - <<'PYEOF'
p = "/opt/LegalMind/engine/claude_reader.py"
src = open(p, encoding="utf-8").read()

src = src.replace("def _split_pdf(path, max_pages=80):", "def _split_pdf(path, max_pages=30):", 1)

i = src.find("def _merge_part(merged, r, k):")
j = src.find("    return merged", i)
assert i != -1 and j != -1, "!! لم أجد دالة الدمج"
j += len("    return merged")
NEW = '''def _merge_part(merged, r, k):
    ch = (r.get("chunks") or []) if isinstance(r, dict) else []
    for c in ch:
        c["local_id"] = "P%d-%s" % (k, c.get("local_id") or "X")
    if not ch:
        print("[claude_reader] تحذير: الجزء %d لم يرجع قطعا — تخطي" % k, flush=True)
    if merged is None:
        base = r if isinstance(r, dict) else {}
        base["chunks"] = ch
        base.setdefault("warnings", [])
        return base
    merged.setdefault("chunks", []).extend(ch)
    merged["warnings"] = (merged.get("warnings") or []) + ((r.get("warnings") or []) if isinstance(r, dict) else [])
    order = {"clean": 0, "degraded": 1, "partial": 2}
    rq = r.get("reading_quality") if isinstance(r, dict) else None
    if order.get(rq, 1) > order.get(merged.get("reading_quality"), 1):
        merged["reading_quality"] = rq
    return merged'''
src = src[:i] + NEW + src[j:]
open(p, "w", encoding="utf-8").write(src)
print("رُكبت دفعات 30 صفحة والدمج المتين ✓")
PYEOF
/opt/LegalMind/.venv/bin/python -m py_compile /opt/LegalMind/engine/claude_reader.py
systemctl restart legalmind-ingest
echo "== إعادة إطلاق إصلاح القانون البحري =="
BID=$(docker exec legalmind-postgres psql -U legalmind -d legalmind -Atc "SELECT batch_id FROM ingestion_batches WHERE object_count=252 AND status='completed' ORDER BY started_at DESC LIMIT 1;")
if [ -z "$BID" ]; then echo "!! لم أجد الدفعة"; exit 1; fi
F=$(ls /opt/legalmind-ingest/archive/${BID}__*.pdf 2>/dev/null | head -1)
if [ -z "$F" ]; then F=$(ls -t /opt/legalmind-ingest/archive/*البحري* 2>/dev/null | head -1); fi
if [ -z "$F" ]; then echo "!! لم أجد الملف"; exit 1; fi
set -a; source /opt/LegalMind/deploy/.env; set +a
nohup /opt/LegalMind/.venv/bin/python /opt/LegalMind/engine/maritime_repair.py "$BID" "$F" > /root/maritime-repair.log 2>&1 &
echo "انطلق الإصلاح من جديد (8 دفعات × 30 صفحة — نحو 12-15 دقيقة)"
echo "تابعه: tail -15 /root/maritime-repair.log"
