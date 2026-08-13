#!/bin/bash
# جولة تنظيف شاملة لبقايا ملفات العمل — لا تمس النسخ الاحتياطية ولا بيانات النظام
set -e
echo "===== المساحة قبل ====="
df -h / | tail -1

echo ""
echo "===== 1) ملفات العمل المؤقتة في /root ====="
cd /root
for f in maritime_repair.py maritime_watcher.py maritime_index.py maritime_coverage.py \
         auto_review.py auto_review_edited.py run_edited_review.sh attribute_laws.py \
         final_five.py draft_trace.py delete_resume.sh rerank_test.py claude_ingest_test.py \
         maritime-repair.log maritime-final.log maritime-index.log maritime-watcher.log \
         auto-review.log auto-review-edited.log attribute-laws.log final-five.log \
         delete-resume.log merge-build.log kmap.log maritime-edited.json merge-build.sh; do
  if [ -e "$f" ]; then
    echo "  حذف: $f ($(du -sh "$f" 2>/dev/null | cut -f1))"
    rm -f "$f"
  fi
done
[ -d /root/ingest-samples ] && { echo "  حذف مجلد: ingest-samples ($(du -sh /root/ingest-samples | cut -f1))"; rm -rf /root/ingest-samples; }
ls /root/ingest-preview-*.json > /dev/null 2>&1 && { echo "  حذف ملفات المعاينة"; rm -f /root/ingest-preview-*.json; }
echo "  تم ✓"

echo ""
echo "===== 2) النسخ المكررة في أرشيف المصادر (نُبقي أحدث نسخة من كل ملف) ====="
python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
import os, re, glob
from collections import defaultdict
files = glob.glob("/opt/legalmind-ingest/archive/*")
groups = defaultdict(list)
for f in files:
    base = os.path.basename(f)
    m = re.match(r"BATCH-(\d{8}-\d{6})-[0-9A-F]+__(?:DUPLICATE__)?(.+)$", base)
    if m:
        groups[m.group(2)].append((m.group(1), "DUPLICATE__" in base, f))
freed = 0
for name, lst in groups.items():
    lst.sort(key=lambda x: (x[1], x[0]))  # الأصلية قبل المكررة، والأقدم أولاً
    originals = [x for x in lst if not x[1]]
    keep = max(originals, key=lambda x: x[0])[2] if originals else max(lst, key=lambda x: x[0])[2]
    for ts, dup, f in lst:
        if f != keep:
            sz = os.path.getsize(f)
            freed += sz
            print("  حذف %s (%s م.بايت)" % (os.path.basename(f)[:70], round(sz/1048576, 1)))
            os.remove(f)
    print("  أُبقيت: %s" % os.path.basename(keep)[:70])
print("المساحة المحررة من الأرشيف: %.1f م.بايت" % (freed/1048576))
PYEOF

echo ""
echo "===== 3) إزالة صفحة /ingest-center القديمة (الواجهة المدمجة تغني عنها) ====="
if grep -q "ingest-center" /etc/nginx/sites-available/legalmind 2>/dev/null; then
  sed -i '/location = \/ingest-center/d' /etc/nginx/sites-available/legalmind
  nginx -t && systemctl reload nginx
  echo "  أُزيلت من nginx ✓"
else
  echo "  غير موجودة أصلاً ✓"
fi

echo ""
echo "===== 4) قضية التجربة في النظام ====="
docker exec legalmind-postgres psql -U legalmind -d legalmind -Atc \
  "SELECT id || ' | ' || title FROM legal_cases WHERE title LIKE 'تجربة%';" | sed 's/^/  وجدت: /'
docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
  "DELETE FROM case_authorities WHERE case_id IN (SELECT id FROM legal_cases WHERE title LIKE 'تجربة%');" 2>/dev/null || true
docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
  "DELETE FROM legal_cases WHERE title LIKE 'تجربة%';"

echo ""
echo "===== 5) ضغط سجلات النظام القديمة ====="
journalctl --vacuum-time=14d 2>&1 | tail -1
apt-get clean

echo ""
echo "===== ما بقي في /root (يفترض: النسخ الاحتياطية فقط) ====="
ls -lah /root/ | grep -vE '^\.|total|snap' | awk '{print "  " $NF " (" $5 ")"}' | grep -vE '^\s+\.\.?$' || true

echo ""
echo "===== المساحة بعد ====="
df -h / | tail -1
echo "===== اكتملت جولة التنظيف ====="
