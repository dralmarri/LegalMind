#!/bin/bash
# أمر آلي 72: مطابقة كل المعلقات (211) مع الملفات الأصلية المؤرشفة على القرص — حتمية وصفر تكلفة
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re, os, glob
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
from pdfminer.high_level import extract_text

pdfs = sorted(glob.glob('/opt/legalmind-ingest/archive/*DUPLICATE*.pdf'))
print("ملفات الأرشيف:", len(pdfs), flush=True)

AR = re.compile(r'[؀-ۿ]{2,}')
def norm(w):
    return w.replace('أ','ا').replace('إ','ا').replace('آ','ا').replace('ى','ي').replace('ة','ه').replace('ـ','')
def sig(w):
    return ''.join(sorted(norm(w)))

filesigs = {}
for p in pdfs:
    try:
        t = extract_text(p) or ''
    except Exception as e:
        t = ''
    s = {sig(tok) for tok in AR.findall(t) if len(tok) >= 3}
    filesigs[p] = s
    name = os.path.basename(p).split('__DUPLICATE__')[-1]
    print("  %s : %d بصمة%s" % (name[:48], len(s), "  (بلا طبقة نص!)" if len(s) < 200 else ""), flush=True)

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""SELECT k.id, coalesce(k.normalized_text, k.original_text, ''), coalesce(s.file_name, k.source_key)
                   FROM knowledge_objects k LEFT JOIN sources s ON s.source_key=k.source_key
                   WHERE k.verification_status='machine_pending_human'""")
    pending = cur.fetchall()
    print("\nالمعلقة:", len(pending), flush=True)
    ok = bad = 0
    per = {}
    for oid, txt, srcname in pending:
        toks = [sig(t) for t in AR.findall(txt[:1500]) if len(t) >= 3]
        best, bestp = 0.0, None
        for p, s in filesigs.items():
            if not s or not toks:
                continue
            cov = sum(1 for x in toks if x in s) / len(toks)
            if cov > best:
                best, bestp = cov, p
        key = str(srcname)[:48]
        per.setdefault(key, [0, 0, []])
        if best >= 0.60 and bestp:
            cur.execute("""UPDATE knowledge_objects
                           SET verification_status='source_verified', usable_as_citation=true,
                               metadata = coalesce(metadata,'{}'::jsonb)
                                 || jsonb_build_object('verified_by','deterministic-text-match'::text)
                                 || jsonb_build_object('match_coverage', round(%s::numeric,2)),
                               updated_at=now()
                           WHERE id=%s""", (best, oid))
            ok += 1
            per[key][0] += 1
        else:
            bad += 1
            per[key][1] += 1
            per[key][2].append("%s(%.0f%%)" % (oid[:30], best * 100))
    print("\n== الحصيلة لكل ملف مصدر ==", flush=True)
    for k, (a, b, misses) in sorted(per.items(), key=lambda kv: -(kv[1][0] + kv[1][1])):
        line = "  %s : اعتُمد %d | لم يطابق %d" % (k, a, b)
        print(line, flush=True)
        for m in misses[:4]:
            print("      × " + m, flush=True)
    print("\nاعتُمد إجمالاً: %d | لم يطابق: %d" % (ok, bad), flush=True)
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE verification_status='machine_pending_human'")
    print("المتبقي معلقاً:", cur.fetchone()[0], flush=True)
    cur.execute("""SELECT verification_status, count(*) FROM knowledge_objects GROUP BY 1 ORDER BY 2 DESC""")
    print("\nتوزيع حالات التحقق كاملاً:", cur.fetchall(), flush=True)
PYEOF

systemctl enable --now legalmind-ingest.service && echo "أعيد تشغيل خط الفهرسة (الوارد فارغ — لا شيء سيُبتلع) ✓"
echo "===== اكتمل الأمر 72 ====="
