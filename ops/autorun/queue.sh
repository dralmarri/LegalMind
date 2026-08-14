#!/bin/bash
# أمر آلي 13: إصلاح NotNullViolation (sha256) + checkpoint يحفظ نتائج الاستخراج فور وصولها
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

echo "== إصلاح table_reader.py: عمود sha256 الناقص + نقطة حفظ احتياطية =="
python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
p = "/opt/LegalMind/tools/table_reader.py"
src = open(p, encoding="utf-8").read()

# 1) إصلاح الإدراج الناقص + إضافة checkpoint فوري بعد الاستخراج
OLD = '''def run(path, branch, topic):
    reader = PdfReader(path)
    npg = len(reader.pages)
    print("الملف: %s (%d صفحة)" % (path, npg), flush=True)
    src_key = "SRC-" + hashlib.sha256(os.path.basename(path).encode()).hexdigest()[:20].upper()
    all_units = []
    for p in range(0, npg, PAGES_PER_BATCH):
        b64 = slice_pdf(reader, p, p + PAGES_PER_BATCH)
        print("  صفحات %d-%d..." % (p, min(p + PAGES_PER_BATCH, npg)), flush=True)
        units = call(b64)
        print("    استُخرج %d عنصراً (%d جدول)" %
              (len(units), sum(1 for u in units if u.get("kind") == "table")), flush=True)
        all_units += [(p, u) for u in units]

    with eng.psycopg.connect(eng.database_url()) as conn:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""INSERT INTO sources (source_key, source_type, title, file_name, verification_status, metadata)
                       VALUES (%s,'document',%s,%s,'source_verified','{}'::jsonb)
                       ON CONFLICT (source_key) DO NOTHING""",
                    (src_key, os.path.basename(path), os.path.basename(path)))'''

NEW = '''def run(path, branch, topic):
    reader = PdfReader(path)
    npg = len(reader.pages)
    print("الملف: %s (%d صفحة)" % (path, npg), flush=True)
    src_key = "SRC-" + hashlib.sha256(os.path.basename(path).encode()).hexdigest()[:20].upper()
    file_sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    ckpt_path = "/root/table_reader_checkpoint.json"

    # استئناف من نقطة حفظ سابقة إن وُجدت لنفس الملف (لا نعيد استدعاء النموذج بلا داع)
    all_units = []
    if os.path.exists(ckpt_path):
        try:
            ck = json.load(open(ckpt_path, encoding="utf-8"))
            if ck.get("path") == path:
                all_units = [(u["part"], u["unit"]) for u in ck.get("units", [])]
                print("استُؤنف من نقطة حفظ سابقة: %d عنصر محفوظ مسبقاً" % len(all_units), flush=True)
        except Exception as exc:
            print("تعذرت قراءة نقطة الحفظ: %s" % exc, flush=True)

    if not all_units:
        for p in range(0, npg, PAGES_PER_BATCH):
            b64 = slice_pdf(reader, p, p + PAGES_PER_BATCH)
            print("  صفحات %d-%d..." % (p, min(p + PAGES_PER_BATCH, npg)), flush=True)
            units = call(b64)
            print("    استُخرج %d عنصراً (%d جدول)" %
                  (len(units), sum(1 for u in units if u.get("kind") == "table")), flush=True)
            all_units += [(p, u) for u in units]
            # حفظ فوري بعد كل دفعة صفحات — لا نخسر العمل المكلف عند أي عطل لاحق
            json.dump({"path": path, "units": [{"part": part, "unit": u} for part, u in all_units]},
                      open(ckpt_path, "w", encoding="utf-8"), ensure_ascii=False)
        print("حُفظت نقطة الحفظ الكاملة: %d عنصر" % len(all_units), flush=True)

    with eng.psycopg.connect(eng.database_url()) as conn:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""INSERT INTO sources (source_key, source_type, title, file_name, sha256,
                                            content_sha256, verification_status, metadata)
                       VALUES (%s,'document',%s,%s,%s,%s,'source_verified','{}'::jsonb)
                       ON CONFLICT (source_key) DO NOTHING""",
                    (src_key, os.path.basename(path), os.path.basename(path), file_sha, file_sha))'''

assert OLD in src, "لم أجد الدالة المتوقعة"
src = src.replace(OLD, NEW, 1)

# 2) بعد نجاح الإدراج في القاعدة نظّف نقطة الحفظ حتى لا تتعارض مع ملف مختلف لاحقاً
OLD2 = '''        print("فُهرست %d نقطة في محرك البحث ✓" % len(rows), flush=True)'''
NEW2 = '''        print("فُهرست %d نقطة في محرك البحث ✓" % len(rows), flush=True)
    try:
        os.remove(ckpt_path)
    except Exception:
        pass'''
assert OLD2 in src, "لم أجد سطر الفهرسة"
src = src.replace(OLD2, NEW2, 1)

open(p, "w", encoding="utf-8").write(src)
print("أُصلح الكود ✓")
PYEOF

/opt/LegalMind/.venv/bin/python -m py_compile /opt/LegalMind/tools/table_reader.py && echo "الكود سليم ✓"

echo ""
echo "== التحقق من عمود sha256 في جدول sources (فهم القيد بدقة قبل إعادة التشغيل) =="
docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
  "SELECT column_name, is_nullable FROM information_schema.columns
   WHERE table_name='sources' AND is_nullable='NO';"

echo ""
echo "== إعادة تشغيل القراءة الجدولية (ستستأنف من نقطة الحفظ الفارغة، أي من الصفر لأنه لا حفظ سابق) =="
FNAME="BATCH-20260813-223443-937A1650__الكتاب-السابع-عشر-اسواق-المال.pdf"
if [ ! -f "/opt/legalmind-ingest/inbox/${FNAME}" ]; then
  echo "الملف غير موجود في صندوق الإدخال — نسخه من الأرشيف"
  cp -a "/opt/legalmind-ingest/archive/${FNAME}" "/opt/legalmind-ingest/inbox/${FNAME}"
fi
nohup /opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/table_reader.py \
  "/opt/legalmind-ingest/inbox/${FNAME}" "تجاري" "أسواق المال" \
  > /root/tables-reingest3.log 2>&1 &
PID=$!
echo "انطلقت (PID=$PID) — ستأخذ حتى 20 دقيقة (استدعاءات نموذج فعلية)"

echo ""
echo "== انتظار الاكتمال (حتى 25 دقيقة) =="
for i in $(seq 1 150); do
  kill -0 $PID 2>/dev/null || break
  sleep 10
done
echo "انتهت أو تجاوزت المهلة"

echo ""
echo "== سجل التنفيذ =="
cat /root/tables-reingest3.log

echo ""
echo "== تحقق ذاتي حقيقي =="
/opt/LegalMind/.venv/bin/python /root/verify_tables.py > /root/verify2.log 2>&1 || true
cat /root/verify2.log
VERDICT=$(grep "الحكم النهائي" /root/verify2.log | grep -o "PASS\|PARTIAL\|FAIL" || echo "UNKNOWN")

{
  echo "=== إعادة تشغيل مُصلَحة + تحقق ذاتي — $(date -u +%F' '%T) UTC ==="
  echo "الحكم: $VERDICT"
  echo ""
  echo "-- سجل التنفيذ --"
  cat /root/tables-reingest3.log
  echo ""
  echo "-- التحقق الذاتي --"
  cat /root/verify2.log
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشرت النتيجة - الحكم: $VERDICT ====="
