#!/bin/bash
# أمر آلي 54: إلحاق التعريف المضاف بالمادة الأولى + معالجة البند 7 من الملحق رقم 2
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

DEF_MARK = 'الوحدات الخاضعة لرقابة البنك المركزي'
DEF_BLOCK = (
    "\n\n- الوحدات الخاضعة لرقابة البنك المركزي:\n"
    "1- البنوك المحلية (البنوك الكويتية وفروع البنوك الأجنبية المرخص لها بالعمل داخل دولة الكويت من قبل البنك المركزي).\n"
    "2- شركات التمويل المنشأة وفقاً للقرار الوزاري رقم (38) لسنة 2011 في شأن تنظيم رقابة البنك المركزي على شركات التمويل.\n"
    "3- شركات الاستثمار فيما يخص نشاط التمويل الذي تزاوله هذه الشركات.\n"
    "(أُضيف هذا التعريف بالقرار الوزاري 99/2025)"
)
BAND7_NEW = 'يجب على الوحدات التي تخضع لرقابة البنك المركزي الالتزام بتعليماته المتعلقة بتقييم الأصول العقارية'

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    print("== (أ) إلحاق التعريف المضاف بالمادة الأولى ==", flush=True)
    cur.execute("SELECT coalesce(original_text,'') FROM knowledge_objects WHERE id='legis-152-2023-m1'")
    row = cur.fetchone()
    if not row:
        print("!! المادة الأولى غير موجودة", flush=True)
    elif DEF_MARK in row[0]:
        print("التعريف ملحق مسبقاً — لا تغيير (منفذ من قبل).", flush=True)
    else:
        old = row[0]
        cur.execute("""UPDATE knowledge_objects
                       SET original_text = original_text || %s,
                           normalized_text = coalesce(normalized_text,'') || %s,
                           metadata = coalesce(metadata,'{}'::jsonb)
                             || jsonb_build_object('pre_amendment_text', %s::text)
                             || jsonb_build_object('amended_by', 'القرار الوزاري 99/2025 (إضافة تعريف)'::text),
                           updated_at=now()
                       WHERE id='legis-152-2023-m1'""", (DEF_BLOCK, DEF_BLOCK, old))
        print("أُلحق التعريف بالمادة الأولى ✓ (النص القديم محفوظ احتياطياً)", flush=True)

    print("\n== (ب) البحث عن الملحق رقم (2) في كائنات القرار ==", flush=True)
    cur.execute("""SELECT id, left(coalesce(original_text,''),120)
                   FROM knowledge_objects
                   WHERE (id LIKE %s OR id LIKE %s)
                     AND (original_text ILIKE %s OR original_text ILIKE %s OR title ILIKE %s)""",
                ('legis-152-2023-%', 'legis-99-2025-%', '%ملحق رقم (2)%', '%الملحق رقم (2)%', '%ملحق%'))
    hits = cur.fetchall()
    annex_obj = None
    for oid, head in hits:
        print("  %s | %s" % (oid, head.replace(chr(10),' ')), flush=True)
        if oid.startswith('legis-152-2023') and not oid.endswith('preamble'):
            cur.execute("SELECT coalesce(original_text,'') FROM knowledge_objects WHERE id=%s", (oid,))
            full = cur.fetchone()[0]
            if 'الملحق رقم (2)' in full or 'ملحق رقم (2)' in full:
                annex_obj = (oid, full)

    if annex_obj is None:
        print("الملحق رقم (2) غير مفهرس كنص مستقل ضمن مواد القرار — نصه المعدَّل موثق في مجلد «القرار الوزاري 99/2025 المعدِّل» ويظهر في البحث.", flush=True)
    else:
        oid, full = annex_obj
        if BAND7_NEW in full:
            print("البند 7 محدث مسبقاً في %s — لا تغيير." % oid, flush=True)
        else:
            NOTE = ("\n\n(عُدّل البند رقم (7) من الملحق رقم (2) بالقرار الوزاري 99/2025 ليصبح نصه: \"" 
                    + BAND7_NEW + "\")")
            cur.execute("""UPDATE knowledge_objects
                           SET original_text = original_text || %s,
                               normalized_text = coalesce(normalized_text,'') || %s,
                               metadata = coalesce(metadata,'{}'::jsonb)
                                 || jsonb_build_object('amended_by', 'القرار الوزاري 99/2025 (تعديل البند 7 من الملحق 2)'::text),
                               updated_at=now()
                           WHERE id=%s""", (NOTE, NOTE, oid))
            print("أُلحق نص البند 7 المعدَّل بالكائن الحاوي للملحق: %s ✓" % oid, flush=True)

    print("\n== تأكيد نهائي: حالة مواد القرار المعدلة ==", flush=True)
    cur.execute("""SELECT id, metadata->>'amended_by', left(coalesce(original_text,''),80)
                   FROM knowledge_objects
                   WHERE id LIKE %s AND metadata->>'amended_by' IS NOT NULL
                   ORDER BY id""", ('legis-152-2023-%',))
    for oid, ab, head in cur.fetchall():
        print("  %s | %s | %s" % (oid, ab, head.replace(chr(10),' ')), flush=True)
PYEOF
echo "===== اكتمل الأمر 54 ====="