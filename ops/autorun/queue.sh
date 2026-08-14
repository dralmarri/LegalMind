#!/bin/bash
# أمر آلي 19: عاجل جداً — إيقاف فوري ونهائي لكل عمل يستدعي النموذج تلقائياً (تكلفة حقيقية)
# لن يُستأنف شيء إلا بطلب صريح من المستخدم. يبقى فقط تصحيح التصنيف (مجاني — قاعدة بيانات فقط).
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

echo "===== إيقاف فوري لكل استهلاك تلقائي (الأولوية القصوى) ====="

echo "== 1) تعطيل الجدولة الدائمة (مراجعة + تنظيف طباعي) =="
rm -f /etc/cron.d/legalmind-autoreview /etc/cron.d/legalmind-typofix
echo "أُزيلت جداول cron الدائمة نهائياً ✓ (لن تعمل تلقائياً بعد الآن)"

echo ""
echo "== 2) إنهاء أي عملية تستدعي النموذج تعمل الآن =="
for p in reviewer.py typo_fixer.py table_reader.py; do
  pkill -f "$p" 2>/dev/null && echo "  أُنهيت: $p" || echo "  لم تكن تعمل: $p"
done

echo ""
echo "== 3) عدد استدعاءات النموذج اليوم (تقدير من السجلات المتاحة) =="
grep -c "محاولة\|صفحات\|نتيجة الجولة" /root/reviewer.log 2>/dev/null | sed 's/^/  سطور نشاط المراجعة الدائمة: /' || true
grep -c "محاولة\|فُحص" /root/typofix.log 2>/dev/null | sed 's/^/  سطور نشاط التنظيف الطباعي: /' || true
ls -la /root/tables-reingest*.log 2>/dev/null | wc -l | sed 's/^/  عدد محاولات إعادة قراءة الكتاب السابع عشر (بصرية، الأعلى تكلفة): /'

echo ""
echo "===== لن يُستدعى النموذج بعد الآن إلا بأمر صريح جديد منك عبر القناة ====="

echo ""
echo "== 4) تصحيح التصنيف المتبقي (مجاني تماماً — قاعدة بيانات فقط، صفر استدعاء نموذج) =="
cat > /root/reclass_free.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
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
    if j >= 1: return "judicial"
    if b >= 1: return "bylaw"
    return "ambiguous"

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    # تراجع عن أي إصلاح سابق أخطأ (لو كان الأمر 17 قد نُفّذ فعلاً بمعيار النسبة الخطر)
    cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic,
                          metadata->>'micro_issue', source_key
                   FROM knowledge_objects
                   WHERE metadata->>'reclassified_from' = 'judicial_principle'
                     AND coalesce(metadata->>'reclass_method','') <> 'content_check_v2'""")
    prev = cur.fetchall()
    reverted = 0
    touched_sources = set()
    for oid, title, text, ot, br, tp, st, mi, sk in prev:
        if content_kind(text, title) == "judicial":
            cur.execute("""UPDATE knowledge_objects SET object_type='judicial_principle',
                           metadata = metadata - 'reclassified_from', updated_at=now() WHERE id=%s""", (oid,))
            reverted += 1
            touched_sources.add(sk)
    print("رُدّ للأصل (كان إصلاحاً خاطئاً بمعيار النسبة القديم):", reverted, flush=True)

    # التصحيح الصحيح بمعيار المحتوى فقط
    cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic,
                          metadata->>'micro_issue', source_key
                   FROM knowledge_objects WHERE object_type='judicial_principle'""")
    rows = cur.fetchall()
    fixed = 0
    for oid, title, text, ot, br, tp, st, mi, sk in rows:
        if content_kind(text, title) == "bylaw":
            cur.execute("""UPDATE knowledge_objects SET object_type='legislation_article',
                           metadata = metadata || '{"reclassified_from":"judicial_principle","reclass_method":"content_check_v2"}'::jsonb,
                           updated_at=now() WHERE id=%s""", (oid,))
            fixed += 1
            touched_sources.add(sk)
    print("أُعيد تصنيفه بثقة (نص لائحة صريح بلا أثر قضائي):", fixed, flush=True)

    for sk in touched_sources:
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
    print("أُعيدت فهرسة %d مصدراً متأثراً (فهرسة عادية، بلا تكلفة نموذج)" % len(touched_sources), flush=True)

    cur.execute("""SELECT object_type, count(*) FROM knowledge_objects
                   WHERE object_type IN ('judicial_principle','legislation_article','legislation','regulatory_table')
                   GROUP BY 1 ORDER BY 2 DESC""")
    print("\nتوزيع الأنواع الآن:", flush=True)
    for ot, c in cur.fetchall():
        print("  %s: %d" % (ot, c), flush=True)
PYEOF
/opt/LegalMind/.venv/bin/python /root/reclass_free.py > /root/reclass_free.log 2>&1
cat /root/reclass_free.log

{
  echo "=== إيقاف طارئ لكل استهلاك تلقائي + تصحيح مجاني — $(date -u +%F' '%T) UTC ==="
  echo ""
  echo "تم إيقاف نهائياً: خدمة المراجعة الدورية، خدمة التنظيف الطباعي، أي إعادة قراءة جارية."
  echo "لن يُستدعى نموذج الذكاء الاصطناعي بعد الآن إلا بأمر صريح جديد."
  echo ""
  echo "-- التصحيح المجاني المتبقي (قاعدة بيانات فقط) --"
  cat /root/reclass_free.log
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشر تقرير الإيقاف الطارئ ====="
