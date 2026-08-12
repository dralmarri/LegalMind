#!/bin/bash
# ميزة "تعديل واعتماد" في شاشة المراجعة (تتطلب نسخة v2 من الصفحة)
set -e
python3 - <<'PYEOF'
p = "/opt/LegalMind/admin/app.py"
src = open(p, encoding="utf-8").read()
assert 'data-approve="' in src, "!! شغل lm-center-v2.sh أولا ثم أعد هذا السكربت"

if "/api/review/edit/" not in src:
    anchor = '@app.post("/api/review/approve/{object_id:path}")'
    NEWEP = '''@app.post("/api/review/edit/{object_id:path}")
def review_edit(object_id: str, body: dict, _: str = Depends(require_auth)) -> dict:
    text = (body.get("text") or "").strip()
    if len(text) < 20:
        raise HTTPException(400, "النص بعد التعديل قصير جدا")
    title = (body.get("title") or "").strip()
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("""UPDATE knowledge_objects SET original_text=%s, normalized_text=%s,
                       title=COALESCE(NULLIF(%s,''), title),
                       verification_status='operationally_accepted',
                       authority_status='human_verified_authority', usable_as_citation=true,
                       metadata = metadata || %s::jsonb, updated_at=now()
                       WHERE id=%s""",
                    (text, text, title, json.dumps({"human_edited": True}), object_id))
        n = cur.rowcount
        conn.commit()
    if not n:
        raise HTTPException(404, "الكائن غير موجود")
    proc = _sb2.run([ENGINE_PY, "/opt/LegalMind/engine/reindex_one_cli.py", object_id],
                    cwd="/opt/LegalMind", env=_engine_env(), capture_output=True, text=True, timeout=180)
    return {"ok": True, "id": object_id, "reindexed": proc.returncode == 0}

'''
    assert anchor in src, "!! لم أجد نقطة الاعتماد"
    src = src.replace(anchor, NEWEP + anchor, 1)

OLDBTN = """+'<div style="margin-top:8px"><button class="btn ok" data-approve="'+encodeURIComponent(it.id)+'">&#10004; اعتماد</button>'"""
NEWBTN = OLDBTN + """
        +'<button class="btn sec" data-edit="'+encodeURIComponent(it.id)+'">&#9998; تعديل واعتماد</button>'"""
if "data-edit=" not in src:
    assert OLDBTN in src, "!! لم أجد صف الأزرار"
    src = src.replace(OLDBTN, NEWBTN, 1)

OLDCLK = 'document.addEventListener("click",function(ev){\n  var t=ev.target;if(!t||!t.getAttribute)return;'
NEWCLK = '''function startEdit(btn,id){
  var card=btn.closest(".card");if(!card)return;
  btn.disabled=true;
  fetch("/api/review/text/"+id).then(function(r){return r.json()}).then(function(r){
    var box=document.createElement("div");
    box.innerHTML='<textarea style="width:100%;min-height:260px;font-size:13px;line-height:1.8;padding:8px;border:1px solid #cbd3ee;border-radius:8px">'+esc(r.text||"")+'</textarea>'
      +'<div style="margin-top:8px"><button class="btn ok" data-save="'+id+'">&#128190; حفظ واعتماد</button>'
      +'<button class="btn sec" data-cancel="1">إلغاء</button></div>';
    var det=card.querySelector("details");
    card.insertBefore(box,det||null);
    if(det)det.style.display="none";
    var ap=card.querySelector("[data-approve]");
    if(ap&&ap.parentNode)ap.parentNode.style.display="none";
  });
}
document.addEventListener("click",function(ev){
  var t=ev.target;if(!t||!t.getAttribute)return;
  var ed=t.getAttribute("data-edit");
  if(ed){startEdit(t,ed);return}
  var sv=t.getAttribute("data-save");
  if(sv){var card=t.closest(".card");var ta=card?card.querySelector("textarea"):null;
    if(!ta)return;t.disabled=true;act("/api/review/edit/"+sv,{text:ta.value});return}
  if(t.getAttribute("data-cancel")){loadReview();return}'''
if "startEdit" not in src:
    assert OLDCLK in src, "!! لم أجد مستمع النقر"
    src = src.replace(OLDCLK, NEWCLK, 1)

open(p, "w", encoding="utf-8").write(src)
print("رُكبت ميزة التعديل والاعتماد ✓")
PYEOF
/opt/LegalMind/admin/.venv/bin/python -m py_compile /opt/LegalMind/admin/app.py
systemctl restart legalmind-admin
sleep 2
systemctl is-active legalmind-admin
echo "تم - حدث صفحة المركز"
