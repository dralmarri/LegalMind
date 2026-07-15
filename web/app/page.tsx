'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Activity, Archive, BookOpen, Boxes, BriefcaseBusiness, CheckCircle2, ClipboardCheck,
  FileSearch, FileText, FolderTree, Gavel, LayoutDashboard, Network, PenLine, Plus,
  RefreshCw, Scale, Search, UploadCloud, XCircle
} from 'lucide-react';

type Stats = { objects: Record<string, number>; batches: Record<string, number>; inbox: number; archive: number; failed: number };
type Job = { batch_id: string; status: string; object_count: number; relationship_count: number; started_at: string; completed_at?: string };
type Topic = { branch: string; topic?: string; subtopic?: string; micro_issue?: string; object_count: number };
type DocumentRow = { id: string; object_type: string; branch: string; topic?: string; subtopic?: string; micro_issue?: string; title?: string; verification_status: string };
type LegalCase = { id: string; case_key: string; title: string; branch: string; topic?: string; subtopic?: string; client_name?: string; client_capacity?: string; opponent_name?: string; court_name?: string; court_level?: string; status: string; facts?: string; requests?: string; notes?: string; updated_at: string; authorities?: unknown[]; drafts?: unknown[] };
type Coverage = { counts: Record<string, number>; drafting_ready: boolean; drafting_status: string; missing: string[]; note: string };
type View = 'dashboard' | 'cases' | 'workspace' | 'research' | 'drafting' | 'review' | 'upload' | 'knowledge' | 'documents' | 'jobs' | 'graph';
type UploadMethod = 'file' | 'paste';
type DuplicateOf = { first_batch_id: string; object_count: number; ingested_at?: string; title?: string };
type FileStatus = { file_id: string; status: string; batch_id?: string; object_count?: number; duplicate_of?: DuplicateOf; error?: string };

const nav = [
  ['dashboard', 'الرئيسية', LayoutDashboard],
  ['cases', 'القضايا', BriefcaseBusiness],
  ['research', 'البحث القانوني', FileSearch],
  ['drafting', 'استوديو الصياغة', PenLine],
  ['review', 'مراجعة الأسانيد', ClipboardCheck],
  ['knowledge', 'شجرة المعرفة', FolderTree],
  ['graph', 'الرسم المعرفي', Network],
  ['documents', 'المصادر والكائنات', Boxes],
  ['upload', 'رفع المصادر', UploadCloud],
  ['jobs', 'دفعات المعالجة', Activity],
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
const fmt = (value?: string) => value ? new Date(value).toLocaleString('ar-KW') : '—';
const typeLabel: Record<string,string> = {
  legislation:'تشريع', judicial_principle:'مبدأ قضائي', full_judgment:'حكم كامل',
  judicial_template:'صيغة قضائية', legal_memorandum:'مذكرة دفاع', legal_document:'مستند قانوني'
};

export default function Home() {
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

  async function refresh() {
    setLoading(true);
    try {
      const [s,j,t,d,c] = await Promise.all([
        api<Stats>('/api/stats'), api<Job[]>('/api/jobs?limit=100'), api<Topic[]>('/api/topics'),
        api<DocumentRow[]>('/api/documents?limit=1000'), api<LegalCase[]>('/api/cases')
      ]);
      setStats(s); setJobs(j); setTopics(t); setDocuments(d); setCases(c);
    } finally { setLoading(false); }
  }
  useEffect(() => { refresh(); const id=setInterval(refresh,30000); return()=>clearInterval(id); }, []);

  const filteredDocuments = useMemo(() => documents.filter(d => !query || [d.id,d.title,d.branch,d.topic,d.subtopic,d.micro_issue,d.object_type].some(v=>String(v||'').includes(query))), [documents,query]);
  const groupedTopics = useMemo(() => {
    const map=new Map<string,Topic[]>(); topics.forEach(t=>{const k=t.branch||'غير مصنف';map.set(k,[...(map.get(k)||[]),t]);}); return [...map.entries()];
  },[topics]);

  async function openCase(item: LegalCase) {
    const full=await api<LegalCase>(`/api/cases/${item.id}`);
    const cov=await api<Coverage>(`/api/cases/${item.id}/coverage`);
    setSelectedCase(full); setCoverage(cov); setView('workspace');
  }
  async function submitCase(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form=new FormData(event.currentTarget); const payload=Object.fromEntries(form.entries());
    const created=await api<LegalCase>('/api/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    event.currentTarget.reset(); await refresh(); await openCase(created);
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

  const title = view==='workspace' ? selectedCase?.title || 'مساحة القضية' : nav.find(n=>n[0]===view)?.[1] || 'LegalMind';
  return <div className="min-h-screen bg-slate-50 text-slate-950">
    <aside className="fixed inset-y-0 right-0 z-20 w-72 border-l border-slate-800 bg-slate-950 px-5 py-6 text-white">
      <div className="mb-8 flex items-center gap-3 px-2"><div className="grid h-11 w-11 place-items-center rounded-2xl bg-amber-400 text-slate-950"><Scale size={24}/></div><div><div className="text-xl font-bold">LegalMind</div><div className="text-xs text-slate-400">Legal Operating System</div></div></div>
      <nav className="space-y-1">{nav.map(([id,label,Icon])=><button key={id} onClick={()=>setView(id)} className={`flex w-full items-center gap-3 rounded-xl px-4 py-3 text-right ${view===id?'bg-white/10':'text-slate-300 hover:bg-white/5'}`}><Icon size={18}/>{label}</button>)}</nav>
      <div className="absolute bottom-5 left-5 right-5 rounded-2xl border border-white/10 bg-white/5 p-4 text-xs text-slate-300"><div className="mb-2 flex items-center gap-2 text-emerald-400"><CheckCircle2 size={15}/> النظام متصل</div>القضايا والمعرفة ومحرك الإدخال في وضع التشغيل.</div>
    </aside>
    <main className="mr-72 min-h-screen">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/90 px-10 py-5 backdrop-blur"><div><h1 className="text-2xl font-bold">{title}</h1><p className="mt-1 text-sm text-slate-500">من المعرفة القانونية إلى إدارة القضية والصياغة والمراجعة</p></div><div className="flex items-center gap-3"><div className="relative"><Search className="absolute right-3 top-2.5 text-slate-400" size={18}/><input value={query} onChange={e=>setQuery(e.target.value)} className="w-72 rounded-xl border border-slate-200 bg-slate-50 py-2.5 pr-10 pl-4 outline-none focus:border-amber-400" placeholder="ابحث في المعرفة..."/></div><button onClick={refresh} className="rounded-xl border border-slate-200 bg-white p-2.5"><RefreshCw size={18} className={loading?'animate-spin':''}/></button></div></header>
      <div className="p-10">
        {view==='dashboard'&&<Dashboard stats={stats} jobs={jobs} cases={cases} setView={setView}/>} 
        {view==='cases'&&<CasesView cases={cases} onOpen={openCase} onCreate={submitCase}/>} 
        {view==='workspace'&&selectedCase&&<CaseWorkspace item={selectedCase} coverage={coverage} onSave={saveCase} setView={setView}/>} 
        {view==='research'&&<ResearchView rows={filteredDocuments} query={query}/>} 
        {view==='drafting'&&<DraftingView cases={cases} onOpen={openCase}/>} 
        {view==='review'&&<ReviewView cases={cases} onOpen={openCase}/>} 
        {view==='upload'&&<UploadPanel onSubmit={submitSource} message={uploadMessage} error={uploadError}
          method={uploadMethod} setMethod={m=>{setUploadMethod(m);setUploadMessage('');setUploadError('');setProcessing([]);}}
          processing={processing} busy={uploading}/>}
        {view==='knowledge'&&<KnowledgeTree groups={groupedTopics}/>} 
        {view==='documents'&&<DocumentsTable rows={filteredDocuments}/>} 
        {view==='jobs'&&<JobsTable jobs={jobs}/>} 
        {view==='graph'&&<GraphView topics={topics}/>} 
      </div>
    </main>
  </div>
}

function Dashboard({stats,jobs,cases,setView}:{stats:Stats|null;jobs:Job[];cases:LegalCase[];setView:(v:View)=>void}) {
  const cards=[['القضايا',cases.length,BriefcaseBusiness],['التشريعات',stats?.objects.legislation||0,BookOpen],['المبادئ',stats?.objects.judicial_principle||0,Gavel],['الأحكام',stats?.objects.full_judgment||0,FileText],['النماذج',stats?.objects.judicial_template||0,Archive],['قيد المعالجة',stats?.inbox||0,Activity]] as const;
  return <div className="space-y-8"><section className="rounded-3xl bg-gradient-to-l from-slate-950 to-slate-800 p-8 text-white"><p className="mb-2 text-amber-400">LegalMind 4.0</p><div className="flex items-end justify-between"><div><h2 className="text-3xl font-bold">نظام تشغيل قانوني للمحامي الكويتي</h2><p className="mt-3 max-w-3xl text-slate-300">أنشئ القضية، نظّم وقائعها وطلباتك، اربطها بالمصادر، ثم راجع جاهزية الصياغة قبل إنتاج المسودة.</p></div><button onClick={()=>setView('cases')} className="flex items-center gap-2 rounded-2xl bg-amber-400 px-5 py-3 font-bold text-slate-950"><Plus size={19}/> قضية جديدة</button></div></section><section className="grid grid-cols-3 gap-5">{cards.map(([l,v,I])=><div key={l} className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex justify-between text-sm text-slate-500"><span>{l}</span><I size={20} className="text-amber-500"/></div><div className="mt-4 text-3xl font-bold">{v}</div></div>)}</section><section className="grid grid-cols-2 gap-6"><div className="rounded-2xl border bg-white p-6"><h3 className="mb-4 text-lg font-bold">آخر القضايا</h3>{cases.length?cases.slice(0,6).map(c=><div key={c.id} className="flex justify-between border-b py-3 text-sm"><span>{c.title}</span><span className="text-slate-500">{c.status}</span></div>):<Empty/>}</div><div className="rounded-2xl border bg-white p-6"><h3 className="mb-4 text-lg font-bold">آخر دفعات المعرفة</h3><JobsTable jobs={jobs.slice(0,6)}/></div></section></div>
}

function CasesView({cases,onOpen,onCreate}:{cases:LegalCase[];onOpen:(c:LegalCase)=>void;onCreate:(e:React.FormEvent<HTMLFormElement>)=>void}) {
  return <div className="grid grid-cols-[1fr_420px] gap-7"><section className="rounded-2xl border bg-white p-6"><h2 className="mb-5 text-xl font-bold">ملفات القضايا</h2>{cases.length?<div className="space-y-3">{cases.map(c=><button onClick={()=>onOpen(c)} key={c.id} className="w-full rounded-2xl border p-5 text-right hover:border-amber-400"><div className="flex justify-between"><div><div className="font-bold">{c.title}</div><div className="mt-1 text-sm text-slate-500">{c.case_key} · {c.branch} · {c.topic||'دون موضوع'}</div></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs">{c.status}</span></div></button>)}</div>:<Empty/>}</section><form onSubmit={onCreate} className="space-y-4 rounded-2xl border bg-white p-6"><div><h2 className="text-xl font-bold">إنشاء قضية جديدة</h2><p className="mt-1 text-sm text-slate-500">يُنشأ ملف مستقل محفوظ في قاعدة البيانات.</p></div><input className="input" name="title" placeholder="عنوان القضية" required/><select className="input" name="branch" required><option>أحوال شخصية</option><option>مدني</option><option>تجاري</option><option>عمالي</option><option>جزائي</option><option>إداري</option></select><input className="input" name="topic" placeholder="الموضوع: حضانة / نفقة / تعويض"/><input className="input" name="subtopic" placeholder="المسألة الدقيقة"/><div className="grid grid-cols-2 gap-3"><input className="input" name="client_name" placeholder="اسم الموكل"/><input className="input" name="client_capacity" placeholder="صفته"/></div><input className="input" name="opponent_name" placeholder="الخصم"/><div className="grid grid-cols-2 gap-3"><input className="input" name="court_name" placeholder="المحكمة"/><input className="input" name="court_level" placeholder="درجة التقاضي"/></div><textarea className="input min-h-28" name="facts" placeholder="ملخص الوقائع"/><textarea className="input min-h-24" name="requests" placeholder="طلبات الموكل"/><button className="w-full rounded-xl bg-slate-950 py-3 font-bold text-white">إنشاء مساحة القضية</button></form></div>
}

function CaseWorkspace({item,coverage,onSave,setView}:{item:LegalCase;coverage:Coverage|null;onSave:(e:React.FormEvent<HTMLFormElement>)=>void;setView:(v:View)=>void}) {
  return <div className="space-y-6"><section className="rounded-3xl bg-slate-950 p-7 text-white"><div className="flex justify-between"><div><div className="text-sm text-amber-400">{item.case_key}</div><h2 className="mt-2 text-2xl font-bold">{item.title}</h2><p className="mt-2 text-slate-300">{item.branch} · {item.topic||'غير محدد'} · {item.subtopic||'غير محدد'}</p></div><div className="text-left"><div className={`rounded-full px-4 py-2 text-sm ${coverage?.drafting_ready?'bg-emerald-500/20 text-emerald-300':'bg-amber-500/20 text-amber-300'}`}>{coverage?.drafting_ready?'جاهزة لمسودة مسندة':'الصياغة مقيدة بنقص المصادر'}</div></div></div></section><div className="grid grid-cols-[1fr_360px] gap-6"><form onSubmit={onSave} className="space-y-5 rounded-2xl border bg-white p-6"><h3 className="text-lg font-bold">ملف القضية</h3><div className="grid grid-cols-2 gap-4"><input className="input" name="title" defaultValue={item.title}/><input className="input" name="status" defaultValue={item.status}/><input className="input" name="topic" defaultValue={item.topic}/><input className="input" name="subtopic" defaultValue={item.subtopic}/><input className="input" name="client_name" defaultValue={item.client_name} placeholder="الموكل"/><input className="input" name="client_capacity" defaultValue={item.client_capacity} placeholder="الصفة"/><input className="input" name="opponent_name" defaultValue={item.opponent_name} placeholder="الخصم"/><input className="input" name="court_name" defaultValue={item.court_name} placeholder="المحكمة"/></div><label className="block"><span className="mb-2 block font-bold">الوقائع</span><textarea className="input min-h-44" name="facts" defaultValue={item.facts}/></label><label className="block"><span className="mb-2 block font-bold">الطلبات</span><textarea className="input min-h-32" name="requests" defaultValue={item.requests}/></label><label className="block"><span className="mb-2 block font-bold">ملاحظات العمل</span><textarea className="input min-h-24" name="notes" defaultValue={item.notes}/></label><button className="rounded-xl bg-slate-950 px-6 py-3 font-bold text-white">حفظ التعديلات</button></form><aside className="space-y-5"><div className="rounded-2xl border bg-white p-5"><h3 className="font-bold">تغطية المعرفة</h3><div className="mt-4 space-y-3">{Object.entries(coverage?.counts||{}).map(([k,v])=><div key={k} className="flex justify-between text-sm"><span>{typeLabel[k]||k}</span><strong>{v}</strong></div>)}</div>{coverage?.missing?.length?<div className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">ناقص: {coverage.missing.join('، ')}</div>:null}</div><button onClick={()=>setView('research')} className="w-full rounded-xl border bg-white py-3 font-bold">بحث مرتبط بالقضية</button><button onClick={()=>setView('drafting')} className="w-full rounded-xl bg-amber-400 py-3 font-bold text-slate-950">فتح استوديو الصياغة</button><div className="rounded-2xl border bg-white p-5 text-sm text-slate-600">{coverage?.note||'يجري حساب التغطية...'}</div></aside></div></div>
}

function ResearchView({rows,query}:{rows:DocumentRow[];query:string}) { return <div className="space-y-5"><div className="rounded-2xl border bg-white p-6"><h2 className="text-xl font-bold">البحث القانوني</h2><p className="mt-2 text-slate-500">استخدم مربع البحث العلوي للبحث في المعرف والعنوان والفرع والموضوع والمسألة الدقيقة.</p></div><DocumentsTable rows={rows.slice(0,300)}/>{!query&&<p className="text-center text-sm text-slate-500">أدخل عبارة بحث لخفض النتائج.</p>}</div> }
function DraftingView({cases,onOpen}:{cases:LegalCase[];onOpen:(c:LegalCase)=>void}) { return <div className="rounded-2xl border bg-white p-7"><h2 className="text-2xl font-bold">استوديو الصياغة</h2><p className="mt-2 text-slate-500">اختر قضية لفتح ملفها وفحص جاهزية مصادرها قبل إنشاء صحيفة أو مذكرة.</p><div className="mt-6 grid grid-cols-2 gap-4">{cases.map(c=><button key={c.id} onClick={()=>onOpen(c)} className="rounded-2xl border p-5 text-right hover:border-amber-400"><div className="font-bold">{c.title}</div><div className="mt-2 text-sm text-slate-500">{c.branch} · {c.topic||'—'}</div></button>)}</div></div> }
function ReviewView({cases,onOpen}:{cases:LegalCase[];onOpen:(c:LegalCase)=>void}) { return <div className="rounded-2xl border bg-white p-7"><h2 className="text-2xl font-bold">مراجعة الأسانيد</h2><p className="mt-2 text-slate-500">تعرض هذه المرحلة مدى وجود التشريع والمبدأ والنموذج لكل قضية. افتح القضية لعرض تقرير التغطية.</p><div className="mt-6 space-y-3">{cases.map(c=><button key={c.id} onClick={()=>onOpen(c)} className="flex w-full justify-between rounded-xl border p-4"><span>{c.title}</span><span className="text-slate-500">فتح التقرير</span></button>)}</div></div> }

const statusLabel: Record<string,string> = {
  queued:'في طابور المعالجة', started:'قيد المعالجة', completed:'اكتملت المعالجة',
  failed:'فشلت المعالجة', duplicate:'مكرر — لم تُنشأ نسخة', unknown:'غير معروفة'
};

function ProcessingStatus({items}:{items:FileStatus[]}) {
  if (!items.length) return null;
  return <div className="space-y-3 rounded-2xl border bg-slate-50 p-5">
    <h3 className="font-bold">حالة المعالجة</h3>
    {items.map(s => {
      const tone = s.status==='completed' ? 'border-emerald-300 bg-emerald-50 text-emerald-900'
        : s.status==='failed' ? 'border-red-300 bg-red-50 text-red-900'
        : s.status==='duplicate' ? 'border-amber-300 bg-amber-50 text-amber-900'
        : 'border-slate-200 bg-white text-slate-700';
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
        {(s.status==='queued'||s.status==='started') && <p className="mt-2 text-slate-500">جارٍ التطبيع والاستخراج والفهرسة...</p>}
      </div>;
    })}
  </div>;
}

function UploadPanel({onSubmit,message,error,method,setMethod,processing,busy}:{
  onSubmit:(e:React.FormEvent<HTMLFormElement>)=>void; message:string; error:string;
  method:UploadMethod; setMethod:(m:UploadMethod)=>void; processing:FileStatus[]; busy:boolean;
}) {
  const tab = (id:UploadMethod, label:string) =>
    <button key={id} type="button" onClick={()=>setMethod(id)}
      className={`rounded-xl px-6 py-3 font-bold ${method===id?'bg-slate-950 text-white':'border bg-white text-slate-600 hover:border-amber-400'}`}>{label}</button>;

  return <form onSubmit={onSubmit} className="mx-auto max-w-5xl space-y-6 rounded-3xl border bg-white p-8">
    <div>
      <h2 className="text-2xl font-bold">إضافة مصدر قانوني</h2>
      <p className="mt-2 text-slate-500">اختر طريقة واحدة: رفع ملف أو لصق نص. عنوان تصنيف محكمة التمييز هو مفتاح الاسترجاع الأساسي.</p>
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
      <Field label="الموضوع"><input className="input" name="topic" required placeholder="مثال: الحضانة"/></Field>
      <Field label="عنوان تصنيف محكمة التمييز"><input className="input" name="classification_title" placeholder="مثال: سقوط الحضانة"/></Field>
      <Field label="المسألة الدقيقة (اختياري)"><input className="input" name="micro_issue" placeholder="مثال: زواج الحاضنة"/></Field>
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
      ? <label className="flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed bg-slate-50 p-8">
          <UploadCloud size={38} className="mb-3 text-amber-500"/>
          <span className="font-bold">اسحب الملفات هنا أو اضغط للاختيار</span>
          <span className="mt-2 text-sm text-slate-500">DOCX · PDF نصي · HTML · TXT · Markdown</span>
          <span className="mt-1 text-xs text-slate-400">الـPDF الممسوح ضوئيًا (بلا طبقة نصية) يُرفض ولا يُنشئ سجلًا</span>
          <input type="file" name="files" multiple accept=".docx,.pdf,.html,.htm,.txt,.md" className="hidden"/>
        </label>
      : <Field label="نص المصدر القانوني">
          <textarea name="content" dir="rtl" rows={16} minLength={20}
            className="input min-h-80 leading-loose"
            placeholder="الصق هنا نص الحكم أو المبدأ أو مواد التشريع كما هي حرفيًا، بلا تحرير ولا تلخيص..."/>
          <span className="text-xs text-slate-500">الحد الأدنى 20 حرفًا، والأقصى 500,000 حرف. يُحفظ النص كما لُصق حرفيًا.</span>
        </Field>}

    <button disabled={busy} className="w-full rounded-xl bg-slate-950 py-3.5 font-bold text-white disabled:opacity-50">
      {busy ? 'جارٍ الحفظ...' : 'حفظ وبدء المعالجة'}
    </button>

    {message && <p className="rounded-xl bg-slate-100 p-4 text-sm">{message}</p>}
    {error && <p className="flex items-center gap-2 rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-900"><XCircle size={16}/>{error}</p>}
    <ProcessingStatus items={processing}/>
  </form>;
}
function Field({label,children}:{label:string;children:React.ReactNode}) { return <label className="space-y-2"><span className="text-sm font-bold">{label}</span>{children}</label> }
function KnowledgeTree({groups}:{groups:[string,Topic[]][]}) { return <div className="space-y-5">{groups.length===0?<Empty/>:groups.map(([branch,items])=><section key={branch} className="rounded-2xl border bg-white p-6"><h3 className="mb-4 text-lg font-bold">{branch}</h3><div className="grid grid-cols-2 gap-3">{items.map((t,i)=><div key={i} className="rounded-xl bg-slate-50 p-4"><div className="font-bold">{t.topic||'غير مصنف'}</div><div className="mt-1 text-sm text-slate-600">{t.subtopic||'—'} {t.micro_issue?`← ${t.micro_issue}`:''}</div><div className="mt-2 text-xs text-amber-700">{t.object_count} عنصر</div></div>)}</div></section>)}</div> }
function DocumentsTable({rows}:{rows:DocumentRow[]}) { return rows.length?<div className="overflow-auto rounded-2xl border bg-white"><table className="w-full text-sm"><thead className="bg-slate-50"><tr>{['المعرف','النوع','الفرع','الموضوع','العنوان','المسألة','الحالة'].map(x=><th key={x} className="p-3 text-right">{x}</th>)}</tr></thead><tbody>{rows.map(r=><tr key={r.id} className="border-t"><td className="p-3 font-mono text-xs">{r.id}</td><td className="p-3">{typeLabel[r.object_type]||r.object_type}</td><td className="p-3">{r.branch}</td><td className="p-3">{r.topic||'—'}</td><td className="p-3">{r.subtopic||'—'}</td><td className="p-3">{r.micro_issue||'—'}</td><td className="p-3">{r.verification_status}</td></tr>)}</tbody></table></div>:<Empty/> }
function JobsTable({jobs}:{jobs:Job[]}) { return jobs.length?<div className="overflow-auto"><table className="w-full text-sm"><thead><tr>{['الدفعة','الحالة','العناصر','العلاقات','بدأت','اكتملت'].map(x=><th key={x} className="p-3 text-right">{x}</th>)}</tr></thead><tbody>{jobs.map(j=><tr key={j.batch_id} className="border-t"><td className="p-3 font-mono text-xs">{j.batch_id}</td><td className="p-3">{j.status}</td><td className="p-3">{j.object_count}</td><td className="p-3">{j.relationship_count}</td><td className="p-3">{fmt(j.started_at)}</td><td className="p-3">{fmt(j.completed_at)}</td></tr>)}</tbody></table></div>:<Empty/> }
function GraphView({topics}:{topics:Topic[]}) { const sample=topics.slice(0,8); return <div className="rounded-3xl border bg-white p-8"><h2 className="text-2xl font-bold">الرسم المعرفي</h2><p className="mt-2 text-slate-500">تمهيد بصري للعلاقات. ستظهر الروابط الفعلية بعد إدخال الأحكام والمبادئ والنماذج وربطها.</p><div className="mt-10 flex flex-wrap items-center justify-center gap-6">{sample.map((t,i)=><div key={i} className="grid h-36 w-36 place-items-center rounded-full border-4 border-amber-300 bg-amber-50 p-4 text-center text-sm font-bold">{t.topic||t.branch}<small className="block font-normal text-slate-500">{t.object_count} عنصر</small></div>)}</div></div> }
function Empty(){return <div className="rounded-xl bg-slate-50 p-8 text-center text-slate-500">لا توجد بيانات بعد.</div>}
