#!/bin/bash
# أمر آلي 57: (أ) بطاقة موحدة لكتاب القانون البحري بمجلدات (ب) بطاقة لنسخة كفاية رأس المال القديمة (ج) فحص التكرار مع TBL
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

SEA = 'SRC-22A9E6644B7E96895A01'
CAP = 'SRC-937A1650BC733E4F20CF'
SEA_CARD = 'قانون التجارة البحرية والقوانين المكملة له (28/1980)'
CAP_CARD = 'تعليمات كفاية رأس المال — نسخة قديمة (قيد المراجعة)'

def folder_of(title):
    t = (title or '').strip()
    if any(k in t for k in ('فهرس', 'المحتويات', 'صورة ', 'شكر وتقدير', 'الطبعة', 'شعار', 'الاختصارات', 'الإهداء')):
        return 'صفحات تمهيدية'
    if any(k in t for k in ('معاهدة', 'بروتوكول', 'مذكرة تفسيرية', 'المفوضين')):
        return 'معاهدة بروكسل 1924 لسندات الشحن'
    if any(k in t for k in ('جواز بحري', 'الجواز البحري', 'الربابنة', 'ضباط الملاحة', 'الأمن والنظام والتأديب')):
        return 'القوانين المكملة (الجواز البحري — الربابنة 30/1980 — الأمن والتأديب 31/1980)'
    if re.match(r'^(المادة|مادة)\s*\(?\s*[0-9٠-٩]', t) and 'شرح' not in t:
        return 'مواد القانون (المرسوم بقانون 28/1980)'
    return 'المذكرة الإيضاحية والشرح'

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    print("== (أ) تنظيم كتاب القانون البحري (579) ==", flush=True)
    cur.execute("SELECT id, coalesce(title,'') FROM knowledge_objects WHERE source_key=%s", (SEA,))
    rows = cur.fetchall()
    buckets = {}
    for oid, t in rows:
        buckets.setdefault(folder_of(t), []).append(oid)
    for folder, ids in sorted(buckets.items()):
        cur.execute("""UPDATE knowledge_objects
                       SET metadata = coalesce(metadata,'{}'::jsonb)
                             || jsonb_build_object('library_group', 'maritime-book-2011'::text)
                             || jsonb_build_object('library_card_name', %s::text)
                             || jsonb_build_object('doc_part', %s::text),
                           updated_at=now()
                       WHERE id = ANY(%s)""", (SEA_CARD, folder, ids))
        print("  مجلد '%s' : %d" % (folder, cur.rowcount), flush=True)

    try:
        cur.execute("""UPDATE knowledge_objects SET usable_as_citation=false, updated_at=now()
                       WHERE source_key=%s AND metadata->>'doc_part'='صفحات تمهيدية'""", (SEA,))
        print("  صفحات تمهيدية أخرجت من الاستشهاد: %d" % cur.rowcount, flush=True)
    except Exception as e:
        print("  (تعذر ضبط usable_as_citation: %s)" % str(e)[:80], flush=True)

    print("\n== (ب) بطاقة نسخة كفاية رأس المال القديمة (307) ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET metadata = coalesce(metadata,'{}'::jsonb)
                         || jsonb_build_object('library_group', 'cap-adequacy-legacy'::text)
                         || jsonb_build_object('library_card_name', %s::text),
                       updated_at=now()
                   WHERE source_key=%s""", (CAP_CARD, CAP))
    print("  جُمعت في بطاقة واحدة: %d ✓" % cur.rowcount, flush=True)

    print("\n== (ج) فحص التكرار مع كتاب 17 (TBL) ==", flush=True)
    cur.execute("SELECT coalesce(title,''), left(coalesce(original_text,''),100) FROM knowledge_objects WHERE source_key=%s", (CAP,))
    cap_arts = set()
    for t, x in cur.fetchall():
        m = re.search(r'مادة\s+(\d+-\d+)', t + ' ' + x)
        if m:
            cap_arts.add(m.group(1))
    cur.execute("SELECT coalesce(title,''), left(coalesce(original_text,''),200) FROM knowledge_objects WHERE id LIKE 'TBL-%%'")
    tbl_text_arts = set()
    tbl_samples = []
    for t, x in cur.fetchall():
        blob = t + ' ' + x
        for m in re.finditer(r'(\d+)\s*[-–]\s*(\d+)', blob):
            tbl_text_arts.add(m.group(1) + '-' + m.group(2))
        if len(tbl_samples) < 5:
            tbl_samples.append((t[:60], x[:80].replace(chr(10), ' ')))
    inter = cap_arts & tbl_text_arts
    print("  مواد النسخة القديمة (بنمط ن-ف): %d" % len(cap_arts), flush=True)
    print("  منها موجود في كائنات كتاب 17 الجديدة: %d (%.0f%%)" % (len(inter), 100.0 * len(inter) / max(1, len(cap_arts))), flush=True)
    print("  عينات من كائنات كتاب 17 (للاطلاع على شكلها):", flush=True)
    for t, x in tbl_samples:
        print("    عنوان: %s | نص: %s" % (t, x), flush=True)
    missing = sorted(cap_arts - tbl_text_arts)[:20]
    print("  عينة مواد قديمة لم يُعثر عليها في الجديد: %s" % (", ".join(missing) if missing else "لا شيء"), flush=True)

    print("\n== الخلاصة ==", flush=True)
    cur.execute("""SELECT coalesce(metadata->>'library_card_name','؟'), count(*) FROM knowledge_objects
                   WHERE id LIKE 'LEG-UNKNOWN-%%' GROUP BY 1 ORDER BY 2 DESC""")
    for cn, c in cur.fetchall():
        print("  %s : %d" % (cn[:70], c), flush=True)
PYEOF
echo "===== اكتمل الأمر 57 ====="