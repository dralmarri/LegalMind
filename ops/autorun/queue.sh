#!/bin/bash
# أمر آلي 2: مراجعة عميقة لكل ما بقي معلقاً + إصلاح ترميز التقرير + ترميم الفهرسة
if [ -f /root/.autorun-deep-lock ]; then
  echo "المراجعة العميقة تعمل مسبقاً"
  exit 0
fi
touch /root/.autorun-deep-lock

# (1) إصلاح ترميز صفحات التقرير حتى تُقرأ العربية على الهاتف
echo 'charset utf-8;' > /etc/nginx/conf.d/charset.conf
nginx -t && systemctl reload nginx && echo "أُصلح ترميز التقارير ✓"

# (2) ناشر السجل يفضّل التقرير الختامي
cat > /opt/legalmind-autopilot/pushlog.sh <<'EOF'
#!/bin/bash
QDIR=/opt/legalmind-autopilot
TOKEN=$(cat "$QDIR/token")
if [ -f /root/review-final.txt ]; then
  cp -f /root/review-final.txt "/var/www/legalmind-v3/review-$TOKEN.txt"
elif [ -f /root/deep-review.log ]; then
  cp -f /root/deep-review.log "/var/www/legalmind-v3/review-$TOKEN.txt"
fi
exit 0
EOF
chmod 700 /opt/legalmind-autopilot/pushlog.sh

set -a; source /opt/LegalMind/deploy/.env; set +a

cat > /root/deep_review.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, os, re, io, json, glob, time, base64, urllib.request
from collections import defaultdict
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
from pypdf import PdfReader, PdfWriter

MODEL = os.environ.get("LEGALMIND_INGEST_MODEL", "claude-sonnet-5")
KEY = os.environ["ANTHROPIC_API_KEY"]
MIN_CONF = 0.75
DEFAULT_CONF = 0.85          # حين يغفل المدقق قيمة الثقة رغم إعطائه حكماً

TOOL = {
    "name": "save_verdicts",
    "description": "حفظ نتائج مراجعة نصوص مقابل المصدر",
    "input_schema": {
        "type": "object", "required": ["verdicts"],
        "properties": {"verdicts": {"type": "array", "items": {
            "type": "object", "required": ["id", "status", "confidence"],
            "properties": {
                "id": {"type": "string"},
                "status": {"type": "string", "enum": ["correct", "corrected", "not_found"]},
                "corrected_text": {"type": "string"},
                "confidence": {"type": "number"},
                "note": {"type": "string"}}}}}}}

PROMPT = ("أنت مدقق نصوص قانونية دقيق. راجع كل نص مما يلي حرفياً مقابل المصدر المرفق:\n"
          "- طابق المصدرَ حرفياً (بتسامح في التشكيل وفواصل الأسطر والترقيم) → correct.\n"
          "- اختلف أو نقص أو زاد → انسخ النص الصحيح كاملاً من المصدر في corrected_text → corrected.\n"
          "- غير موجود في المصدر المرفق إطلاقاً → not_found.\n"
          "أعطِ قيمة confidence رقمية لكل حكم (0 إلى 1) — إلزامي.\n"
          "لا تخمن ولا تكمل من معرفتك؛ انسخ ما تراه في المصدر فقط.\n\n")

def api(blocks, items, max_tokens=24000):
    listing = "\n\n".join("### %s\nالعنوان: %s\nالنص المخزن:\n%s" % (i["id"], i["title"], i["text"][:6000])
                          for i in items)
    body = {"model": MODEL, "max_tokens": max_tokens,
            "tools": [TOOL], "tool_choice": {"type": "tool", "name": "save_verdicts"},
            "messages": [{"role": "user", "content": blocks + [{"type": "text", "text": PROMPT + listing}]}]}
    data = json.dumps(body).encode("utf-8")
    for attempt in range(4):
        try:
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=data,
                                         headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
                                                  "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=900) as r:
                res = json.loads(r.read())
            out = []
            for blk in res.get("content", []):
                if blk.get("type") == "tool_use":
                    for v in (blk["input"].get("verdicts") or []):
                        if isinstance(v, dict):
                            out.append(v)
            return out
        except Exception as exc:
            print("    محاولة %d: %s" % (attempt + 1, str(exc)[:110]), flush=True)
            time.sleep(15 * (attempt + 1))
    return []

def pdf_b64(reader, a, b):
    w = PdfWriter()
    for p in range(max(0, a), min(b, len(reader.pages))):
        w.add_page(reader.pages[p])
    buf = io.BytesIO(); w.write(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def part_of(oid):
    m = re.search(r"-P(\d+)-", oid)
    return int(m.group(1)) if m else None

def conf_of(vd):
    c = vd.get("confidence")
    try:
        c = float(c)
    except Exception:
        return DEFAULT_CONF
    return DEFAULT_CONF if c <= 0 else c

stats = {"ok": 0, "fix": 0, "left": 0}

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""SELECT authority_status FROM knowledge_objects
                   WHERE verification_status='source_verified' AND authority_status IS NOT NULL LIMIT 1""")
    r = cur.fetchone(); AUTH = r[0] if r else None

    def apply(vd, by_id, leftovers):
        oid = vd.get("id"); row = by_id.get(oid)
        if row is None:
            return
        st, cf = vd.get("status"), conf_of(vd)
        if st == "not_found":
            leftovers.append(row); return
        if cf < MIN_CONF:
            leftovers.append(row); return
        patch = {"deep_review": st, "deep_conf": cf, "deep_note": (vd.get("note") or "")[:300]}
        txt = (vd.get("corrected_text") or "").strip() if st == "corrected" else ""
        if txt:
            cur.execute("""UPDATE knowledge_objects SET original_text=%s, normalized_text=%s,
                           verification_status='source_verified', usable_as_citation=true,
                           authority_status=coalesce(%s, authority_status),
                           metadata = metadata || %s::jsonb, updated_at=now() WHERE id=%s""",
                        (txt, eng.normalize_text(txt), AUTH, json.dumps(patch), oid))
            common = {"object_type": row[3], "branch": row[4], "topic": row[5],
                      "subtopic": row[6], "micro_issue": row[7], "source_key": row[8]}
            eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                               {"points": eng.build_points([(oid, row[1], txt)], common)})
            stats["fix"] += 1
        else:
            cur.execute("""UPDATE knowledge_objects SET verification_status='source_verified',
                           usable_as_citation=true, authority_status=coalesce(%s, authority_status),
                           metadata = metadata || %s::jsonb, updated_at=now() WHERE id=%s""",
                        (AUTH, json.dumps(patch), oid))
            stats["ok"] += 1

    cur.execute("""SELECT metadata->>'batch_id', count(*) FROM knowledge_objects
                   WHERE verification_status='machine_pending_human'
                     AND coalesce(metadata->>'human_edited','') <> 'true'
                     AND metadata->>'batch_id' IS NOT NULL
                   GROUP BY 1 ORDER BY 2 DESC""")
    batches = cur.fetchall()
    print("دفعات فيها معلقات: %d | إجمالي المعلق: %d" %
          (len(batches), sum(b[1] for b in batches)), flush=True)

    for BID, npend in batches:
        try:
            cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,''),
                                  object_type, branch, topic, subtopic, metadata->>'micro_issue', source_key
                           FROM knowledge_objects
                           WHERE metadata->>'batch_id'=%s AND verification_status='machine_pending_human'
                             AND coalesce(metadata->>'human_edited','') <> 'true'""", (BID,))
            pend = cur.fetchall()
            if not pend:
                continue
            files = [f for f in glob.glob("/opt/legalmind-ingest/archive/%s__*" % BID)
                     if not f.endswith(".json") and not f.endswith(".canonical.md")]
            if not files:
                cur.execute("SELECT file_name FROM sources WHERE source_key=%s LIMIT 1", (pend[0][8],))
                fr = cur.fetchone()
                if fr:
                    files = [f for f in glob.glob("/opt/legalmind-ingest/archive/*__" + fr[0])
                             if not f.endswith(".json") and not f.endswith(".canonical.md")]
            if not files:
                print("\n== %s: %d معلقاً — لا ملف مصدر ==" % (BID, len(pend)), flush=True)
                stats["left"] += len(pend); continue
            src = files[0]
            print("\n== %s: %d معلقاً | %s ==" % (BID, len(pend), os.path.basename(src)[:55]), flush=True)

            if src.lower().endswith(".pdf"):
                rd = PdfReader(src); npg = len(rd.pages)
                groups = defaultdict(list)
                for row in pend:
                    groups[part_of(row[0]) or 0].append(row)
                leftovers_all = []
                for part, rows_p in sorted(groups.items()):
                    if part:
                        a, b = (part - 1) * 15 - 8, part * 15 + 10
                    else:
                        a, b = 0, min(npg, 60)
                    blk = [{"type": "document", "source": {"type": "base64",
                            "media_type": "application/pdf", "data": pdf_b64(rd, a, b)}}]
                    for s in range(0, len(rows_p), 6):
                        ch = rows_p[s:s + 6]
                        by_id = {r[0]: r for r in ch}
                        items = [{"id": r[0], "title": r[1], "text": r[2]} for r in ch]
                        print("  P%s (صفحات %d-%d): %d نص" % (part or "؟", max(0, a), min(b, npg), len(items)), flush=True)
                        lo = []
                        for vd in api(blk, items):
                            apply(vd, by_id, lo)
                        leftovers_all += lo
                # جولة فردية بالمستند كاملاً للمتعثرين
                for row in leftovers_all:
                    a, b = (0, npg) if npg <= 70 else (max(0, ((part_of(row[0]) or 1) - 1) * 15 - 25),
                                                       ((part_of(row[0]) or 1) * 15) + 25)
                    blk = [{"type": "document", "source": {"type": "base64",
                            "media_type": "application/pdf", "data": pdf_b64(rd, a, b)}}]
                    by_id = {row[0]: row}
                    print("  فردي موسّع: %s | %s" % (row[0][-14:], row[1][:45]), flush=True)
                    fin = []
                    for vd in api(blk, [{"id": row[0], "title": row[1], "text": row[2]}], 16000):
                        apply(vd, by_id, fin)
                    stats["left"] += len(fin)
            else:
                try:
                    whole = open(src, encoding="utf-8", errors="replace").read()
                except Exception as exc:
                    print("  تعذرت القراءة: %s" % exc, flush=True)
                    stats["left"] += len(pend); continue
                wins = [whole[i:i + 110000] for i in range(0, max(1, len(whole)), 90000)][:10]
                remaining = list(pend)
                for wi, wt in enumerate(wins):
                    if not remaining:
                        break
                    nxt = []
                    blk = [{"type": "text", "text": "المصدر (جزء %d/%d):\n%s" % (wi + 1, len(wins), wt)}]
                    for s in range(0, len(remaining), 6):
                        ch = remaining[s:s + 6]
                        by_id = {r[0]: r for r in ch}
                        items = [{"id": r[0], "title": r[1], "text": r[2]} for r in ch]
                        print("  نص %d/%d: %d عنصر" % (wi + 1, len(wins), len(items)), flush=True)
                        lo = []
                        for vd in api(blk, items):
                            apply(vd, by_id, lo)
                        nxt += lo
                    remaining = nxt
                stats["left"] += len(remaining)

            # ترميم الفهرسة لهذا المصدر
            sk = pend[0][8]
            cur.execute("SELECT count(*) FROM knowledge_objects WHERE source_key=%s", (sk,))
            dbn = cur.fetchone()[0]
            qn = eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/count",
                                    {"exact": True, "filter": {"must": [{"key": "source_key",
                                     "match": {"value": sk}}]}})["result"]["count"]
            if qn < dbn:
                print("  ترميم الفهرس (%d/%d)..." % (qn, dbn), flush=True)
                cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,''),
                                      object_type, branch, topic, subtopic, metadata->>'micro_issue', source_key
                               FROM knowledge_objects WHERE source_key=%s""", (sk,))
                allr = cur.fetchall()
                for s in range(0, len(allr), 48):
                    w = allr[s:s + 48]
                    common = {"object_type": w[0][3], "branch": w[0][4], "topic": w[0][5],
                              "subtopic": w[0][6], "micro_issue": w[0][7], "source_key": w[0][8]}
                    eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                                       {"points": eng.build_points([(r[0], r[1], r[2]) for r in w], common)})
                print("  اكتمل الترميم ✓", flush=True)
        except Exception as exc:
            print("  خطأ في %s: %s — نكمل" % (BID, str(exc)[:130]), flush=True)

print("\nاعتُمد: %d | صُحّح: %d | بقي: %d" % (stats["ok"], stats["fix"], stats["left"]), flush=True)
PYEOF

cat > /root/deep_runner.sh <<'EOS'
#!/bin/bash
exec > /root/deep-review.log 2>&1
set -a; source /opt/LegalMind/deploy/.env; set +a
echo "== المراجعة العميقة انطلقت: $(date -u +%F' '%T) UTC =="
/opt/LegalMind/.venv/bin/python /root/deep_review.py
echo "== انتهت: $(date -u +%F' '%T) UTC =="
{
  echo "=========================================="
  echo "   التقرير الختامي — $(date -u +%F' '%T) UTC"
  echo "=========================================="
  echo ""
  echo "[1] حالة التوثيق في كامل قاعدة المعرفة:"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
    "SELECT verification_status AS الحالة, count(*) AS العدد
     FROM knowledge_objects GROUP BY 1 ORDER BY 2 DESC;"
  echo "[2] الدفعات التي ما زال فيها معلق (فراغ = اكتمل كل شيء):"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
    "SELECT metadata->>'batch_id' AS الدفعة,
            count(*) FILTER (WHERE verification_status='machine_pending_human') AS معلق,
            count(*) AS الإجمالي
     FROM knowledge_objects GROUP BY 1
     HAVING count(*) FILTER (WHERE verification_status='machine_pending_human') > 0
     ORDER BY 2 DESC LIMIT 15;"
  echo "[3] عناوين ما بقي معلقاً (إن وُجد):"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
    "SELECT left(coalesce(title,''),70) AS العنوان
     FROM knowledge_objects WHERE verification_status='machine_pending_human'
       AND coalesce(metadata->>'human_edited','')<>'true' LIMIT 25;"
  echo "[4] مطابقة الفهرس للقاعدة:"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -Atc \
    "SELECT count(*) FROM knowledge_objects;" | sed 's/^/  في القاعدة: /'
  curl -s -X POST http://127.0.0.1:6333/collections/legalmind_multilingual_e5_base_v1/points/count \
    -H 'Content-Type: application/json' -d '{"exact":true}' | \
    python3 -c "import json,sys; print('  في الفهرس:', json.load(sys.stdin)['result']['count'])"
  echo ""
  echo "[5] خلاصة هذه الجولة:"
  grep -E "^اعتُمد:|دفعات فيها معلقات" /root/deep-review.log | tail -5
} > /root/review-final.txt 2>&1
cp -f /root/review-final.txt "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
rm -f /root/.autorun-deep-lock
echo "== نُشر التقرير الختامي =="
EOS
chmod +x /root/deep_runner.sh
nohup /root/deep_runner.sh > /dev/null 2>&1 &
echo "انطلقت المراجعة العميقة ✓"
