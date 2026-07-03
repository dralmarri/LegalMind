/* ============================================================
   db.js — طبقة التخزين (IndexedDB)
   الإصدار 2: مخزن "sources" موحّد (حكم | نص قانوني | نموذج)
   مع ترحيل تلقائي لبيانات الإصدار الأول (مخزن "entries")
   ============================================================ */

const DB_NAME = "legalmind_db_v1"; // نبقي الاسم للحفاظ على بيانات المستخدمين الحالية
const DB_VERSION = 2;
const STORE = "sources";
const OLD_STORE = "entries";

function migrateOldEntry(v) {
  const body = v.body || "";
  return {
    type: "ruling",
    kind: v.kind || "مبدأ",
    title: v.appealNo ? `طعن ${v.appealNo}` : (v.meta || "حكم قضائي"),
    branch: v.branch || "عام",
    court: v.court || "محكمة التمييز",
    appealNo: v.appealNo || "",
    circuitNo: v.circuitNo || "",
    sessionDate: v.sessionDate || "",
    meta: v.meta || "",
    topics: classifyTopics(body),
    citedArticles: extractArticleRefs(body),
    body,
    createdAt: v.createdAt || Date.now(),
    updatedAt: v.createdAt || Date.now(),
  };
}

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);

    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      const tx = e.target.transaction;

      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
        store.createIndex("by_createdAt", "createdAt", { unique: false });
        store.createIndex("by_type", "type", { unique: false });
      }

      // ترحيل بيانات الإصدار الأول إن وجدت
      if (db.objectStoreNames.contains(OLD_STORE)) {
        const oldStore = tx.objectStore(OLD_STORE);
        const newStore = tx.objectStore(STORE);
        oldStore.openCursor().onsuccess = (ev) => {
          const cursor = ev.target.result;
          if (cursor) {
            try { newStore.add(migrateOldEntry(cursor.value)); } catch (_) { /* سجل تالف — نتجاوزه */ }
            cursor.continue();
          } else {
            db.deleteObjectStore(OLD_STORE);
          }
        };
      }
    };

    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
    req.onblocked = () => reject(new Error("قاعدة البيانات مفتوحة في تبويب آخر — أغلق بقية التبويبات وحدّث الصفحة."));
  });
}

async function txStore(mode = "readonly") {
  const db = await openDB();
  const tx = db.transaction(STORE, mode);
  return { db, tx, store: tx.objectStore(STORE) };
}

function reqToPromise(req, db) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
    if (db) req.transaction.oncomplete = () => db.close();
  });
}

async function dbAddSource(source) {
  const { db, store } = await txStore("readwrite");
  return reqToPromise(store.add(source), db);
}

async function dbGetAllSources() {
  const { db, store } = await txStore("readonly");
  const result = await reqToPromise(store.getAll(), db);
  return result || [];
}

async function dbUpdateSource(source) {
  const { db, store } = await txStore("readwrite");
  return reqToPromise(store.put(source), db);
}

async function dbDeleteSource(id) {
  const { db, store } = await txStore("readwrite");
  return reqToPromise(store.delete(id), db);
}

async function dbClearAll() {
  const { db, store } = await txStore("readwrite");
  return reqToPromise(store.clear(), db);
}
