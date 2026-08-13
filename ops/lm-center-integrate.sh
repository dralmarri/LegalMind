#!/bin/bash
# دمج مركز المصادر داخل واجهة النظام نفسها (مكون React في الصفحة الرئيسية) ثم بناء ونشر
set -e
P=/opt/LegalMind/web/app/page.tsx
cp "$P" "$P.bak_integrate"
python3 - <<'PYEOF'
p = "/opt/LegalMind/web/app/page.tsx"
src = open(p, encoding="utf-8").read()

if "SmartIngestCenter" in src:
    print("المكون مدمج مسبقا — ننتقل للبناء")
else:
    imp = 'import { useEffect as _uE, useRef as _uR, useState as _uS } from "react";\n'
    if '"use client";' in src:
        src = src.replace('"use client";', '"use client";\n' + imp, 1)
    elif "'use client';" in src:
        src = src.replace("'use client';", "'use client';\n" + imp, 1)
    else:
        src = imp + src

    h = src.find('إضافة مستند جديد</h2>')
    assert h != -1, "!! لم أجد العنوان"
    start = src.rfind('return <div className="space-y-6">', 0, h)
    assert start != -1, "!! لم أجد بداية الدالة"
    endmark = '</div>;\n}\n\nfunction ResearchView'
    end = src.find(endmark, h)
    assert end != -1, "!! لم أجد نهاية الدالة"

    NEW = '''return <SmartIngestCenter/>;
}

function SmartIngestCenter() {
  const [queue,setQueue]=_uS<any>({waiting:[],batches:[]});
  const [review,setReview]=_uS<any>({count:0,items:[]});
  const [sel,setSel]=_uS<any>({items:[]});
  const [checked,setChecked]=_uS<Record<string,number[]>>({});
  const [editing,setEditing]=_uS<Record<string,string>>({});
  const [fulls,setFulls]=_uS<Record<string,string>>({});
  const [opened,setOpened]=_uS<Record<string,boolean>>({});
  const [ptext,setPtext]=_uS(''); const [ptitle,setPtitle]=_uS('');
  const [pOpen,setPOpen]=_uS(false); const [busy,setBusy]=_uS(false);
  const [drag,setDrag]=_uS(false);
  const fiRef=_uR<HTMLInputElement>(null);
  const editRef=_uR<Record<string,string>>({}); editRef.current=editing;

  const loadQueue=async()=>{ try{ setQueue(await api<any>('/api/ingest/queue')); }catch{} };
  const loadReview=async()=>{ if(Object.keys(editRef.current).length) return; try{ setReview(await api<any>('/api/review/pending')); }catch{} };
  const loadSel=async()=>{ try{ setSel(await api<any>('/api/selection/pending')); }catch{} };
  _uE(()=>{ loadQueue(); loadReview(); loadSel();
    const a=setInterval(loadQueue,5000), b=setInterval(loadReview,20000), c=setInterval(loadSel,20000);
    return ()=>{ clearInterval(a); clearInterval(b); clearInterval(c); };
  },[]);

  const upload=async(files:FileList|File[])=>{
    const arr:File[]=Array.prototype.slice.call(files);
    for(const f of arr){
      const fd=new FormData(); fd.append('files',f);
      fd.append('source_type',''); fd.append('branch',''); fd.append('topic',''); fd.append('classification_title','');
      try{ await api<any>('/api/upload',{method:'POST',body:fd}); }
      catch(ex:any){ alert('تعذر رفع '+f.name+': '+(ex?.message||'')); }
    }
    loadQueue();
  };
  const sendPaste=async()=>{
    const tx=ptext.trim();
    if(tx.length<20){ alert('النص قصير جدًا — 20 حرفًا على الأقل'); return; }
    setBusy(true);
    const fd=new FormData(); fd.append('content',tx);
    fd.append('branch',''); fd.append('topic',''); fd.append('source_type',''); fd.append('classification_title','');
    fd.append('source_title',ptitle.trim());
    try{ await api<any>('/api/paste-text',{method:'POST',body:fd}); setPtext(''); setPtitle(''); setPOpen(false); loadQueue(); }
    catch(ex:any){ alert(ex?.message||'تعذر الإرسال'); }
    finally{ setBusy(false); }
  };
  const showFull=async(id:string)=>{
    setOpened(pp=>({...pp,[id]:!pp[id]}));
    if(!fulls[id]){ try{ const r=await api<any>('/api/review/text/'+encodeURIComponent(id)); setFulls(pp=>({...pp,[id]:r.text||''})); }catch{} }
  };
  const approve=async(id:string)=>{
    try{ await api<any>('/api/review/approve/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); }
    catch(ex:any){ alert(ex?.message||''); }
    loadReview(); loadQueue();
  };
  const reject=async(id:string)=>{
    if(!confirm('حذف نهائي؟')) return;
    try{ await api<any>('/api/review/reject/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); }
    catch(ex:any){ alert(ex?.message||''); }
    loadReview();
  };
  const startEdit=async(id:string)=>{
    try{ const r=await api<any>('/api/review/text/'+encodeURIComponent(id)); setEditing(pp=>({...pp,[id]:r.text||''})); }catch{}
  };
  const saveEdit=async(id:string)=>{
    setBusy(true);
    try{
      await api<any>('/api/review/edit/'+encodeURIComponent(id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:editing[id]||''})});
      setEditing(pp=>{ const q={...pp}; delete q[id]; return q; });
      loadReview(); loadQueue();
    }catch(ex:any){ alert(ex?.message||'تعذر الحفظ'); }
    finally{ setBusy(false); }
  };
  const cancelEdit=(id:string)=>setEditing(pp=>{ const q={...pp}; delete q[id]; return q; });
  const toggleChk=(bid:string,idx:number)=>setChecked(pp=>{
    const cur=new Set(pp[bid]||[]); if(cur.has(idx)) cur.delete(idx); else cur.add(idx);
    return {...pp,[bid]:Array.from(cur)};
  });
  const confirmSel=async(bid:string,all:boolean)=>{
    const idx:any = all ? 'all' : (checked[bid]||[]);
    if(!all && idx.length===0){ alert('حدد قطعة واحدة على الأقل'); return; }
    setBusy(true);
    try{ await api<any>('/api/selection/confirm/'+encodeURIComponent(bid),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({indices:idx})}); }
    catch(ex:any){ alert(ex?.message||''); }
    finally{ setBusy(false); }
    loadSel(); loadQueue();
  };
  const discardSel=async(bid:string)=>{
    if(!confirm('إهمال الملف كاملًا؟')) return;
    try{ await api<any>('/api/selection/discard/'+encodeURIComponent(bid),{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); }
    catch(ex:any){ alert(ex?.message||''); }
    loadSel(); loadQueue();
  };
  const chipCls=(s:string)=>((({waiting:'bg-amber-100 text-amber-800',started:'bg-blue-100 text-blue-700',completed:'bg-emerald-100 text-emerald-700',needs_selection:'bg-violet-100 text-violet-700',failed:'bg-rose-100 text-rose-700',duplicate:'bg-amber-100 text-amber-800'}) as any)[s]||'bg-slate-100 text-slate-600');
  const chipTxt=(s:string)=>((({waiting:'في الانتظار',started:'تحت المعالجة',completed:'اكتمل',needs_selection:'بانتظار اختيارك',failed:'فشل',duplicate:'مكرر'}) as any)[s]||s);

  return <div className="space-y-6">
    <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="mb-4"><h2 className="text-lg font-bold text-ink dark:text-white">إضافة مستند جديد</h2><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">قراءة وفهرسة ذكية بعقل كلود — ملفات متعددة، تصنيف تلقائي، نسبة إنجاز حية.</p></div>
      <label onDragOver={e=>{e.preventDefault();setDrag(true);}} onDragLeave={()=>setDrag(false)}
        onDrop={e=>{e.preventDefault();setDrag(false);upload(e.dataTransfer.files);}}
        className={'group relative flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition '+(drag?'border-brand-blue bg-blue-50/60 dark:bg-blue-900/10':'border-slate-300 bg-slate-50/50 hover:border-brand-blue hover:bg-blue-50/40 dark:border-slate-600 dark:bg-slate-800/40')}>
        <div className="mb-3 grid h-14 w-14 place-items-center rounded-full bg-white shadow-sm dark:bg-slate-700"><UploadCloud size={26} className="text-brand-blue"/></div>
        <h3 className="mb-1 text-lg font-bold text-ink dark:text-white">اسحب ملفاتك هنا (عدة ملفات معًا)</h3>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">أو انقر لاختيارها من جهازك — PDF · DOCX · TXT · MD · HTML — حتى 512 م.ب</p>
        <input ref={fiRef} type="file" multiple className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
          onChange={e=>{ const fs=Array.prototype.slice.call(e.target.files||[]); (e.target as any).value=''; upload(fs); }}/>
      </label>
      <button onClick={()=>setPOpen(!pOpen)} className="mt-3 text-sm font-bold text-brand-blue">&#128203; {pOpen?'إخفاء اللصق':'أو الصق نصًا قانونيًا مباشرة'}</button>
      {pOpen && <div className="mt-3 space-y-2">
        <input value={ptitle} onChange={e=>setPtitle(e.target.value)} className="input" placeholder="عنوان المصدر (اختياري)"/>
        <textarea value={ptext} onChange={e=>setPtext(e.target.value)} className="input min-h-48 leading-8" placeholder="الصق النص هنا كما هو حرفيًا — سيقرؤه كلود ويقطعه ويصنفه تلقائيًا"/>
        <button onClick={sendPaste} disabled={busy} className="rounded-xl bg-brand-blue px-6 py-2.5 font-bold text-white disabled:opacity-50">{busy?'جارٍ الإرسال...':'إرسال للمعالجة الذكية'}</button>
      </div>}
    </section>

    <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <h3 className="mb-3 font-bold text-ink dark:text-white">&#9201; الطابور</h3>
      {queue.waiting.length===0 && queue.batches.length===0 && <p className="text-sm text-slate-500 dark:text-slate-400">لا شيء في الطابور — ارفع ملفاتك أعلاه</p>}
      <div className="space-y-2">
        {queue.waiting.map((w:any,i:number)=><div key={'w'+i} className="rounded-xl border border-slate-100 p-3 dark:border-slate-800">
          <span className="text-sm font-bold text-ink dark:text-white">{w.file}</span>
          <span className={'ms-2 rounded-full px-3 py-0.5 text-xs '+chipCls('waiting')}>{chipTxt('waiting')}</span>
        </div>)}
        {queue.batches.map((b:any)=><div key={b.batch_id} className="rounded-xl border border-slate-100 p-3 dark:border-slate-800">
          <span className="text-sm font-bold text-ink dark:text-white">{b.title||b.file||b.batch_id}</span>
          <span className={'ms-2 rounded-full px-3 py-0.5 text-xs '+chipCls(b.status)}>{chipTxt(b.status)}</span>
          {b.status==='started' && <div><div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{b.stage} — {b.percent||0}%</div>
            <div className="mt-1 h-2 overflow-hidden rounded bg-slate-100 dark:bg-slate-800"><div className="h-full bg-brand-blue transition-all" style={{width:(b.percent||3)+'%'}}/></div></div>}
          {b.status==='completed' && <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{b.object_count||0} كائنًا{b.needs_review?(' — منها '+b.needs_review+' للمراجعة'):''}</div>}
          {b.status==='failed' && <div className="mt-1 text-xs text-rose-600">{b.error||''}</div>}
        </div>)}
      </div>
    </section>

    <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <h3 className="mb-3 font-bold text-ink dark:text-white">&#128269; بانتظار مراجعتك {review.count?'('+review.count+')':''}</h3>
      {(!review.items || review.items.length===0) && <p className="text-sm text-slate-500 dark:text-slate-400">لا شيء بانتظار المراجعة ✓</p>}
      <div className="space-y-3">
        {(review.items||[]).slice(0,30).map((it:any)=><div key={it.id} className="rounded-xl border border-slate-100 p-4 dark:border-slate-800">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-bold text-ink dark:text-white">{it.title}</span>
            <span className="rounded-full bg-pink-100 px-3 py-0.5 text-xs text-pink-800">ثقة {it.confidence||'?'}</span>
          </div>
          <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{it.branch} / {it.topic||''}</div>
          {it.notes && <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">&#128221; {it.notes}</div>}
          {editing[it.id]!==undefined
            ? <div className="mt-2">
                <textarea value={editing[it.id]} onChange={e=>setEditing(pp=>({...pp,[it.id]:e.target.value}))} className="input min-h-64 leading-8"/>
                <div className="mt-2 flex gap-2">
                  <button onClick={()=>saveEdit(it.id)} disabled={busy} className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-bold text-white disabled:opacity-50">{busy?'جارٍ الحفظ...':'حفظ واعتماد'}</button>
                  <button onClick={()=>cancelEdit(it.id)} className="rounded-lg border border-slate-300 px-5 py-2 text-sm font-bold text-slate-600 dark:border-slate-600 dark:text-slate-300">إلغاء</button>
                </div>
              </div>
            : <div className="mt-2">
                <button onClick={()=>showFull(it.id)} className="text-sm font-bold text-brand-blue">{opened[it.id]?'إخفاء النص':'معاينة النص الكامل'}</button>
                {opened[it.id] && <pre className="mt-2 max-h-60 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs leading-6 dark:bg-slate-800/60">{fulls[it.id]!==undefined?fulls[it.id]:(it.preview||'')+'\\n... جارٍ تحميل النص الكامل'}</pre>}
                <div className="mt-2 flex flex-wrap gap-2">
                  <button onClick={()=>approve(it.id)} className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-bold text-white">&#10004; اعتماد</button>
                  <button onClick={()=>startEdit(it.id)} className="rounded-lg bg-slate-200 px-4 py-1.5 text-sm font-bold text-slate-700 dark:bg-slate-700 dark:text-slate-200">&#9998; تعديل واعتماد</button>
                  <button onClick={()=>reject(it.id)} className="rounded-lg bg-rose-600 px-4 py-1.5 text-sm font-bold text-white">&#10008; رفض وحذف</button>
                </div>
              </div>}
        </div>)}
      </div>
      {review.count>30 && <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">و {review.count-30} عنصرًا آخر بانتظار المراجعة</p>}
    </section>

    <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <h3 className="mb-3 font-bold text-ink dark:text-white">&#128450; مستندات مركبة بانتظار اختيارك</h3>
      {(!sel.items || sel.items.length===0) && <p className="text-sm text-slate-500 dark:text-slate-400">لا مستندات مركبة معلقة ✓</p>}
      <div className="space-y-3">
        {(sel.items||[]).map((it:any)=><div key={it.batch_id} className="rounded-xl border border-slate-100 p-4 dark:border-slate-800">
          <div className="text-sm font-bold text-ink dark:text-white">{it.title||it.file}</div>
          <div className="mt-2 space-y-1">
            {it.chunks.map((c:any)=><label key={c.index} className="flex items-start gap-2 rounded-lg p-1.5 text-sm hover:bg-slate-50 dark:hover:bg-slate-800/50">
              <input type="checkbox" checked={(checked[it.batch_id]||[]).includes(c.index)} onChange={()=>toggleChk(it.batch_id,c.index)} className="mt-1"/>
              <span className="text-ink dark:text-white">{c.title} <span className="text-xs text-slate-500 dark:text-slate-400">({c.kind} — {c.chars} حرف — ثقة {c.confidence||'?'})</span></span>
            </label>)}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button onClick={()=>confirmSel(it.batch_id,false)} disabled={busy} className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-bold text-white disabled:opacity-50">&#10004; تثبيت المختار</button>
            <button onClick={()=>confirmSel(it.batch_id,true)} disabled={busy} className="rounded-lg bg-slate-200 px-4 py-1.5 text-sm font-bold text-slate-700 dark:bg-slate-700 dark:text-slate-200">إدخال الكل</button>
            <button onClick={()=>discardSel(it.batch_id)} className="rounded-lg bg-rose-600 px-4 py-1.5 text-sm font-bold text-white">إهمال الكل</button>
          </div>
        </div>)}
      </div>
    </section>
  </div>;
}

function ResearchView'''
    src = src[:start] + NEW + src[end + len(endmark):]
    open(p, "w", encoding="utf-8").write(src)
    print("دُمج المركز مكونًا أصيلًا في الواجهة ✓")
PYEOF
nohup /root/merge-build.sh > /root/merge-build.log 2>&1 &
echo "انطلق البناء والنشر في الخلفية (2-4 دقائق)"
echo "تابعه: tail -5 /root/merge-build.log"
