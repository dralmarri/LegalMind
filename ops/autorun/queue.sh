#!/bin/bash
# أمر آلي 52: تشخيص + تطبيق تعديل 99/2025 على متن 152/2023 (استبدال/إكمال) بضمانات كاملة
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

AR = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
def norm_num(s):
    s = (s or '').strip().translate(AR)
    digits = ''.join(ch for ch in s if ch.isdigit())
    return digits

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_name='knowledge_objects' ORDER BY ordinal_position""")
    cols = [r[0] for r in cur.fetchall()]
    print("== أعمدة الجدول ==", flush=True)
    print("  " + ", ".join(cols), flush=True)
    TEXTCOL = next((c for c in ['content','text','body','raw_text','chunk_text',
                                'document_text','markdown','payload'] if c in cols), None)
    print("عمود النص:", TEXTCOL, flush=True)
    if not TEXTCOL:
        print("!! لا عمود نص معروف — توقف.", flush=True)
        raise SystemExit(0)

    hay = "coalesce(metadata->>'library_card_name','') || ' ' || coalesce(metadata->>'title','')"
    if 'title' in cols:
        hay += " || ' ' || coalesce(title,'')"
    hay += " || ' ' || left(coalesce(" + TEXTCOL + ",''),200)"

    print("\n== المجموعات المطابقة ==", flush=True)
    cur.execute("""SELECT coalesce(metadata->>'library_group','(بلا مجموعة)'), count(*),
                          min(coalesce(metadata->>'library_card_name', metadata->>'title', '-'))
                   FROM knowledge_objects
                   WHERE """ + hay + """ ILIKE %s OR """ + hay + """ ILIKE %s
                   GROUP BY 1 ORDER BY 2 DESC""",
                ('%مقيمي العقار%', '%99/2025%'))
    rows = cur.fetchall()
    base_g = amend_g = None
    for g, c, nm in rows:
        print("  مجموعة=%s | %d | %s" % (g[:50], c, nm[:60]), flush=True)
        if c > 10 and base_g is None:
            base_g = g
        if c <= 10 and amend_g is None and g != '(بلا مجموعة)':
            amend_g = g

    # مجموعة التعديل قد تكون بلا library_group — نلتقط كائناتها بالمحتوى
    if amend_g:
        cur.execute("""SELECT id FROM knowledge_objects
                       WHERE metadata->>'library_group' = %s ORDER BY id""", (amend_g,))
        amend_ids = [r[0] for r in cur.fetchall()]
    else:
        cur.execute("""SELECT id FROM knowledge_objects
                       WHERE metadata->>'library_group' IS NULL
                         AND (""" + hay + """ ILIKE %s)
                       ORDER BY id LIMIT 10""", ('%99/2025%',))
        amend_ids = [r[0] for r in cur.fetchall()]

    if base_g is None or base_g == '(بلا مجموعة)' or not amend_ids or len(amend_ids) > 10:
        print("\n!! لم تتحقق شروط الأمان (base=%s, amend=%d) — تشخيص فقط دون تغيير." % (base_g, len(amend_ids)), flush=True)
        for oid in amend_ids[:10]:
            cur.execute("SELECT coalesce(metadata->>'article_number','؟'), coalesce(metadata->>'title','-'), left(coalesce(" + TEXTCOL + ",''),1500) FROM knowledge_objects WHERE id=%s", (oid,))
            an, t, txt = cur.fetchone()
            print("\n--- %s | مادة=%s | %s\n%s" % (oid[:50], an, t[:60], txt), flush=True)
        raise SystemExit(0)

    print("\nالمجموعة الأساس: %s | كائنات التعديل: %d" % (base_g[:50], len(amend_ids)), flush=True)

    # مواد الأساس: رقم -> id
    cur.execute("""SELECT id, coalesce(metadata->>'article_number','') FROM knowledge_objects
                   WHERE metadata->>'library_group' = %s""", (base_g,))
    base_arts = {}
    for oid, an in cur.fetchall():
        n = norm_num(an)
        if n:
            base_arts.setdefault(n, oid)
    print("مواد الأساس المرقمة: %d" % len(base_arts), flush=True)

    NEWNAME = 'تنظيم مهنة مقيمي العقار ومقدمي خدمات التقييم (152/2023 وتعديله)'
    replaced = added = flagged = 0
    for oid in amend_ids:
        cur.execute("SELECT coalesce(metadata->>'article_number',''), coalesce(metadata->>'title','-'), coalesce(" + TEXTCOL + ",'') FROM knowledge_objects WHERE id=%s", (oid,))
        an, t, txt = cur.fetchone()
        n = norm_num(an)
        head = txt.strip()[:100]
        print("\n--- تعديل: %s | مادة=%s | %s" % (oid[:45], an, t[:50]), flush=True)
        print(txt.strip()[:1500], flush=True)
        procedural = any(k in head for k in ('يُستبدل', 'يستبدل', 'يُضاف', 'يضاف', 'يُلغى', 'يلغى', 'يُنشر', 'ينشر', 'على جهات الاختصاص'))
        if n and n in base_arts and not procedural:
            tgt = base_arts[n]
            cur.execute("SELECT coalesce(" + TEXTCOL + ",'') FROM knowledge_objects WHERE id=%s", (tgt,))
            old_txt = cur.fetchone()[0]
            cur.execute("""UPDATE knowledge_objects
                           SET """ + TEXTCOL + """ = %s,
                               metadata = metadata
                                 || jsonb_build_object('pre_amendment_text', %s::text)
                                 || jsonb_build_object('amended_by', 'القرار الوزاري 99/2025'::text),
                               updated_at=now()
                           WHERE id=%s""", (txt, old_txt, tgt))
            replaced += 1
            print(">> استُبدلت المادة %s في القرار الأصلي (النص القديم محفوظ احتياطياً) ✓" % n, flush=True)
        elif n and n not in base_arts and not procedural:
            cur.execute("""UPDATE knowledge_objects
                           SET metadata = metadata
                                 || jsonb_build_object('library_group', %s::text)
                                 || jsonb_build_object('doc_part', 'القرار 152/2023'::text)
                                 || jsonb_build_object('added_by', 'القرار الوزاري 99/2025'::text)
                                 || jsonb_build_object('library_card_name', %s::text),
                               updated_at=now()
                           WHERE id=%s""", (base_g, NEWNAME, oid))
            added += 1
            print(">> أُلحقت المادة %s الجديدة بمواد القرار ✓" % n, flush=True)
        else:
            cur.execute("""UPDATE knowledge_objects
                           SET metadata = metadata
                                 || jsonb_build_object('library_group', %s::text)
                                 || jsonb_build_object('doc_part', 'القرار الوزاري 99/2025 المعدِّل'::text)
                                 || jsonb_build_object('library_card_name', %s::text),
                               updated_at=now()
                           WHERE id=%s""", (base_g, NEWNAME, oid))
            flagged += 1
            print(">> مادة إجرائية/غير مرقمة — وُضعت في مجلد القرار المعدِّل داخل البطاقة نفسها.", flush=True)

    cur.execute("""UPDATE knowledge_objects
                   SET metadata = metadata
                         || jsonb_build_object('library_card_name', %s::text)
                         || (CASE WHEN coalesce(metadata->>'doc_part','')='' THEN jsonb_build_object('doc_part','القرار 152/2023'::text) ELSE '{}'::jsonb END),
                       updated_at=now()
                   WHERE metadata->>'library_group' = %s""", (NEWNAME, base_g))
    print("\nوحّد اسم البطاقة على %d كائناً ✓" % cur.rowcount, flush=True)
    print("النتيجة: استُبدل %d | أُضيف %d | إجرائي %d" % (replaced, added, flagged), flush=True)

    print("\n== بطاقة توصيل الطلبات: تصحيح الاسم ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET metadata = metadata || jsonb_build_object('library_card_name',
                        'القرار 109/2026 — تنظيم قطاع توصيل الطلبات عبر المنصات'::text),
                       updated_at=now()
                   WHERE """ + hay + """ ILIKE %s""", ('%توصيل الطلبات%',))
    print("سُمّيت (%d كائناً) ✓" % cur.rowcount, flush=True)
PYEOF
echo "===== اكتمل الأمر 52 ====="