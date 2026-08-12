#!/bin/bash
# إصلاح قسم المراجعة في مركز المصادر: معاينة خفيفة + نص كامل عند الطلب + أزرار متينة
set -e
python3 - <<'PYEOF'
p = "/opt/LegalMind/admin/app.py"
src = open(p, encoding="utf-8").read()

src = src.replace("coalesce(original_text,'') AS preview",
                  "left(coalesce(original_text,''), 400) AS preview")

if "/api/review/text/" not in src:
    anchor = '@app.post("/api/review/approve/{object_id:path}")'
    NEWEP = '''@app.get("/api/review/text/{object_id:path}")
def review_text(object_id: str, _: str = Depends(require_auth)) -> dict:
    rows = db_rows("SELECT coalesce(original_text,'') AS t FROM knowledge_objects WHERE id=%s", (object_id,))
    if not rows:
        raise HTTPException(404, "غير موجود")
    return {"id": object_id, "text": rows[0]["t"]}

'''
    assert anchor in src, "!! لم أجد نقطة الاعتماد"
    src = src.replace(anchor, NEWEP + anchor, 1)

i = src.find("async function loadReview(){")
j = src.find("async function confirmSel")
assert i != -1 and j != -1, "!! لم أجد حدود loadReview"
NEWJS = '''async function loadReview(){
  try{var d=await (await fetch("/api/review/pending")).json();var h="";
    var items=d.items.slice(0,30);
    items.forEach(function(it){
      h+='<div class="card"><span class="ttl">'+esc(it.title)+'</span><span class="chip c-rev">ثقة '+esc(it.confidence||"?")+"</span>"
        +'<div class="muted">'+esc(it.branch||"")+" / "+esc(it.topic||"")+"</div>"
        +(it.notes?'<div class="muted">&#128221; '+esc(it.notes)+"</div>":"")
        +'<details data-full="'+encodeURIComponent(it.id)+'"><summary>معاينة النص الكامل</summary><pre>'+esc(it.preview||"")+"\\n... (افتح لتحميل النص كاملاً)</pre></details>"
        +'<div style="margin-top:8px"><button class="btn ok" data-approve="'+encodeURIComponent(it.id)+'">&#10004; اعتماد</button>'
        +'<button class="btn no" data-reject="'+encodeURIComponent(it.id)+'">&#10008; رفض وحذف</button></div></div>'});
    if(d.count>30){h+='<div class="muted">و '+(d.count-30)+' عنصراً آخر بانتظار المراجعة — اعتمد تباعاً أو استخدم الاعتماد الجماعي</div>'}
    $("#review").innerHTML=h||'<span class="muted">لا شيء بانتظار المراجعة &#10003;</span>'}catch(e){}
}
document.addEventListener("click",function(ev){
  var t=ev.target;if(!t||!t.getAttribute)return;
  var a=t.getAttribute("data-approve"),r=t.getAttribute("data-reject");
  if(a){t.disabled=true;act("/api/review/approve/"+a)}
  if(r&&confirm("حذف نهائي؟")){t.disabled=true;act("/api/review/reject/"+r)}
});
document.addEventListener("toggle",async function(ev){
  var d=ev.target;if(!d||!d.getAttribute)return;
  var id=d.getAttribute("data-full");
  if(id&&d.open&&!d.getAttribute("data-loaded")){
    d.setAttribute("data-loaded","1");
    try{var r=await (await fetch("/api/review/text/"+id)).json();
        d.querySelector("pre").textContent=r.text||"(فارغ)"}
    catch(e){d.querySelector("pre").textContent="تعذر التحميل"}}
},true);
'''
src = src[:i] + NEWJS + src[j:]
open(p, "w", encoding="utf-8").write(src)
print("رُقيت شاشة المراجعة ✓")
PYEOF
/opt/LegalMind/admin/.venv/bin/python -m py_compile /opt/LegalMind/admin/app.py
systemctl restart legalmind-admin
sleep 2
systemctl is-active legalmind-admin
echo "تم — حدّث صفحة المركز في متصفحك"
