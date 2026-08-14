#!/bin/bash
# أمر آلي 61: هل ملف الكتاب العاشر (الإفصاح والشفافية) محفوظ على الخادم؟ + حجمه وعدد صفحاته لتقدير التكلفة
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

echo "== (أ) جدول المصادر: ملفات تذكر العاشر/الإفصاح =="
$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
with eng.psycopg.connect(eng.database_url()) as conn:
    cur = conn.cursor()
    cur.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_name='sources' ORDER BY ordinal_position""")
    cols = [r[0] for r in cur.fetchall()]
    print("أعمدة جدول sources:", ", ".join(cols), flush=True)
    namecol = next((c for c in ['filename','file_name','name','title','original_name','path'] if c in cols), None)
    if namecol:
        cur.execute("SELECT source_key, " + namecol + " FROM sources WHERE " + namecol + " ILIKE '%عاشر%' OR " + namecol + " ILIKE '%10%' OR " + namecol + " ILIKE '%افصاح%' OR " + namecol + " ILIKE '%إفصاح%' LIMIT 20")
        rows = cur.fetchall()
        if not rows:
            print("(لا ملف مطابق في جدول المصادر)", flush=True)
        for sk, nm in rows:
            print("  %s | %s" % (sk, str(nm)[:80]), flush=True)
        cur.execute("SELECT count(*) FROM sources")
        print("إجمالي الملفات المسجلة:", cur.fetchone()[0], flush=True)
    else:
        print("(لا عمود اسم ملف واضح)", flush=True)
PYEOF

echo ""
echo "== (ب) البحث في القرص عن ملف الكتاب العاشر =="
find /opt/LegalMind /root /home /var/www -maxdepth 4 -type f \
  \( -iname '*عاشر*' -o -iname '*افصاح*' -o -iname '*إفصاح*' -o -iname '*10*سواق*' -o -iname '*اسواق*10*' \) 2>/dev/null | head -30
echo "-- مجلدات الرفع المحتملة:"
for d in /opt/LegalMind/uploads /opt/LegalMind/data/uploads /opt/LegalMind/files /root/uploads /var/www/legalmind-v3/uploads; do
  [ -d "$d" ] && echo "[$d]" && ls -lat "$d" 2>/dev/null | head -25
done
echo ""
echo "-- كل ملفات PDF وZIP الكبيرة حديثة الرفع على الخادم:"
find /opt/LegalMind /root -maxdepth 4 -type f \( -iname '*.pdf' -o -iname '*.zip' \) -size +1M -newermt '2026-08-01' 2>/dev/null -printf '%s\t%p\n' | sort -rn | head -25
echo "===== اكتمل الأمر 61 ====="