#!/bin/bash
# إصلاح استجابة زري الحفظ والإلغاء في محرر المراجعة
set -e
python3 - <<'PYEOF'
p = "/opt/LegalMind/admin/app.py"
src = open(p, encoding="utf-8").read()

OLD = '''  var sv=t.getAttribute("data-save");
  if(sv){var card=t.closest(".card");var ta=card?card.querySelector("textarea"):null;
    if(!ta)return;t.disabled=true;act("/api/review/edit/"+sv,{text:ta.value});return}
  if(t.getAttribute("data-cancel")){loadReview();return}'''
NEW = '''  var sv=t.getAttribute("data-save");
  if(sv){var card=t.closest(".card");var ta=card?card.querySelector("textarea"):null;
    if(!ta)return;t.disabled=true;t.textContent="جار الحفظ...";
    fetch("/api/review/edit/"+sv,{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({text:ta.value})})
      .then(function(r){
        if(!r.ok){return r.text().then(function(x){alert(x.slice(0,250));t.disabled=false;t.textContent="حفظ واعتماد"})}
        if(card)card.remove();
        loadReview();loadQueue();
      })
      .catch(function(){alert("خطأ في الاتصال - أعد المحاولة");t.disabled=false;t.textContent="حفظ واعتماد"});
    return}
  if(t.getAttribute("data-cancel")){
    var cc=t.closest(".card");
    if(cc){var bx=t.parentNode.parentNode;if(bx&&bx.parentNode)bx.parentNode.removeChild(bx);
      var dd=cc.querySelector("details");if(dd)dd.style.display="";
      var ap=cc.querySelector("[data-approve]");if(ap&&ap.parentNode)ap.parentNode.style.display="";}
    loadReview();return}'''
assert OLD in src, "!! النمط غير مطابق — أخبر كلود"
src = src.replace(OLD, NEW, 1)
open(p, "w", encoding="utf-8").write(src)
print("أُصلح زرا الحفظ والإلغاء ✓")
PYEOF
/opt/LegalMind/admin/.venv/bin/python -m py_compile /opt/LegalMind/admin/app.py
systemctl restart legalmind-admin
sleep 2
systemctl is-active legalmind-admin
echo "تم - حدث صفحة المركز"
