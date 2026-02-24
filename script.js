const DB_NAME = "legalmind_db_v1";
const DB_VERSION = 1;
const STORE = "entries";

const el = (id) => document.getElementById(id);

const form = el("entryForm");
const entryKind = el("entryKind");
const branch = el("branch");
const court = el("court");
const appealNo = el("appealNo");

const circuitPrefix = el("circuitPrefix");
const circuitNo = el("circuitNo");

const sessionDate = el("sessionDate");
const metaPreview = el("metaPreview");
const bodyText = el("bodyText");

const btnClearForm = el("btnClearForm");
const btnExport = el("btnExport");
const btnImport = el("btnImport");
const importFile = el("importFile");
const btnTheme = el("btnTheme");
const saveStatus = el("saveStatus");

const q = el("q");
const filterKind = el("filterKind");
const filterBranch = el("filterBranch");
const btnSearch = el("btnSearch");
const btnResetSearch = el("btnResetSearch");
const btnWipe = el("btnWipe");

const results = el("results");
const latest = el("latest");
const resultsInfo = el("resultsInfo");
const dbSizeInfo = el("dbSizeInfo");

// -------- Theme
(function initTheme(){
  const saved = localStorage.getItem("lm_theme") || "light";
  document.documentElement.dataset.theme = saved;
})();
btnTheme.addEventListener("click", () => {
  const cur = document.documentElement.dataset.theme || "light";
  const next = (cur === "light") ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("lm_theme", next);
});

// -------- Utilities
function formatDateDDMMYYYY(iso){
  if(!iso) return "";
  const [y,m,d] = iso.split("-");
  if(!y || !m || !d) return "";
  return `${d}/${m}/${y}`;
}

// -------- Circuit options
function setCircuitOptions(){
  const opts = ["", "1","2","3","4","5","6","7","8","9","10"];
  circuitNo.innerHTML = "";
  opts.forEach(v => {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = v === "" ? "— رقم الدائرة —" : v;
    circuitNo.appendChild(o);
  });
}

// ✅ المطلوب: الفرع يظهر تلقائيًا داخل رقم الدائرة
function updateCircuitPrefix(){
  circuitPrefix.value = `${branch.value.trim()}/`;
}

// -------- Meta builder
function buildMeta(){
  const b = branch.value.trim();
  const c = circuitNo.value.trim(); // رقم الدائرة فقط
  const dt = formatDateDDMMYYYY(sessionDate.value);

  // جزء الفرع/الدائرة
  let left = `${b}/`;
  if (c) left += `${c}`;

  // جزء الجلسة
  let right = "";
  if (dt) right = `جلسة ${dt}`;

  return [left.trim(), right.trim()].filter(Boolean).join(" ").trim();
}

function updateMetaPreview(){
  metaPreview.value = buildMeta();
}

// events
branch.addEventListener("change", () => {
  updateCircuitPrefix();
  // نترك رقم الدائرة للمستخدم يختاره، لا نجبره
  updateMetaPreview();
});
circuitNo.addEventListener("change", updateMetaPreview);
sessionDate.addEventListener("change", updateMetaPreview);

// init ui
setCircuitOptions();
updateCircuitPrefix();
updateMetaPreview();

// -------- IndexedDB
function openDB(){
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);

    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if(!db.objectStoreNames.contains(STORE)){
        const store = db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
        store.createIndex("by_createdAt", "createdAt", { unique:false });
      }
    };

    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function txStore(mode="readonly"){
  const db = await openDB();
  const tx = db.transaction(STORE, mode);
  const store = tx.objectStore(STORE);
  return { db, tx, store };
}

async function addEntry(entry){
  const { db, tx, store } = await txStore("readwrite");
  return new Promise((resolve, reject) => {
    const req = store.add(entry);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
    tx.onerror = () => reject(tx.error);
  });
}

async function getAllEntries(){
  const { db, tx, store } = await txStore("readonly");
  return new Promise((resolve, reject) => {
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
  });
}

async function deleteEntry(id){
  const { db, tx, store } = await txStore("readwrite");
  return new Promise((resolve, reject) => {
    const req = store.delete(id);
    req.onsuccess = () => resolve(true);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
  });
}

async function updateEntry(entry){
  const { db, tx, store } = await txStore("readwrite");
  return new Promise((resolve, reject) => {
    const req = store.put(entry);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
    tx.onerror = () => reject(tx.error);
  });
}

async function clearDB(){
  const { db, tx, store } = await txStore("readwrite");
  return new Promise((resolve, reject) => {
    const req = store.clear();
    req.onsuccess = () => resolve(true);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
  });
}

// -------- UI Render
function escapeHTML(str){
  if(str == null) return "";
  return String(str)
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

function renderItem(item, container){
  const div = document.createElement("div");
  div.className = "item";

  const badges = [
    item.kind,
    item.branch,
    item.court,
    item.appealNo ? `طعن: ${item.appealNo}` : "",
    item.meta || ""
  ].filter(Boolean).map(b => `<span class="badge">${escapeHTML(b)}</span>`).join("");

  div.innerHTML = `
    <div class="item-top">
      <div>
        <div class="badges">${badges}</div>
        <div class="meta">تاريخ الإدخال: ${escapeHTML(new Date(item.createdAt).toLocaleString("ar-KW"))}</div>
      </div>
      <div class="item-actions">
        <button class="btn btn-edit" type="button" data-edit="${item.id}">تعديل</button>
        <button class="btn btn-danger" type="button" data-del="${item.id}">حذف</button>
      </div>
    </div>
    <div class="body" data-body="${item.id}">${escapeHTML(item.body || "")}</div>
  `;

  div.querySelector(`[data-edit="${item.id}"]`).addEventListener("click", () => {
    openEditForm(item, div);
  });

  div.querySelector(`[data-del="${item.id}"]`).addEventListener("click", async () => {
    if(confirm("تأكيد حذف هذا السجل؟")) {
      await deleteEntry(item.id);
      await refreshLatest();
      await runSearch();
      await updateDBSize();
    }
  });

  container.appendChild(div);
}

function openEditForm(item, containerDiv){
  if(containerDiv.querySelector(".edit-form")) return;

  const kindOptions = ["مبدأ","حكم"].map(v =>
    `<option value="${v}" ${item.kind===v?"selected":""}>${v}</option>`
  ).join("");

  const branchOptions = ["عام","مدني","تجاري","إداري","عمالي","أحوال شخصية","جزائي"].map(v =>
    `<option value="${v}" ${item.branch===v?"selected":""}>${v}</option>`
  ).join("");

  const courtOptions = ["محكمة التمييز"].map(v =>
    `<option value="${v}" ${item.court===v?"selected":""}>${v}</option>`
  ).join("");

  const circuitOpts = ["","1","2","3","4","5","6","7","8","9","10"].map(v =>
    `<option value="${v}" ${item.circuitNo===v?"selected":""}>${v===""?"— رقم الدائرة —":v}</option>`
  ).join("");

  const formHTML = `
    <div class="edit-form">
      <div class="edit-grid">
        <div class="field">
          <label>نوع الإدخال</label>
          <select class="edit-kind">${kindOptions}</select>
        </div>
        <div class="field">
          <label>الفرع</label>
          <select class="edit-branch">${branchOptions}</select>
        </div>
        <div class="field">
          <label>المحكمة</label>
          <select class="edit-court">${courtOptions}</select>
        </div>
        <div class="field">
          <label>رقم الطعن</label>
          <input class="edit-appealNo" type="text" value="${escapeHTML(item.appealNo || "")}" />
        </div>
        <div class="field">
          <label>رقم الدائرة</label>
          <select class="edit-circuitNo">${circuitOpts}</select>
        </div>
        <div class="field">
          <label>تاريخ الجلسة</label>
          <input class="edit-sessionDate" type="date" value="${escapeHTML(item.sessionDate || "")}" />
        </div>
      </div>
      <div class="field">
        <label>نص الحكم/المبدأ</label>
        <textarea class="edit-body" rows="8">${escapeHTML(item.body || "")}</textarea>
      </div>
      <div class="edit-actions">
        <button class="btn btn-primary edit-save" type="button">حفظ التعديل</button>
        <button class="btn btn-ghost edit-cancel" type="button">إلغاء</button>
      </div>
    </div>
  `;

  const bodyEl = containerDiv.querySelector(`[data-body="${item.id}"]`);
  bodyEl.style.display = "none";

  const wrapper = document.createElement("div");
  wrapper.innerHTML = formHTML;
  const editForm = wrapper.firstElementChild;
  bodyEl.after(editForm);

  editForm.querySelector(".edit-cancel").addEventListener("click", () => {
    editForm.remove();
    bodyEl.style.display = "";
  });

  editForm.querySelector(".edit-save").addEventListener("click", async () => {
    const editBranch = editForm.querySelector(".edit-branch").value.trim();
    const editCircuit = editForm.querySelector(".edit-circuitNo").value.trim();
    const editDate = editForm.querySelector(".edit-sessionDate").value;
    const dtFormatted = formatDateDDMMYYYY(editDate);

    let metaLeft = `${editBranch}/`;
    if(editCircuit) metaLeft += editCircuit;
    let metaRight = dtFormatted ? `جلسة ${dtFormatted}` : "";
    const newMeta = [metaLeft.trim(), metaRight.trim()].filter(Boolean).join(" ").trim();

    const updated = {
      id: item.id,
      kind: editForm.querySelector(".edit-kind").value.trim(),
      branch: editBranch,
      court: editForm.querySelector(".edit-court").value.trim(),
      appealNo: editForm.querySelector(".edit-appealNo").value.trim(),
      circuitNo: editCircuit,
      sessionDate: editDate || "",
      meta: newMeta,
      body: editForm.querySelector(".edit-body").value || "",
      createdAt: item.createdAt,
    };

    if(!updated.body.trim()){
      alert("لا يمكن حفظ سجل بنص فارغ.");
      return;
    }

    try{
      await updateEntry(updated);
      await refreshLatest();
      await runSearch();
      await updateDBSize();
    }catch(err){
      alert("فشل حفظ التعديل: " + (err?.message || err));
    }
  });
}

// ✅ المطلوب: تفريغ بعد الحفظ
function resetFormAfterSave(){
  appealNo.value = "";
  circuitNo.value = "";
  sessionDate.value = "";
  bodyText.value = "";

  // نحافظ على الاختيارات الأساسية (نوع/فرع/محكمة) كما هي لتسريع الإدخال
  updateCircuitPrefix();
  updateMetaPreview();
}

function setStatus(msg, isError=false){
  saveStatus.textContent = msg;
  saveStatus.style.color = isError ? "var(--danger)" : "";
}

// -------- Save (مهم)
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  setStatus("جارٍ الحفظ...");

  try{
    const meta = buildMeta();

    const entry = {
      kind: entryKind.value.trim(),
      branch: branch.value.trim(),
      court: court.value.trim(),
      appealNo: appealNo.value.trim(),
      circuitNo: circuitNo.value.trim(),
      sessionDate: sessionDate.value || "",
      meta: meta || "",
      body: bodyText.value || "",
      createdAt: Date.now(),
    };

    // إذا لم يكتب نص، لا نحفظ سجل فارغ بلا معنى
    if(!entry.body.trim()){
      setStatus("لم يتم الحفظ: نص الحكم/المبدأ فارغ.", true);
      return;
    }

    await addEntry(entry);

    // ✅ إذا نجح الحفظ: نفرّغ فورًا
    resetFormAfterSave();

    await refreshLatest();
    await runSearch();

    await updateDBSize();
    setStatus("تم الحفظ بنجاح ✅ يمكنك إدخال حكم جديد الآن.");
  }catch(err){
    // ✅ هنا سنعرف لماذا لا يتم الحفظ ولا التفريغ
    console.error("SAVE ERROR:", err);

    // رسالة واضحة للمستخدم
    setStatus(
      "فشل الحفظ ❌ غالبًا المتصفح يمنع التخزين أو IndexedDB غير متاح (جرّب إغلاق التصفح الخاص/تغيير المتصفح).",
      true
    );

    alert("فشل الحفظ. افتح Console لمعرفة الخطأ أو جرّب متصفح آخر/عدم التصفح الخاص.");
  }
});

btnClearForm.addEventListener("click", () => {
  appealNo.value = "";
  circuitNo.value = "";
  sessionDate.value = "";
  bodyText.value = "";
  updateCircuitPrefix();
  updateMetaPreview();
  setStatus("تم تفريغ الحقول.");
});

// -------- Search
function matchesFilters(item){
  const fk = filterKind.value;
  const fb = filterBranch.value;
  if (fk && item.kind !== fk) return false;
  if (fb && item.branch !== fb) return false;
  return true;
}

function matchesQuery(item, query){
  if(!query) return true;
  const ql = query.toLowerCase();
  const hay = [
    item.kind, item.branch, item.court, item.appealNo, item.meta, item.body
  ].join(" ").toLowerCase();
  return hay.includes(ql);
}

async function runSearch(){
  const all = await getAllEntries();
  const query = (q.value || "").trim();

  const filtered = all
    .filter(matchesFilters)
    .filter(item => matchesQuery(item, query))
    .sort((a,b) => b.createdAt - a.createdAt);

  results.innerHTML = "";
  resultsInfo.textContent = `النتائج: ${filtered.length} سجل`;

  if(filtered.length === 0){
    results.innerHTML = `<div class="muted">لا توجد نتائج.</div>`;
    return;
  }

  filtered.slice(0, 200).forEach(item => renderItem(item, results));
  if(filtered.length > 200){
    const more = document.createElement("div");
    more.className = "muted";
    more.textContent = "تم عرض أول 200 نتيجة فقط لتخفيف الحمل.";
    results.appendChild(more);
  }
}

btnSearch.addEventListener("click", runSearch);
btnResetSearch.addEventListener("click", async () => {
  q.value = "";
  filterKind.value = "";
  filterBranch.value = "";
  await runSearch();
});

// -------- Latest
async function refreshLatest(){
  const all = await getAllEntries();
  const sorted = all.sort((a,b) => b.createdAt - a.createdAt);
  const slice = sorted.slice(0, 10);

  latest.innerHTML = "";
  if(slice.length === 0){
    latest.innerHTML = `<div class="muted">لا توجد مدخلات بعد.</div>`;
    return;
  }
  slice.forEach(item => renderItem(item, latest));
}

// -------- Export / Import (نفس المنطق السابق لكن مبسط)
function downloadJSON(filename, data){
  const blob = new Blob([JSON.stringify(data, null, 2)], { type:"application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

btnExport.addEventListener("click", async () => {
  const all = await getAllEntries();
  if(all.length === 0){
    alert("لا توجد بيانات لتصديرها.");
    return;
  }
  downloadJSON("LegalMind_export.json", { entries: all });
});

btnImport.addEventListener("click", () => importFile.click());

importFile.addEventListener("change", async () => {
  const file = importFile.files?.[0];
  if(!file) return;

  try{
    const text = await file.text();
    const data = JSON.parse(text);
    const arr = Array.isArray(data) ? data : (data.entries || []);
    if(!Array.isArray(arr)) throw new Error("صيغة الملف غير صحيحة.");

    let added = 0;
    for(const item of arr){
      const entry = {
        kind: item.kind || "مبدأ",
        branch: item.branch || "عام",
        court: item.court || "محكمة التمييز",
        appealNo: item.appealNo || "",
        circuitNo: item.circuitNo || "",
        sessionDate: item.sessionDate || "",
        meta: item.meta || "",
        body: item.body || "",
        createdAt: item.createdAt || Date.now(),
      };
      if(!entry.body.trim()) continue;
      await addEntry(entry);
      added++;
    }

    alert(`تم الاستيراد. تمت إضافة: ${added} سجل.`);
    await refreshLatest();
    await runSearch();
    await updateDBSize();
  }catch(err){
    alert("فشل الاستيراد: " + (err?.message || err));
  }finally{
    importFile.value = "";
  }
});

// -------- Wipe
btnWipe.addEventListener("click", async () => {
  const ok = confirm("تحذير: سيتم مسح القاعدة بالكامل من هذا الجهاز/المتصفح. هل أنت متأكد؟");
  if(!ok) return;
  await clearDB();
  results.innerHTML = "";
  latest.innerHTML = "";
  resultsInfo.textContent = "تم مسح القاعدة.";
  await refreshLatest();
  await updateDBSize();
});

// -------- DB Size
function formatBytes(bytes){
  if(bytes === 0) return "0 بايت";
  const units = ["بايت","كيلوبايت","ميغابايت","غيغابايت"];
  const k = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const val = (bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 2);
  return `${val} ${units[i] || units[units.length-1]}`;
}

async function updateDBSize(){
  try{
    const all = await getAllEntries();
    const count = all.length;
    const jsonStr = JSON.stringify(all);
    const size = new Blob([jsonStr]).size;
    dbSizeInfo.textContent = `حجم القاعدة: ${formatBytes(size)} — عدد السجلات: ${count}`;
  }catch(e){
    dbSizeInfo.textContent = "تعذّر حساب الحجم";
  }
}

// -------- Initial
(async function init(){
  updateCircuitPrefix();
  updateMetaPreview();
  await refreshLatest();
  await runSearch();
  await updateDBSize();
  setStatus("جاهز للإدخال.");
})();
