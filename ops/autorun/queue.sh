#!/bin/bash
# أمر آلي 46: (أ) كسر تخزين CDN المؤقت في pull.sh (ب) تثبيت كل عناوين الكتب 5-19 (ج) إلحاق مبدأ 'الكتاب العاشر اسواق المال' بكتابه
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

echo "== (أ) كسر التخزين المؤقت في آلية السحب =="
cat > /opt/legalmind-autopilot/pull.sh <<'EOF'
#!/bin/bash
QDIR=/opt/legalmind-autopilot
TOKEN=$(cat "$QDIR/token")
URL="https://raw.githubusercontent.com/dralmarri/LegalMind/main/ops/autorun/queue.sh?nc=$(date +%s)"
NEW=$(curl -fsSL -H 'Cache-Control: no-cache' "$URL" 2>/dev/null) || exit 0
[ -n "$NEW" ] || exit 0
SUM=$(printf '%s' "$NEW" | sha256sum | cut -d' ' -f1)
LAST=$(cat "$QDIR/last-sha" 2>/dev/null || true)
[ "$SUM" = "$LAST" ] && exit 0
echo "$SUM" > "$QDIR/last-sha"
OUT="/var/www/legalmind-v3/status-$TOKEN.txt"
{
  echo "== تنفيذ آلي: $(date -u +%FT%TZ) | sha: ${SUM:0:12} =="
  printf '%s' "$NEW" | timeout 3300 bash 2>&1 | tail -n 500
  echo "== انتهى التنفيذ =="
} > "$OUT.tmp" 2>&1 && mv "$OUT.tmp" "$OUT"
EOF
chmod 700 /opt/legalmind-autopilot/pull.sh
echo "أُضيف كسر التخزين المؤقت ✓"

echo ""
echo "== (ب) تثبيت كل عناوين الكتب 5-19 + (ج) المبدأ اليتيم =="
$PY - &lt;&lt;'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

TITLES = {
    "الكتاب الخامس":      "أنشطة الأوراق المالية والأشخاص المسجلون",
    "الكتاب السادس":      "السياسات والإجراءات الداخلية للشخص المرخص له",
    "الكتاب السابع":      "أموال العملاء وأصولهم",
    "الكتاب الثامن":      "أخلاقيات العمل",
    "الكتاب التاسع":      "الاندماج والاستحواذ",
    "الكتاب العاشر":      "الإفصاح والشفافية",
    "الكتاب الحادي عشر":  "التعامل في الأوراق المالية",
    "الكتاب الثاني عشر":  "قواعد الإدراج",
    "الكتاب الثالث عشر":  "أنظمة الاستثمار الجماعي",
    "الكتاب الرابع عشر":  "سلوكيات السوق",
    "الكتاب الخامس عشر":  "حوكمة الشركات",
    "الكتاب السادس عشر":  "مكافحة غسل الأموال وتمويل الإرهاب",
    "الكتاب السابع عشر":  "تعليمات كفاية رأس المال للأشخاص المرخص لهم",
    "الكتاب الثامن عشر":  "التسجيل البيني للمنتجات المالية",
    "الكتاب التاسع عشر":  "التقنيات المالية",
}

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    done = skipped = 0
    for book, subject in TITLES.items():
        old = "اللائحة التنفيذية — " + book
        new = old + " — " + subject
        cur.execute("""UPDATE knowledge_objects
                       SET metadata = metadata || jsonb_build_object('doc_part', %s::text),
                           updated_at=now()
                       WHERE metadata->>'library_group'='cma-authority-unified'
                         AND metadata->>'doc_part' = %s""", (new, old))
        if cur.rowcount:
            done += 1
            print("ثُبِّت: %s — %s (%d)" % (book, subject[:35], cur.rowcount), flush=True)
        else:
            skipped += 1
    print("\nثُبِّت الآن: %d | كان مثبتاً مسبقاً: %d" % (done, skipped), flush=True)

    cur.execute("""UPDATE knowledge_objects
                   SET subtopic='الكتاب العاشر — الإفصاح والشفافية', updated_at=now()
                   WHERE object_type='judicial_principle'
                     AND topic='مبادئ هيئة أسواق المال'
                     AND (subtopic IS NULL OR subtopic='')""")
    print("مبادئ ألحقت بالكتاب العاشر:", cur.rowcount, flush=True)

    print("\n===== البنية الختامية لبطاقة هيئة أسواق المال =====", flush=True)
    cur.execute("""SELECT metadata->>'doc_part', count(*) FROM knowledge_objects
                   WHERE metadata->>'library_group'='cma-authority-unified'
                   GROUP BY 1 ORDER BY 1""")
    plain = 0
    for p, c in cur.fetchall():
        mark = ""
        if p and p.startswith("اللائحة") and p.count("—") < 2:
            mark = "  !! بلا عنوان بعد"
            plain += 1
        print("  %s : %d%s" % (p, c, mark), flush=True)
    print("\nمجلدات بلا عنوان متبقية:", plain, flush=True)
PYEOF
echo "===== اكتمل الأمر 46 ====="