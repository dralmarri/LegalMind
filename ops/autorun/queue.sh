#!/bin/bash
# أمر آلي 63: الفهرسة الدلالية لمواد الكتاب العاشر (73) والمادتين المعدلتين 18 و22 — بموافقة صريحة من المالك
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, inspect, traceback
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

print("== (أ) تشريح مسار الفهرسة في المحرك ==", flush=True)
names = [n for n in dir(eng) if any(k in n.lower() for k in
        ('embed', 'index', 'vector', 'qdrant', 'collection', 'upsert', 'ingest'))]
for n in names:
    obj = getattr(eng, n)
    if callable(obj):
        try:
            print("  دالة:", n, str(inspect.signature(obj))[:90], flush=True)
        except Exception:
            print("  دالة:", n, flush=True)
    else:
        print("  قيمة:", n, "=", str(obj)[:70], flush=True)

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""SELECT id, coalesce(title,''), coalesce(normalized_text, original_text, '')
                   FROM knowledge_objects
                   WHERE id LIKE 'legis-b10-cma-%%'
                      OR id IN ('legis-152-2023-m18', 'legis-152-2023-m22')
                   ORDER BY id""")
    rows = cur.fetchall()
print("\nالمواد المستهدفة:", len(rows), "| إجمالي الأحرف:", sum(len(r[2]) for r in rows), flush=True)

print("\n== (ب) محاولة الفهرسة عبر المسار القياسي ==", flush=True)
done = 0
last_err = None
for fname in ('index_objects', 'index_object', 'reindex_object', 'upsert_object',
              'upsert_objects', 'add_to_index', 'embed_and_store', 'index_knowledge_object',
              'sync_object_to_vectors', 'vector_upsert'):
    fn = getattr(eng, fname, None)
    if not fn or not callable(fn):
        continue
    print("أجرب:", fname, flush=True)
    try:
        sig = inspect.signature(fn)
        nparams = len([p for p in sig.parameters.values() if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
        oid = rows[0][0]
        if nparams == 1:
            fn(oid)
        else:
            raise RuntimeError("توقيع غير بسيط: %s" % sig)
        print("  نجحت التجربة على %s ✓ — أفهرس البقية" % oid, flush=True)
        done = 1
        for r in rows[1:]:
            fn(r[0])
            done += 1
        print("فُهرس دلالياً: %d ✓" % done, flush=True)
        break
    except Exception as e:
        last_err = e
        print("  فشل %s: %s" % (fname, str(e)[:110]), flush=True)

if not done:
    print("\nلم يوجد مسار جاهز — أطبع مقاطع الشيفرة اللازمة لبناء المسار يدوياً:", flush=True)
    for n in names:
        obj = getattr(eng, n)
        if callable(obj) and any(k in n.lower() for k in ('embed', 'upsert', 'index')):
            try:
                src = inspect.getsource(obj)
                print("---- %s ----" % n, flush=True)
                print(src[:1400], flush=True)
            except Exception:
                pass
    import subprocess
    out = subprocess.run(['grep', '-n', '-m', '8', '-E', 'embed|qdrant|collection|upsert',
                          '/opt/LegalMind/admin/app.py'], capture_output=True, text=True)
    print("---- من app.py ----", flush=True)
    print(out.stdout[:1200], flush=True)
PYEOF
echo "===== اكتمل الأمر 63 ====="
