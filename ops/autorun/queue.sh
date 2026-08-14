#!/bin/bash
# أمر آلي 5: (أ) مصالحة الفهرس مع القاعدة كاملةً (ب) كشف أنواع الكائنات المحجوبة عن البحث
#            (ج) تشخيص الدفعات التي لم يُعثر على ملف مصدرها
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
OUT=/root/diag-report.txt

# ── (أ) مصالحة الفهرس: أي كائن في القاعدة وليس في الفهرس يُفهرَس ──────────────
cat > /root/reconcile_index.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

COLL = eng.COLLECTION
have, nxt = set(), None
while True:
    body = {"limit": 4000, "with_payload": ["object_id"], "with_vector": False}
    if nxt:
        body["offset"] = nxt
    res = eng.qdrant_request("POST", "/collections/%s/points/scroll" % COLL, body)["result"]
    for p in res["points"]:
        oid = (p.get("payload") or {}).get("object_id")
        if oid:
            have.add(oid)
    nxt = res.get("next_page_offset")
    if not nxt:
        break
print("نقاط الفهرس:", len(have), flush=True)

with eng.psycopg.connect(eng.database_url()) as conn, conn.cursor() as cur:
    cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,''),
                          object_type, branch, topic, subtopic,
                          metadata->>'micro_issue', source_key
                   FROM knowledge_objects""")
    rows = cur.fetchall()
print("كائنات القاعدة:", len(rows), flush=True)
missing = [r for r in rows if r[0] not in have]
print("ناقص من الفهرس:", len(missing), flush=True)
for s in range(0, len(missing), 48):
    w = missing[s:s + 48]
    common = {"object_type": w[0][3], "branch": w[0][4], "topic": w[0][5],
              "subtopic": w[0][6], "micro_issue": w[0][7], "source_key": w[0][8]}
    eng.qdrant_request("PUT", "/collections/%s/points?wait=true" % COLL,
                       {"points": eng.build_points([(r[0], r[1], r[2]) for r in w], common)})
    print("  فُهرس %d/%d" % (min(s + 48, len(missing)), len(missing)), flush=True)
if missing:
    print("اكتملت المصالحة ✓", flush=True)
PYEOF
/opt/LegalMind/.venv/bin/python /root/reconcile_index.py > /root/reconcile.log 2>&1 || true

# ── (ب) كشف الأنواع المحجوبة: أي object_type في القاعدة لا يذكره كود البحث ────
docker exec legalmind-postgres psql -U legalmind -d legalmind -Atc \
  "SELECT object_type || '|' || count(*) FROM knowledge_objects GROUP BY 1 ORDER BY 2 DESC;" \
  > /root/types.txt

{
  echo "=========== تشخيص فني — $(date -u +%F' '%T) UTC ==========="
  echo ""
  echo "[أ] مصالحة الفهرس:"
  tail -6 /root/reconcile.log | sed 's/^/   /'
  echo ""
  echo "[ب] أنواع الكائنات في القاعدة وهل يراها البحث:"
  while IFS='|' read -r t c; do
    [ -z "$t" ] && continue
    if grep -q "\"$t\"" /opt/LegalMind/admin/app.py; then
      echo "   ✓ مرئي   | $t | $c"
    else
      echo "   ✗ محجوب | $t | $c"
    fi
  done < /root/types.txt
  echo ""
  echo "[ج] قوائم الأنواع في كود البحث (للمعالجة الدقيقة):"
  grep -n '"legislation_article"\|"judicial_principle"\|"full_judgment"\|"judicial_template"\|"legal_memorandum"\|"legal_document"' \
    /opt/LegalMind/admin/app.py | head -20 | sed 's/^/   /'
  echo ""
  echo "[د] دفعات بلا ملف مصدر (لتشخيص سبب التعذر):"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
    "SELECT DISTINCT k.metadata->>'batch_id' AS الدفعة, left(s.file_name,45) AS الملف,
            count(*) AS معلق
     FROM knowledge_objects k LEFT JOIN sources s ON s.source_key = k.source_key
     WHERE k.verification_status='machine_pending_human'
     GROUP BY 1,2 ORDER BY 3 DESC LIMIT 12;"
  echo "   -- الموجود فعلاً في الأرشيف --"
  ls -1 /opt/legalmind-ingest/archive/ 2>/dev/null | grep -v '\.json$' | grep -v 'canonical' | tail -25 | sed 's/^/   /'
} > "$OUT" 2>&1

# نشر التشخيص مع حالة المحرك والتقرير
CODE=$(curl -s -o /tmp/ac.json -w '%{http_code}' https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" -H 'anthropic-version: 2023-06-01' \
  -H 'content-type: application/json' \
  -d '{"model":"claude-sonnet-5","max_tokens":8,"messages":[{"role":"user","content":"مرحبا"}]}')
{
  echo "=== محرك القراءة: $([ "$CODE" = "200" ] && echo 'يعمل ✓' || echo "متوقف ✗ (رمز $CODE)") ==="
  [ "$CODE" != "200" ] && { head -c 300 /tmp/ac.json; echo; echo "المطلوب: console.anthropic.com ← Billing ← Retry payment"; }
  echo ""
  [ -f /root/review-final.txt ] && cat /root/review-final.txt
  echo ""
  cat "$OUT"
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
rm -f /tmp/ac.json
echo "اكتملت المصالحة والتشخيص ونُشرا"
