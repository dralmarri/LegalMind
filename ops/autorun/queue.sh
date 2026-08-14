#!/bin/bash
# أمر آلي 53: استبدال نصوص المواد المعدلة بالقرار 99/2025 داخل متن 152/2023 + دمج البطاقتين + تسمية بطاقة 109/2026
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

AR = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""SELECT id, coalesce(original_text,'') FROM knowledge_objects
                   WHERE id LIKE 'legis-99-2025-issue-%%' ORDER BY id""")
    issues = cur.fetchall()
    print("== نصوص مواد إصدار القرار 99/2025 (%d) ==" % len(issues), flush=True)

    cur.execute("""SELECT id FROM knowledge_objects WHERE id LIKE 'legis-152-2023-m%%'""")
    base_ids = {r[0] for r in cur.fetchall()}
    print("مواد القرار الأصلي:", len(base_ids), flush=True)

    NEWNAME = 'تنظيم مهنة مقيمي العقار ومقدمي خدمات التقييم (152/2023 وتعديله بالقرار 99/2025)'
    replaced = []
    unparsed = []
    for oid, txt in issues:
        t = txt.strip()
        print("\n--- %s ---" % oid, flush=True)
        print(t[:2000], flush=True)
        segs = re.split(r'(?:^|\n)\s*(?:مادة|المادة)\s*\(?\s*([0-9٠-٩]+)\s*\)?\s*(?:مكرر[اً]?\s*)?[:\-–—]?\s*\n?', t)
        # segs = [مقدمة إجرائية, رقم1, نص1, رقم2, نص2, ...]
        pairs = []
        for i in range(1, len(segs) - 1, 2):
            num = segs[i].translate(AR)
            body = (segs[i + 1] or '').strip()
            if num.isdigit() and len(body) >= 80:
                pairs.append((num, body))
        if not pairs:
            unparsed.append(oid)
            print(">> لا نص مادة قابل للاستخراج آلياً من هذا الكائن (إجرائي غالباً).", flush=True)
            continue
        for num, body in pairs:
            tgt = 'legis-152-2023-m' + num
            if tgt in base_ids:
                cur.execute("SELECT coalesce(original_text,'') FROM knowledge_objects WHERE id=%s", (tgt,))
                old_txt = cur.fetchone()[0]
                cur.execute("""UPDATE knowledge_objects
                               SET original_text=%s, normalized_text=%s,
                                   metadata = coalesce(metadata,'{}'::jsonb)
                                     || jsonb_build_object('pre_amendment_text', %s::text)
                                     || jsonb_build_object('amended_by', 'القرار الوزاري 99/2025'::text),
                                   updated_at=now()
                               WHERE id=%s""", (body, body, old_txt, tgt))
                replaced.append(num)
                print(">> استُبدل نص المادة %s في القرار الأصلي (القديم محفوظ احتياطياً) ✓" % num, flush=True)
            else:
                print(">> المادة %s غير موجودة في الأصل — تُركت داخل مجلد القرار المعدِّل (لا إنشاء آلياً)." % num, flush=True)

    print("\n== دمج البطاقتين في بطاقة واحدة بمجلدين ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET metadata = coalesce(metadata,'{}'::jsonb)
                         || jsonb_build_object('library_group', 'legis-152-2023'::text)
                         || jsonb_build_object('doc_part', 'القرار الوزاري 99/2025 المعدِّل'::text)
                         || jsonb_build_object('library_card_name', %s::text),
                       updated_at=now()
                   WHERE id LIKE 'legis-99-2025-%%'""", (NEWNAME,))
    print("كائنات القرار المعدِّل المنقولة إلى البطاقة: %d ✓" % cur.rowcount, flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET metadata = coalesce(metadata,'{}'::jsonb)
                         || jsonb_build_object('doc_part', 'القرار 152/2023'::text)
                         || jsonb_build_object('library_card_name', %s::text),
                       updated_at=now()
                   WHERE id LIKE 'legis-152-2023-%%'""", (NEWNAME,))
    print("كائنات القرار الأصلي الموسومة: %d ✓" % cur.rowcount, flush=True)

    print("\n== تسمية بطاقة القرار 109/2026 (توصيل الطلبات) ==", flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET metadata = coalesce(metadata,'{}'::jsonb)
                         || jsonb_build_object('library_card_name',
                              'القرار 109/2026 — تنظيم قطاع توصيل الطلبات عبر المنصات'::text),
                       updated_at=now()
                   WHERE id LIKE 'legis-109-2026-%%'""")
    print("سُمّيت (%d كائناً) ✓" % cur.rowcount, flush=True)

    print("\n===== الخلاصة =====", flush=True)
    print("مواد استُبدل نصها: %s" % (", ".join(replaced) if replaced else "لا شيء"), flush=True)
    print("كائنات إصدار بقيت للاطلاع اليدوي: %s" % (", ".join(unparsed) if unparsed else "لا شيء"), flush=True)
    if replaced:
        print("ملاحظة: المواد المستبدلة قد تحتاج إعادة فهرسة دلالية لاحقاً (بتكلفة رمزية) — لن أفعلها إلا بموافقتك.", flush=True)
PYEOF
echo "===== اكتمل الأمر 53 ====="