#!/bin/bash
# أمر آلي 8: إصلاح الحجب — البحث السابق أصاب مستندات سليمة وفوّت الهدف الفعلي بسبب source_key فارغ
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

cat > /root/quarantine2.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re, json
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    # 1) استهداف مباشر: نوع "مبدأ قضائي" + بصمات فريدة جداً من نص المستخدم نفسه
    UNIQUE = ["Venture Capital", "Private Equity", "عمليات الوكالة غير المدرجة",
              "انكشافات مشاركة", "استثمارات أخرى غير محددة"]
    like_sql = " OR ".join(["k.original_text ILIKE %s"] * len(UNIQUE))
    cur.execute(f"""SELECT k.id, k.title, k.object_type, k.verification_status,
                          k.usable_as_citation, k.source_key, k.metadata->>'batch_id',
                          k.branch, k.topic, left(k.original_text,150)
                   FROM knowledge_objects k
                   WHERE k.object_type ILIKE '%%principle%%' AND ({like_sql})""",
                tuple("%" + u + "%" for u in UNIQUE))
    exact = cur.fetchall()
    print("الهدف الدقيق (مبدأ قضائي + بصمة المستخدم):", len(exact), flush=True)
    for r in exact:
        print("  ", r, flush=True)

    # 2) توسعة: أي كائن (أي نوع) يحوي هذه البصمات تحديداً (وليس مفردات عامة)
    cur.execute(f"""SELECT k.id, k.title, k.object_type, k.verification_status,
                          k.usable_as_citation, k.source_key, k.metadata->>'batch_id'
                   FROM knowledge_objects k WHERE {like_sql}""",
                tuple("%" + u + "%" for u in UNIQUE))
    broader = cur.fetchall()
    print("\nكل كائن يحوي البصمة الدقيقة (أي نوع):", len(broader), flush=True)
    for r in broader:
        print("  ", r, flush=True)

    target_ids = {r[0] for r in exact} | {r[0] for r in broader}

    # 3) إن وُجد مصدر حقيقي لأي منها، وسّع البحث لبقية نفس الملف عبر sources.file_name
    src_keys = {r[5] for r in broader if r[5]} | {r[5] for r in exact if r[5]}
    file_names = set()
    if src_keys:
        cur.execute("SELECT file_name FROM sources WHERE source_key = ANY(%s)", (list(src_keys),))
        file_names = {r[0] for r in cur.fetchall()}
    print("\nمفاتيح مصدر فعلية:", src_keys, "| أسماء ملفات:", file_names, flush=True)

    if src_keys:
        cur.execute("""SELECT id FROM knowledge_objects WHERE source_key = ANY(%s)""",
                    (list(src_keys),))
        same_source = {r[0] for r in cur.fetchall()}
        print("كائنات إضافية من نفس المصدر:", len(same_source - target_ids), flush=True)
        target_ids |= same_source

    print("\n=== إجمالي الكائنات المستهدفة للحجب: %d ===" % len(target_ids), flush=True)

    if target_ids:
        ids = list(target_ids)
        cur.execute("""SELECT id, title, object_type FROM knowledge_objects WHERE id = ANY(%s)""",
                    (ids,))
        print("قائمة الحجب الكاملة:", flush=True)
        for i, t, ot in cur.fetchall():
            print("  - [%s] %s | %s" % (ot, i, t[:60]), flush=True)

        cur.execute("""UPDATE knowledge_objects
                       SET verification_status='machine_pending_human', usable_as_citation=false,
                           metadata = metadata || '{"quarantined":"table_misread_as_prose_v2"}'::jsonb,
                           updated_at=now()
                       WHERE id = ANY(%s)""", (ids,))
        for oid in ids:
            eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/delete?wait=true",
                               {"filter": {"must": [{"key": "object_id", "match": {"value": oid}}]}})
        print("\nحُجب %d كائناً وأُزيلت نقاطهم من الفهرس ✓" % len(ids), flush=True)
    else:
        print("\nلم يُعثر على الكائن المستهدف بالبصمات الدقيقة — يلزم فحص يدوي بمعرّف الكائن", flush=True)

    # 4) التحقق: هل الكائن الذي رأيته لا يزال حياً في الفهرس؟ (فحص مباشر في qdrant)
    v = eng._embed_query("انكشافات مشاركة الناتجة عن الاستثمارات في المشاريع الخاصة والتجارية") \
        if hasattr(eng, "_embed_query") else None
PYEOF
/opt/LegalMind/.venv/bin/python /root/quarantine2.py > /root/quarantine2.log 2>&1
cat /root/quarantine2.log

{
  echo "=== تصويب الحجب — $(date -u +%F' '%T) UTC ==="
  echo ""
  cat /root/quarantine2.log
  echo ""
  echo "-- حالة القاعدة الآن --"
  docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
    "SELECT verification_status, count(*) FROM knowledge_objects GROUP BY 1 ORDER BY 2 DESC;"
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشرت نتيجة التصويب ====="
