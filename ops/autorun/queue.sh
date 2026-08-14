#!/bin/bash
# أمر آلي 55: (أ) فرز المبادئ المتناثرة تحت تجاري إلى فروعها بالكلمات المفتاحية (ب) تسمية بطاقات القوانين بلا اسم
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
from collections import Counter
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

KEEP = ['تجاري', 'تجارية', 'شيك', 'كمبيالة', 'شحن', 'سفينة', 'بحري', 'جوي', 'بنك', 'بنوك',
        'مصرف', 'إفلاس', 'افلاس', 'شرك', 'أسواق المال', 'اسواق المال', 'متجر', 'صراف',
        'حساب جاري', 'تأمين', 'أوراق مالية', 'سمسرة', 'مضاربة', 'استثمار', 'فوائد', 'رجوع',
        'أعمال تجارية', 'اعمال تجارية', 'إدراج', 'اكتتاب']
EVID = ['إثبات', 'اثبات', 'يمين', 'إقرار', 'اقرار', 'قرائن', 'قرينة', 'خبير', 'خبرة',
        'استجواب', 'تزوير', 'محرر', 'بينة']
PROC = ['تمييز', 'استئناف', 'استئنا', 'طعن', 'دعوى', 'دعاوى', 'خصوم', 'اختصاص', 'إعلان', 'اعلان',
        'محكمة', 'حكم', 'قاض', 'قضاة', 'مرافعات', 'تنفيذ', 'أمر أداء', 'أمر الأداء', 'التماس',
        'رسوم قضائية', 'جلسة', 'حجز', 'تحكيم', 'صحيفة', 'ميعاد', 'إحالة', 'احالة',
        'قضاء مستعجل', 'أعمال ولائية', 'أوامر ولائية', 'محضر']
CIV = ['عقد', 'عقود', 'التزام', 'تعويض', 'مسئولية', 'مسؤولية', 'ضرر', 'إيجار', 'ايجار', 'بيع',
       'ملكية', 'كفالة', 'قرض', 'مقاولة', 'تقادم', 'إثراء', 'اثراء', 'وكالة', 'حوالة', 'رهن',
       'شيوع', 'قسمة', 'صلح', 'وديعة', 'صورية', 'غلط', 'تدليس', 'إذعان', 'فسخ', 'حراسة',
       'نظام عام', 'آداب', 'حسن نية', 'حُسن نية', 'سوء نية', 'شرط جزائي', 'مرض الموت', 'تعسف',
       'إعالة', 'ديات', 'بناء على أرض الغير', 'أتعاب المحاماة']

def classify(t):
    for k in KEEP:
        if k in t:
            return None
    for k in EVID:
        if k in t:
            return 'إثبات'
    for k in PROC:
        if k in t:
            return 'مرافعات'
    for k in CIV:
        if k in t:
            return 'مدني'
    return None

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    print("== (أ) فرز المبادئ المتبقية تحت تجاري ==", flush=True)
    cur.execute("""SELECT coalesce(topic,''), count(*) FROM knowledge_objects
                   WHERE object_type='judicial_principle' AND branch='تجاري'
                   GROUP BY 1""")
    plan = {'إثبات': [], 'مرافعات': [], 'مدني': []}
    kept = 0
    for t, c in cur.fetchall():
        dest = classify(t)
        if dest:
            plan[dest].append(t)
        else:
            kept += c
    total_moved = 0
    for dest, topics in plan.items():
        if not topics:
            continue
        cur.execute("""UPDATE knowledge_objects SET branch=%s, updated_at=now()
                       WHERE object_type='judicial_principle' AND branch='تجاري'
                         AND topic = ANY(%s)""", (dest, topics))
        total_moved += cur.rowcount
        print("-> %s : %d مبدأ (%d موضوعاً)" % (dest, cur.rowcount, len(topics)), flush=True)
        for s in topics[:8]:
            print("     مثال: %s" % s[:60], flush=True)
    print("انتقل: %d | بقي في تجاري: %d" % (total_moved, kept), flush=True)

    cur.execute("""SELECT branch, count(*) FROM knowledge_objects
                   WHERE object_type='judicial_principle' GROUP BY 1 ORDER BY 2 DESC""")
    print("\nالتوزيع النهائي:", flush=True)
    for b, c in cur.fetchall():
        print("  %s : %d" % (b or '-', c), flush=True)

    print("\n== (ب) بطاقات القوانين بلا اسم ==", flush=True)
    cur.execute("""SELECT id, coalesce(title,''), coalesce(metadata->>'library_card_name','')
                   FROM knowledge_objects
                   WHERE object_type IN ('legislation_article','legislation',
                                         'legislation_issuing_article','legislation_preamble')""")
    groups = {}
    for oid, title, cardname in cur.fetchall():
        m = re.match(r'^((?:legis|lreg|regl|reg|TBL)[-][^-]+[-][^-]+)', oid)
        key = m.group(1) if m else oid.rsplit('-', 1)[0]
        groups.setdefault(key, []).append((title, cardname))
    fixed = 0
    for key, items in sorted(groups.items()):
        has_card = any(cn for _, cn in items)
        has_dash = any('—' in t for t, _ in items)
        if has_card or has_dash:
            continue
        names = Counter()
        for t, _ in items:
            t = (t or '').strip()
            mm = re.search(r'((?:قانون|مرسوم|قرار|لائحة|اتفاقية)[^.\n]{5,90})', t)
            if mm:
                names[mm.group(1).strip()] += 1
        print("  المجموعة %s (%d كائناً):" % (key, len(items)), flush=True)
        if names:
            best, freq = names.most_common(1)[0]
            cur.execute("""UPDATE knowledge_objects
                           SET metadata = coalesce(metadata,'{}'::jsonb)
                                 || jsonb_build_object('library_card_name', %s::text),
                               updated_at=now()
                           WHERE id LIKE %s""", (best[:90], key + '-%'))
            fixed += 1
            print("    سُمّيت: '%s' (تكرار الاسم في %d عنواناً، حُدّث %d كائناً) ✓" % (best[:70], freq, cur.rowcount), flush=True)
        else:
            samples = [t[:70] for t, _ in items[:3] if t]
            print("    !! تعذر استخراج اسم آمن — عينات: %s" % (" | ".join(samples) if samples else "(عناوين فارغة)"), flush=True)
    print("\nبطاقات سُمّيت آلياً:", fixed, flush=True)
PYEOF
echo "===== اكتمل الأمر 55 ====="