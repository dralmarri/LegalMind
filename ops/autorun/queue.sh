#!/bin/bash
# أمر آلي 18: عاجل جداً — إيقاف الاعتماد على نسبة النوع (قد يفسد ملفات مبادئ حقيقية)
# استبداله بفحص محتوى كل كائن على حدة: مبدأ قضائي حقيقي (يذكر طعن/جلسة/محكمة) يبقى كما هو،
# ومادة لائحة تنفيذية حقيقية (فصل/مادة/تعريفات بلا أثر قضائي) تُعاد تصنيفها فقط
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

cat > /root/audit19_v2.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re, json
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

JUDICIAL_MARKERS = ["الطعن رقم", "الطعن ", "جلسة ", "محكمة التمييز", "محكمة الاستئناف",
                     "قضت محكمة", "قضت المحكمة", "مج القسم", "مبدأ:", "المبدأ:"]
BYLAW_MARKERS = ["الفصل ", "المادة ", "اللائحة التنفيذية", "الكتاب ", "جدول المحتويات",
                 "تعريفات", "الملحق رقم", "الباب "]

def content_kind(text, title):
    t = (text or "") + " " + (title or "")
    j = sum(1 for m in JUDICIAL_MARKERS if m in t)
    b = sum(1 for m in BYLAW_MARKERS if m in t)
    if j >= 1:
        return "judicial"       # فيه أثر قضائي حقيقي — لا يُمس مهما كان نوعه الحالي
    if b >= 1:
        return "bylaw"          # نص لائحة/تشريع صريح بلا أثر قضائي
    return "ambiguous"          # لا قرينة كافية — يُترك كما هو، لا قرار آلي

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    # 0) أولاً: هل نفّذ الأمر السابق (17) إعادة تصنيف فعلاً؟ إن كان قد فعل، دقّق كل واحدة ورُدّ الخطأ منها
    cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic,
                          metadata->>'micro_issue', source_key
                   FROM knowledge_objects
                   WHERE metadata->>'reclassified_from' = 'judicial_principle'""")
    prev_fixed = cur.fetchall()
    print("كائنات أعادها الأمر السابق تصنيفها (سنراجعها فرداً فرداً):", len(prev_fixed), flush=True)
    reverted = 0
    for oid, title, text, ot, br, tp, st, mi, sk in prev_fixed:
        kind = content_kind(text, title)
        if kind == "judicial":
            cur.execute("""UPDATE knowledge_objects
                           SET object_type='judicial_principle',
                               metadata = metadata - 'reclassified_from' || '{"revert_wrong_reclass":"true"}'::jsonb,
                               updated_at=now() WHERE id=%s""", (oid,))
            reverted += 1
            print("  رُدّ للأصل (مبدأ قضائي حقيقي وُجد فيه أثر قضائي): %s | %s" %
                  (oid[-14:], title[:50]), flush=True)
    if reverted:
        print("أُعيد %d كائناً لتصنيفه الصحيح (مبدأ قضائي) بعد ثبوت خطأ الإصلاح السابق ✓" % reverted, flush=True)
    else:
        print("لا حاجة لأي تراجع — الإصلاح السابق (إن نُفّذ) لم يمسّ أي مبدأ قضائي حقيقي", flush=True)

    # إعادة فهرسة ما رُدّ (إن وُجد)
    if reverted:
        sks = {sk for oid, title, text, ot, br, tp, st, mi, sk in prev_fixed}
        for sk in sks:
            cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic,
                                  metadata->>'micro_issue', source_key
                           FROM knowledge_objects WHERE source_key=%s""", (sk,))
            allr = cur.fetchall()
            for s in range(0, len(allr), 48):
                w = allr[s:s + 48]
                common = {"object_type": w[0][3], "branch": w[0][4], "topic": w[0][5],
                          "subtopic": w[0][6], "micro_issue": w[0][7], "source_key": w[0][8]}
                eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                                   {"points": eng.build_points([(x[0], x[1], x[2]) for x in w], common)})
        print("أُعيدت فهرسة المصادر المتأثرة بالتراجع ✓", flush=True)

    # 1) الفحص الصحيح من جديد: كل كائن نوعه judicial_principle حالياً — بمحتواه لا بنسبة مصدره
    cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic,
                          metadata->>'micro_issue', source_key
                   FROM knowledge_objects WHERE object_type='judicial_principle'""")
    all_jur = cur.fetchall()
    print("\nإجمالي الكائنات المصنّفة حالياً 'مبدأ قضائي' في كامل القاعدة:", len(all_jur), flush=True)

    to_fix = []
    kept_judicial = 0
    ambiguous = 0
    for oid, title, text, ot, br, tp, st, mi, sk in all_jur:
        kind = content_kind(text, title)
        if kind == "bylaw":
            to_fix.append((oid, title, text, ot, br, tp, st, mi, sk))
        elif kind == "judicial":
            kept_judicial += 1
        else:
            ambiguous += 1

    print("بمحتوى لائحة صريح (سيُعاد تصنيفه): %d" % len(to_fix), flush=True)
    print("بأثر قضائي حقيقي (يبقى كما هو): %d" % kept_judicial, flush=True)
    print("غامض (يُترك بلا قرار آلي، للمراجعة اليدوية لاحقاً): %d" % ambiguous, flush=True)

    fixed_sources = set()
    for oid, title, text, ot, br, tp, st, mi, sk in to_fix:
        cur.execute("""UPDATE knowledge_objects
                       SET object_type='legislation_article',
                           metadata = metadata || '{"reclassified_from":"judicial_principle","reclass_method":"content_check_v2"}'::jsonb,
                           updated_at=now() WHERE id=%s""", (oid,))
        fixed_sources.add(sk)

    for sk in fixed_sources:
        cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic,
                              metadata->>'micro_issue', source_key
                       FROM knowledge_objects WHERE source_key=%s""", (sk,))
        allr = cur.fetchall()
        for s in range(0, len(allr), 48):
            w = allr[s:s + 48]
            common = {"object_type": w[0][3], "branch": w[0][4], "topic": w[0][5],
                      "subtopic": w[0][6], "micro_issue": w[0][7], "source_key": w[0][8]}
            eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                               {"points": eng.build_points([(x[0], x[1], x[2]) for x in w], common)})
    print("\nأُعيد تصنيف %d كائناً عبر %d مصدراً وأُعيدت فهرستهم ✓" % (len(to_fix), len(fixed_sources)), flush=True)

    # 2) عيّنة للمراجعة البشرية: نماذج من "الغامض" حتى تحكم أنت لا الخوارزمية
    cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic,
                          metadata->>'micro_issue', source_key
                   FROM knowledge_objects WHERE object_type='judicial_principle'""")
    remaining = cur.fetchall()
    amb_sample = [(oid, title, text) for oid, title, text, ot, br, tp, st, mi, sk in remaining
                  if content_kind(text, title) == "ambiguous"][:6]
    print("\nعيّنة من الحالات الغامضة (لمراجعتك):", flush=True)
    for oid, title, text in amb_sample:
        print("  -", title[:50], "|", (text or "")[:120].replace("\n", " "), flush=True)

    # 3) حصيلة نهائية
    cur.execute("""SELECT object_type, count(*) FROM knowledge_objects
                   WHERE object_type IN ('judicial_principle','legislation_article','legislation','regulatory_table')
                   GROUP BY 1 ORDER BY 2 DESC""")
    print("\nتوزيع الأنواع في كامل القاعدة الآن:", flush=True)
    for ot, c in cur.fetchall():
        print("  %s: %d" % (ot, c), flush=True)
PYEOF
/opt/LegalMind/.venv/bin/python /root/audit19_v2.py > /root/audit19_v2.log 2>&1
cat /root/audit19_v2.log

{
  echo "=== تصحيح عاجل: فحص محتوى بدل نسبة + تراجع عن أي خطأ سابق — $(date -u +%F' '%T) UTC ==="
  echo ""
  cat /root/audit19_v2.log
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشر التصحيح العاجل ====="
