

# ==================== محرّر المواد والمبادئ داخل النظام — /edit ====================
from fastapi import Request as _EditRequest

_EDIT_FIELDS = ("branch", "topic", "subtopic", "micro_issue", "title")

def _edit_normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").replace("ـ", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


@app.put("/api/object/{object_id}")
async def update_object(object_id: str, request: _EditRequest,
                        _: str = Depends(require_auth)) -> dict:
    """تعديل نصّ مادة/مبدأ (وحقول التصنيف اختياريًا). لا يعيد الفهرسة تلقائيًّا."""
    body = await request.json()
    text = (body.get("text") or "").strip()
    if len(text) < 2:
        raise HTTPException(400, "النص فارغ أو قصير جدًّا")
    dsn = _draft_env("DATABASE_URL") or DATABASE_URL
    sets = ["original_text=%s", "normalized_text=%s",
            "verification_status=%s", "updated_at=now()"]
    vstatus = body.get("verification_status") or "source_verified"
    if vstatus not in VERIFICATION_STATUSES:
        vstatus = "source_verified"
    vals = [text, _edit_normalize(text), vstatus]
    for f in _EDIT_FIELDS:
        if f in body:
            v = body.get(f)
            v = (str(v).strip() or None) if v is not None else None
            sets.append(f + "=%s"); vals.append(v)
    vals.append(object_id)
    with psycopg.connect(dsn) as _c, _c.cursor() as _cur:
        _cur.execute("SELECT 1 FROM knowledge_objects WHERE id=%s", (object_id,))
        if not _cur.fetchone():
            raise HTTPException(404, "المصدر غير موجود")
        _cur.execute("UPDATE knowledge_objects SET " + ",".join(sets) + " WHERE id=%s",
                     tuple(vals))
        _c.commit()
    return {"ok": True, "id": object_id,
            "note": "حُفِظ في قاعدة البيانات. اضغط «إعادة الفهرسة» ليظهر التعديل في البحث."}


@app.post("/api/reindex")
def reindex_now(_: str = Depends(require_auth)) -> dict:
    """إعادة فهرسة كاملة عند الطلب (بضع ثوانٍ) لتحديث متجهات البحث بعد التعديل."""
    env = dict(os.environ)
    envf = Path("/opt/LegalMind/deploy/.env")
    if envf.exists():
        for line in envf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env["HF_HUB_OFFLINE"] = "1"; env["TRANSFORMERS_OFFLINE"] = "1"
    try:
        proc = subprocess.run([ENGINE_PY, "-m", "engine.legalmind_engine", "reindex"],
                              cwd="/opt/LegalMind", env=env,
                              capture_output=True, text=True, timeout=600)
    except Exception as exc:
        raise HTTPException(500, f"تعذّرت إعادة الفهرسة: {exc}")
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        raise HTTPException(500, f"فشلت إعادة الفهرسة: {out[-400:]}")
    m = re.search(r'\{[^{}]*"consistent"[^{}]*\}', out, re.S)
    return {"ok": True, "reindex": (json.loads(m.group(0)) if m else {"raw": out[-400:]})}


@app.get("/edit", response_class=HTMLResponse)
def edit_page(_: str = Depends(require_auth)) -> HTMLResponse:
    return HTMLResponse(_EDIT_HTML)


_EDIT_HTML = r"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>محرّر المواد والمبادئ — LegalMind</title>
<style>
:root{--bg:#0f1720;--card:#16212e;--line:#26374a;--tx:#e6edf3;--mut:#8aa0b4;--acc:#2f81f7;--ok:#2ea043;--warn:#d29922}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.7 "Segoe UI",Tahoma,sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:18px}
h1{font-size:20px;margin:6px 0 14px}.mut{color:var(--mut)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:14px}
.row{display:flex;gap:8px;flex-wrap:wrap}.row>*{flex:1;min-width:120px}
input,select,textarea,button{font:inherit;color:var(--tx);background:#0d1520;border:1px solid var(--line);border-radius:8px;padding:9px 11px}
input:focus,textarea:focus,select:focus{outline:none;border-color:var(--acc)}
textarea{width:100%;min-height:340px;line-height:1.9;resize:vertical}
label{display:block;font-size:13px;color:var(--mut);margin:8px 0 4px}
button{cursor:pointer;background:#1b2b3d;border-color:var(--line)}button:hover{border-color:var(--acc)}
button.pri{background:var(--acc);border-color:var(--acc);color:#fff}button.ok{background:var(--ok);border-color:var(--ok);color:#fff}
.res{border:1px solid var(--line);border-radius:8px;max-height:230px;overflow:auto;margin-top:8px}
.res div{padding:8px 10px;border-bottom:1px solid var(--line);cursor:pointer}.res div:hover{background:#0d1520}
.res b{color:var(--acc)}.msg{padding:9px 12px;border-radius:8px;margin-top:10px;display:none}
.msg.s{display:block;background:#12331d;border:1px solid var(--ok)}.msg.e{display:block;background:#3a1d1d;border:1px solid #b62324}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}@media(max-width:640px){.grid{grid-template-columns:1fr}}
small{color:var(--mut)}.tag{font-size:12px;color:var(--mut)}
</style></head><body><div class="wrap">
<h1>محرّر المواد والمبادئ <span class="mut" style="font-size:13px">— تعديل نصّ أي مصدر في قاعدة المعرفة</span></h1>

<div class="card">
  <label>ابحث بالمعرّف (مثل <span class="tag">legis-67-1980-m202</span>) أو بالنصّ:</label>
  <div class="row">
    <input id="q" placeholder="معرّف المادة أو كلمات للبحث الدلالي" style="flex:3">
    <button onclick="byId()">تحميل بالمعرّف</button>
    <button onclick="byText()">بحث دلالي</button>
  </div>
  <div id="res" class="res" style="display:none"></div>
</div>

<div id="editor" class="card" style="display:none">
  <div class="row"><div><label>المعرّف</label><input id="oid" readonly></div>
    <div><label>النوع</label><input id="otype" readonly></div></div>
  <div class="grid">
    <div><label>العنوان</label><input id="title"></div>
    <div><label>الفرع</label><input id="branch"></div>
    <div><label>الموضوع</label><input id="topic"></div>
    <div><label>الموضوع الفرعي</label><input id="subtopic"></div>
  </div>
  <label>حالة التوثيق</label>
  <select id="vstatus">
    <option value="source_verified">مُوثَّق من المصدر (source_verified)</option>
    <option value="operationally_accepted">مقبول تشغيليًّا</option>
    <option value="machine_pending_human">بانتظار مراجعة بشرية</option>
    <option value="historical_only">تاريخي فقط</option>
    <option value="requires_post_2026_reassessment">يحتاج إعادة تقييم</option>
  </select>
  <label>النصّ الكامل للمادة/المبدأ</label>
  <textarea id="text" spellcheck="false"></textarea>
  <small id="len"></small>
  <div class="row" style="margin-top:12px">
    <button class="pri" onclick="save()">💾 حفظ</button>
    <button class="ok" onclick="reindex()">🔄 إعادة الفهرسة (لتحديث البحث)</button>
    <button onclick="reload()">استرجاع الأصل</button>
  </div>
  <div id="msg" class="msg"></div>
</div>

<script>
var cur=null;
function j(u,o){return fetch(u,o).then(function(r){return r.json().then(function(d){if(!r.ok)throw new Error(d.detail||JSON.stringify(d));return d})})}
function esc(s){return (s||'').replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c]})}
function show(m,ok){var e=document.getElementById('msg');e.className='msg '+(ok?'s':'e');e.textContent=m}
function fill(o){cur=o;document.getElementById('editor').style.display='block';
 document.getElementById('oid').value=o.id;document.getElementById('otype').value=o.object_type||'';
 document.getElementById('title').value=o.title||'';document.getElementById('branch').value=o.branch||'';
 document.getElementById('topic').value=o.topic||'';document.getElementById('subtopic').value=o.subtopic||'';
 document.getElementById('vstatus').value=o.verification_status||'source_verified';
 document.getElementById('text').value=o.text||o.original_text||'';upd();
 document.getElementById('res').style.display='none';window.scrollTo(0,document.getElementById('editor').offsetTop-10)}
function upd(){var t=document.getElementById('text').value;document.getElementById('len').textContent=t.length+' حرف'}
document.addEventListener('input',function(e){if(e.target.id==='text')upd()});
function byId(){var id=document.getElementById('q').value.trim();if(!id)return;
 j('/api/object/'+encodeURIComponent(id)).then(fill).catch(function(e){show('لم يُعثر على المعرّف: '+e.message,false)})}
function byText(){var q=document.getElementById('q').value.trim();if(q.length<2)return;
 j('/api/search?limit=15&q='+encodeURIComponent(q)).then(function(d){var r=document.getElementById('res');
  if(!d.results||!d.results.length){r.style.display='block';r.innerHTML='<div>لا نتائج</div>';return}
  r.style.display='block';r.innerHTML=d.results.map(function(x){return '<div onclick="load(\''+x.object_id+'\')"><b>'+x.object_id+'</b> — '+esc(x.title||'')+'<br><small>'+esc((x.text||'').slice(0,90))+'…</small></div>'}).join('')})
  .catch(function(e){show(e.message,false)})}
function load(id){j('/api/object/'+encodeURIComponent(id)).then(fill).catch(function(e){show(e.message,false)})}
function reload(){if(cur)load(cur.id)}
function save(){if(!cur)return;var b={text:document.getElementById('text').value,
  title:document.getElementById('title').value,branch:document.getElementById('branch').value,
  topic:document.getElementById('topic').value,subtopic:document.getElementById('subtopic').value,
  verification_status:document.getElementById('vstatus').value};
 j('/api/object/'+encodeURIComponent(cur.id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})
  .then(function(d){show(d.note||'حُفِظ.',true)}).catch(function(e){show('تعذّر الحفظ: '+e.message,false)})}
function reindex(){show('جارٍ إعادة الفهرسة…',true);
 j('/api/reindex',{method:'POST'}).then(function(d){var x=d.reindex||{};
  show('تمّت الفهرسة: '+(x.postgres_objects||'?')+' كائن، متّسق='+(x.consistent),true)})
  .catch(function(e){show('فشلت الفهرسة: '+e.message,false)})}
</script></div></body></html>"""
# ==================== نهاية المحرّر ====================
