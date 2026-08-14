#!/bin/bash
# أمر آلي 64: (أ) فهرسة دلالية محلية لمواد الكتاب العاشر والمادتين المعدلتين (ب) اعتماد المبادئ المعلقة بالمطابقة النصية الحتمية
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re, os, glob
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
import embedding

print("== (أ) الفهرسة الدلالية المحلية ==", flush=True)
with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic, micro_issue, source_key
                   FROM knowledge_objects
                   WHERE id LIKE 'legis-b10-cma-%%'
                      OR id IN ('legis-152-2023-m18','legis-152-2023-m22')
                   ORDER BY id""")
    rows = cur.fetchall()
print("المستهدف:", len(rows), flush=True)
eng.ensure_collection()
B = 32
upserted = 0
for s in range(0, len(rows), B):
    win = rows[s:s+B]
    vecs = embedding.embed_passages([r[2] or '' for r in win])
    points = []
    for r, v in zip(win, vecs):
        oid, title, text, otype, branch, topic, subtopic, micro, skey = r
        points.append({"id": embedding.point_id(oid), "vector": v,
                       "payload": {"object_type": otype, "branch": branch, "topic": topic,
                                   "subtopic": subtopic, "micro_issue": micro,
                                   "source_key": skey, "title": title}})
    eng.qdrant_request("PUT", "/collections/%s/points?wait=true" % eng.COLLECTION, {"points": points})
    upserted += len(points)
    print("  فُهرس حتى الآن:", upserted, flush=True)
print("اكتملت الفهرسة الدلالية: %d ✓" % upserted, flush=True)

print("\n== (ب) المبادئ المعلقة: المطابقة النصية الحتمية ==", flush=True)
try:
    from pdfminer.high_level import extract_text as pdf_text
except Exception:
    import subprocess
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'pdfminer.six'], check=False)
    from pdfminer.high_level import extract_text as pdf_text

AR = re.compile(r'[؀-ۿ]{2,}')
def norm(w):
    w = w.replace('أ','ا').replace('إ','ا').replace('آ','ا').replace('ى','ي').replace('ة','ه').replace('ـ','')
    return w
def sig(w):
    return ''.join(sorted(norm(w)))
def sigs(text):
    return [sig(t) for t in AR.findall(text) if len(t) >= 3]

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""SELECT coalesce(verification_status,'-'), count(*) FROM knowledge_objects
                   WHERE coalesce(verification_status,'') NOT IN ('source_verified','verified')
                   GROUP BY 1 ORDER BY 2 DESC""")
    print("حالات التحقق غير المعتمدة:", cur.fetchall(), flush=True)

    cur.execute("""SELECT id, coalesce(normalized_text, original_text, ''), coalesce(source_key,'')
                   FROM knowledge_objects
                   WHERE coalesce(verification_status,'') = 'pending'""")
    pending = cur.fetchall()
    print("المعلقة:", len(pending), flush=True)
    if pending:
        bysrc = {}
        for oid, txt, sk in pending:
            bysrc.setdefault(sk, []).append((oid, txt))
        print("موزعة على %d ملفاً مصدرياً" % len(bysrc), flush=True)

        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='sources'")
        scols = [r[0] for r in cur.fetchall()]
        pathcol = next((c for c in ('archive_path','path','file_path','stored_path','location','filename') if c in scols), None)
        print("عمود المسار في sources:", pathcol, "| الأعمدة:", ",".join(scols), flush=True)

        verified = failed = nofile = 0
        for sk, items in bysrc.items():
            fpath = None
            if pathcol:
                cur.execute("SELECT " + pathcol + " FROM sources WHERE source_key=%s", (sk,))
                r = cur.fetchone()
                if r and r[0]:
                    cand = str(r[0])
                    if os.path.exists(cand):
                        fpath = cand
                    else:
                        g = glob.glob('/opt/LegalMind/**/' + os.path.basename(cand), recursive=True)
                        fpath = g[0] if g else None
            if not fpath:
                print("  !! لا ملف لمصدر %s (%d مبدأ)" % (sk[:30], len(items)), flush=True)
                nofile += len(items)
                continue
            print("  مصدر %s → %s (%d مبدأ)" % (sk[:24], os.path.basename(fpath)[:45], len(items)), flush=True)
            try:
                full = pdf_text(fpath) or ''
            except Exception as e:
                print("    فشل الاستخراج:", str(e)[:80], flush=True)
                nofile += len(items)
                continue
            page_sigs = set(sigs(full))
            for oid, txt in items:
                ss = sigs(txt[:1200])
                if not ss:
                    failed += 1
                    continue
                cov = sum(1 for x in ss if x in page_sigs) / len(ss)
                if cov >= 0.60:
                    cur.execute("""UPDATE knowledge_objects
                                   SET verification_status='source_verified', usable_as_citation=true,
                                       metadata = coalesce(metadata,'{}'::jsonb)
                                         || jsonb_build_object('verified_by', 'deterministic-text-match'::text)
                                         || jsonb_build_object('match_coverage', round(%s::numeric, 2)),
                                       updated_at=now()
                                   WHERE id=%s""", (cov, oid))
                    verified += 1
                else:
                    failed += 1
        print("\nاعتُمد بالمطابقة النصية (صفر تكلفة): %d ✓" % verified, flush=True)
        print("لم يبلغ عتبة المطابقة: %d | بلا ملف مصدر: %d" % (failed, nofile), flush=True)
        if failed or nofile:
            print("هذه البقية تحتاج تحققاً بصرياً بالنموذج — سأقدر تكلفتها بدقة قبل أي تنفيذ.", flush=True)
PYEOF
echo "===== اكتمل الأمر 64 ====="
