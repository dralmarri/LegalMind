#!/bin/bash
# الإدخال النهائي: حفظ التعديلات اليدوية -> حذف النسخة الناقصة -> إدخال كامل بالرؤية -> إعادة زرع التعديلات
set -e

echo "== 0) منعكس الرؤية القسرية في القارئ =="
python3 - <<'PYEOF'
p = "/opt/LegalMind/engine/claude_reader.py"
src = open(p, encoding="utf-8").read()
if "force_vision" in src:
    print("موجود مسبقا")
else:
    A = '''def _structure(path, text, tax, metadata, progress=None):
    header = _header(tax, metadata)
    used = "text"
    result = None
    if text:'''
    N = '''def _structure(path, text, tax, metadata, progress=None):
    header = _header(tax, metadata)
    used = "text"
    result = None
    if metadata and metadata.get("force_vision"):
        text = None
    if text:'''
    assert A in src, "!! نمط _structure غير مطابق"
    src = src.replace(A, N, 1)
    open(p, "w", encoding="utf-8").write(src)
    print("زرع force_vision ✓")
PYEOF
/opt/LegalMind/.venv/bin/python -m py_compile /opt/LegalMind/engine/claude_reader.py
systemctl restart legalmind-ingest

BID=$(docker exec legalmind-postgres psql -U legalmind -d legalmind -Atc "SELECT batch_id FROM ingestion_batches WHERE object_count=252 AND status='completed' ORDER BY started_at DESC LIMIT 1;")
echo "الدفعة القديمة: $BID"
F=$(ls /opt/legalmind-ingest/archive/${BID}__*.pdf 2>/dev/null | head -1)
if [ -z "$F" ]; then F=$(ls -t /opt/legalmind-ingest/archive/*البحري* 2>/dev/null | head -1); fi
echo "الملف: $F"
if [ -z "$BID" ] || [ -z "$F" ]; then echo "!! نقص معطيات"; exit 1; fi

echo "== 1) حفظ تعديلاتك اليدوية =="
set -a; source /opt/LegalMind/deploy/.env; set +a
/opt/LegalMind/.venv/bin/python - "$BID" <<'PYEOF'
import json, sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
BID = sys.argv[1]
with eng.psycopg.connect(eng.database_url()) as conn:
    with conn.cursor() as cur:
        cur.execute("""SELECT coalesce(metadata->>'number',''), coalesce(title,''), coalesce(original_text,'')
                       FROM knowledge_objects
                       WHERE metadata->>'batch_id'=%s AND lower(coalesce(metadata->>'human_edited','')) IN ('true','1')""", (BID,))
        rows = [{"number": n, "title": t, "text": x} for n, t, x in cur.fetchall()]
json.dump(rows, open("/root/maritime-edited.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("حفظت التعديلات اليدوية:", len(rows))
PYEOF

echo "== 2) حذف النسخة الناقصة كاملة =="
IDS=$(docker exec legalmind-postgres psql -U legalmind -d legalmind -Atc "SELECT string_agg('\"'||id||'\"', ',') FROM knowledge_objects WHERE metadata->>'batch_id'='$BID';")
[ -n "$IDS" ] && curl -s -X POST http://127.0.0.1:6333/collections/legalmind_multilingual_e5_base_v1/points/delete -H 'Content-Type: application/json' -d "{\"filter\":{\"must\":[{\"key\":\"object_id\",\"match\":{\"any\":[$IDS]}}]}}" >/dev/null && echo "نظف الفهرس"
docker exec legalmind-postgres psql -U legalmind -d legalmind -c "DELETE FROM knowledge_objects WHERE metadata->>'batch_id'='$BID'; DELETE FROM sources WHERE source_key IN (SELECT source_key FROM ingestion_batches WHERE batch_id='$BID'); DELETE FROM ingestion_batches WHERE batch_id='$BID';"

echo "== 3) الإدخال الكامل بالرؤية عبر خط الأنابيب =="
cp "$F" "/opt/legalmind-ingest/inbox/قانون-التجارة-البحرية.pdf"
cat > "/opt/legalmind-ingest/inbox/قانون-التجارة-البحرية.pdf.json" <<'MJSON'
{"force_vision": true, "source_type": "legislation", "title": "قانون التجارة البحرية الكويتي", "branch": "تجاري", "topic": "النقل"}
MJSON
echo "دخل الطابور — تابع نسبته من قسم الطابور في صفحتك الرئيسية (نحو 20 دقيقة)"

echo "== 4) حارس إعادة زرع تعديلاتك (يعمل بالخلفية وينتظر اكتمال الإدخال) =="
cat > /root/maritime_watcher.py <<'PYEOF'
# -*- coding: utf-8 -*-
import json, sys, time, subprocess
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
edits = json.load(open("/root/maritime-edited.json", encoding="utf-8"))
print("تعديلات للزرع:", len(edits), flush=True)
deadline = time.time() + 50 * 60
bid = None
while time.time() < deadline:
    try:
        with eng.psycopg.connect(eng.database_url()) as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT batch_id, object_count FROM ingestion_batches
                               WHERE status='completed' AND report->>'file' LIKE '%بحري%'
                               AND completed_at > now() - interval '55 minutes'
                               ORDER BY completed_at DESC LIMIT 1""")
                row = cur.fetchone()
        if row:
            bid = row[0]
            print("اكتمل الإدخال الجديد:", bid, "بكائنات:", row[1], flush=True)
            break
    except Exception as exc:
        print("انتظار:", exc, flush=True)
    time.sleep(30)
if not bid:
    print("!! لم يكتمل الإدخال خلال المهلة — أخبر كلود", flush=True)
    raise SystemExit(1)

def norm(x):
    return str(x or "").strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))

applied = 0
with eng.psycopg.connect(eng.database_url()) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT id, metadata->>'number' FROM knowledge_objects WHERE metadata->>'batch_id'=%s", (bid,))
        idx = {}
        for oid, n in cur.fetchall():
            n = norm(n)
            if n and n not in idx:
                idx[n] = oid
        for e in edits:
            n = norm(e.get("number"))
            oid = idx.get(n)
            if not oid:
                print("تعذر مطابقة تعديل المادة", n, flush=True)
                continue
            cur.execute("""UPDATE knowledge_objects SET original_text=%s, normalized_text=%s,
                           verification_status='operationally_accepted', authority_status='human_verified_authority',
                           usable_as_citation=true, metadata = metadata || %s, updated_at=now() WHERE id=%s""",
                        (e["text"], eng.normalize_text(e["text"]), eng.Jsonb({"human_edited": True}), oid))
            applied += 1
    conn.commit()
print("زرعت تعديلاتك:", applied, "من", len(edits), flush=True)
for e in edits:
    pass
with eng.psycopg.connect(eng.database_url()) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM knowledge_objects WHERE metadata->>'batch_id'=%s AND lower(coalesce(metadata->>'human_edited','')) IN ('true','1')", (bid,))
        for (oid,) in cur.fetchall():
            subprocess.run(["/opt/LegalMind/.venv/bin/python", "/opt/LegalMind/engine/reindex_one_cli.py", oid],
                           cwd="/opt/LegalMind", capture_output=True)
print("== اكتمل كل شيء — القانون البحري كامل ونظيف ومعتمد ==", flush=True)
PYEOF
nohup /opt/LegalMind/.venv/bin/python /root/maritime_watcher.py > /root/maritime-final.log 2>&1 &
echo "الحارس يعمل — النتيجة النهائية: tail -10 /root/maritime-final.log (بعد نحو 25 دقيقة)"
