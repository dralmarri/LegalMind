'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Activity, Archive, BookOpen, Boxes, BriefcaseBusiness, CheckCircle2,
  FileText, FolderTree, Gavel, LayoutDashboard, Network, PlusCircle,
  RefreshCw, Scale, Search, UploadCloud, XCircle
} from 'lucide-react';

type Stats = { objects: Record<string, number>; batches: Record<string, number>; inbox: number; archive: number; failed: number };
type Job = { batch_id: string; status: string; object_count: number; relationship_count: number; started_at: string; completed_at?: string };
type Topic = { branch: string; topic?: string; subtopic?: string; micro_issue?: string; object_count: number };
type DocumentRow = { id: string; object_type: string; branch: string; topic?: string; subtopic?: string; micro_issue?: string; title?: string; verification_status: string };

type View = 'dashboard' | 'upload' | 'knowledge' | 'jobs' | 'documents' | 'graph' | 'case';

const nav = [
  ['dashboard', 'لوحة المعلومات', LayoutDashboard],
  ['upload', 'رفع المصادر', UploadCloud],
  ['knowledge', 'شجرة المعرفة', FolderTree],
  ['documents', 'الكائنات القانونية', Boxes],
  ['jobs', 'دفعات المعالجة', Activity],
  ['graph', 'الرسم المعرفي', Network],
  ['case', 'ابدأ قضية جديدة', BriefcaseBusiness],
] as const;

async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

const fmt = (value?: string) => value ? new Date(value).toLocaleString('ar-KW') : '—';

export default function Home() {
  const [view, setView] = useState<View>('dashboard');
  const [stats, setStats] = useState<Stats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [uploadMessage, setUploadMessage] = useState('');

  async function refresh() {
    setLoading(true);
    try {
      const [s, j, t, d] = await Promise.all([
        api<Stats>('/api/stats'), api<Job[]>('/api/jobs?limit=100'), api<Topic[]>('/api/topics'), api<DocumentRow[]>('/api/documents?limit=500')
      ]);
      setStats(s); setJobs(j); setTopics(t); setDocuments(d);
    } finally { setLoading(false); }
  }

  useEffect(() => { refresh(); const id = setInterval(refresh, 30000); return () => clearInterval(id); }, []);

  const filteredDocuments = useMemo(() => documents.filter(d => !query || [d.id,d.title,d.branch,d.topic,d.subtopic,d.micro_issue,d.object_type].some(v => String(v || '').includes(query))), [documents, query]);
  const groupedTopics = useMemo(() => {
    const map = new Map<string, Topic[]>();
    topics.forEach(t => { const key = t.branch || 'غير مصنف'; map.set(key, [...(map.get(key) || []), t]); });
    return [...map.entries()];
  }, [topics]);

  async function submitUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setUploadMessage('جارٍ رفع الملفات...');
    try {
      const body = new FormData(event.currentTarget);
      const result = await api<{files: unknown[]}>('/api/upload', { method: 'POST', body });
      setUploadMessage(`تم إدراج ${result.files.length} ملف/ملفات في طابور المعالجة.`);
      event.currentTarget.reset(); setTimeout(refresh, 1800);
    } catch (error) { setUploadMessage(`تعذر الرفع: ${String(error)}`); }
  }

  const title = nav.find(n => n[0] === view)?.[1] || 'LegalMind';

  return (
    <div className="min-h-screen bg-mist text-ink">
      <aside className="fixed inset-y-0 right-0 z-20 w-72 border-l border-slate-800 bg-ink px-5 py-6 text-white">
        <div className="mb-9 flex items-center gap-3 px-2">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-gold text-ink"><Scale size={24}/></div>
          <div><div className="text-xl font-bold">LegalMind</div><div className="text-xs text-slate-400">منصة صوت العدالة</div></div>
        </div>
        <nav className="space-y-1.5">{nav.map(([id,label,Icon]) => (
          <button key={id} onClick={() => setView(id)} className={`flex w-full items-center gap-3 rounded-xl px-4 py-3 text-right transition ${view===id?'bg-white/10 text-white':'text-slate-300 hover:bg-white/5 hover:text-white'}`}>
            <Icon size={19}/><span>{label}</span>
          </button>
        ))}</nav>
        <div className="absolute bottom-6 left-5 right-5 rounded-2xl border border-white/10 bg-white/5 p-4 text-xs text-slate-300">
          <div className="mb-2 flex items-center gap-2 text-emerald-400"><CheckCircle2 size={15}/> النظام متصل</div>
          PostgreSQL وQdrant ومحرك الإدخال في وضع التشغيل.
        </div>
      </aside>

      <main className="mr-72 min-h-screen">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/90 px-10 py-5 backdrop-blur">
          <div><h1 className="text-2xl font-bold">{title}</h1><p className="mt-1 text-sm text-slate-500">إدارة المعرفة القانونية الكويتية من المصدر إلى الاستدلال</p></div>
          <div className="flex items-center gap-3">
            <div className="relative"><Search className="absolute right-3 top-2.5 text-slate-400" size={18}/><input value={query} onChange={e=>setQuery(e.target.value)} className="w-72 rounded-xl border border-slate-200 bg-slate-50 py-2.5 pr-10 pl-4 outline-none focus:border-gold" placeholder="ابحث في المعرفة..."/></div>
            <button onClick={refresh} className="rounded-xl border border-slate-200 bg-white p-2.5 hover:bg-slate-50"><RefreshCw size={18} className={loading?'animate-spin':''}/></button>
          </div>
        </header>

        <div className="p-10">
          {view === 'dashboard' && <Dashboard stats={stats} jobs={jobs} setView={setView}/>} 
          {view === 'upload' && <UploadPanel onSubmit={submitUpload} message={uploadMessage}/>} 
          {view === 'knowledge' && <KnowledgeTree groups={groupedTopics}/>} 
          {view === 'jobs' && <JobsTable jobs={jobs}/>} 
          {view === 'documents' && <DocumentsTable rows={filteredDocuments}/>} 
          {view === 'graph' && <GraphPlaceholder/>}
          {view === 'case' && <CaseWizard/>}
        </div>
      </main>
    </div>
  );
}

function Dashboard({stats,jobs,setView}:{stats:Stats|null;jobs:Job[];setView:(v:View)=>void}) {
  const cards = [
    ['التشريعات', stats?.objects.legislation||0, BookOpen], ['المبادئ القضائية', stats?.objects.judicial_principle||0, Gavel],
    ['الأحكام الكاملة', stats?.objects.full_judgment||0, FileText], ['النماذج والصيغ', stats?.objects.judicial_template||0, Archive],
    ['قيد المعالجة', stats?.inbox||0, Activity], ['تعذر معالجتها', stats?.failed||0, XCircle]
  ] as const;
  return <div className="space-y-8">
    <section className="rounded-3xl bg-gradient-to-l from-ink to-slate-800 p-8 text-white shadow-soft">
      <div className="flex items-center justify-between"><div><p className="mb-2 text-gold">LegalMind 3.0</p><h2 className="text-3xl font-bold">المعرفة القانونية، منظمة وقابلة للاستدلال</h2><p className="mt-3 max-w-2xl text-slate-300">ارفع الأحكام والمبادئ والنماذج بحسب تصنيف محكمة التمييز، ثم تابع تحويلها إلى شبكة قانونية مترابطة.</p></div><button onClick={()=>setView('upload')} className="flex items-center gap-2 rounded-2xl bg-gold px-5 py-3 font-bold text-ink"><UploadCloud size={19}/> رفع مصادر</button></div>
    </section>
    <section className="grid grid-cols-3 gap-5">{cards.map(([label,value,Icon])=><div key={label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center justify-between"><span className="text-sm text-slate-500">{label}</span><Icon size={20} className="text-gold"/></div><div className="mt-4 text-3xl font-bold">{value}</div></div>)}</section>
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><h3 className="mb-5 text-lg font-bold">آخر دفعات المعالجة</h3><JobsTable jobs={jobs.slice(0,8)}/></section>
  </div>
}

function UploadPanel({onSubmit,message}:{onSubmit:(e:React.FormEvent<HTMLFormElement>)=>void;message:string}) {
  return <form onSubmit={onSubmit} className="mx-auto max-w-5xl space-y-6 rounded-3xl border border-slate-200 bg-white p-8 shadow-soft">
    <div><h2 className="text-2xl font-bold">رفع المصادر القانونية</h2><p className="mt-2 text-slate-500">حافظ على عنوان مجلد محكمة التمييز كما هو؛ فهو مفتاح الاسترجاع الأساسي.</p></div>
    <div className="grid grid-cols-2 gap-5">
      <Field label="نوع المصدر"><select name="source_type" required className="input"><option value="judicial_principles_collection">مجموعة مبادئ قضائية مختصرة</option><option value="single_judicial_principle">مبدأ قضائي منفرد</option><option value="full_judgment">حكم كامل</option><option value="legislation">تشريع</option><option value="judicial_template">صيغة أو صحيفة قضائية</option><option value="legal_memorandum">مذكرة دفاع</option></select></Field>
      <Field label="الفرع"><select name="branch" required className="input"><option>أحوال شخصية</option><option>مدني</option><option>تجاري</option><option>عمالي</option><option>جزائي</option><option>إداري</option><option>دستوري</option><option>مرافعات</option><option>إثبات</option><option>تنفيذ</option></select></Field>
      <Field label="الموضوع"><input className="input" name="topic" placeholder="مثال: الحضانة" required/></Field>
      <Field label="عنوان تصنيف محكمة التمييز"><input className="input" name="classification_title" placeholder="مثال: سقوط الحضانة" required/></Field>
      <Field label="المسألة الدقيقة"><input className="input" name="micro_issue" placeholder="مثال: زواج الحاضنة"/></Field>
      <Field label="الدائرة"><input className="input" name="circuit" placeholder="أحوال شخصية / مدني / تجاري"/></Field>
      <Field label="درجة المحكمة"><input className="input" name="court_level" placeholder="أول درجة / استئناف / تمييز"/></Field>
    </div>
    <label className="flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 p-8 text-center hover:border-gold"><UploadCloud size={38} className="mb-3 text-gold"/><span className="font-bold">اسحب الملفات هنا أو اضغط للاختيار</span><span className="mt-2 text-sm text-slate-500">DOCX وTXT وMarkdown — حتى 100 ميغابايت للملف</span><input type="file" name="files" multiple accept=".docx,.txt,.md" required className="hidden"/></label>
    <button className="flex w-full items-center justify-center gap-2 rounded-xl bg-ink px-5 py-3.5 font-bold text-white hover:bg-slate-800"><UploadCloud size={19}/> رفع وبدء المعالجة</button>
    {message && <p className="rounded-xl bg-slate-100 p-4 text-sm">{message}</p>}
  </form>
}

function Field({label,children}:{label:string;children:React.ReactNode}) { return <label className="space-y-2"><span className="text-sm font-bold text-slate-700">{label}</span>{children}</label> }

function KnowledgeTree({groups}:{groups:[string,Topic[]][]}) { return <div className="space-y-5">{groups.length===0?<Empty/>:groups.map(([branch,items])=><section key={branch} className="rounded-2xl border border-slate-200 bg-white p-6"><h3 className="mb-4 flex items-center gap-2 text-lg font-bold"><FolderTree className="text-gold" size={20}/>{branch}</h3><div className="grid grid-cols-2 gap-3">{items.map((t,i)=><div key={i} className="rounded-xl border border-slate-100 bg-slate-50 p-4"><div className="font-bold">{t.topic||'غير محدد'}</div><div className="mt-1 text-sm text-slate-500">{t.subtopic||'بلا عنوان فرعي'}{t.micro_issue?` ← ${t.micro_issue}`:''}</div><div className="mt-3 text-xs text-gold">{t.object_count} كائن</div></div>)}</div></section>)}</div> }

function JobsTable({jobs}:{jobs:Job[]}) { return jobs.length===0?<Empty/>:<div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-right text-slate-500"><th className="p-3">الدفعة</th><th>الحالة</th><th>العناصر</th><th>العلاقات</th><th>بدأت</th><th>اكتملت</th></tr></thead><tbody>{jobs.map(j=><tr key={j.batch_id} className="border-b border-slate-100"><td className="p-3 font-mono text-xs">{j.batch_id}</td><td><span className={`rounded-full px-2.5 py-1 text-xs ${j.status==='completed'?'bg-emerald-50 text-emerald-700':'bg-amber-50 text-amber-700'}`}>{j.status}</span></td><td>{j.object_count}</td><td>{j.relationship_count}</td><td>{fmt(j.started_at)}</td><td>{fmt(j.completed_at)}</td></tr>)}</tbody></table></div> }

function DocumentsTable({rows}:{rows:DocumentRow[]}) { return <section className="rounded-2xl border border-slate-200 bg-white p-6">{rows.length===0?<Empty/>:<div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-right text-slate-500"><th className="p-3">المعرف</th><th>النوع</th><th>الفرع</th><th>الموضوع</th><th>العنوان</th><th>المسألة</th><th>الحالة</th></tr></thead><tbody>{rows.map(r=><tr key={r.id} className="border-b border-slate-100"><td className="p-3 font-mono text-xs">{r.id}</td><td>{r.object_type}</td><td>{r.branch}</td><td>{r.topic||'—'}</td><td>{r.subtopic||'—'}</td><td>{r.micro_issue||'—'}</td><td>{r.verification_status}</td></tr>)}</tbody></table></div>}</section> }

function GraphPlaceholder(){return <div className="grid min-h-[560px] place-items-center rounded-3xl border border-slate-200 bg-white p-10 text-center shadow-sm"><div><div className="mx-auto grid h-20 w-20 place-items-center rounded-3xl bg-gold/15 text-gold"><Network size={38}/></div><h2 className="mt-5 text-2xl font-bold">Knowledge Graph</h2><p className="mx-auto mt-3 max-w-xl text-slate-500">ستظهر هنا العلاقات بين المواد والأحكام والمبادئ والنماذج. الصفحة جاهزة للربط بمحرك العلاقات بعد إدخال أول مجموعة أحكام كاملة.</p></div></div>}

function CaseWizard(){return <div className="mx-auto max-w-4xl rounded-3xl border border-slate-200 bg-white p-8 shadow-soft"><div className="mb-7 flex items-center gap-3"><div className="grid h-12 w-12 place-items-center rounded-2xl bg-gold/15 text-gold"><PlusCircle/></div><div><h2 className="text-2xl font-bold">ابدأ قضية جديدة</h2><p className="text-slate-500">مسار منظم لجمع الوقائع والطلبات والمستندات قبل الصياغة.</p></div></div><div className="grid grid-cols-2 gap-5"><Field label="الفرع"><select className="input"><option>أحوال شخصية</option></select></Field><Field label="نوع القضية"><input className="input" placeholder="حضانة، نفقة، نسب..."/></Field><Field label="صفة الموكل"><input className="input" placeholder="مدعٍ / مدعى عليه / مستأنف"/></Field><Field label="المحكمة"><input className="input" placeholder="محكمة الأسرة..."/></Field></div><Field label="الوقائع"><textarea className="input mt-2 min-h-36" placeholder="اكتب الوقائع دون إضافة استنتاجات قانونية..."/></Field><button disabled className="mt-6 w-full rounded-xl bg-slate-200 px-5 py-3.5 font-bold text-slate-500">الصياغة ستُفعّل بعد إدخال الأحكام والنماذج الكافية</button></div>}

function Empty(){return <div className="py-12 text-center text-slate-400">لا توجد بيانات بعد.</div>}
