#!/bin/bash
# المدخل الوحيد: بطاقة "إضافة مستند جديد" في الرئيسية تفتح المركز — وبناء ونشر يمسح الترقيعات
set -e
P=/opt/LegalMind/web/app/page.tsx
if grep -q "ingest-center" "$P"; then
  echo "المصدر مدموج مسبقا — ننتقل للبناء"
else
  cp "$P" "$P.bak_smartcenter"
  python3 - <<'PYEOF'
p = "/opt/LegalMind/web/app/page.tsx"
src = open(p, encoding="utf-8").read()
h = src.find('إضافة مستند جديد</h2>')
assert h != -1, "!! لم أجد العنوان"
start = src.rfind('return <div className="space-y-6">', 0, h)
assert start != -1, "!! لم أجد بداية الدالة"
endmark = '</div>;\n}\n\nfunction ResearchView'
end = src.find(endmark, h)
assert end != -1, "!! لم أجد نهاية الدالة"
NEW = '''return <div className="space-y-6">
    <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="mb-4"><h2 className="text-lg font-bold text-ink dark:text-white">إضافة مستند جديد</h2><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">قراءة وفهرسة ذكية بعقل كلود — ملفات متعددة معاً، تصنيف تلقائي، نسبة إنجاز حية، ومراجعة لما يحتاج نظرك.</p></div>
      <a href="/ingest-center" className="group relative flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50/50 px-6 py-12 text-center transition hover:border-brand-blue hover:bg-blue-50/40 dark:border-slate-600 dark:bg-slate-800/40">
        <div className="mb-4 grid h-16 w-16 place-items-center rounded-full bg-white shadow-sm transition group-hover:scale-110 dark:bg-slate-700"><UploadCloud size={30} className="text-brand-blue"/></div>
        <h3 className="mb-2 text-lg font-bold text-ink dark:text-white">رفع مستند</h3>
        <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">اسحب ملفاتك أو اخترها من جهازك — يقرؤها كلود ويفهرسها كمحرر خبير وتتابع الإنجاز أولاً بأول</p>
        <span className="rounded-xl bg-brand-blue px-8 py-3 font-bold text-white shadow-md shadow-brand-blue/20 transition group-hover:bg-brand-dark">رفع مستند</span>
      </a>
    </section>
  </div>;
}

function ResearchView'''
src = src[:start] + NEW + src[end + len(endmark):]
open(p, "w", encoding="utf-8").write(src)
print("استبدل القسم في المصدر بنجاح")
PYEOF
fi
cat > /root/merge-build.sh <<'EOS'
#!/bin/bash
set -e
cd /opt/LegalMind/web
echo "== بدء بناء الواجهة =="
npm run build
echo "== البناء نجح — النشر =="
rm -rf /root/legalmind-v3.bak-merge
cp -a /var/www/legalmind-v3 /root/legalmind-v3.bak-merge
cp -a /opt/LegalMind/web/out/. /var/www/legalmind-v3/
echo "== نُشر بنجاح — الترقيعات القديمة أزيلت والمدخل الموحد يعمل =="
EOS
chmod +x /root/merge-build.sh
nohup /root/merge-build.sh > /root/merge-build.log 2>&1 &
echo "انطلق البناء والنشر في الخلفية (2-4 دقائق)"
echo "تابعه: tail -5 /root/merge-build.log"
