#!/bin/bash
# إضافة قسم "لصق نص" إلى مركز المصادر
set -e
python3 - <<'PYEOF'
p = "/opt/LegalMind/admin/app.py"
src = open(p, encoding="utf-8").read()
if 'id="pastebox"' in src:
    print("لصق النص موجود مسبقا")
else:
    A1 = '<input type="file" id="fi" multiple style="display:none"></div>'
    N1 = A1 + '''
<details id="pastebox" class="card" style="margin-top:10px"><summary>&#128203; أو الصق نصا قانونيا مباشرة (حكم، مبدأ، مواد...)</summary>
<input id="ptitle" placeholder="عنوان المصدر (اختياري)" style="width:100%;margin-top:10px;padding:9px;border:1px solid #cbd3ee;border-radius:8px;font-size:13px">
<textarea id="ptext" placeholder="الصق النص هنا كما هو حرفيا (20 حرفا على الأقل) - سيقرؤه كلود ويقطعه ويصنفه تلقائيا" style="width:100%;min-height:200px;margin-top:8px;padding:9px;border:1px solid #cbd3ee;border-radius:8px;font-size:13px;line-height:1.8"></textarea>
<button id="psend" class="btn ok" style="margin-top:8px">&#10148; إرسال للمعالجة الذكية</button></details>'''
    assert A1 in src, "!! لم أجد منطقة الرفع — شغل lm-center-v2.sh أولا"
    src = src.replace(A1, N1, 1)

    A2 = "loadQueue();loadReview();loadSelection();\nsetInterval"
    N2 = '''document.getElementById("psend").onclick=function(){
  var tx=document.getElementById("ptext").value.trim();
  if(tx.length<20){alert("النص قصير جدا - 20 حرفا على الأقل");return}
  var fd=new FormData();
  fd.append("content",tx);fd.append("branch","");fd.append("topic","");
  fd.append("source_type","");fd.append("classification_title","");
  fd.append("source_title",document.getElementById("ptitle").value.trim());
  var b=this;b.disabled=true;b.textContent="جار الإرسال...";
  fetch("/api/paste-text",{method:"POST",body:fd}).then(function(r){
    if(!r.ok){return r.text().then(function(t){alert(t.slice(0,250))})}
    document.getElementById("ptext").value="";
    document.getElementById("ptitle").value="";
    document.getElementById("pastebox").open=false;
    loadQueue();
  }).catch(function(){alert("خطأ في الاتصال")})
    .then(function(){b.disabled=false;b.textContent="\\u27a4 إرسال للمعالجة الذكية"});
};
loadQueue();loadReview();loadSelection();
setInterval'''
    assert A2 in src, "!! لم أجد نقطة التشغيل"
    src = src.replace(A2, N2, 1)
    open(p, "w", encoding="utf-8").write(src)
    print("أضيف لصق النص ✓")
PYEOF
/opt/LegalMind/admin/.venv/bin/python -m py_compile /opt/LegalMind/admin/app.py
systemctl restart legalmind-admin
sleep 2
systemctl is-active legalmind-admin
echo "تم - حدث صفحة المركز"
