#!/bin/bash
# أمر آلي 71: مطابقة كل المعلقات مع الملفات المرفوعة في صندوق الوارد (حتمية، صفر تكلفة) ثم الأرشفة وإعادة تشغيل الخط
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re, os, glob, shutil
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
from pdfminer.high_level import extract_text

roots = [os.environ.get('LEGALMIND_INGEST_ROOT', '')]
roots += glob.glob('/opt/LegalMind/**/inbox', recursive=True) + glob.glob('/root/**/inbox', recursive=True)
inbox = None
for r in roots:
    if not r:
        continue
    cand = r if r.endswith('inbox') else os.path.join(r, 'inbox')
    if os.path.isdir(cand):
        inbox = cand
        break
print("صندوق الوارد:", inbox, flush=True)
pdfs = sorted(glob.glob(inbox + '/*.pdf')) if inbox else []
print("ملفات PDF فيه:", len(pdfs), flush=True)
for p in pdfs:
    print("  -", os.path.basename(p)[:70], "(%d كب)" % (os.path.getsize(p)//1024), flush=True)
if not pdfs:
    print("!! لا ملفات — ارفعها عبر النظام ثم أعد تشغيل هذا الأمر.", flush=True)
    raise SystemExit(0)

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
        print("  فشل استخراج %s: %s" % (os.path.basename(p)[:40], str(e)[:60]), flush=True)
        t = ''
    s = {sig(tok) for tok in AR.findall(t) if len(tok) >= 3}
    filesigs[p] = s
    print("  بصمات %s: %d" % (os.path.basename(p)[:45], len(s)), flush=True)

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
        if not toks:
            bad += 1
            continue
        best, bestp = 0.0, None
        for p, s in filesigs.items():
            if not s:
                continue
            cov = sum(1 for x in toks if x in s) / len(toks)
            if cov > best:
                best, bestp = cov, p
        if best >= 0.60 and bestp:
            cur.execute("""UPDATE knowledge_objects
                           SET verification_status='source_verified', usable_as_citation=true,
                               metadata = coalesce(metadata,'{}'::jsonb)
                                 || jsonb_build_object('verified_by','deterministic-text-match'::text)
                                 || jsonb_build_object('match_file', %s::text)
                                 || jsonb_build_object('match_coverage', round(%s::numeric,2)),
                               updated_at=now()
                           WHERE id=%s""", (os.path.basename(bestp)[:80], best, oid))
            ok += 1
            per[srcname] = per.get(srcname, [0, 0])
            per[srcname][0] += 1
        else:
            bad += 1
            per[srcname] = per.get(srcname, [0, 0])
            per[srcname][1] += 1
    print("\n== الحصيلة ==", flush=True)
    for srcname, (a, b) in sorted(per.items(), key=lambda kv: -(kv[1][0]+kv[1][1])):
        print("  %s : اعتُمد %d | لم يطابق %d" % (str(srcname)[:50], a, b), flush=True)
    print("اعتُمد إجمالاً: %d | لم يطابق: %d" % (ok, bad), flush=True)
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE verification_status='machine_pending_human'")
    print("المتبقي معلقاً:", cur.fetchone()[0], flush=True)

arch = os.path.join(os.path.dirname(inbox), 'archive')
os.makedirs(arch, exist_ok=True)
for p in pdfs:
    shutil.move(p, os.path.join(arch, 'VERIFYONLY-' + os.path.basename(p)))
print("\nنُقلت الملفات إلى الأرشيف (لن يبتلعها خط الفهرسة) ✓", flush=True)
PYEOF

systemctl enable --now legalmind-ingest.service && echo "أعيد تشغيل خط الفهرسة ✓"
echo "===== اكتمل الأمر 71 ====="
