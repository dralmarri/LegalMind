#!/bin/bash
# أمر آلي 21: إعادة الصورة الكاملة (كتب + مبادئ) مع تشخيص كل خطوة — قراءة فقط، صفر تكلفة
echo "بدء التنفيذ..."
set -e

echo "تحميل ملف الإعدادات..."
if [ -f /opt/LegalMind/deploy/.env ]; then
  set -a
  source /opt/LegalMind/deploy/.env
  set +a
  echo "حُمّل بنجاح ✓"
else
  echo "خطأ: ملف الإعدادات غير موجود!"
  exit 1
fi

echo "التحقق من اتصال قاعدة البيانات..."
docker exec legalmind-postgres psql -U legalmind -d legalmind -c "SELECT 1;" > /dev/null 2>&1 \
  && echo "القاعدة تستجيب ✓" || echo "تحذير: القاعدة لا تستجيب!"

echo "كتابة سكربت الفحص..."
cat > /root/full_picture2.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
print("بدء فحص بايثون...", flush=True)
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
print("تم استيراد المحرك ✓", flush=True)

BOOK_NUM = {
    "التاسع عشر": 19, "الثامن عشر": 18, "السابع عشر": 17, "السادس عشر": 16,
    "الخامس عشر": 15, "الرابع عشر": 14, "الثالث عشر": 13, "الثاني عشر": 12,
    "الحادي عشر": 11, "العاشر": 10, "التاسع": 9, "الثامن": 8, "السابع": 7,
    "السادس": 6, "الخامس": 5, "الرابع": 4, "الثالث": 3, "الثاني": 2,
    "الاول": 1, "الأول": 1,
}

def book_number(fname):
    f = (fname or "").replace("-", " ").replace("_", " ")
    for key in sorted(BOOK_NUM, key=len, reverse=True):
        if key in f:
            return BOOK_NUM[key]
    return None

def looks_garbled(text):
    t = text or ""
    digits = len(re.findall(r"\d", t))
    density = digits / max(1, len(t))
    en_hit = any(m in t for m in ("Venture Capital", "Private Equity", "Off Balance"))
    frags = [x for x in t.split("\n") if x.strip()]
    short = sum(1 for x in frags if 0 < len(x.strip()) < 25)
    return ((density > 0.06) + (en_hit * 2) + (short >= 4)) >= 2

JUDICIAL_MARKERS = ["الطعن رقم", "الطعن ", "جلسة ", "محكمة التمييز", "محكمة الاستئناف",
                     "قضت محكمة", "قضت المحكمة", "مج القسم", "مجلس التأديب", "مبدأ:", "المبدأ:"]

def has_judicial_marker(text):
    t = text or ""
    return any(m in t for m in JUDICIAL_MARKERS)

print("الاتصال بقاعدة البيانات...", flush=True)
conn = eng.psycopg.connect(eng.database_url())
print("اتصال ناجح ✓", flush=True)
cur = conn.cursor()

print("\n===== (1) كتب اللائحة التنفيذية =====", flush=True)
cur.execute("""SELECT source_key, file_name FROM sources
               WHERE file_name ILIKE '%الكتاب%' AND file_name ILIKE '%اسواق-المال%'""")
sources = cur.fetchall()
print("مصادر بنمط 'الكتاب...اسواق-المال':", len(sources), flush=True)

bylaw_source_keys = set()
books = {}
for sk, fname in sources:
    bylaw_source_keys.add(sk)
    n = book_number(fname)
    cur.execute("""SELECT object_type, verification_status, usable_as_citation, original_text
                   FROM knowledge_objects WHERE source_key=%s""", (sk,))
    rows = cur.fetchall()
    garbled = sum(1 for r in rows if looks_garbled(r[3]))
    by_type = {}
    for r in rows:
        by_type[r[0]] = by_type.get(r[0], 0) + 1
    books[n or fname] = {"file": fname, "total": len(rows), "garbled": garbled, "by_type": by_type}

healthy = missing = garbled_books = misclassified = 0
for n in range(5, 20):
    b = books.get(n)
    if not b:
        print("  كتاب %d: غير مرفوع إطلاقاً" % n, flush=True)
        missing += 1
        continue
    gr = b["garbled"] / b["total"] if b["total"] else 0
    jur = b["by_type"].get("judicial_principle", 0)
    jur_ratio = jur / b["total"] if b["total"] else 0
    if gr > 0.15:
        status = "مشوّه (يحتاج إعادة قراءة مكلفة)"; garbled_books += 1
    elif jur_ratio > 0.1:
        status = "بقي فيه تصنيف خاطئ"; misclassified += 1
    else:
        status = "سليم"; healthy += 1
    print("  كتاب %d: %d كائن | عطب=%.0f%% | مبدأ_قضائي_متبقٍ=%d | %s | %s" %
          (n, b["total"], gr * 100, jur, status, b["file"][:45]), flush=True)

print("\nخلاصة الكتب (من أصل 15: كتب 5-19):", flush=True)
print("  سليمة: %d | غير مرفوعة: %d | مشوّهة: %d | تصنيف خاطئ متبقٍ: %d" %
      (healthy, missing, garbled_books, misclassified), flush=True)

print("\n\n===== (2) ملفات المبادئ القانونية المنفصلة =====", flush=True)
cur.execute("SELECT DISTINCT source_key FROM knowledge_objects WHERE object_type='judicial_principle'")
jur_source_keys = {r[0] for r in cur.fetchall()}
principle_sources = jur_source_keys - bylaw_source_keys
print("مصادر منفصلة فيها كائنات 'مبدأ قضائي':", len(principle_sources), flush=True)

p_healthy = p_garbled = p_ambiguous = 0
for sk in principle_sources:
    cur.execute("SELECT file_name FROM sources WHERE source_key=%s", (sk,))
    r = cur.fetchone()
    fname = r[0] if r else (sk or "بلا اسم/بلا مصدر مسجل")
    cur.execute("""SELECT title, original_text FROM knowledge_objects
                   WHERE source_key=%s AND object_type='judicial_principle'""", (sk,))
    rows = cur.fetchall()
    total = len(rows)
    garbled = sum(1 for t, tx in rows if looks_garbled(tx))
    with_marker = sum(1 for t, tx in rows if has_judicial_marker(tx))
    marker_ratio = with_marker / total if total else 0
    gr = garbled / total if total else 0
    if gr > 0.15:
        status = "مشوّه"; p_garbled += 1
    elif marker_ratio > 0.5:
        status = "سليم — مبادئ حقيقية موثّقة"; p_healthy += 1
    else:
        status = "غامض (يستحق مراجعتك)"; p_ambiguous += 1
    print("  %s: %d كائن | أثر قضائي واضح=%.0f%% | عطب=%.0f%% | %s" %
          (str(fname)[:45], total, marker_ratio * 100, gr * 100, status), flush=True)

print("\nخلاصة ملفات المبادئ (%d ملفاً):" % len(principle_sources), flush=True)
print("  سليمة: %d | مشوّهة: %d | غامضة: %d" % (p_healthy, p_garbled, p_ambiguous), flush=True)

cur.execute("SELECT count(*) FROM knowledge_objects WHERE object_type='judicial_principle'")
print("\nإجمالي 'مبدأ قضائي' في كل القاعدة:", cur.fetchone()[0], flush=True)

print("\n\n===== (3) حالة التوثيق الكلية =====", flush=True)
cur.execute("SELECT verification_status, count(*) FROM knowledge_objects GROUP BY 1 ORDER BY 2 DESC")
for vs, c in cur.fetchall():
    print("  %s: %d" % (vs, c), flush=True)

conn.close()
print("\nانتهى الفحص بنجاح ✓", flush=True)
PYEOF
echo "سُكتب السكربت ✓"

echo "تشغيل الفحص..."
/opt/LegalMind/.venv/bin/python /root/full_picture2.py > /root/full_picture2.log 2>&1
RC=$?
echo "انتهى التشغيل (رمز الخروج=$RC)"
echo ""
echo "===== محتوى السجل ====="
cat /root/full_picture2.log
echo "===== نهاية السجل ====="

TOKEN=$(cat /opt/legalmind-autopilot/token 2>/dev/null || echo "unknown")
{
  echo "=== الصورة الكاملة v2 (مع تشخيص) — $(date -u +%F' '%T) UTC ==="
  echo ""
  cat /root/full_picture2.log
} > "/var/www/legalmind-v3/review-${TOKEN}.txt"
echo "نُشر التقرير على review-${TOKEN}.txt"
