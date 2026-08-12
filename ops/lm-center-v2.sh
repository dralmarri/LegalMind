#!/bin/bash
# استبدال صفحة مركز المصادر بنسخة v2 موحدة نظيفة
set -e
python3 - <<'PYEOF'
p = "/opt/LegalMind/admin/app.py"
src = open(p, encoding="utf-8").read()
i = src.find('_INGEST_CENTER = """')
assert i != -1, "!! لم أجد بداية الصفحة"
j = src.find('"""', i + len('_INGEST_CENTER = """'))
assert j != -1, "!! لم أجد نهاية الصفحة"
NEW = r"""<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>مركز المصادر الذكي</title><style>
body{font-family:system-ui,'Segoe UI',Tahoma;background:#f4f6fb;margin:0;padding:16px;color:#1a2340}
h1{font-size:20px;margin:6px 0 14px}h2{font-size:16px;margin:18px 0 8px;color:#33406b}
.card{background:#fff;border:1px solid #e3e8f4;border-radius:12px;padding:12px;margin-bottom:10px;box-shadow:0 1px 3px rgba(20,30,80,.06)}
#drop{border:2px dashed #7b8cf0;border-radius:14px;padding:30px;text-align:center;background:#fff}
.btn{border:0;border-radius:8px;padding:8px 14px;cursor:pointer;font-size:13px;margin-inline-start:6px}
.ok{background:#16a34a;color:#fff}.no{background:#dc2626;color:#fff}.sec{background:#e5e9f8;color:#33406b}
.bar{height:8px;background:#e8ecf7;border-radius:6px;overflow:hidden;margin-top:6px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#5b6ef5,#8b5bf5);transition:width .6s}
.chip{display:inline-block;padding:2px 10px;border-radius:20px;font-size:12px;margin-inline-start:6px}
.c-wait{background:#fef3c7;color:#92400e}.c-run{background:#dbeafe;color:#1d4ed8}.c-done{background:#dcfce7;color:#166534}
.c-rev{background:#fce7f3;color:#9d174d}.c-sel{background:#ede9fe;color:#5b21b6}.c-fail{background:#fee2e2;color:#991b1b}
.muted{color:#7a86ab;font-size:12px}.ttl{font-weight:600;font-size:14px}
details{margin-top:6px}summary{cursor:pointer;color:#3b4fd8;font-size:13px}
pre{white-space:pre-wrap;background:#f8f9fe;border-radius:8px;padding:8px;font-size:12px;max-height:240px;overflow:auto}
label.ck{display:flex;gap:8px;align-items:flex-start;padding:6px;border-radius:8px}
</style></head><body>
<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
<h1>&#128229; مركز المصادر الذكي <span class="muted">- قراءة وفهرسة بعقل كلود</span></h1>
<a href="/" class="btn" style="background:#33406b;color:#fff;text-decoration:none">&#11013; العودة للوحة</a></div>
<div id="drop">اسحب ملفاتك هنا (عدة ملفات معا)<br>
<span class="muted">PDF, DOCX, TXT, MD, HTML - حتى 512 م.ب</span><br>
<button id="pick" class="btn" style="margin-top:12px;font-size:15px;padding:10px 22px;background:#3b4fd8;color:#fff">&#128194; اختر الملفات من جهازك</button>
<input type="file" id="fi" multiple style="display:none"></div>
<h2>&#9201; الطابور</h2><div id="queue" class="card muted">...</div>
<h2>&#128269; بانتظار مراجعتك</h2><div id="review" class="card muted">...</div>
<h2>&#128450; مستندات مركبة بانتظار اختيارك</h2><div id="selection" class="card muted">...</div>
<script>
function $(q){return document.querySelector(q)}
function esc(s){s=(s==null?"":String(s));return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}
var drop=$("#drop"),fi=$("#fi"),pick=$("#pick");
pick.onclick=function(e){e.stopPropagation();fi.click()};
drop.ondragover=function(e){e.preventDefault()};
drop.ondrop=function(e){e.preventDefault();upload(e.dataTransfer.files)};
fi.onchange=function(){var fs=Array.prototype.slice.call(fi.files);fi.value="";upload(fs)};
function upload(files){
  var chain=Promise.resolve();
  Array.prototype.forEach.call(files,function(f){
    chain=chain.then(function(){
      var fd=new FormData();fd.append("files",f);
      fd.append("source_type","");fd.append("branch","");fd.append("topic","");fd.append("classification_title","");
      return fetch("/api/upload",{method:"POST",body:fd}).then(function(r){
        if(!r.ok){return r.text().then(function(t){alert("تعذر رفع "+f.name+": "+t.slice(0,180))})}});
    });
  });
  chain.then(loadQueue);
}
function chip(st){var m={waiting:["c-wait","في الانتظار"],started:["c-run","تحت المعالجة"],completed:["c-done","اكتمل"],
  needs_selection:["c-sel","بانتظار اختيارك"],failed:["c-fail","فشل"],duplicate:["c-wait","مكرر"]};
  var x=m[st]||["c-wait",st];return '<span class="chip '+x[0]+'">'+x[1]+'</span>'}
function loadQueue(){
  fetch("/api/ingest/queue").then(function(r){return r.json()}).then(function(d){
    var h="";
    d.waiting.forEach(function(w){h+='<div class="card"><span class="ttl">'+esc(w.file)+'</span>'+chip("waiting")+'</div>'});
    d.batches.forEach(function(b){
      h+='<div class="card"><span class="ttl">'+esc(b.title||b.file||b.batch_id)+'</span>'+chip(b.status);
      if(b.status==="started"){h+='<div class="muted">'+esc(b.stage||"")+' - '+(b.percent||0)+'%</div><div class="bar"><i style="width:'+(b.percent||3)+'%"></i></div>'}
      else if(b.status==="completed"){h+='<div class="muted">'+(b.object_count||0)+' كائنا'+(b.needs_review?' - منها '+b.needs_review+' للمراجعة':'')+'</div>'}
      else if(b.status==="failed"){h+='<div class="muted">'+esc(b.error||"")+'</div>'}
      h+='</div>'});
    $("#queue").innerHTML=h||'<span class="muted">لا شيء في الطابور - ارفع ملفاتك أعلاه</span>';
  }).catch(function(){});
}
function loadReview(){
  fetch("/api/review/pending").then(function(r){return r.json()}).then(function(d){
    var h="";
    d.items.slice(0,30).forEach(function(it){
      h+='<div class="card"><span class="ttl">'+esc(it.title)+'</span><span class="chip c-rev">ثقة '+esc(it.confidence||"?")+'</span>'
        +'<div class="muted">'+esc(it.branch||"")+' / '+esc(it.topic||"")+'</div>'
        +(it.notes?'<div class="muted">&#128221; '+esc(it.notes)+'</div>':'')
        +'<details data-full="'+encodeURIComponent(it.id)+'"><summary>معاينة النص الكامل</summary><pre>'+esc(it.preview||"")+'</pre></details>'
        +'<div style="margin-top:8px"><button class="btn ok" data-approve="'+encodeURIComponent(it.id)+'">&#10004; اعتماد</button>'
        +'<button class="btn no" data-reject="'+encodeURIComponent(it.id)+'">&#10008; رفض وحذف</button></div></div>';
    });
    if(d.count>30){h+='<div class="muted">و '+(d.count-30)+' عنصرا آخر - اعتمد تباعا أو استخدم الاعتماد الجماعي</div>'}
    $("#review").innerHTML=h||'<span class="muted">لا شيء بانتظار المراجعة &#10003;</span>';
  }).catch(function(){});
}
function loadSelection(){
  fetch("/api/selection/pending").then(function(r){return r.json()}).then(function(d){
    var h="";
    d.items.forEach(function(it){
      h+='<div class="card"><span class="ttl">'+esc(it.title||it.file)+'</span>';
      it.chunks.forEach(function(c){
        h+='<label class="ck"><input type="checkbox" data-b="'+esc(it.batch_id)+'" value="'+c.index+'"><span>'
          +esc(c.title)+' <span class="muted">('+esc(c.kind||"")+' - '+c.chars+' حرف - ثقة '+(c.confidence||"?")+')</span></span></label>';
      });
      h+='<div style="margin-top:8px"><button class="btn ok" data-selpick="'+esc(it.batch_id)+'">&#10004; تثبيت المختار</button>'
        +'<button class="btn sec" data-selall="'+esc(it.batch_id)+'">إدخال الكل</button>'
        +'<button class="btn no" data-seldiscard="'+esc(it.batch_id)+'">إهمال الكل</button></div></div>';
    });
    $("#selection").innerHTML=h||'<span class="muted">لا مستندات مركبة معلقة &#10003;</span>';
  }).catch(function(){});
}
function act(url,body){
  return fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body||{})})
    .then(function(r){if(!r.ok){return r.text().then(function(t){alert(t.slice(0,250))})}})
    .then(function(){loadQueue();loadReview();loadSelection()});
}
document.addEventListener("click",function(ev){
  var t=ev.target;if(!t||!t.getAttribute)return;
  var a=t.getAttribute("data-approve");
  if(a){t.disabled=true;act("/api/review/approve/"+a);return}
  var r=t.getAttribute("data-reject");
  if(r){if(confirm("حذف نهائي؟")){t.disabled=true;act("/api/review/reject/"+r)}return}
  var sp=t.getAttribute("data-selpick");
  if(sp){var idx=[];document.querySelectorAll('input[data-b="'+sp+'"]:checked').forEach(function(c){idx.push(parseInt(c.value,10))});
    if(!idx.length){alert("حدد قطعة واحدة على الأقل");return}
    t.disabled=true;act("/api/selection/confirm/"+encodeURIComponent(sp),{indices:idx});return}
  var sa=t.getAttribute("data-selall");
  if(sa){t.disabled=true;act("/api/selection/confirm/"+encodeURIComponent(sa),{indices:"all"});return}
  var sd=t.getAttribute("data-seldiscard");
  if(sd){if(confirm("إهمال الملف كاملا؟")){t.disabled=true;act("/api/selection/discard/"+encodeURIComponent(sd))}return}
});
document.addEventListener("toggle",function(ev){
  var d=ev.target;if(!d||!d.getAttribute)return;
  var id=d.getAttribute("data-full");
  if(id&&d.open&&!d.getAttribute("data-loaded")){
    d.setAttribute("data-loaded","1");
    fetch("/api/review/text/"+id).then(function(r){return r.json()}).then(function(r){
      d.querySelector("pre").textContent=r.text||"(فارغ)";
    }).catch(function(){d.querySelector("pre").textContent="تعذر التحميل"});
  }
},true);
loadQueue();loadReview();loadSelection();
setInterval(loadQueue,5000);setInterval(loadReview,20000);setInterval(loadSelection,20000);
</script></body></html>"""
src = src[:i + len('_INGEST_CENTER = """')] + NEW + src[j:]
open(p, "w", encoding="utf-8").write(src)
print("رُكبت صفحة v2 ✓")
PYEOF
/opt/LegalMind/admin/.venv/bin/python -m py_compile /opt/LegalMind/admin/app.py
systemctl restart legalmind-admin
sleep 2
systemctl is-active legalmind-admin
echo "تم - حدث صفحة المركز في متصفحك"
