#!/bin/bash
# أمر آلي 14: (أ) تجاهل عناصر غير سليمة النوع من رد النموذج بدل الانهيار
#            (ب) استئناف تراكمي حقيقي: تخطي الدُفعات المكتملة فقط، إكمال الباقي، لا تخطي كامل
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

echo "== إصلاح شامل لـ table_reader.py =="
python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
p = "/opt/LegalMind/tools/table_reader.py"
src = open(p, encoding="utf-8").read()

# 1) تنقية العناصر غير السليمة قبل إرجاعها من call()
OLD_CALL = '''            for blk in res.get("content", []):
                if blk.get("type") == "tool_use":
                    return blk["input"].get("units", [])
            return []'''
NEW_CALL = '''            for blk in res.get("content", []):
                if blk.get("type") == "tool_use":
                    raw = blk["input"].get("units", [])
                    clean = [u for u in raw if isinstance(u, dict)]
                    if len(clean) != len(raw):
                        print("    تجاهلت %d عنصراً غير سليم النوع من رد النموذج" %
                              (len(raw) - len(clean)), flush=True)
                    return clean
            return []'''
assert OLD_CALL in src, "لم أجد call()"
src = src.replace(OLD_CALL, NEW_CALL, 1)

# 2) استئناف تراكمي حقيقي: تتبع الدُفعات المكتملة، وتخطي المكتمل فقط لا الكل
OLD_RUN = '''    # استئناف من نقطة حفظ سابقة إن وُجدت لنفس الملف (لا نعيد استدعاء النموذج بلا داع)
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
        print("حُفظت نقطة الحفظ الكاملة: %d عنصر" % len(all_units), flush=True)'''

NEW_RUN = '''    # استئناف تراكمي: تحميل ما أُنجز سابقاً، وتخطي دُفعات الصفحات المكتملة فقط
    all_units, done_parts = [], set()
    if os.path.exists(ckpt_path):
        try:
            ck = json.load(open(ckpt_path, encoding="utf-8"))
            if ck.get("path") == path:
                all_units = [(u["part"], u["unit"]) for u in ck.get("units", [])]
                done_parts = set(ck.get("done_parts", []))
                print("استئناف: %d عنصر محفوظ | %d دفعة صفحات مكتملة مسبقاً" %
                      (len(all_units), len(done_parts)), flush=True)
        except Exception as exc:
            print("تعذرت قراءة نقطة الحفظ (سنبدأ من الصفر): %s" % exc, flush=True)

    def save_ckpt():
        json.dump({"path": path, "done_parts": sorted(done_parts),
                   "units": [{"part": part, "unit": u} for part, u in all_units]},
                  open(ckpt_path, "w", encoding="utf-8"), ensure_ascii=False)

    for p in range(0, npg, PAGES_PER_BATCH):
        if p in done_parts:
            continue
        b64 = slice_pdf(reader, p, p + PAGES_PER_BATCH)
        print("  صفحات %d-%d..." % (p, min(p + PAGES_PER_BATCH, npg)), flush=True)
        units = call(b64)
        tbl_n = sum(1 for u in units if u.get("kind") == "table")
        print("    استُخرج %d عنصراً (%d جدول)" % (len(units), tbl_n), flush=True)
        all_units += [(p, u) for u in units]
        done_parts.add(p)
        save_ckpt()   # حفظ فوري بعد كل دفعة — لا خسارة عند أي عطل لاحق
    print("اكتمل الاستخراج: %d عنصر إجمالاً عبر %d دفعة" % (len(all_units), len(done_parts)), flush=True)'''

assert OLD_RUN in src, "لم أجد كتلة الاستخراج الرئيسية"
src = src.replace(OLD_RUN, NEW_RUN, 1)

open(p, "w", encoding="utf-8").write(src)
print("أُصلح الكود (تنقية + استئناف تراكمي) ✓")
PYEOF

/opt/LegalMind/.venv/bin/python -m py_compile /opt/LegalMind/tools/table_reader.py && echo "الكود سليم ✓"

echo ""
echo "== حالة نقطة الحفظ الحالية قبل الاستئناف =="
python3 -c "
import json
try:
    ck = json.load(open('/root/table_reader_checkpoint.json', encoding='utf-8'))
    print('عناصر محفوظة:', len(ck.get('units', [])))
    print('دُفعات مكتملة سابقاً:', ck.get('done_parts', 'غير مسجلة (نسخة قديمة) — ستُعاد كل الدفعات')) 
except Exception as e:
    print('لا نقطة حفظ:', e)
"

echo ""
echo "== استئناف القراءة الجدولية (يتخطى ما اكتمل فقط) =="
FNAME="BATCH-20260813-223443-937A1650__الكتاب-السابع-عشر-اسواق-المال.pdf"
[ -f "/opt/legalmind-ingest/inbox/${FNAME}" ] || \
  cp -a "/opt/legalmind-ingest/archive/${FNAME}" "/opt/legalmind-ingest/inbox/${FNAME}"

nohup /opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/table_reader.py \
  "/opt/legalmind-ingest/inbox/${FNAME}" "تجاري" "أسواق المال" \
  > /root/tables-reingest4.log 2>&1 &
PID=$!
echo "انطلقت (PID=$PID)"

for i in $(seq 1 170); do
  kill -0 $PID 2>/dev/null || break
  sleep 10
done
echo "انتهت أو تجاوزت المهلة"

echo ""
echo "== سجل التنفيذ =="
cat /root/tables-reingest4.log

echo ""
echo "== تحقق ذاتي =="
/opt/LegalMind/.venv/bin/python /root/verify_tables.py > /root/verify3.log 2>&1 || true
cat /root/verify3.log
VERDICT=$(grep "الحكم النهائي" /root/verify3.log | grep -o "PASS\|PARTIAL\|FAIL" || echo "UNKNOWN")

{
  echo "=== إصلاح شامل + استئناف تراكمي — $(date -u +%F' '%T) UTC ==="
  echo "الحكم: $VERDICT"
  echo ""
  echo "-- سجل التنفيذ --"
  cat /root/tables-reingest4.log
  echo ""
  echo "-- التحقق الذاتي --"
  cat /root/verify3.log
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشرت النتيجة - الحكم: $VERDICT ====="
