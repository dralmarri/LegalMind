#!/bin/bash
# أمر آلي 68: تحقق الكتاب التاسع بالبصمات + عرض معلقة الكتاب 12 للتدقيق البصري + إقفال معلقات النسخة المؤرشفة
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python
curl -fsSL "https://raw.githubusercontent.com/dralmarri/LegalMind/main/ops/autorun/sigs-book9.json?nc=$(date +%s)" -o /tmp/sigs-book9.json

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re, json
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

AR = re.compile(r'[؀-ۿ]{2,}')
def norm(w):
    return w.replace('أ','ا').replace('إ','ا').replace('آ','ا').replace('ى','ي').replace('ة','ه').replace('ـ','')
def sig(w):
    return ''.join(sorted(norm(w)))

sigsets = {k: set(v) for k, v in json.load(open('/tmp/sigs-book9.json', encoding='utf-8')).items()}

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    print("== (أ) تحقق معلقات الكتاب التاسع بالبصمات ==", flush=True)
    for sk, sigset in sigsets.items():
        cur.execute("""SELECT id, coalesce(normalized_text, original_text, '') FROM knowledge_objects
                       WHERE source_key=%s AND verification_status='machine_pending_human'""", (sk,))
        ok = bad = 0
        for oid, txt in cur.fetchall():
            toks = [sig(t) for t in AR.findall(txt[:1500]) if len(t) >= 3]
            cov = (sum(1 for x in toks if x in sigset) / len(toks)) if toks else 0
            if cov >= 0.60:
                cur.execute("""UPDATE knowledge_objects
                               SET verification_status='source_verified', usable_as_citation=true,
                                   metadata = coalesce(metadata,'{}'::jsonb)
                                     || jsonb_build_object('verified_by','deterministic-text-match'::text)
                                     || jsonb_build_object('match_coverage', round(%s::numeric,2)),
                                   updated_at=now()
                               WHERE id=%s""", (cov, oid))
                ok += 1
            else:
                bad += 1
                print("  لم يبلغ العتبة: %s (تغطية %.0f%%)" % (oid[:45], cov*100), flush=True)
        print("مصدر %s: اعتُمد %d | دون العتبة %d" % (sk[:24], ok, bad), flush=True)

    print("\n== (ب) معلقة الكتاب 12 (مبادئ التأديب) — نصها الكامل للتدقيق البصري ==", flush=True)
    cur.execute("""SELECT id, coalesce(title,'-'), coalesce(normalized_text, original_text, '')
                   FROM knowledge_objects
                   WHERE source_key='SRC-CEE26F5A78C0B2AD35FE' AND verification_status='machine_pending_human'""")
    for oid, t, txt in cur.fetchall():
        print("--- %s | %s" % (oid[:60], t[:60]), flush=True)
        print(txt[:1800], flush=True)

    print("\n== (ج) إقفال معلقات النسخة المؤرشفة (كفاية رأس المال القديمة) ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET verification_status='archived_superseded', usable_as_citation=false, updated_at=now()
                   WHERE source_key='SRC-937A1650BC733E4F20CF' AND verification_status='machine_pending_human'""")
    print("أُقفلت (نسخة مؤرشفة مكررة): %d ✓" % cur.rowcount, flush=True)

    cur.execute("""SELECT count(*) FROM knowledge_objects WHERE verification_status='machine_pending_human'""")
    print("\nالمتبقي معلقاً الآن:", cur.fetchone()[0], flush=True)
PYEOF
echo "===== اكتمل الأمر 68 ====="
