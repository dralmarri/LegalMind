#!/bin/bash
# أمر آلي 48: نقل بقية المواضيع من فرع تجاري إلى فروعها الصحيحة (مدني/مرافعات/إثبات/إداري/دستوري)
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

MOVES = {
    "مدني": ['إيجار', 'التقادم', 'نظام عام وآداب عامة', 'بيع',
             'تحديد التعويض بقيمة الضرر', 'بطلان التصرفات والعقود', 'الحوالة',
             'تملك مساكن الدولة', 'بطلان', 'ملكية', 'كفالة', 'الحق', 'قرض',
             'أركان العقد', 'مقاولة', 'حلول', 'حُسن نية', 'مقاصة', 'عقد'],
    "مرافعات": ['تمييز', 'حكم', 'بطلان حُكم المُحكم', 'دعوى'],
    "إثبات": ['الإثبات'],
    "إداري": ['ضرائب ()'],
    "دستوري": ['اتفاقيات ومعاهدات'],
}

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    grand = 0
    for dest, topics in MOVES.items():
        moved = 0
        for topic in topics:
            cur.execute("""UPDATE knowledge_objects SET branch=%s, updated_at=now()
                           WHERE object_type='judicial_principle' AND branch='تجاري'
                             AND topic=%s""", (dest, topic))
            moved += cur.rowcount
            if cur.rowcount == 0:
                print("  (لم يوجد: '%s')" % topic, flush=True)
        grand += moved
        print("-> %s : %d" % (dest, moved), flush=True)
    print("\nإجمالي المنقول:", grand, flush=True)

    print("\n== ما بقي تحت تجاري بعد النقل (كامل القائمة) ==", flush=True)
    cur.execute("""SELECT coalesce(NULLIF(topic,''),'بلا موضوع'), count(*) FROM knowledge_objects
                   WHERE object_type='judicial_principle' AND branch='تجاري'
                   GROUP BY 1 ORDER BY 2 DESC""")
    rows = cur.fetchall()
    for t, c in rows:
        print("  '%s' : %d" % (t[:50], c), flush=True)
    print("عدد المواضيع المتبقية:", len(rows), flush=True)

    cur.execute("""SELECT branch, count(*) FROM knowledge_objects
                   WHERE object_type='judicial_principle'
                   GROUP BY 1 ORDER BY 2 DESC""")
    print("\n== توزيع المبادئ على الفروع الآن ==", flush=True)
    for b, c in cur.fetchall():
        print("  %s : %d" % (b or 'بلا فرع', c), flush=True)
PYEOF
echo "===== اكتمل الأمر 48 ====="