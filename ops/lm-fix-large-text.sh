#!/bin/bash
# مقسم النصوص الطويلة لقارئ كلود + تنظيف دفعة القانون البحري الناقصة وإعادته
set -e
python3 - <<'PYEOF'
p = "/opt/LegalMind/engine/claude_reader.py"
src = open(p, encoding="utf-8").read()
if "_split_text" in src:
    print("المقسم النصي مركب مسبقاً — تخطٍ")
else:
    i = src.find("def _structure(path, text, tax, metadata, progress=None):")
    j = src.find('    result["_read_via"] = used\n    return result', i)
    assert i != -1 and j != -1, "!! لم أجد حدود الدالة"
    j += len('    result["_read_via"] = used\n    return result')
    NEW = '''def _merge_part(merged, r, k):
    for c in r.get("chunks", []):
        c["local_id"] = "P%d-%s" % (k, c.get("local_id") or "X")
    if merged is None:
        return r
    merged["chunks"].extend(r.get("chunks", []))
    merged["warnings"] = (merged.get("warnings") or []) + (r.get("warnings") or [])
    order = {"clean": 0, "degraded": 1, "partial": 2}
    if order.get(r.get("reading_quality"), 1) > order.get(merged.get("reading_quality"), 1):
        merged["reading_quality"] = r.get("reading_quality")
    return merged

def _split_text(text, max_chars=50000):
    if len(text) <= max_chars + 15000:
        return None
    parts, cur, size = [], [], 0
    for para in text.split("\\n"):
        cur.append(para); size += len(para) + 1
        if size >= max_chars:
            parts.append("\\n".join(cur)); cur, size = [], 0
    if cur:
        parts.append("\\n".join(cur))
    return parts

def _ctx_of(merged, k, n):
    if not (merged and merged.get("chunks")):
        return ""
    tails = [c.get("title", "") for c in merged["chunks"][-3:]]
    return ("\\n\\nهذا الجزء %d من %d من المستند نفسه. آخر قطع الجزء السابق: %s. "
            "تابع السياق والترقيم من حيث انتهى ولا تكرر ما سبق.") % (k, n, " | ".join(tails))

def _structure(path, text, tax, metadata, progress=None):
    header = _header(tax, metadata)
    used = "text"
    result = None
    if text:
        parts = _split_text(text)
        if parts:
            n = len(parts); merged = None
            for k, seg in enumerate(parts, 1):
                if progress:
                    progress("قراءة الجزء %d من %d (نص)" % (k, n), 25 + int(45 * k / n))
                r = _call([{"type": "text", "text": header + _ctx_of(merged, k, n)
                            + "\\n\\nالمستند (جزء %d من %d):\\n" % (k, n) + seg + "\\n\\nهيكل هذا الجزء."}])
                merged = _merge_part(merged, r, k)
            result = merged
        else:
            result = _call([{"type": "text", "text": header + "\\n\\nالمستند:\\n" + text + "\\n\\nهيكل المستند أعلاه."}])
            confs = [float(c.get("confidence", 0)) for c in result.get("chunks", [])] or [0]
            if path.suffix.lower() == ".pdf" and (result.get("reading_quality") == "partial" or max(confs) < 0.65):
                text = None
    if text is None:
        used = "vision"
        raw = path.read_bytes()
        batches = _split_pdf(path) if path.suffix.lower() == ".pdf" else None
        if not batches:
            result = _vision_call(raw, header + "\\n\\nاقرأ المستند المرفق قراءة بصرية وهيكله.")
        else:
            n = len(batches); merged = None
            for k, part in enumerate(batches, 1):
                if progress:
                    progress("قراءة الدفعة %d من %d (رؤية)" % (k, n), 25 + int(45 * k / n))
                r = _vision_call(part, header + _ctx_of(merged, k, n) + "\\n\\nاقرأ هذا الجزء قراءة بصرية وهيكله.")
                merged = _merge_part(merged, r, k)
            result = merged
    result["_read_via"] = used
    return result'''
    src = src[:i] + NEW + src[j:]
    open(p, "w", encoding="utf-8").write(src)
    print("رُكب المقسم النصي ✓")
PYEOF
/opt/LegalMind/.venv/bin/python -m py_compile /opt/LegalMind/engine/claude_reader.py &amp;&amp; echo "الكود سليم ✓"
systemctl restart legalmind-ingest
echo "========== تنظيف دفعة القانون البحري الناقصة وإعادته =========="
BID=$(docker exec legalmind-postgres psql -U legalmind -d legalmind -Atc "SELECT batch_id FROM ingestion_batches WHERE object_count=20 ORDER BY started_at DESC LIMIT 1;")
echo "الدفعة: $BID"
if [ -n "$BID" ]; then
  IDS=$(docker exec legalmind-postgres psql -U legalmind -d legalmind -Atc "SELECT string_agg('\"'||id||'\"', ',') FROM knowledge_objects WHERE metadata->>'batch_id'='$BID';")
  [ -n "$IDS" ] &amp;&amp; curl -s -X POST http://127.0.0.1:6333/collections/legalmind_multilingual_e5_base_v1/points/delete -H 'Content-Type: application/json' -d "{\"filter\":{\"must\":[{\"key\":\"object_id\",\"match\":{\"any\":[$IDS]}}]}}" >/dev/null &amp;&amp; echo "نُظف الفهرس"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c "DELETE FROM knowledge_objects WHERE metadata->>'batch_id'='$BID'; DELETE FROM sources WHERE source_key IN (SELECT source_key FROM ingestion_batches WHERE batch_id='$BID'); DELETE FROM ingestion_batches WHERE batch_id='$BID';"
  F=$(ls /opt/legalmind-ingest/archive/${BID}__*.pdf 2>/dev/null | head -1)
  echo "الملف الأرشيفي: $F"
  [ -n "$F" ] &amp;&amp; cp "$F" "/opt/legalmind-ingest/inbox/$(basename "$F" | sed 's/^[^_]*__//')" &amp;&amp; echo "أُعيد للطابور ✓ — تابع الأجزاء من مركز المصادر"
else
  echo "!! لم أجد دفعة بعشرين كائناً — أخبر كلود"
fi
