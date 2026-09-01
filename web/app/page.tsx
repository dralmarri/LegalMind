'use client';
import { useEffect as _uE, useRef as _uR, useState as _uS } from "react";


import { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft, BookOpen, BriefcaseBusiness, CheckCheck, CheckCircle2, ChevronLeft, Clock, Copy, Download, FilePlus2, FileSignature, FileText, FolderOpen, FolderPlus, Gavel, LayoutDashboard, ListTree, Mail, Menu, MoreVertical, Moon, Paperclip, PenLine, Plus, Printer, RefreshCw, Search, Share2, SlidersHorizontal, Sun, Target, Trash2, UploadCloud, XCircle
} from 'lucide-react';

const BrandIcon = ({size = 20, className = ''}: {size?: number; className?: string}) => <img src="/brand-192.png" alt="" width={size} height={size} className={'rounded-md ' + className} />;

const SRC_BADGE:Record<string,{label:string;Icon:typeof BookOpen;cls:string}>={
  legislation_article:{label:'مادة قانونية',Icon:BookOpen,cls:'bg-blue-50 text-brand-blue dark:bg-blue-900/30 dark:text-blue-400'},
  legislation_issuing_article:{label:'مادة إصدار',Icon:BookOpen,cls:'bg-blue-50 text-brand-blue dark:bg-blue-900/30 dark:text-blue-400'},
  legislation_preamble:{label:'ديباجة',Icon:BookOpen,cls:'bg-blue-50 text-brand-blue dark:bg-blue-900/30 dark:text-blue-400'},
  judicial_principle:{label:'مبدأ تمييز',Icon:Gavel,cls:'bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400'},
  full_judgment:{label:'حكم كامل',Icon:(BrandIcon as any),cls:'bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400'},
  judicial_template:{label:'صيغة قانونية',Icon:FileSignature,cls:'bg-purple-50 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400'},
};
const srcBadge=(t?:string)=>SRC_BADGE[t||'']||{label:'مصدر',Icon:BookOpen,cls:'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'};

type Stats = { objects: Record<string, number>; laws?: number; batches: Record<string, number>; inbox: number; archive: number; failed: number };
type Job = { batch_id: string; status: string; object_count: number; relationship_count: number; started_at: string; completed_at?: string };
type Topic = { branch: string; topic?: string; subtopic?: string; micro_issue?: string; object_count: number };
type DocumentRow = { id: string; object_type: string; branch: string; topic?: string; subtopic?: string; micro_issue?: string; title?: string; verification_status: string };
type LegalCase = { id: string; case_key: string; title: string; branch: string; topic?: string; subtopic?: string; client_name?: string; client_capacity?: string; opponent_name?: string; court_name?: string; court_level?: string; status: string; facts?: string; requests?: string; notes?: string; updated_at: string; authorities?: unknown[]; drafts?: unknown[] };
type Coverage = { counts: Record<string, number>; drafting_ready: boolean; drafting_status: string; missing: string[]; note: string };
type View = 'dashboard' | 'cases' | 'workspace' | 'research' | 'drafting' | 'review' | 'upload' | 'docx' | 'knowledge' | 'documents' | 'jobs' | 'graph' | 'laws';
type UploadMethod = 'file' | 'paste';
type DuplicateOf = { first_batch_id: string; object_count: number; ingested_at?: string; title?: string };
type FileStatus = { file_id: string; status: string; batch_id?: string; object_count?: number; duplicate_of?: DuplicateOf; error?: string };

const nav = [
  ['dashboard', 'الرئيسية', LayoutDashboard],
  ['cases', 'القضايا', BriefcaseBusiness],
] as const;

// رسالة الخطأ تُعرض كما كتبها الخادم بالعربية، لا JSON خامًا في وجه المستخدم.
async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') message = body.detail;
      else if (body.detail) message = JSON.stringify(body.detail);
    } catch { /* الرد ليس JSON — نبقي نص الحالة */ }
    throw new Error(message);
  }
  return response.json();
}
// أرقام لاتينية موحّدة (يوم/شهر/سنة، ساعة:دقيقة) بدل الأرقام العربية-الهندية
const fmt = (value?: string) => value ? new Date(value).toLocaleString('en-GB', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—';
const OBJ_LABEL: Record<string,string> = {
  judicial_principle: 'مبادئ قضائية', legislation_article: 'مواد تشريعية',
  legislation_issuing_article: 'مواد الإصدار', legislation_preamble: 'ديباجات',
  full_judgment: 'أحكام كاملة', judicial_template: 'صيغ قضائية',
  legal_memorandum: 'مذكرات دفاع', legal_document: 'مستندات قانونية',
};
const typeLabel: Record<string,string> = {
  legislation:'تشريع', judicial_principle:'مبدأ قضائي', full_judgment:'حكم كامل',
  judicial_template:'صيغة قضائية', legal_memorandum:'مذكرة دفاع', legal_document:'مستند قانوني'
};
// أسماء القوانين المعروفة؛ وأي قانون جديد يظهر تلقائيًا باسمه المشتق من معرّفه.
const LAW_NAMES: Record<string,string> = {
  'legis-51-1984': 'قانون الأحوال الشخصية',
  'legis-124-2019': 'قانون الأحوال الشخصية الجعفري',
  'legis-12-2015': 'قانون إنشاء محكمة الأسرة',
  'legis-53-2026': 'مرسوم بقانون دعاوى النسب وتصحيح الأسماء',
  'legis-67-1980': 'القانون المدني',
  'legis-39-1980': 'قانون الإثبات في المواد المدنية والتجارية',
};
const lawKeyOf = (id: string) => (id.match(/^(legis-\d+-\d+)/) || [])[1] || '';
const artNumOf = (id: string) => { const m = id.match(/-m(\d+)/); return m ? parseInt(m[1], 10) : 0; };
const lawTitle = (key: string, name?: string) => {
  const m = key.match(/legis-(\d+)-(\d+)/);
  return (LAW_NAMES[key] || name || 'تشريع') + (m ? ` (${m[1]}/${m[2]})` : '');
};

function HomeInner() {
  const [view, setView] = useState<View>('dashboard');
  const [stats, setStats] = useState<Stats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [cases, setCases] = useState<LegalCase[]>([]);
  const [selectedCase, setSelectedCase] = useState<LegalCase | null>(null);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [uploadMessage, setUploadMessage] = useState('');
  const [uploadError, setUploadError] = useState('');
  const [uploadMethod, setUploadMethod] = useState<UploadMethod>('file');
  const [processing, setProcessing] = useState<FileStatus[]>([]);
  const [uploading, setUploading] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [dark, setDark] = useState(false);
  useEffect(() => { setDark(document.documentElement.classList.contains('dark')); }, []);
  const toggleTheme = () => {
    const el = document.documentElement; const next = !el.classList.contains('dark');
    el.classList.toggle('dark', next); try { localStorage.setItem('lm-theme', next ? 'dark' : 'light'); } catch {}
    setDark(next);
  };

  async function refresh() {
    setLoading(true);
    try {
      const [s,j,t,d,c] = await Promise.all([
        api<Stats>('/api/stats'), api<Job[]>('/api/jobs?limit=100'), api<Topic[]>('/api/topics'),
        api<DocumentRow[]>('/api/documents?limit=6000'), api<LegalCase[]>('/api/cases')
      ]);
      setStats(s); setJobs(j); setTopics(t); setDocuments(d); setCases(c);
    } finally { setLoading(false); }
  }
  useEffect(() => { refresh(); const id=setInterval(refresh,30000); return()=>clearInterval(id); }, []);

  const filteredDocuments = useMemo(() => documents.filter(d => !query || [d.id,d.title,d.branch,d.topic,d.subtopic,d.micro_issue,d.object_type].some(v=>String(v||'').includes(query))), [documents,query]);
  const groupedTopics = useMemo(() => {
    const map=new Map<string,Topic[]>(); topics.forEach(t=>{const k=t.branch||'غير مصنف';map.set(k,[...(map.get(k)||[]),t]);}); return [...map.entries()];
  },[topics]);
  // تجميع التشريعات في قوانين كاملة: كل قانون = مفتاح معرّف واحد (legis-N-Y)
  const laws = useMemo(() => {
    const m = new Map<string, DocumentRow[]>();
    documents.forEach(d => {
      if (!d.object_type?.startsWith('legislation')) return;
      const k = lawKeyOf(d.id); if (!k) return;
      m.set(k, [...(m.get(k) || []), d]);
    });
    return m;
  }, [documents]);

  async function openCase(item: LegalCase) {
    const full=await api<LegalCase>(`/api/cases/${item.id}`);
    const cov=await api<Coverage>(`/api/cases/${item.id}/coverage`);
    setSelectedCase(full); setCoverage(cov); setView('workspace');
  }
  async function submitCase(event: React.FormEvent<HTMLFormElement>, files?: File[]) {
    event.preventDefault();
    const formEl=event.currentTarget;
    const payload=Object.fromEntries(new FormData(formEl).entries());
    try {
      const created=await api<LegalCase>('/api/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      if(files&&files.length){
        try{ const fd=new FormData(); files.forEach(f=>fd.append('files',f));
          await fetch('/api/cases/'+encodeURIComponent(String(created.id))+'/files',{method:'POST',body:fd});
        }catch{}
      }
      try{ formEl.reset(); }catch{}
      await refresh(); await openCase(created);
    } catch(ex:any) {
      alert('تعذّر إنشاء القضية: '+(ex?.message||'خطأ غير معروف')+'\nراجع البيانات (العنوان ثلاثة أحرف على الأقل) ثم أعد المحاولة.');
    }
  }
  async function saveCase(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if(!selectedCase)return; const payload=Object.fromEntries(new FormData(event.currentTarget).entries());
    const updated=await api<LegalCase>(`/api/cases/${selectedCase.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    setSelectedCase({...selectedCase,...updated}); await refresh();
  }
  // متابعة المعالجة فعليًا: نستقصي حالة كل مصدر حتى ينتهي (اكتمل/فشل/مكرر)،
  // فلا يبقى المستخدم أمام «تم الإدراج» بلا علم بما جرى بعدها.
  async function trackFiles(ids: string[]) {
    const terminal = new Set(['completed','failed','duplicate']);
    for (let attempt=0; attempt<40; attempt++) {
      const items = await Promise.all(ids.map(id =>
        api<FileStatus>(`/api/file-status/${encodeURIComponent(id)}`).catch(()=>({file_id:id,status:'unknown'} as FileStatus))
      ));
      setProcessing(items);
      if (items.every(s => terminal.has(s.status))) break;
      await new Promise(r => setTimeout(r, 2000));
    }
    await refresh();
  }

  async function submitSource(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setProcessing([]); setUploadError('');

    if (uploadMethod === 'file') {
      data.delete('content');
      const files = data.getAll('files').filter(f => f instanceof File && f.size > 0);
      if (!files.length) { setUploadError('اختر ملفًا واحدًا على الأقل.'); return; }
    } else {
      data.delete('files');
      const text = String(data.get('content') || '').trim();
      if (text.length < 20) { setUploadError('النص فارغ أو أقصر من 20 حرفًا.'); return; }
      data.set('content', text);
    }

    setUploading(true); setUploadMessage('جارٍ الحفظ...');
    try {
      let ids: string[];
      if (uploadMethod === 'paste') {
        const result = await api<{file_id:string}>('/api/paste-text', {method:'POST', body:data});
        ids = [result.file_id];
      } else {
        const result = await api<{files:{file_id:string}[]}>('/api/upload', {method:'POST', body:data});
        ids = result.files.map(f => f.file_id);
      }
      setUploadMessage(`حُفظ المصدر (${ids.length}) وبدأت معالجته.`);
      form.reset();
      await trackFiles(ids);
    } catch(error) {
      setUploadMessage('');
      setUploadError(error instanceof Error ? error.message : String(error));
    } finally { setUploading(false); }
  }

  return <div className="min-h-screen bg-mist text-ink dark:bg-brand-deep dark:text-slate-100">
    <header className="sticky top-0 z-30 border-b border-slate-200 dark:border-slate-800 bg-white/90 backdrop-blur dark:bg-slate-900/90">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-5 py-3 md:px-8">
        <button onClick={()=>setView('dashboard')} className="flex shrink-0 items-center gap-2.5">
          <img src="/brand-192.png" alt="صوت العدالة" className="h-10 w-10 rounded-2xl bg-white object-contain" />
          <div className="hidden text-right sm:block"><div className="text-base font-bold leading-tight">صوت العدالة</div><div className="text-[11px] text-slate-500 dark:text-slate-400">منظومة قانونية ذكية</div></div>
        </button>
        <nav className="mr-2 hidden flex-1 items-center gap-1 lg:flex">{nav.filter(([id])=>!(isNativeApp()&&id==='cases')).map(([id,label,Icon])=><button key={id} onClick={()=>setView(id)} className={`flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-semibold transition ${view===id?'bg-brand-blue text-white shadow-md shadow-brand-blue/25':'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'}`}><Icon size={16}/>{label}</button>)}</nav>
        <div className="mr-auto flex items-center gap-2">
          <div className="relative hidden md:block"><Search className="absolute right-3 top-2.5 text-slate-400" size={16}/><input value={query} onChange={e=>setQuery(e.target.value)} className="w-40 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 py-2 pr-9 pl-3 text-sm outline-none focus:border-brand-blue dark:bg-slate-800 lg:w-56" placeholder="ابحث في المصادر..."/></div>
          <button onClick={toggleTheme} aria-label="تبديل الوضع" className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800 p-2.5 text-slate-500 dark:text-slate-300">{dark?<Sun size={18}/>:<Moon size={18}/>}</button>
          <button onClick={refresh} aria-label="تحديث" className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800 p-2.5"><RefreshCw size={18} className={loading?'animate-spin':''}/></button>
          <button onClick={()=>setNavOpen(o=>!o)} aria-label="القائمة" className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800 p-2.5 text-slate-500 dark:text-slate-300 lg:hidden"><Menu size={18}/></button>
        </div>
      </div>
      {navOpen && <nav className="border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 py-3 lg:hidden"><div className="mx-auto grid max-w-7xl grid-cols-2 gap-2">{nav.filter(([id])=>!(isNativeApp()&&id==='cases')).map(([id,label,Icon])=><button key={id} onClick={()=>{setView(id);setNavOpen(false);}} className={`flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold transition ${view===id?'bg-brand-blue text-white':'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'}`}><Icon size={16}/>{label}</button>)}</div></nav>}
    </header>
    <main className="min-h-screen">
      <div className="mx-auto max-w-7xl p-6 md:p-10">
        {view==='dashboard'&&<OverviewView stats={stats} lawsCount={stats?.laws ?? laws.size} cases={cases} setView={setView}/>}
        {view==='laws'&&<KnowledgeView/>}
        {view==='cases'&&!isNativeApp()&&<CasesView cases={cases} onOpen={openCase} onCreate={submitCase}/>} 
        {view==='workspace'&&selectedCase&&!isNativeApp()&&<CaseWorkspace item={selectedCase} coverage={coverage} onSave={saveCase} setView={setView}/>} 
        {view==='research'&&<ResearchView/>}
        {view==='docx'&&<DocxView/>} 
        {view==='drafting'&&<DraftingView cases={cases} onOpen={openCase}/>} 
        {view==='review'&&<ReviewView cases={cases} onOpen={openCase}/>} 
        {view==='upload'&&<UploadPanel topics={topics} onSubmit={submitSource} message={uploadMessage} error={uploadError}
          method={uploadMethod} setMethod={m=>{setUploadMethod(m);setUploadMessage('');setUploadError('');setProcessing([]);}}
          processing={processing} busy={uploading}/>}
        {view==='knowledge'&&<KnowledgeTree groups={groupedTopics}/>} 
        {view==='documents'&&<DocumentsTable rows={filteredDocuments}/>} 
        {view==='jobs'&&<JobsTable jobs={jobs}/>} 
        {view==='graph'&&<GraphView topics={topics}/>} 
      </div>
    </main>
    <footer className="border-t border-slate-200 dark:border-slate-800 py-4 text-center text-xs text-slate-400 dark:text-slate-500">
      <a href="/support.html" target="_blank" rel="noopener noreferrer" className="hover:text-brand-blue">تواصل معنا</a>
      <span className="mx-2">·</span>
      <a href="/privacy.html" target="_blank" rel="noopener noreferrer" className="hover:text-brand-blue">سياسة الخصوصية</a>
      <span className="mx-2">·</span>
      <span>الإصدار 1.0</span>
    </footer>
  </div>
}

const BRANCH_BADGE:Record<string,string>={
  'تجاري':'bg-blue-50 text-brand-blue dark:bg-blue-900/30 dark:text-blue-400',
  'عمالي':'bg-purple-50 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
  'أحوال شخصية':'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400',
  'مدني':'bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
  'جزائي':'bg-rose-50 text-rose-600 dark:bg-rose-900/30 dark:text-rose-400',
  'إداري':'bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400',
};
const caseStatusDot=(s?:string)=>{ const v=s||''; if(/مغلق|منته/.test(v)) return 'bg-slate-400'; if(/مكتمل|منجز|جاهز/.test(v)) return 'bg-emerald-500'; if(/صياغة|مراجع|معلّق|معلق/.test(v)) return 'bg-amber-500'; return 'bg-emerald-500'; };
function CasesView({cases,onOpen,onCreate}:{cases:LegalCase[];onOpen:(c:LegalCase)=>void;onCreate:(e:React.FormEvent<HTMLFormElement>,files?:File[])=>void}) {
  const [newFiles,setNewFiles]=useState<File[]>([]);
  const [showForm,setShowForm]=useState(false);
  const [q,setQ]=useState('');
  const filtered=cases.filter(c=>{const s=(c.title+' '+c.case_key+' '+(c.branch||'')+' '+(c.topic||'')).toLowerCase(); return !q.trim()||s.includes(q.trim().toLowerCase());});
  const submit=(e:React.FormEvent<HTMLFormElement>)=>{ onCreate(e,newFiles); setShowForm(false); setNewFiles([]); };
  return <div className="space-y-6">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
      <div><h2 className="text-2xl font-bold text-ink dark:text-white">القضايا النشطة</h2><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">إدارة ومتابعة جميع القضايا الموكلة إليك.</p></div>
      <div className="flex items-center gap-3">
        <div className="relative w-full sm:w-64"><Search className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={16}/><input value={q} onChange={e=>setQ(e.target.value)} className="w-full rounded-lg border border-slate-200 bg-white py-2 pr-10 pl-4 text-sm outline-none focus:ring-2 focus:ring-brand-blue/40 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200" placeholder="بحث في القضايا..."/></div>
        <button onClick={()=>setShowForm(s=>!s)} className="flex shrink-0 items-center gap-2 rounded-lg bg-brand-blue px-4 py-2 font-medium text-white shadow-sm shadow-brand-blue/20 transition hover:bg-brand-dark"><Plus size={16}/><span>قضية جديدة</span></button>
      </div>
    </div>
    {showForm&&<form onSubmit={submit} className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900 sm:grid-cols-2">
      <div className="sm:col-span-2"><h3 className="text-lg font-bold text-ink dark:text-white">إنشاء قضية جديدة</h3><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">يُنشأ ملف مستقل محفوظ في قاعدة البيانات.</p></div>
      <input className="input" name="title" placeholder="عنوان القضية" required/>
      <select className="input" name="branch" required><option>أحوال شخصية</option><option>مدني</option><option>تجاري</option><option>عمالي</option><option>جزائي</option><option>إداري</option></select>
      <input className="input" name="topic" placeholder="الموضوع: حضانة / نفقة / تعويض"/>
      <input className="input" name="subtopic" placeholder="المسألة الدقيقة"/>
      <input className="input" name="client_name" placeholder="اسم الموكل"/>
      <input className="input" name="client_capacity" placeholder="صفته"/>
      <input className="input" name="opponent_name" placeholder="الخصم"/>
      <input className="input" name="court_name" placeholder="المحكمة"/>
      <textarea className="input min-h-24 sm:col-span-2" name="facts" placeholder="ملخص الوقائع"/>
      <textarea className="input min-h-20 sm:col-span-2" name="requests" placeholder="طلبات الموكل"/>
      <div className="sm:col-span-2 rounded-xl border border-dashed border-slate-300 p-4 dark:border-slate-700">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h4 className="text-sm font-bold text-ink dark:text-white">أوراق القضية (اختياري)</h4>
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">مذكرات دفاع، صحف دعاوى، أوامر، أحكام، عقود… تُحفظ في ملف القضية فور إنشائه. ورقم القضية يُولَّد آليًا.</p>
          </div>
          <label className="shrink-0 cursor-pointer rounded-lg border border-brand-blue px-3 py-1.5 text-xs font-bold text-brand-blue transition hover:bg-brand-soft dark:hover:bg-brand-blue/15">+ اختيار ملفات<input type="file" multiple className="hidden" onChange={e=>setNewFiles(Array.from(e.target.files||[]))}/></label>
        </div>
        {newFiles.length>0&&<p className="mt-2 text-xs font-bold text-emerald-700 dark:text-emerald-300">{newFiles.length} ورقة جاهزة: {newFiles.map(f=>f.name).join('، ').slice(0,140)}</p>}
      </div>
      <div className="flex gap-3 sm:col-span-2"><button className="rounded-xl bg-brand-blue px-6 py-2.5 font-bold text-white transition hover:bg-brand-dark">إنشاء مساحة القضية</button><button type="button" onClick={()=>setShowForm(false)} className="rounded-xl border border-slate-300 px-6 py-2.5 font-bold text-slate-600 transition hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800">إلغاء</button></div>
    </form>}
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      {filtered.length? <div className="overflow-x-auto"><table className="w-full text-right text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs font-bold text-slate-600 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-300">
          <tr><th className="px-6 py-4">اسم القضية / الرقم</th><th className="px-6 py-4">المجال القانوني</th><th className="px-6 py-4">الحالة</th><th className="px-6 py-4">تاريخ الإضافة</th><th className="px-6 py-4 text-center">إجراءات</th></tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {filtered.map(c=><tr key={c.id} onClick={()=>onOpen(c)} className="cursor-pointer transition hover:bg-slate-50 dark:hover:bg-slate-800/40">
            <td className="px-6 py-4"><div className="text-base font-bold text-ink dark:text-white">{c.title}</div><div className="mt-1 text-xs text-slate-400">{c.case_key}</div></td>
            <td className="px-6 py-4"><span className={`rounded px-2.5 py-1 text-xs font-medium ${BRANCH_BADGE[c.branch||'']||'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'}`}>{c.branch||'—'}</span></td>
            <td className="px-6 py-4"><div className="flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${caseStatusDot(c.status)}`}/><span className="font-medium text-slate-700 dark:text-slate-300">{c.status||'—'}</span></div></td>
            <td className="px-6 py-4 text-slate-500 dark:text-slate-400">{(c.updated_at||'').slice(0,10)||'—'}</td>
            <td className="px-6 py-4 text-center"><span className="inline-flex text-slate-400 transition hover:text-brand-blue"><MoreVertical size={18}/></span></td>
          </tr>)}
        </tbody>
      </table></div>
      : <div className="flex flex-col items-center justify-center p-12 text-center"><div className="mb-4 grid h-20 w-20 place-items-center rounded-full bg-slate-50 dark:bg-slate-800/50"><FolderOpen size={32} className="text-slate-300 dark:text-slate-500"/></div><h3 className="mb-2 text-lg font-bold text-ink dark:text-white">{q?'لا قضايا مطابقة':'لا توجد قضايا حالياً'}</h3><p className="mb-6 max-w-sm text-sm text-slate-500 dark:text-slate-400">{q?'جرّب كلمة بحث أخرى.':'ابدأ بإضافة قضية جديدة لإدارتها ومتابعتها.'}</p>{!q&&<button onClick={()=>setShowForm(true)} className="flex items-center gap-2 rounded-lg bg-brand-blue px-6 py-2.5 font-medium text-white shadow-sm shadow-brand-blue/20 transition hover:bg-brand-dark"><Plus size={16}/><span>إضافة أول قضية</span></button>}</div>}
    </div>
  </div>;
}

function CaseActivity({caseId,setView}:{caseId:string;setView:(v:View)=>void}) {
  const [rounds,setRounds]=useState<any[]>([]);
  const [files,setFiles]=useState<any[]>([]);
  const [up,setUp]=useState(false);
  const loadFiles=async()=>{try{const r=await fetch('/api/cases/'+encodeURIComponent(caseId)+'/files');if(r.ok){const d=await r.json();if(Array.isArray(d.files))setFiles(d.files);}}catch{}};
  const onUp=async(e:React.ChangeEvent<HTMLInputElement>)=>{const fs=e.target.files;if(!fs||!fs.length)return;setUp(true);try{const fd=new FormData();Array.from(fs).forEach(f=>fd.append('files',f));await fetch('/api/cases/'+encodeURIComponent(caseId)+'/files',{method:'POST',body:fd});await loadFiles();}catch{}finally{setUp(false);e.target.value='';}};
  const delFile=async(id:number)=>{try{await fetch('/api/casefiles/'+id,{method:'DELETE'});setFiles(f=>f.filter((x:any)=>x.id!==id));}catch{}};
  useEffect(()=>{(async()=>{
    try{const r=await fetch('/api/draft/threads?case_id='+encodeURIComponent(caseId));if(r.ok){const d=await r.json();if(Array.isArray(d.threads))setRounds(d.threads);}}catch{}
    try{const r=await fetch('/api/cases/'+encodeURIComponent(caseId)+'/files');if(r.ok){const d=await r.json();if(Array.isArray(d.files))setFiles(d.files);}}catch{}
  })();},[caseId]);
  const open=(r:any,follow:boolean)=>{_openThread.rec=r;_openThread.follow=follow;_openThread.caseId=caseId;setView('drafting');};
  const byTs=[...rounds].sort((a:any,b:any)=>String(b.ts||'').localeCompare(String(a.ts||'')));
  const last=byTs[0];
  const pend=(String(last?.a||'').match(/\[للتحقق\]/g)||[]).length;
  const kb=(n:number)=>n>1048576?(n/1048576).toFixed(1)+' م.ب':Math.max(1,Math.round(n/1024))+' ك.ب';
  return <div className="space-y-5">
    <div className="rounded-2xl border bg-white dark:bg-slate-900 p-5">
      <h3 className="mb-3 font-bold text-ink dark:text-white">ملخص عمل القضية</h3>
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-slate-50 p-3 text-center dark:bg-slate-800"><div className="text-2xl font-bold text-brand-blue">{rounds.length}</div><div className="text-xs text-slate-500 dark:text-slate-400">جولة استوديو</div></div>
        <div className="rounded-xl bg-slate-50 p-3 text-center dark:bg-slate-800"><div className="text-2xl font-bold text-brand-blue">{files.length}</div><div className="text-xs text-slate-500 dark:text-slate-400">ورقة محفوظة</div></div>
      </div>
      <div className="mt-3 flex justify-between gap-2 text-sm text-slate-600 dark:text-slate-300"><span>آخر نشاط</span><strong>{last?new Date(last.ts).toLocaleDateString('ar'):'—'}</strong></div>
      {last?<p className="mt-1 text-xs leading-6 text-slate-500 dark:text-slate-400">آخر جولة: {String(last.q||'').slice(0,90)}</p>:null}
      {last?(pend?<div className="mt-3 rounded-xl bg-amber-50 p-3 text-sm font-bold text-amber-900 dark:bg-amber-900/20 dark:text-amber-300">في آخر مسودة {pend} موضعًا موسومًا [للتحقق] — راجعها قبل الإيداع.</div>:<div className="mt-3 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-300">لا مواضع معلّقة في آخر مسودة.</div>):null}
    </div>
    <div className="rounded-2xl border bg-white dark:bg-slate-900 p-5">
      <h3 className="mb-3 font-bold text-ink dark:text-white">جولات الاستوديو ({rounds.length})</h3>
      {rounds.length? <div className="max-h-80 space-y-2 overflow-y-auto">
        {rounds.map((r:any)=><div key={r.id||r.ts} className="rounded-xl border border-slate-100 p-3 dark:border-slate-800">
          <p className="text-sm font-bold leading-6 text-ink dark:text-white">{r.follow?'↩ ':''}{String(r.q||'').slice(0,110)}</p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{new Date(r.ts).toLocaleString('ar')}{r.atts&&r.atts.length?' · أوراق '+r.atts.length:''}</p>
          <div className="mt-2 flex gap-2">
            <button onClick={()=>open(r,false)} className="rounded border border-slate-300 px-2 py-0.5 text-xs dark:border-slate-600">فتح</button>
            <button onClick={()=>open(r,true)} className="rounded border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">↩ متابعة</button>
          </div>
        </div>)}
      </div> : <p className="text-sm text-slate-500 dark:text-slate-400">لا جولات بعد — افتح الاستوديو من هنا فتُنسب كل جولة لهذه القضية.</p>}
    </div>
    <div className="rounded-2xl border bg-white dark:bg-slate-900 p-5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="font-bold text-ink dark:text-white">أوراق القضية ({files.length})</h3>
        <label className="shrink-0 cursor-pointer rounded-lg border border-brand-blue px-3 py-1 text-xs font-bold text-brand-blue transition hover:bg-brand-soft dark:hover:bg-brand-blue/15">{up?'يرفع…':'+ إضافة أوراق'}<input type="file" multiple className="hidden" onChange={onUp} disabled={up}/></label>
      </div>
      {files.length? <div className="max-h-64 space-y-2 overflow-y-auto">
        {files.map((f:any)=><div key={f.id} className="flex items-center justify-between gap-2 rounded-lg border border-slate-100 px-3 py-2 text-sm dark:border-slate-800">
          <a href={'/api/casefiles/'+f.id+'/download'} className="min-w-0 flex-1 truncate font-medium text-ink transition hover:text-brand-blue dark:text-white">{f.name}</a>
          <span className="shrink-0 text-xs text-slate-400">{kb(f.size||0)}</span>
          <button onClick={()=>delFile(f.id)} className="shrink-0 rounded border border-rose-200 px-1.5 py-0.5 text-xs text-rose-500 dark:border-rose-800">حذف</button>
        </div>)}
      </div> : <p className="text-sm text-slate-500 dark:text-slate-400">لا أوراق بعد — ارفعها بزر «إضافة أوراق»، أو أرفقها في الاستوديو وأنت على هذه القضية.</p>}
    </div>
  </div>;
}

function CaseWorkspace({item,coverage,onSave,setView}:{item:LegalCase;coverage:Coverage|null;onSave:(e:React.FormEvent<HTMLFormElement>)=>void;setView:(v:View)=>void}) {
  return <div className="space-y-6"><section className="rounded-3xl bg-gradient-to-l from-brand-navy to-brand-deep p-7 text-white"><div className="flex justify-between"><div><div className="text-sm text-brand-blue">{item.case_key}</div><h2 className="mt-2 text-2xl font-bold">{item.title}</h2><p className="mt-2 text-slate-300">{item.branch} · {item.topic||'غير محدد'} · {item.subtopic||'غير محدد'}</p></div><div className="text-left"><div className="rounded-full bg-white/10 px-4 py-2 text-sm text-slate-200">{item.status||'قيد العمل'}</div></div></div></section><div className="grid grid-cols-[1fr_360px] gap-6"><form onSubmit={onSave} className="space-y-5 rounded-2xl border bg-white dark:bg-slate-900 p-6"><h3 className="text-lg font-bold">ملف القضية</h3><div className="grid grid-cols-2 gap-4"><input className="input" name="title" defaultValue={item.title}/><input className="input" name="status" defaultValue={item.status}/><input className="input" name="topic" defaultValue={item.topic}/><input className="input" name="subtopic" defaultValue={item.subtopic}/><input className="input" name="client_name" defaultValue={item.client_name} placeholder="الموكل"/><input className="input" name="client_capacity" defaultValue={item.client_capacity} placeholder="الصفة"/><input className="input" name="opponent_name" defaultValue={item.opponent_name} placeholder="الخصم"/><input className="input" name="court_name" defaultValue={item.court_name} placeholder="المحكمة"/></div><label className="block"><span className="mb-2 block font-bold">الوقائع</span><textarea className="input min-h-44" name="facts" defaultValue={item.facts}/></label><label className="block"><span className="mb-2 block font-bold">الطلبات</span><textarea className="input min-h-32" name="requests" defaultValue={item.requests}/></label><label className="block"><span className="mb-2 block font-bold">ملاحظات العمل</span><textarea className="input min-h-24" name="notes" defaultValue={item.notes}/></label><button className="rounded-xl bg-brand-blue px-6 py-3 font-bold text-white">حفظ التعديلات</button></form><aside className="space-y-5"><button onClick={()=>setView('research')} className="w-full rounded-xl border bg-white dark:bg-slate-900 py-3 font-bold">بحث مرتبط بالقضية</button><button onClick={()=>{_openThread.caseId=String(item.id);setView('drafting');}} className="w-full rounded-xl bg-brand-blue hover:bg-brand-dark py-3 font-bold text-white">فتح الاستوديو على هذه القضية</button><CaseActivity caseId={String(item.id)} setView={setView}/></aside></div></div>
}

function OverviewView({stats,lawsCount,cases,setView}:{stats:Stats|null;lawsCount:number;cases:LegalCase[];setView:(v:View)=>void}) {
  const [acts,setActs]=useState<any[]>([]);
  useEffect(()=>{(async()=>{try{const r=await fetch('/api/draft/threads');if(!r.ok)return;const d=await r.json();if(Array.isArray(d.threads))setActs(d.threads.slice(0,8));}catch{}})();},[]);
  const principles=(stats?.objects?.judicial_principle||0)+(stats?.objects?.full_judgment||0);
  const templates=stats?.objects?.judicial_template||0;
  const nf=(n:number)=>n.toLocaleString('en-US');
  const cards=[
    {label:'إجمالي التشريعات',value:lawsCount,Icon:BookOpen,tone:'text-brand-blue',bg:'bg-brand-soft dark:bg-brand-blue/15',unit:'قانون',go:()=>setView('laws')},
    {label:'المبادئ والأحكام',value:principles,Icon:(BrandIcon as any),tone:'text-indigo-600 dark:text-indigo-400',bg:'bg-indigo-50 dark:bg-indigo-900/20',unit:'مبدأ وحكم',go:()=>setView('laws')},
    {label:'الصيغ والنماذج',value:templates,Icon:FileSignature,tone:'text-purple-600 dark:text-purple-400',bg:'bg-purple-50 dark:bg-purple-900/20',unit:'صيغة',go:()=>setView('laws')},
  ];
  const quick=[
    {t:'استوديو الصياغة',d:'استشارة أو مذكرة مسندة — بالوقائع أو بالأوراق',Icon:PenLine,go:()=>setView('drafting')},
    {t:'بحث قانوني متقدم',d:'البحث في التشريعات والمبادئ والأحكام',Icon:Search,go:()=>setView('laws')},
    
    {t:'رفع مستند جديد',d:'إدخال مصادر جديدة لقاعدة المعرفة',Icon:FilePlus2,go:()=>setView('docx')},
  ];
  const statusTone=(s?:string)=>{
    const v=s||''; if(/مكتمل|منجز|جاهز/.test(v)) return 'bg-emerald-50 text-emerald-600 border-emerald-100 dark:bg-emerald-900/20 dark:text-emerald-400 dark:border-emerald-800/50';
    if(/مراجع|معلّق|معلق/.test(v)) return 'bg-amber-50 text-amber-600 border-amber-100 dark:bg-amber-900/20 dark:text-amber-400 dark:border-amber-800/50';
    return 'bg-blue-50 text-brand-blue border-blue-100 dark:bg-blue-900/20 dark:text-brand-blue dark:border-blue-800/50';
  };
  const recent=[...cases].sort((a,b)=>(b.updated_at||'').localeCompare(a.updated_at||'')).slice(0,5);
  const fmtDate=(s?:string)=>{ if(!s) return '—'; const d=s.slice(0,10); return d; };
  return <div className="mx-auto max-w-7xl space-y-8">
    <section className="relative overflow-hidden rounded-2xl bg-gradient-to-l from-brand-navy to-[#1a3a6c] p-6 text-white shadow-lg lg:p-8">
      <div className="flex flex-col items-start justify-between gap-6 md:flex-row md:items-center">
        <div className="space-y-2">
          <h2 className="text-2xl font-bold">مرحباً بك مجدداً</h2>
          <p className="max-w-xl text-sm leading-relaxed text-slate-300">منصة «صوت العدالة» توفّر لك وصولاً سريعاً ودقيقاً لأحدث التشريعات والمبادئ القانونية، إضافةً إلى استوديو صياغة متقدّم لتسهيل أعمالك اليومية.</p>
        </div>
        <button onClick={()=>setView('drafting')} className="flex shrink-0 items-center gap-2 rounded-xl bg-brand-blue px-6 py-3 font-semibold text-white shadow-md shadow-brand-blue/30 transition hover:bg-brand-dark">
          <PenLine size={18}/><span>بدء صياغة جديدة</span>
        </button>
      </div>
    </section>

    <section className="grid grid-cols-1 gap-6 md:grid-cols-3">
      {cards.map(c=><button key={c.label} onClick={c.go} className="group flex flex-col gap-4 rounded-2xl border border-slate-100 bg-white p-6 text-right shadow-sm transition hover:-translate-y-0.5 hover:border-brand-blue hover:shadow-md dark:border-slate-800 dark:bg-slate-900">
        <div className="flex w-full items-start justify-between">
          <div className={`grid h-12 w-12 place-items-center rounded-xl ${c.bg} ${c.tone} transition group-hover:scale-110`}><c.Icon size={22}/></div>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">محدّث باستمرار</span>
        </div>
        <div>
          <p className="mb-1 text-sm font-medium text-slate-500 dark:text-slate-400">{c.label}</p>
          <h3 className="text-3xl font-bold text-ink dark:text-white">{nf(c.value)}</h3>
          <p className="mt-1 text-xs text-slate-400">{c.unit}</p>
        </div>
      </button>)}
    </section>

    <section className="grid grid-cols-1 gap-8 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-1">
        <h3 className="text-lg font-bold text-ink dark:text-white">دخول سريع</h3>
        <div className="flex flex-col gap-3">
          {quick.map(q=><button key={q.t} onClick={q.go} className="group flex items-center gap-4 rounded-xl border border-slate-100 bg-white p-4 text-right shadow-sm transition hover:border-brand-blue hover:shadow-md dark:border-slate-800 dark:bg-slate-900">
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-slate-50 text-slate-500 transition group-hover:bg-brand-blue group-hover:text-white dark:bg-slate-800 dark:text-slate-400"><q.Icon size={18}/></div>
            <div className="flex-1"><h4 className="text-sm font-bold text-ink transition group-hover:text-brand-blue dark:text-white">{q.t}</h4><p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{q.d}</p></div>
            <ChevronLeft size={16} className="text-slate-300 rtl:rotate-180"/>
          </button>)}
        </div>
      </div>

      <div className="space-y-4 lg:col-span-2">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-ink dark:text-white">أحدث جولاتك</h3>
          <button onClick={()=>setView('drafting')} className="text-sm font-medium text-brand-blue hover:text-brand-dark">فتح الاستوديو</button>
        </div>
        <div className="overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
          {acts.length? <div className="divide-y divide-slate-50 dark:divide-slate-800">
            {acts.map((r:any)=><div key={r.id||r.ts} className="flex items-center gap-3 px-5 py-3.5 transition hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded bg-blue-50 text-brand-blue dark:bg-blue-900/20"><PenLine size={15}/></div>
              <button onClick={()=>{_openThread.rec=r;_openThread.follow=false;setView('drafting');}} className="min-w-0 flex-1 text-right">
                <p className="truncate text-sm font-bold text-ink dark:text-white">{r.follow?'↩ ':''}{String(r.q||'').slice(0,80)}</p>{r.case_id&&<p className="mt-0.5 truncate text-xs font-bold text-brand-blue">{(cases.find((c:any)=>String(c.id)===String(r.case_id))||{title:'قضية'}).title}</p>}
                <p className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400"><Clock size={12}/>{new Date(r.ts).toLocaleString('ar')}{r.atts&&r.atts.length?' · مرفقات '+r.atts.length:''}</p>
              </button>
              <button onClick={()=>{_openThread.rec=r;_openThread.follow=true;setView('drafting');}} className="shrink-0 rounded-lg border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700 transition hover:bg-emerald-100 dark:border-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">↩ متابعة</button>
            </div>)}
          </div>
          : <div className="p-10 text-center text-sm text-slate-500 dark:text-slate-400">لا جولات بعد — ابدأ من «استوديو الصياغة» وستظهر جولاتك هنا للمتابعة.</div>}
        </div>
      </div>
    </section>
  </div>;
}

function DocxView() {
  const [busy,setBusy]=useState(false); const [err,setErr]=useState('');
  const [prev,setPrev]=useState<any>(null); const [done,setDone]=useState<any>(null);
  const [drag,setDrag]=useState(false); const [fname,setFname]=useState('');
  const [mode,setMode]=useState<'file'|'paste'>('file');
  const [paste,setPaste]=useState(''); const [pbranch,setPbranch]=useState('');
  const handleFile=async(f?:File)=>{
    if(!f)return; setFname(f.name);
    setBusy(true); setErr(''); setPrev(null); setDone(null);
    try{ const fd=new FormData(); fd.append('file',f);
      const r=await api<any>('/api/docx/preview',{method:'POST',body:fd}); setPrev(r);
    }catch(ex:any){setErr(ex?.message||'تعذّر التحليل');} finally{setBusy(false);}
  };
  const analyzeText=async()=>{
    if(!paste.trim()){ setErr('الصق نصًّا أولًا'); return; }
    setFname('نص ملصوق'); setBusy(true); setErr(''); setPrev(null); setDone(null);
    try{ const fd=new FormData(); fd.append('text',paste); if(pbranch.trim()) fd.append('branch',pbranch.trim());
      const r=await api<any>('/api/docx/preview-text',{method:'POST',body:fd}); setPrev(r);
    }catch(ex:any){setErr(ex?.message||'تعذّر التحليل');} finally{setBusy(false);}
  };
  const onFile=(e:React.ChangeEvent<HTMLInputElement>)=>handleFile(e.target.files?.[0]);
  const onDrop=(e:React.DragEvent)=>{ e.preventDefault(); setDrag(false); handleFile(e.dataTransfer.files?.[0]); };
  const ingest=async()=>{ if(!prev)return; setBusy(true); setErr('');
    try{ const r=await api<any>('/api/docx/ingest',{method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify({token:prev.token})});
      setDone(r); setPrev(null);
    }catch(ex:any){setErr(ex?.message||'تعذّر الإدخال');} finally{setBusy(false);}
  };
  const total=prev?prev.tree.reduce((s:number,r:any)=>s+(r.count||0),0):0;
  const reset=()=>{ setPrev(null); setFname(''); setErr(''); };
  return <SmartIngestCenter/>;
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
                {opened[it.id] && <pre className="mt-2 max-h-60 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs leading-6 dark:bg-slate-800/60">{fulls[it.id]!==undefined?fulls[it.id]:(it.preview||'')+'\n... جارٍ تحميل النص الكامل'}</pre>}
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

function ResearchView() {
  const [q,setQ]=useState(''); const [busy,setBusy]=useState(false);
  const [err,setErr]=useState(''); const [res,setRes]=useState<any[]|null>(null);
  const run=async(e:React.FormEvent)=>{
    e.preventDefault(); const query=q.trim();
    if(query.length<2){setErr('اكتب سؤالًا لا يقل عن حرفين');return;}
    setBusy(true); setErr(''); setRes(null);
    try{
      const data=await api<{count:number;results:any[]}>(`/api/search?q=${encodeURIComponent(query)}&limit=15`);
      setRes(data.results);
    }catch(ex:any){setErr(ex?.message||'تعذّر البحث');}
    finally{setBusy(false);}
  };
  const vlabel:Record<string,string>={source_verified:'موثّق من مصدره',machine_pending_human:'بانتظار مراجعة بشرية',operationally_accepted:'مقبول تشغيليًا',historical_only:'تاريخي فقط'};
  return <div className="space-y-5">
    <form onSubmit={run} className="rounded-2xl border bg-white dark:bg-slate-900 p-6">
      <h2 className="text-xl font-bold">البحث القانوني الدلالي</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">بحث دلالي يسترجع النص الأصلي كما هو.</p>
      <div className="mt-4 flex gap-3">
        <input value={q} onChange={e=>setQ(e.target.value)} className="input flex-1" placeholder="مثال: شروط استحقاق الحضانة"/>
        <button disabled={busy} className="rounded-xl bg-brand-blue px-8 py-3 font-bold text-white disabled:opacity-50">{busy?'يبحث…':'بحث'}</button>
      </div>
      {err&&<p className="mt-3 rounded-xl bg-rose-50 px-4 py-2 text-sm text-rose-700">{err}</p>}
    </form>
    {res&&res.length===0&&<p className="rounded-2xl border bg-white dark:bg-slate-900 p-6 text-center text-slate-500 dark:text-slate-400">لا نتائج مطابقة. جرّب صياغة أخرى.</p>}
    {res&&res.length>0&&<div className="space-y-3">
      <p className="text-sm text-slate-500 dark:text-slate-400">{res.length} نتيجة مرتّبة بدرجة التشابه الدلالي.</p>
      {res.map((h:any,i:number)=><div key={i} className="rounded-2xl border bg-white dark:bg-slate-900 p-5">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div className="text-sm text-slate-500 dark:text-slate-400">{h.branch} · {h.topic||'—'}{h.subtopic?` · ${h.subtopic}`:''}</div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-slate-100 dark:bg-slate-800 px-3 py-1 text-xs">{(h.score*100).toFixed(1)}%</span>
            <span className={`rounded-full px-3 py-1 text-xs ${h.verification_status==='source_verified'?'bg-emerald-50 text-emerald-700':'bg-amber-50 text-amber-700'}`}>{vlabel[h.verification_status]||h.verification_status}</span>
          </div>
        </div>
        {h.title&&<div className="font-bold">{h.title}</div>}
        <p className="mt-1 whitespace-pre-wrap text-sm leading-7 text-slate-800 dark:text-slate-200">{h.text}</p>
        <div className="mt-2 text-xs text-slate-400">{h.object_id}</div>
      </div>)}
    </div>}
  </div>;
}

function MdLite({text}:{text:string}) {
  const bold=(s:string)=>{const parts=s.split('**');return parts.map((p,j)=>j%2?<strong key={j}>{p}</strong>:p);};
  return <div className="space-y-1 leading-8 text-slate-800 dark:text-slate-200">{text.split('\n').map((ln,i)=>{
    if(ln.startsWith('### '))return <h4 key={i} className="mt-4 font-bold">{bold(ln.slice(4))}</h4>;
    if(ln.startsWith('## '))return <h3 key={i} className="mt-5 text-lg font-bold">{bold(ln.slice(3))}</h3>;
    if(ln.startsWith('# '))return <h2 key={i} className="mt-6 border-b pb-2 text-xl font-bold text-slate-950 dark:text-slate-100">{bold(ln.slice(2))}</h2>;
    if(/^\s*[-*]{3,}\s*$/.test(ln))return <hr key={i} className="my-4"/>;
    return <div key={i} className="whitespace-pre-wrap">{bold(ln)}</div>;
  })}</div>;
}
const _snap:{q:string;atts:string[];follow:boolean;caseId:string}={q:'',atts:[],follow:false,caseId:''};
const _openThread:{rec:any;follow:boolean;caseId:string|null}={rec:null,follow:false,caseId:null};
function DraftingView({cases}:{cases:LegalCase[];onOpen:(c:LegalCase)=>void}) {
  const [domain,setDomain]=useState('أحوال شخصية');
  const [rtype,setRtype]=useState('صحف');
  const [madhab,setMadhab]=useState('غير محدد');
  const [facts,setFacts]=useState('');
  const [attach,setAttach]=useState<any>(null);
  // ضغط الصور في المتصفح: أقصى بعد 2200 بكسل، JPEG 82% — صور الهاتف الكبيرة تهبط دون الميغا
  const compressImage=(f:File)=>new Promise<{data:string;media_type:string}>((resolve,reject)=>{
    const img=new Image(); const u=URL.createObjectURL(f);
    img.onload=()=>{ URL.revokeObjectURL(u);
      const M=2200; const sc=Math.min(1,M/Math.max(img.width,img.height));
      const w=Math.round(img.width*sc), h=Math.round(img.height*sc);
      const c=document.createElement('canvas'); c.width=w; c.height=h;
      const x=c.getContext('2d'); if(!x){reject(new Error('ctx'));return;}
      x.drawImage(img,0,0,w,h);
      const d=c.toDataURL('image/jpeg',0.82);
      resolve({data:d.split(',')[1]||'',media_type:'image/jpeg'});
    };
    img.onerror=()=>{ URL.revokeObjectURL(u); reject(new Error('img')); };
    img.src=u;
  });
  const [attachMore,setAttachMore]=useState<any[]>([]);
  const fileToAtt=(f:File)=>new Promise<any>((resolve)=>{
    if(f.size>30 * 1024 * 1024){ setErr('ملف تجاوز 30 ميغابايت: '+f.name); resolve(null); return; }
    const isImg=f.type.startsWith('image/'); const isPdf=f.type==='application/pdf';
    const isText=f.type.startsWith('text/')||/\.(txt|md|json)$/i.test(f.name);
    if(isImg){ compressImage(f).then(({data,media_type})=>resolve({kind:'image',media_type,data,name:f.name})).catch(()=>{setErr('تعذر معالجة الصورة: '+f.name);resolve(null);}); }
    else if(isPdf){ const r=new FileReader(); r.onload=()=>resolve({kind:'pdf',media_type:'application/pdf',data:String(r.result).split(',')[1]||'',name:f.name}); r.onerror=()=>resolve(null); r.readAsDataURL(f); }
    else if(isText){ const r=new FileReader(); r.onload=()=>resolve({kind:'text',text:String(r.result),name:f.name}); r.onerror=()=>resolve(null); r.readAsText(f); }
    else { setErr('نوع غير مدعوم: '+f.name); resolve(null); }
  });
  const onAttach=(e:React.ChangeEvent<HTMLInputElement>)=>{
    const fs=Array.from(e.target.files||[]); if(!fs.length)return;
    setErr('');
    Promise.all(fs.map(fileToAtt)).then(list=>{
      const okA=list.filter(Boolean);
      if(!okA.length)return;
      setAttach(okA[0]); setAttachMore(okA.slice(1,12));
    });
    e.target.value='';
  };
  const [busy,setBusy]=useState(false);
  const [err,setErr]=useState('');
  const [answer,setAnswer]=useState('');
  const [meta,setMeta]=useState<{sources_used?:number;model?:string}>({});
  const [copied,setCopied]=useState(false);
  const [provider,setProvider]=useState('');
  const [cmp,setCmp]=useState<any>(null);
  const [cmpBusy,setCmpBusy]=useState(false);
  const [caseId,setCaseId]=useState<string>('');
  const [followOn,setFollowOn]=useState(false);
  const [priorFacts,setPriorFacts]=useState('');
  const [priorAnswer,setPriorAnswer]=useState('');
  const [showThread,setShowThread]=useState(false);
  const [thread,setThread]=useState<any[]>(()=>{try{return JSON.parse(localStorage.getItem('lm-draft-thread')||'[]');}catch{return [];}});
  useEffect(()=>{(async()=>{try{const r=await fetch('/api/draft/threads');if(!r.ok)return;const d=await r.json();if(!Array.isArray(d.threads))return;setThread(t=>{const sv=d.threads.slice().reverse();const key=(x:any)=>String(x.ts||'')+'|'+String(x.q||'').slice(0,40);const have=new Set(sv.map(key));const extra=t.filter((x:any)=>!have.has(key(x)));extra.forEach((x:any)=>{try{fetch('/api/draft/threads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:String(x.q||''),a:String(x.a||''),atts:(x.atts||[]).map((y:any)=>typeof y==='string'?y:((y&&y.name)||'مرفق')),follow:!!x.follow,ts:Number(x.ts)||0})}).catch(()=>{});}catch{}});return [...extra,...sv].sort((a:any,b:any)=>(a.ts||0)-(b.ts||0)).slice(-100);});}catch{}})();},[]);
  useEffect(()=>{try{localStorage.setItem('lm-draft-thread',JSON.stringify(thread.slice(-30)));}catch{}},[thread]);
  useEffect(()=>{ if(_openThread.caseId){ setCaseId(String(_openThread.caseId)); _openThread.caseId=null; } },[]);
  useEffect(()=>{ const r=_openThread.rec; if(!r) return; _openThread.rec=null; setAnswer(String(r.a||'')); if(_openThread.follow){ setPriorFacts(String(r.q||'')); setPriorAnswer(String(r.a||'')); setFollowOn(true); setFacts(''); setAttach(null); setAttachMore([]); } },[]);
  useEffect(()=>{ if(answer&&!busy&&_snap.q){ setThread(t=>{const l=t[t.length-1]; if(l&&l.a===answer)return t; const e={q:_snap.q,a:answer,atts:_snap.atts,follow:_snap.follow,ts:Date.now(),case_id:_snap.caseId||null}; try{fetch('/api/draft/threads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...e,atts:(e.atts||[]).map((x:any)=>typeof x==='string'?x:((x&&x.name)||'مرفق'))})}).then(r=>r.ok?r.json():null).then(d=>{if(d&&d.id)setThread(t2=>t2.map((x:any)=>x.ts===e.ts?{...x,id:d.id}:x));}).catch(()=>{});}catch{} return [...t,e];}); setFollowOn(false); } },[answer,busy]);
  const isPersonal=domain==='أحوال شخصية';
  const copyAnswer=async()=>{
    try{ await navigator.clipboard.writeText(answer); setCopied(true); setTimeout(()=>setCopied(false),1500); }catch{}
  };
  // بناء HTML منسّق (RTL) من ناتج الماركداون — يُستعمل لـ Word والطباعة/PDF
  const buildHtml=(src0?:string)=>{
    const esc=(s:string)=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    const bold=(s:string)=>esc(s).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');
    const body=(src0??answer).split('\n').map(ln=>{
      if(ln.startsWith('# ')) return '<h2>'+bold(ln.slice(2))+'</h2>';
      if(ln.startsWith('## ')) return '<h3>'+bold(ln.slice(3))+'</h3>';
      if(ln.startsWith('### ')) return '<h4>'+bold(ln.slice(4))+'</h4>';
      if(/^\s*[-*]{3,}\s*$/.test(ln)) return '<hr/>';
      if(!ln.trim()) return '<p>&nbsp;</p>';
      return '<p>'+bold(ln)+'</p>';
    }).join('');
    return '<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" dir="rtl"><head><meta charset="utf-8"><style>@page{margin:2.5cm}body{font-family:"Cairo","Tahoma",sans-serif;direction:rtl;text-align:right;line-height:1.9;font-size:13pt}h2{font-size:16pt}h3{font-size:14pt}h4{font-size:13pt}</style></head><body>'+body+'</body></html>';
  };
  const dlBlob=(content:BlobPart,mime:string,ext:string)=>{
    const blob=new Blob([content],{type:mime});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url; a.download=rtype+' - '+new Date().toISOString().slice(0,10)+'.'+ext;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  };
  const downloadWord=()=>dlBlob('﻿'+buildHtml(),'application/msword','doc');
  const downloadTxt=()=>dlBlob(answer.replace(/\*\*/g,''),'text/plain;charset=utf-8','txt');
  const downloadMd=()=>dlBlob(answer,'text/markdown;charset=utf-8','md');
  const downloadJson=()=>dlBlob(JSON.stringify({request_type:rtype,branch:domain,madhab:isPersonal&&madhab!=='غير محدد'?madhab:null,model:meta.model,sources_used:meta.sources_used,answer},null,2),'application/json;charset=utf-8','json');
  const printDoc=()=>{ const w=window.open('','_blank'); if(!w)return; w.document.write(buildHtml()); w.document.close(); w.focus(); setTimeout(()=>w.print(),300); };
  const emailDoc=()=>{ const s=encodeURIComponent(rtype+' — صوت العدالة'); const b=encodeURIComponent(answer.replace(/\*\*/g,'').slice(0,1800)+(answer.length>1800?'\n\n… (النص كامل في ملف Word المرفق)':'')); window.location.href='mailto:?subject='+s+'&body='+b; };
  const waDoc=()=>{ const t=encodeURIComponent(answer.replace(/\*\*/g,'').slice(0,1800)+(answer.length>1800?'\n\n… (النص كامل في ملف Word)':'')); window.open('https://wa.me/?text='+t,'_blank'); };
  const mkBody=(prov:string|null,rid?:string)=>JSON.stringify({request_type:rtype,facts,branch:domain,madhab:isPersonal&&madhab!=='غير محدد'?madhab:null,attachment:attach||null,attachments:attachMore,prior_facts:followOn?priorFacts:null,prior_answer:followOn?priorAnswer:null,case_id:caseId||null,draft_provider:prov,client_rid:rid||null});
  const _mkRid=()=>{try{return (crypto as any).randomUUID();}catch{return String(Date.now())+'-'+Math.floor(Math.random()*1e9);}};
  const waitResult=async(rid:string,ms:number)=>{
    const t0=Date.now();
    while(Date.now()-t0<ms){
      try{
        const r=await fetch('/api/draft/result/'+encodeURIComponent(rid));
        if(r.ok){const d=await r.json().catch(()=>null);
          if(d&&d.found&&d.res&&typeof d.res.answer==='string'&&d.res.answer.trim())return d.res;}
      }catch{}
      await new Promise(res=>setTimeout(res,12000));
    }
    return null;
  };
  const runCompare=async()=>{
    if(!facts.trim()||busy||cmpBusy)return;
    setCmpBusy(true);setErr('');setCmp(null);
    const call=async(prov:string)=>{
      const rid=_mkRid();
      let v:any=null;
      try{
        const r=await fetch('/api/draft',{method:'POST',headers:{'Content-Type':'application/json'},body:mkBody(prov,rid)});
        if(!r.ok){const d=await r.json().catch(()=>null);const he=new Error((d&&d.detail)||('فشل الطلب ('+r.status+')'));(he as any)._http=true;throw he;}
        v=await r.json().catch(()=>null);
      }catch(e){ if((e as any)?._http)throw e; v=null; }
      if(v&&typeof v.answer==='string'&&v.answer.trim())return v;
      const rec=await waitResult(rid,9*60*1000);
      if(rec)return rec;
      throw new Error(String((v&&(v.detail||v.error))||'انقطع البث ولم تُسترد النتيجة خلال المهلة — أعد المحاولة'));
    };
    const names:[string,string][]=[['anthropic','Claude'],['openai','GPT']];
    const rs=await Promise.allSettled(names.map(n=>call(n[0])));
    const pair=rs.map((r,i)=>r.status==='fulfilled'?{prov:names[i][0],name:names[i][1],...(r as any).value}:{prov:names[i][0],name:names[i][1],error:String(((r as any).reason&&(r as any).reason.message)||'خطأ غير متوقع')});
    if(pair.every((p:any)=>p.error))setErr('فشل المزوّدان معًا — '+pair.map((p:any)=>p.name+': '+p.error).join(' | '));
    else setCmp({pair:Math.random()<0.5?pair.slice().reverse():pair,reveal:false});
    setCmpBusy(false);
  };
  const run=async()=>{
    if(!facts.trim()||busy||cmpBusy)return;
    setBusy(true);setErr('');setAnswer('');setMeta({});
    try{
      const rid=_mkRid();
      let d:any=null;
      try{
        const r=await fetch('/api/draft',{method:'POST',headers:{'Content-Type':'application/json'},
          body:mkBody(provider||null,rid)});
        if(!r.ok){const dd=await r.json().catch(()=>null);const he=new Error((dd&&dd.detail)||('فشل الطلب ('+r.status+')'));(he as any)._http=true;throw he;}
        d=await r.json().catch(()=>null);
      }catch(e){ if((e as any)?._http)throw e; d=null; }
      if(!(d&&typeof d.answer==='string'&&d.answer.trim())){
        setErr('انقطع البث أثناء التسليم — أسترد النتيجة من الخادم تلقائيًا، لا تغلق الصفحة…');
        d=await waitResult(rid,9*60*1000);
        setErr('');
        if(!d)throw new Error('انقطع البث ولم تُسترد النتيجة خلال المهلة — أعد المحاولة');
      }
      setAnswer(d.answer||'');setMeta({sources_used:d.sources_used,model:d.model});
    }catch(e){setErr(e instanceof Error?e.message:'خطأ غير متوقع');}
    setBusy(false);
  };
  return <div className="flex flex-col gap-6 lg:h-[calc(100vh-10rem)] lg:flex-row">
    {cmp&&<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-3" dir="rtl">
      <div className="flex h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl dark:bg-slate-900">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 p-4 dark:border-slate-800">
          <h3 className="text-lg font-bold text-ink dark:text-white">⚖ مقارنة الإجابتين — اقرأ ثم اعتمد الأفضل</h3>
          <div className="flex items-center gap-2">
            <button onClick={()=>setCmp((c:any)=>({...c,reveal:!c.reveal}))} className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 transition hover:border-brand-blue hover:text-brand-blue dark:border-slate-600 dark:text-slate-300">{cmp.reveal?'إخفاء النموذجين':'كشف النموذجين'}</button>
            <button onClick={()=>setCmp(null)} className="rounded-lg border border-rose-200 px-3 py-1.5 text-sm font-bold text-rose-500 dark:border-rose-800">إغلاق ✕</button>
          </div>
        </div>
        <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-2">
          {cmp.pair.map((c:any,i:number)=><div key={i} className={'flex min-h-0 flex-col '+(i?'border-t border-slate-200 dark:border-slate-800 md:border-t-0 md:border-r':'')}>
            <div className="flex items-center justify-between gap-2 border-b border-slate-100 bg-slate-50 px-4 py-2 dark:border-slate-800 dark:bg-slate-800/50">
              <span className="font-bold text-ink dark:text-white">الإجابة {i?'ب':'أ'}{cmp.reveal?' — '+c.name+(c.model?' ('+c.model+')':''):''}</span>
              {!c.error&&<span className="flex shrink-0 items-center gap-1.5">
                <button onClick={()=>{try{navigator.clipboard.writeText(c.answer||'');}catch{}}} className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs text-slate-600 transition hover:border-brand-blue hover:text-brand-blue dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300">نسخ</button>
                <button onClick={()=>dlBlob(''+buildHtml(c.answer||''),'application/msword','doc')} className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs text-slate-600 transition hover:border-brand-blue hover:text-brand-blue dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300">Word</button>
                <button onClick={()=>{setAnswer(c.answer||'');setMeta({sources_used:c.sources_used,model:c.model});setCmp(null);}} className="rounded-lg bg-emerald-600 px-3 py-1 text-sm font-bold text-white transition hover:bg-emerald-700">اعتماد هذه الإجابة</button>
              </span>}
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">{c.error?<div className="rounded-lg bg-red-50 p-3 text-sm leading-7 text-red-800 dark:bg-red-950/40 dark:text-red-300">تعذر توليد هذه الإجابة — السبب: <bdi className="font-mono text-xs">{String(c.error||'غير معروف')}</bdi>. أعد المحاولة، وإن تكرر فراجع يوميات الخادم.</div>:<MdLite text={c.answer||''}/>}</div>
          </div>)}
        </div>
      </div>
    </div>}
    <div className="flex w-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900 lg:w-[350px] lg:shrink-0">
      <div className="border-b border-slate-200 p-4 dark:border-slate-800"><h2 className="flex items-center gap-2 text-lg font-bold text-ink dark:text-white"><SlidersHorizontal size={18} className="text-brand-blue"/>محددات الصياغة</h2></div>
      <div className="flex-1 space-y-5 overflow-y-auto p-4">
        <label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-300">المجال القانوني</span>
          <select className="input" value={domain} onChange={e=>{const v=e.target.value;setDomain(v);if(v!=='أحوال شخصية')setMadhab('غير محدد');}}>
            <option>أحوال شخصية</option><option>مدني</option><option>تجاري</option><option>إداري</option><option>جزائي</option><option>عمّالي</option><option>إيجارات</option>
          </select></label>
        {isPersonal&&<label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-300">المذهب</span>
          <select className="input" value={madhab} onChange={e=>setMadhab(e.target.value)}>
            <option>غير محدد</option><option>سني</option><option>جعفري</option>
          </select></label>}
        <label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-300">نوع الطلب</span>
          <select className="input" value={rtype} onChange={e=>setRtype(e.target.value)}>
            <option>صحف</option><option>مذكرات</option><option>طلبات وأوامر</option><option>استشارات قانونية</option><option>عقود</option>
          </select></label>
        <label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-300">النموذج المجيب</span>
          <select className="input" value={provider} onChange={e=>setProvider(e.target.value)}>
            <option value="">Claude (الافتراضي)</option><option value="openai">GPT</option>
          </select></label>
        <label className="block"><span className="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-300">الوقائع والتفاصيل</span>
          <textarea className="input min-h-52 leading-8" value={facts} onChange={e=>setFacts(e.target.value)}
            placeholder={followOn?'متابعة: اسأل، أو اطلب صياغة تالية، أو صف الأوراق الإضافية المرفقة…':'أدخل وقائع القضية وتفاصيلها هنا للبدء في الصياغة…'}/></label>
          {!isNativeApp() && (<label className="block"><span className="mb-1.5 block text-xs font-bold text-slate-500 dark:text-slate-400">القضية — تُحفظ الجولة وأوراقها في ملفها</span><select className="input" value={caseId} onChange={e=>setCaseId(e.target.value)}><option value="">بلا قضية — جولة عامة</option>{cases.map((c:any)=><option key={c.id} value={c.id}>{c.title}{c.case_key?' — '+c.case_key:''}</option>)}</select></label>)}
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <label className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-slate-600 transition hover:border-brand-blue hover:text-brand-blue dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
            <Paperclip size={15}/> إرفاق ملف/صورة
            <input type="file" accept="image/*,application/pdf,.txt,.md,.json" className="hidden" multiple onChange={onAttach}/>
          </label>
          {attach&&<span className="flex items-center gap-1.5 rounded-lg bg-brand-soft px-2.5 py-1 text-xs text-brand-dark dark:bg-brand-blue/15 dark:text-brand-blue">{attach.name}<button type="button" onClick={()=>(setAttach(null),setAttachMore([]))} className="font-bold text-rose-500">✕</button></span>}
          {attachMore.length>0&&<span className="rounded-lg bg-brand-soft px-2 py-1 text-xs text-brand-dark dark:bg-brand-blue/15 dark:text-brand-blue">+{attachMore.length} مستندات</span>}
          {followOn&&<span className="flex items-center gap-1.5 rounded-lg bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">↩ متابعة للجولة السابقة<button type="button" onClick={()=>setFollowOn(false)} className="font-bold text-rose-500">✕</button></span>}
        </div>
      </div>
      <div className="space-y-2 rounded-b-2xl border-t border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-800/50">
        <button onClick={()=>{_snap.q=facts;_snap.atts=[attach?.name,...attachMore.map((x:any)=>x?.name)].filter(Boolean) as string[];_snap.follow=followOn;_snap.caseId=caseId;run();}} disabled={busy||cmpBusy||!facts.trim()} className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-blue py-3 font-bold text-white shadow-sm shadow-brand-blue/20 transition hover:bg-brand-dark disabled:opacity-50">
          {busy?'جارٍ البحث والتحرير…':'نفّذ الطلب'}</button>
        <button onClick={()=>{_snap.q=facts;_snap.atts=[attach?.name,...attachMore.map((x:any)=>x?.name)].filter(Boolean) as string[];_snap.follow=followOn;_snap.caseId=caseId;runCompare();}} disabled={busy||cmpBusy||!facts.trim()} className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-brand-blue bg-white py-2.5 font-bold text-brand-blue transition hover:bg-brand-soft disabled:opacity-50 dark:bg-slate-800 dark:hover:bg-slate-700">
          {cmpBusy?'جارٍ توليد الإجابتين معًا…':'⚖ قارن الإجابتين'}</button>
        {cmpBusy&&<p className="text-center text-xs text-slate-500 dark:text-slate-400">جولتان متوازيتان من نموذجين مختلفين على السؤال نفسه — قد يستغرق حتى ست دقائق. لا تغلق الصفحة.</p>}
        {busy&&<p className="text-center text-xs text-slate-500 dark:text-slate-400">يبحث في قاعدة المعرفة ثم يحرر المخرج — قد يستغرق دقيقتين إلى خمس دقائق. لا تغلق الصفحة.</p>}
        {err&&<div className="rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950/40 dark:text-red-300">{err}</div>}
      </div>
    </div>
    <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-col gap-3 border-b border-slate-200 bg-slate-50/50 p-4 dark:border-slate-800 dark:bg-slate-800/40 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="flex items-center gap-2 text-lg font-bold text-ink dark:text-white"><FileText size={18} className="text-brand-blue"/>مسودة الصياغة</h2>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <button onClick={()=>{ setPriorFacts(_snap.q||facts); setPriorAnswer(answer); setFollowOn(true); setFacts(''); (setAttach(null),setAttachMore([])); }} disabled={!answer} className="flex items-center gap-1.5 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-sm font-bold text-emerald-700 transition hover:bg-emerald-100 disabled:opacity-40 dark:border-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">↩ متابعة</button>
            <button onClick={()=>setShowThread(s=>!s)} className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:border-brand-blue hover:text-brand-blue dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300">السجل ({thread.length})</button>
          </div>
          <span className="hidden h-6 w-px shrink-0 bg-slate-300 dark:bg-slate-600 sm:block"></span>
          <div className="flex flex-wrap items-center gap-1.5">
            <button onClick={copyAnswer} disabled={!answer} className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:border-brand-blue hover:text-brand-blue disabled:opacity-40 disabled:hover:border-slate-200 disabled:hover:text-slate-600 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300"><Copy size={15}/>{copied?'نُسخ ✓':'نسخ'}</button>
            <button onClick={downloadWord} disabled={!answer} className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:border-brand-blue hover:text-brand-blue disabled:opacity-40 disabled:hover:border-slate-200 disabled:hover:text-slate-600 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300"><Download size={15}/>تنزيل Word</button>
            <button onClick={printDoc} disabled={!answer} className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:border-brand-blue hover:text-brand-blue disabled:opacity-40 disabled:hover:border-slate-200 disabled:hover:text-slate-600 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300"><Printer size={15}/>طباعة / PDF</button>
            <select disabled={!answer} onChange={e=>{const v=e.target.value; e.currentTarget.value=''; if(v==='txt')downloadTxt(); else if(v==='md')downloadMd(); else if(v==='json')downloadJson();}} className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 disabled:opacity-40 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300" defaultValue="">
            <option value="" disabled>صيغ أخرى ▾</option><option value="txt">نص (.txt)</option><option value="md">Markdown (.md)</option><option value="json">JSON (.json)</option>
          </select>
          </div>
          <span className="hidden h-6 w-px shrink-0 bg-slate-300 dark:bg-slate-600 sm:block"></span>
          <div className="flex flex-wrap items-center gap-1.5">
            <button onClick={emailDoc} disabled={!answer} className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:border-brand-blue hover:text-brand-blue disabled:opacity-40 disabled:hover:border-slate-200 disabled:hover:text-slate-600 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300"><Mail size={15}/>بريد</button>
            <button onClick={waDoc} disabled={!answer} className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:border-emerald-500 hover:text-emerald-600 disabled:opacity-40 disabled:hover:border-slate-200 disabled:hover:text-slate-600 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300"><Share2 size={15}/>واتساب</button>
          </div>
        </div>
      </div>
        {/* درج-السجل: عائم فلا يزاحم المسودة */}
        {showThread&&<div className="fixed inset-0 z-40 bg-black/30" onClick={()=>setShowThread(false)}>
        {/* سجل-صفحة-كاملة */}
        <div dir="rtl" onClick={e=>e.stopPropagation()} className="absolute inset-0 overflow-y-auto bg-white p-4 text-sm dark:bg-slate-900 sm:p-6">
        <div className="mx-auto max-w-4xl">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-sm font-bold text-ink dark:text-white">سجل الجولات — انقر أي جولة لعرضها أو متابعتها أو حذفها</h3>
            <button onClick={()=>setShowThread(false)} className="shrink-0 rounded-lg border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-500 transition hover:border-rose-300 hover:text-rose-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300">إغلاق ✕</button>
          </div>
          {thread.length===0&&<p className="text-slate-400">لا جولات محفوظة بعد — كل طلب ناجح يُسجَّل هنا بسؤاله وجوابه ومرفقاته.</p>}
          {thread.slice().reverse().map((r:any,i:number)=><details key={r.ts||i} className="mb-2 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/60">
            <summary className="cursor-pointer">
              <span className="flex flex-wrap items-center gap-2 text-xs">
                {r.follow?<span className="rounded bg-emerald-50 px-1.5 py-0.5 font-bold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">↩ متابعة</span>:null}
                <span className="text-slate-400">{new Date(r.ts).toLocaleString('ar')}</span>
                {r.atts&&r.atts.length?<span className="rounded bg-brand-soft px-1.5 py-0.5 text-brand-dark dark:bg-brand-blue/15 dark:text-brand-blue">📎 {r.atts.length} مرفق</span>:null}
              </span>
              <span className="mt-1 block truncate font-semibold leading-7 text-slate-800 dark:text-slate-100">{String(r.q||'').slice(0,140)||'(بلا نص)'}</span>
            </summary>
            <div className="mt-2 whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs leading-6 text-slate-600 dark:bg-slate-800 dark:text-slate-300"><b>السؤال:</b> {r.q}{r.atts&&r.atts.length?'\nالمرفقات: '+r.atts.join('، '):''}</div>
            <div className="mt-2 max-h-60 overflow-y-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs leading-6 dark:bg-slate-800"><b>الجواب:</b> {r.a}</div>
            <div className="mt-2 flex gap-2"><button onClick={()=>setAnswer(r.a)} className="rounded border border-slate-300 px-2 py-0.5 text-xs dark:border-slate-600">عرض في المسودة</button>
            <button onClick={()=>{setPriorFacts(String(r.q||''));setPriorAnswer(String(r.a||''));setFollowOn(true);setAnswer(String(r.a||''));setFacts('');setAttach(null);setAttachMore([]);setShowThread(false);}} className="rounded border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">↩ متابعة من هنا</button>
            <button onClick={()=>{if(r.id){try{fetch('/api/draft/threads/'+r.id,{method:'DELETE'}).catch(()=>{});}catch{}} setThread(t=>t.filter((x:any)=>x!==r));}} className="rounded border border-rose-200 px-2 py-0.5 text-xs text-rose-500 dark:border-rose-800">حذف</button></div>
          </details>)}
        </div>
        </div>
        </div>}
      <div className="flex-1 overflow-y-auto p-6 lg:p-8">
        {answer?<div className="mx-auto max-w-4xl">
          <div className="mb-4 flex items-center justify-end gap-2 text-xs text-slate-500 dark:text-slate-400"><span>استند إلى {meta.sources_used??'—'} مصدرًا</span>{meta.model&&<span className="rounded-full bg-brand-soft px-2 py-0.5 text-brand-dark dark:bg-brand-blue/15 dark:text-brand-blue">{meta.model}</span>}</div>
          <MdLite text={answer}/>
        </div>:<div className="flex h-full flex-col items-center justify-center p-8 text-center">
          <div className="mb-4 grid h-20 w-20 place-items-center rounded-full bg-slate-50 text-brand-blue/40 dark:bg-slate-800"><PenLine size={30}/></div>
          <h3 className="mb-2 text-xl font-bold text-slate-700 dark:text-slate-200">{busy?'جارٍ التحرير…':'استوديو الصياغة الذكي'}</h3>
          <p className="mx-auto max-w-md text-sm text-slate-500 dark:text-slate-400">حدّد المجال ونوع الطلب وأدخل الوقائع في اللوحة الجانبية، ثم اضغط «نفّذ الطلب» للحصول على صياغة قانونية متكاملة مدعّمة بالأسانيد.</p>
        </div>}
      </div>
    </div>
  </div>;
}
function ReviewView({cases,onOpen}:{cases:LegalCase[];onOpen:(c:LegalCase)=>void}) { return <div className="rounded-2xl border bg-white dark:bg-slate-900 p-7"><h2 className="text-2xl font-bold">مراجعة الأسانيد</h2><p className="mt-2 text-slate-500 dark:text-slate-400">تعرض هذه المرحلة مدى وجود التشريع والمبدأ والنموذج لكل قضية. افتح القضية لعرض تقرير التغطية.</p><div className="mt-6 space-y-3">{cases.map(c=><button key={c.id} onClick={()=>onOpen(c)} className="flex w-full justify-between rounded-xl border p-4"><span>{c.title}</span><span className="text-slate-500 dark:text-slate-400">فتح التقرير</span></button>)}</div></div> }

const statusLabel: Record<string,string> = {
  queued:'في طابور المعالجة', started:'قيد المعالجة', completed:'اكتملت المعالجة',
  failed:'فشلت المعالجة', duplicate:'مكرر — لم تُنشأ نسخة', unknown:'غير معروفة'
};

function ProcessingStatus({items}:{items:FileStatus[]}) {
  if (!items.length) return null;
  return <div className="space-y-3 rounded-2xl border bg-slate-50 dark:bg-slate-800/50 p-5">
    <h3 className="font-bold">حالة المعالجة</h3>
    {items.map(s => {
      const tone = s.status==='completed' ? 'border-emerald-300 bg-emerald-50 text-emerald-900'
        : s.status==='failed' ? 'border-red-300 bg-red-50 text-red-900'
        : s.status==='duplicate' ? 'border-amber-300 bg-amber-50 text-amber-900'
        : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300';
      return <div key={s.file_id} className={`rounded-xl border p-4 text-sm ${tone}`}>
        <div className="flex items-center gap-2 font-bold">
          {s.status==='completed' && <CheckCircle2 size={16}/>}
          {s.status==='failed' && <XCircle size={16}/>}
          <span className="font-mono text-xs">{s.file_id}</span>
          <span>— {statusLabel[s.status] || s.status}</span>
        </div>
        {s.status==='completed' && <p className="mt-2">أُنشئ {s.object_count} كائنًا قانونيًا · الدفعة <span className="font-mono text-xs">{s.batch_id}</span></p>}
        {s.status==='duplicate' && s.duplicate_of && <p className="mt-2">
          النص مُدخل مسبقًا تحت الفرع والموضوع نفسيهما. الدفعة السابقة:{' '}
          <span className="font-mono text-xs">{s.duplicate_of.first_batch_id}</span>
          {' '}({s.duplicate_of.object_count} كائنًا{s.duplicate_of.ingested_at ? ` · ${fmt(s.duplicate_of.ingested_at)}` : ''}).
        </p>}
        {s.status==='failed' && s.error && <p className="mt-2">{s.error}</p>}
        {(s.status==='queued'||s.status==='started') && <p className="mt-2 text-slate-500 dark:text-slate-400">جارٍ التطبيع والاستخراج والفهرسة...</p>}
      </div>;
    })}
  </div>;
}

function UploadPanel({topics,onSubmit,message,error,method,setMethod,processing,busy}:{
  topics:Topic[]; onSubmit:(e:React.FormEvent<HTMLFormElement>)=>void; message:string; error:string;
  method:UploadMethod; setMethod:(m:UploadMethod)=>void; processing:FileStatus[]; busy:boolean;
}) {
  const tab = (id:UploadMethod, label:string) =>
    <button key={id} type="button" onClick={()=>setMethod(id)}
      className={`rounded-xl px-6 py-3 font-bold ${method===id?'bg-brand-blue text-white':'border bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 hover:border-brand-blue'}`}>{label}</button>;

  return <form onSubmit={onSubmit} className="mx-auto max-w-5xl space-y-6 rounded-3xl border bg-white dark:bg-slate-900 p-8">
    <div>
      <h2 className="text-2xl font-bold">إضافة مصدر قانوني</h2>
      <p className="mt-2 text-slate-500 dark:text-slate-400">ارفع ملفًا أو الصق نصًا. عنوان التصنيف مفتاح الاسترجاع.</p>
    </div>

    <div className="flex gap-3">{tab('file','رفع ملف')}{tab('paste','لصق نص')}</div>

    <div className="grid grid-cols-2 gap-5">
      <Field label="عنوان المصدر"><input className="input" name="source_title" placeholder="مثال: الطعن رقم 145 لسنة 2023"/></Field>
      <Field label="نوع المصدر"><select name="source_type" className="input">
        <option value="judicial_principles_collection">مجموعة مبادئ قضائية مختصرة</option>
        <option value="single_judicial_principle">مبدأ قضائي منفرد</option>
        <option value="full_judgment">حكم كامل</option>
        <option value="legislation">تشريع</option>
        <option value="judicial_template">صيغة أو صحيفة قضائية</option>
        <option value="legal_memorandum">مذكرة دفاع</option>
      </select></Field>
      <Field label="الفرع"><select name="branch" required className="input">
        <option>أحوال شخصية</option><option>مدني</option><option>تجاري</option>
        <option>عمالي</option><option>جزائي</option><option>إداري</option>
        <option>دستوري</option><option>مرافعات</option><option>إثبات</option><option>تنفيذ</option>
      </select></Field>
      <Field label="الموضوع"><input className="input" name="topic" required list="dl-topics" placeholder="مثال: الحضانة"/><datalist id="dl-topics">{[...new Set(topics.map(t=>t.topic).filter(Boolean))].map(t=><option key={t} value={t}/>)}</datalist></Field>
      <Field label="عنوان تصنيف محكمة التمييز"><input className="input" name="classification_title" list="dl-cls" placeholder="مثال: سقوط الحضانة"/><datalist id="dl-cls">{[...new Set(topics.map(t=>t.subtopic).filter(Boolean))].map(t=><option key={t} value={t}/>)}</datalist></Field>
      <Field label="المسألة الدقيقة (اختياري)"><input className="input" name="micro_issue" list="dl-mi" placeholder="مثال: زواج الحاضنة"/><datalist id="dl-mi">{[...new Set(topics.map(t=>t.micro_issue).filter(Boolean))].map(t=><option key={t} value={t}/>)}</datalist></Field>
      <Field label="الدائرة (اختياري)"><input className="input" name="circuit"/></Field>
      <Field label="درجة المحكمة (اختياري)"><input className="input" name="court_level" placeholder="أول درجة / استئناف / تمييز"/></Field>
      <Field label="حالة التوثيق"><select name="verification_status" required className="input" defaultValue="source_verified">
        <option value="source_verified">موثّق من مصدره — نص أصلي حرفي</option>
        <option value="operationally_accepted">مقبول عمليًا — راجعه إنسان</option>
        <option value="machine_pending_human">مستنبط آليًا — بانتظار مراجعة بشرية</option>
        <option value="historical_only">تاريخي فقط</option>
        <option value="requires_post_2026_reassessment">يحتاج إعادة تقييم بعد 2026</option>
      </select></Field>
      <Field label="ملاحظات على المصدر (اختياري)"><input className="input" name="source_notes" placeholder="مصدر النص، تحفظات، سياق"/></Field>
    </div>

    {method==='file'
      ? <label className="flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed bg-slate-50 dark:bg-slate-800/50 p-8">
          <UploadCloud size={38} className="mb-3 text-brand-blue"/>
          <span className="font-bold">اسحب الملفات هنا أو اضغط للاختيار</span>
          <span className="mt-2 text-sm text-slate-500 dark:text-slate-400">DOCX · PDF نصي · HTML · TXT · Markdown</span>
          <span className="mt-1 text-xs text-slate-400">الـPDF الممسوح ضوئيًا (بلا طبقة نصية) يُرفض ولا يُنشئ سجلًا</span>
          <input type="file" name="files" multiple accept=".docx,.pdf,.html,.htm,.txt,.md" className="hidden"/>
        </label>
      : <Field label="نص المصدر القانوني">
          <textarea name="content" dir="rtl" rows={16} minLength={20}
            className="input min-h-80 leading-loose"
            placeholder="الصق هنا نص الحكم أو المبدأ أو مواد التشريع كما هي حرفيًا، بلا تحرير ولا تلخيص..."/>
          <span className="text-xs text-slate-500 dark:text-slate-400">الحد الأدنى 20 حرفًا، والأقصى 500,000 حرف. يُحفظ النص كما لُصق حرفيًا.</span>
        </Field>}

    <button disabled={busy} className="w-full rounded-xl bg-brand-blue py-3.5 font-bold text-white disabled:opacity-50">
      {busy ? 'جارٍ الحفظ...' : 'حفظ وبدء المعالجة'}
    </button>

    {message && <p className="rounded-xl bg-slate-100 dark:bg-slate-800 p-4 text-sm">{message}</p>}
    {error && <p className="flex items-center gap-2 rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-900"><XCircle size={16}/>{error}</p>}
    <ProcessingStatus items={processing}/>
  </form>;
}
function Field({label,children}:{label:string;children:React.ReactNode}) { return <label className="space-y-2"><span className="text-sm font-bold">{label}</span>{children}</label> }
function KnowledgeTree({groups}:{groups:[string,Topic[]][]}) { return <div className="space-y-5">{groups.length===0?<Empty/>:groups.map(([branch,items])=><section key={branch} className="rounded-2xl border bg-white dark:bg-slate-900 p-6"><h3 className="mb-4 text-lg font-bold">{branch}</h3><div className="grid grid-cols-2 gap-3">{items.map((t,i)=><div key={i} className="rounded-xl bg-slate-50 dark:bg-slate-800/50 p-4"><div className="font-bold">{t.topic||'غير مصنف'}</div><div className="mt-1 text-sm text-slate-600 dark:text-slate-300">{t.subtopic||'—'} {t.micro_issue?`← ${t.micro_issue}`:''}</div><div className="mt-2 text-xs text-amber-700">{t.object_count} عنصر</div></div>)}</div></section>)}</div> }
function DocumentsTable({rows}:{rows:DocumentRow[]}) { return rows.length?<div className="overflow-auto rounded-2xl border bg-white dark:bg-slate-900"><table className="w-full text-sm"><thead className="bg-slate-50 dark:bg-slate-800/50"><tr>{['المعرف','النوع','الفرع','الموضوع','العنوان','المسألة','الحالة'].map(x=><th key={x} className="p-3 text-right">{x}</th>)}</tr></thead><tbody>{rows.map(r=><tr key={r.id} className="border-t"><td className="p-3 font-mono text-xs">{r.id}</td><td className="p-3">{typeLabel[r.object_type]||r.object_type}</td><td className="p-3">{r.branch}</td><td className="p-3">{r.topic||'—'}</td><td className="p-3">{r.subtopic||'—'}</td><td className="p-3">{r.micro_issue||'—'}</td><td className="p-3">{r.verification_status}</td></tr>)}</tbody></table></div>:<Empty/> }
function JobsTable({jobs}:{jobs:Job[]}) { return jobs.length?<div className="overflow-auto"><table className="w-full text-sm"><thead><tr>{['الدفعة','الحالة','العناصر','العلاقات','بدأت','اكتملت'].map(x=><th key={x} className="p-3 text-right">{x}</th>)}</tr></thead><tbody>{jobs.map(j=><tr key={j.batch_id} className="border-t"><td className="p-3 font-mono text-xs">{j.batch_id}</td><td className="p-3">{j.status}</td><td className="p-3">{j.object_count}</td><td className="p-3">{j.relationship_count}</td><td className="p-3">{fmt(j.started_at)}</td><td className="p-3">{fmt(j.completed_at)}</td></tr>)}</tbody></table></div>:<Empty/> }
function GraphView({topics}:{topics:Topic[]}) { const sample=topics.slice(0,8); return <div className="rounded-3xl border bg-white dark:bg-slate-900 p-8"><h2 className="text-2xl font-bold">الرسم المعرفي</h2><p className="mt-2 text-slate-500 dark:text-slate-400">تمهيد بصري للعلاقات. ستظهر الروابط الفعلية بعد إدخال الأحكام والمبادئ والنماذج وربطها.</p><div className="mt-10 flex flex-wrap items-center justify-center gap-6">{sample.map((t,i)=><div key={i} className="grid h-36 w-36 place-items-center rounded-full border-4 border-amber-300 bg-amber-50 p-4 text-center text-sm font-bold">{t.topic||t.branch}<small className="block font-normal text-slate-500 dark:text-slate-400">{t.object_count} عنصر</small></div>)}</div></div> }
function cleanTxt(t:string){ if(!t) return t; if(!/w:[A-Za-z]/.test(t)) return t; return String(t).replace(/<\/?[^>]+>/g,' ').replace(/\bw:[A-Za-z]+="[^"]*"/g,' ').replace(/\bw:[A-Za-z]+/g,' ').replace(/\/>/g,' ').replace(/[ \t]{2,}/g,' ').replace(/\n{3,}/g,'\n\n').trim(); }
function DetailCard({o}:{o:any}) {
  const vlabel:Record<string,string>={source_verified:'موثّق من مصدره',machine_pending_human:'بانتظار مراجعة بشرية',operationally_accepted:'مقبول تشغيليًا',historical_only:'تاريخي فقط'};
  return <section className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
    <div className="mb-3 flex flex-wrap items-center gap-2 border-b border-slate-100 pb-3 dark:border-slate-800">
      <span className="rounded-full bg-brand-soft px-2.5 py-0.5 text-xs font-bold text-brand-dark dark:bg-brand-blue/15 dark:text-brand-blue">{OBJ_LABEL[o.object_type]||typeLabel[o.object_type]||o.object_type||'مصدر'}</span>
      {o.branch&&<span className="text-xs text-slate-400">{o.branch}</span>}
      {o.verification_status&&<span className="mr-auto text-xs text-slate-400">{vlabel[o.verification_status]||o.verification_status}</span>}
    </div>
    {o.title&&<h2 className="text-lg font-bold">{o.title}</h2>}
    <div className="mt-1 text-xs text-slate-400">{[o.topic,o.subtopic,o.micro_issue].filter(Boolean).join(' ← ')}</div>
    <p className="mt-4 whitespace-pre-wrap leading-8 text-slate-800 dark:text-slate-200">{cleanTxt(o.text)||'—'}</p>
    <div className="mt-4 font-mono text-xs text-slate-400">{o.id}</div>
  </section>;
}
function KnowledgeView() {
  const TABS=[{k:'laws',l:'القوانين'},{k:'principles',l:'المبادئ والأحكام'},{k:'templates',l:'الصيغ'}];
  const [tab,setTab]=useState('laws');
  const [path,setPath]=useState<{level:string;key:string}[]>([]);
  const [data,setData]=useState<any>({mode:'groups',groups:[],items:[]});
  const [loading,setLoading]=useState(false);
  const [q,setQ]=useState(''); const [fbranch,setFbranch]=useState('');
  const [branchOpts,setBranchOpts]=useState<string[]>([]);
  const [results,setResults]=useState<any[]|null>(null); const [busy,setBusy]=useState(false);
  const [detail,setDetail]=useState<any|null>(null); const [derr,setDerr]=useState('');
  useEffect(()=>{ api<any>('/api/browse?kind=principles').then(d=>setBranchOpts((d.groups||[]).map((g:any)=>g.key))).catch(()=>{}); },[]);
  const fetchPath=async(t:string,pth:{level:string;key:string}[])=>{
    setLoading(true); setDerr('');
    let url='/api/browse?kind='+t;
    if(t==='laws'){ if(pth[0]) url+='&b='+encodeURIComponent(pth[0].key); if(pth[1]) url+='&group='+encodeURIComponent(pth[1].key); if(pth[2]) url+='&part='+encodeURIComponent(pth[2].key); }
    else { if(pth[0]) url+='&b='+encodeURIComponent(pth[0].key); if(pth[1]) url+='&t='+encodeURIComponent(pth[1].key); }
    try{ const d=await api<any>(url); setData(d); }
    catch(e){ setData({mode:'groups',groups:[],items:[]}); setDerr(e instanceof Error?e.message:'تعذّر التحميل'); }
    finally{ setLoading(false); }
  };
  useEffect(()=>{ if(!results&&!detail) fetchPath(tab,path); },[tab,path]); // eslint-disable-line react-hooks/exhaustive-deps
  const openObj=async(id:string,fallback?:any)=>{ setDerr(''); if(fallback&&fallback.text){setDetail({...fallback,id});return;} try{ const o=await api<any>('/api/object/'+encodeURIComponent(id)); setDetail(o); }catch(e){ setDerr(e instanceof Error?e.message:'تعذّر جلب النص'); } };
  const runSearch=async(e:React.FormEvent)=>{ e.preventDefault(); const query=q.trim(); if(query.length<2){setDerr('اكتب كلمتين على الأقل');return;} setBusy(true);setDerr('');setResults(null);setDetail(null);
    try{ const d=await api<{results:any[]}>('/api/search?q='+encodeURIComponent(query)+'&limit=30'); let rs=d.results||[]; if(fbranch) rs=rs.filter((h:any)=>(h.branch||'')===fbranch); setResults(rs); }
    catch(ex){ setResults([]); setDerr(ex instanceof Error?ex.message:'تعذّر البحث'); } finally{ setBusy(false); } };
  const clearAll=()=>{ setResults(null); setDetail(null); setQ(''); setDerr(''); fetchPath(tab,path); };
  const changeTab=(k:string)=>{ setTab(k); setPath([]); setResults(null); setDetail(null); };
  const gTitle=(key:string,name?:string)=> (tab==='laws'&&path.length===1)? lawTitle(key,name): key;
  const bar=<form onSubmit={runSearch} className="flex flex-wrap gap-2">
    <div className="relative min-w-[180px] flex-1"><Search className="absolute right-3 top-3 text-slate-400" size={18}/><input value={q} onChange={e=>setQ(e.target.value)} className="input pr-10" placeholder="ابحث عن مادة أو حكم أو مبدأ…"/></div>
    {branchOpts.length>1&&<select value={fbranch} onChange={e=>setFbranch(e.target.value)} className="input w-auto min-w-[130px]"><option value="">كل الفروع</option>{branchOpts.map(b=><option key={b} value={b}>{b}</option>)}</select>}
    <button className="rounded-xl bg-brand-blue px-6 font-bold text-white transition hover:bg-brand-dark disabled:opacity-50" disabled={busy}>{busy?'يبحث…':'بحث'}</button>
    {(results||detail||q)&&<button type="button" onClick={clearAll} className="rounded-xl border border-slate-200 bg-white px-4 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">إلغاء</button>}
  </form>;
  const tabbar=<div className="flex flex-wrap gap-2">{TABS.map(x=><button key={x.k} onClick={()=>changeTab(x.k)} className={`rounded-xl px-4 py-2 text-sm font-bold transition ${tab===x.k?'bg-brand-blue text-white':'border border-slate-200 bg-white text-slate-600 hover:border-brand-blue dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300'}`}>{x.l}</button>)}</div>;
  const crumbs=path.length>0&&<div className="flex flex-wrap items-center gap-1.5 text-sm">
    <button onClick={()=>setPath([])} className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-slate-600 hover:border-brand-blue hover:text-brand-blue dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">الكل</button>
    {path.map((c,i)=><span key={i} className="flex items-center gap-1.5"><span className="text-slate-400">←</span><button onClick={()=>setPath(path.slice(0,i+1))} className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">{(tab==='laws'&&i===1)?lawTitle(c.key):c.key}</button></span>)}
  </div>;

  if(detail) return <div className="space-y-4">{bar}<button onClick={()=>setDetail(null)} className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:border-brand-blue hover:text-brand-blue dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">→ رجوع</button><DetailCard o={detail}/></div>;
  if(results) return <div className="space-y-4">{bar}
    {derr&&<p className="rounded-xl bg-rose-50 px-4 py-2 text-sm text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">{derr}</p>}
    <div className="flex items-center justify-between border-b border-slate-200 pb-2 dark:border-slate-700"><h2 className="text-lg font-bold text-ink dark:text-white">نتائج البحث</h2><span className="text-sm text-slate-500 dark:text-slate-400">{results.length?`تم العثور على ${results.length} نتيجة`:'لا نتائج'}</span></div>
    {results.length===0?<p className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">لا نتائج مطابقة — جرّب كلمات أخرى.</p>:
    <div className="space-y-4">{results.map((h:any,i:number)=>{const bt=srcBadge(h.object_type); const mad=h.metadata?.madhab||h.madhab; return (
    <button key={i} onClick={()=>openObj(h.object_id,h)} className="group flex w-full flex-col gap-3 rounded-xl border border-slate-100 bg-white p-5 text-right shadow-sm transition hover:border-brand-blue/50 hover:shadow-md dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-bold ${bt.cls}`}><bt.Icon size={13}/>{bt.label}</span>
          {h.branch&&<span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">{h.branch}</span>}
          {mad&&<span className="rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-600 dark:bg-amber-900/30 dark:text-amber-400">{mad}</span>}
        </div>
        {typeof h.score==='number'&&<span className="flex shrink-0 items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-600 dark:border-emerald-800/50 dark:bg-emerald-900/20 dark:text-emerald-400"><Target size={12}/>{(h.score*100).toFixed(0)}% مطابقة</span>}
      </div>
      {h.title&&<div className="text-lg font-bold text-ink transition group-hover:text-brand-blue dark:text-white">{h.title}</div>}
      <p className="line-clamp-2 text-sm leading-relaxed text-slate-600 dark:text-slate-300">{cleanTxt(h.text)}</p>
      <div className="flex items-center justify-between border-t border-slate-50 pt-3 dark:border-slate-800/60">
        <div className="flex items-center gap-2 text-xs text-slate-400">{[h.topic,h.subtopic].filter(Boolean).join(' · ')||h.object_id}</div>
        <span className="flex items-center gap-1 text-sm font-bold text-brand-blue opacity-0 transition group-hover:opacity-100">عرض التفاصيل <ArrowLeft size={14} className="rtl:rotate-180"/></span>
      </div>
    </button>);})}</div>}
  </div>;
  return <div className="space-y-4">{bar}{tabbar}{crumbs}
    {derr&&<p className="rounded-xl bg-rose-50 px-4 py-2 text-sm text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">{derr}</p>}
    {loading?<p className="text-sm text-slate-500 dark:text-slate-400">جارٍ التحميل…</p>:
     data.mode==='items'?
      <section className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <p className="mb-3 border-b border-slate-100 pb-3 text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">{data.items.length} عنصرًا — اضغط لعرض النص</p>
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {(tab==='laws'?[...data.items].sort((a:any,b:any)=>artNumOf(a.id)-artNumOf(b.id)):data.items).map((a:any)=><button key={a.id} onClick={()=>openObj(a.id)} className="flex w-full items-start justify-between gap-4 py-3 text-right transition hover:bg-slate-50 dark:hover:bg-slate-800/40">
            <div><div className="font-bold text-slate-800 dark:text-slate-200">{a.title||a.id}</div><div className="mt-0.5 text-xs text-slate-400">{[a.subtopic,a.micro_issue].filter(Boolean).join(' ← ')||''}</div></div>
            {tab==='laws'&&<span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">م{artNumOf(a.id)||'—'}</span>}
          </button>)}
        </div>
      </section>
     :<>
      <p className="text-sm text-slate-500 dark:text-slate-400">{data.groups.length} {data.level==='branch'?'فرعًا':data.level==='law'?'قانونًا':data.level==='part'?'ملفًا':'موضوعًا'} — اضغط للتصفّح.</p>
      {data.groups.length?<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.groups.map((g:any)=><button onClick={()=>setPath([...path,{level:data.level,key:g.key}])} key={g.key} className="rounded-2xl border border-slate-200 bg-white p-6 text-right transition hover:border-brand-blue hover:shadow-soft dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center justify-between"><BookOpen size={22} className="text-brand-blue"/><span className="rounded-full bg-brand-soft px-3 py-0.5 text-xs font-bold text-brand-dark dark:bg-brand-blue/15 dark:text-brand-blue">{g.count}</span></div>
          <div className="mt-3 font-bold leading-7">{gTitle(g.key,g.name)}</div>
          {g.branch&&<div className="mt-1 text-xs text-slate-400">{g.branch}</div>}
        </button>)}
      </div>:<Empty/>}
     </>}
  </div>;
}
function Empty(){return <div className="rounded-xl bg-slate-50 dark:bg-slate-800/50 p-8 text-center text-slate-500 dark:text-slate-400">لا توجد بيانات بعد.</div>}


function LoginScreen({onDone}:{onDone:()=>void}) {
  const [u,setU]=useState(''); const [p,setP]=useState('');
  const [err,setErr]=useState(''); const [busy,setBusy]=useState(false);
  const submit=async(e:React.FormEvent)=>{ e.preventDefault(); setBusy(true); setErr('');
    try{
      const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({username:u,password:p})});
      if(r.ok){ onDone(); } else { setErr('بيانات الدخول غير صحيحة'); }
    }catch{ setErr('تعذر الاتصال بالخادم'); } finally{ setBusy(false); } };
  return <div className="flex min-h-screen items-center justify-center bg-[#0f2137] p-6" dir="rtl">
    <form onSubmit={submit} className="w-full max-w-sm rounded-3xl border border-white/10 bg-white/5 p-8">
      <div className="mb-6 text-center">
        <img src="/brand-192.png" alt="صوت العدالة" className="mx-auto mb-3 h-14 w-14 rounded-2xl bg-white object-contain" />
        <h1 className="text-2xl font-bold text-white">صوت العدالة</h1>
        <p className="mt-1 text-sm text-slate-300">منظومة المعرفة القانونية — تسجيل الدخول</p>
      </div>
      <label className="mb-1 block text-sm text-slate-300">اسم المستخدم</label>
      <input value={u} onChange={e=>setU(e.target.value)} autoComplete="username"
        className="mb-4 w-full rounded-xl border border-white/15 bg-white/10 px-4 py-3 text-white outline-none focus:border-[#c9a227]" />
      <label className="mb-1 block text-sm text-slate-300">كلمة السر</label>
      <input type="password" value={p} onChange={e=>setP(e.target.value)} autoComplete="current-password"
        className="mb-5 w-full rounded-xl border border-white/15 bg-white/10 px-4 py-3 text-white outline-none focus:border-[#c9a227]" />
      {err?<p className="mb-4 rounded-xl bg-red-500/15 p-3 text-sm text-red-300">{err}</p>:null}
      <button disabled={busy||!u||!p}
        className="w-full rounded-xl bg-[#c9a227] py-3 font-bold text-[#0f2137] disabled:opacity-50">
        {busy?'جارٍ الدخول…':'دخول'}</button>
    </form>
  </div>;
}

// كشف بيئة تطبيق الجوال (Capacitor يحقن هذا الكائن تلقائيًا حتى مع محتوى بعيد عبر WebView)
const isNativeApp = () => typeof window !== 'undefined' && !!(window as any).Capacitor?.isNativePlatform?.();

export default function Home() {
  const [auth,setAuth]=useState<'checking'|'in'|'out'>('checking');
  const [isOffline,setIsOffline]=useState(false);
  useEffect(()=>{ fetch('/api/whoami').then(r=>setAuth(r.ok?'in':'out')).catch(()=>setAuth('out')); },[]);
  // شريط تنبيه انقطاع الاتصال أثناء الاستعمال (2026-08-31) — لا يعالج فشل التحميل الأول
  // (WebView لا يشغّل React أصلًا في تلك الحالة) بل حالة انقطاع الشبكة بعد تحميل التطبيق فعليًا.
  useEffect(()=>{const upd=()=>setIsOffline(!navigator.onLine);upd();window.addEventListener('online',upd);window.addEventListener('offline',upd);return()=>{window.removeEventListener('online',upd);window.removeEventListener('offline',upd);};},[]);
  const offlineBar = isOffline ? <div className="fixed inset-x-0 top-0 z-[100] bg-amber-500 py-2 text-center text-sm font-bold text-white" dir="rtl">لا يوجد اتصال بالإنترنت حاليًا — تحقّق من اتصالك، بعض الميزات قد لا تعمل.</div> : null;
  if(auth==='in') return <>{offlineBar}<HomeInner/></>;
  if(auth==='checking') return <>{offlineBar}<div className="flex min-h-screen items-center justify-center bg-[#0f2137] text-[#c9a227]">جارٍ التحقق…</div></>;
  return <>{offlineBar}<LoginScreen onDone={()=>setAuth('in')}/></>;
}
