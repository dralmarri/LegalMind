/* ============================================================
   app.js — منطق الواجهة الرئيسي
   ============================================================ */

const el = (id) => document.getElementById(id);

/* ---------- الحالة العامة ---------- */
let allSources = [];        // نسخة في الذاكرة من كل المصادر
let selectedTopics = [];    // مواضيع النموذج الجاري إدخاله
let editingId = null;       // معرّف المصدر الجاري تعديله (null = إضافة)
let askAbort = null;        // للتحكم بإيقاف بث الإجابة

const SETTINGS_KEY = "lm_settings_v1";
function loadSettings() {
  try { return JSON.parse(localStorage.getItem(SETTINGS_KEY)) || {}; }
  catch (_) { return {}; }
}
function saveSettings(s) { localStorage.setItem(SETTINGS_KEY, JSON.stringify(s)); }

/* ---------- الثيم ---------- */
(function initTheme() {
  document.documentElement.dataset.theme = localStorage.getItem("lm_theme") || "light";
})();
el("btnTheme").addEventListener("click", () => {
  const next = (document.documentElement.dataset.theme === "light") ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("lm_theme", next);
});

/* ---------- التبويبات ---------- */
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${name}`));
}

/* ---------- تعبئة القوائم الثابتة ---------- */
function fillSelect(select, values, { keepFirst = false } = {}) {
  const first = keepFirst ? select.querySelector("option") : null;
  select.innerHTML = "";
  if (first) select.appendChild(first);
  for (const v of values) {
    const o = document.createElement("option");
    o.value = v; o.textContent = v;
    select.appendChild(o);
  }
}

fillSelect(el("branch"), LEGAL_BRANCHES);
fillSelect(el("court"), KUWAIT_COURTS);
fillSelect(el("templateCategory"), KUWAIT_TEMPLATE_CATEGORIES);
fillSelect(el("filterBranch"), LEGAL_BRANCHES, { keepFirst: true });
fillSelect(el("qaBranch"), LEGAL_BRANCHES, { keepFirst: true });

(function fillCircuits() {
  const sel = el("circuitNo");
  sel.innerHTML = `<option value="" selected>— رقم الدائرة —</option>`;
  for (let i = 1; i <= 10; i++) {
    const o = document.createElement("option");
    o.value = String(i); o.textContent = String(i);
    sel.appendChild(o);
  }
})();

(function fillDatalists() {
  const lawsList = el("kuwaitLawsList");
  for (const law of KUWAIT_LAWS) {
    const o = document.createElement("option");
    o.value = law.key;
    lawsList.appendChild(o);
  }
  const topicsList = el("topicsList");
  for (const t of Object.keys(TOPIC_KEYWORDS)) {
    const o = document.createElement("option");
    o.value = t;
    topicsList.appendChild(o);
  }
})();

(function fillModels() {
  const sel = el("aiModel");
  for (const m of AI_MODELS) {
    const o = document.createElement("option");
    o.value = m.id; o.textContent = m.label;
    sel.appendChild(o);
  }
})();

/* ---------- نموذج الإضافة: إظهار الحقول حسب النوع ---------- */
function updateFormForType() {
  const type = el("srcType").value;
  document.querySelectorAll(".ruling-only").forEach((n) => (n.hidden = type !== "ruling"));
  document.querySelectorAll(".law-only").forEach((n) => (n.hidden = type !== "law"));
  document.querySelectorAll(".template-only").forEach((n) => (n.hidden = type !== "template"));
  el("bodyLabel").textContent =
    type === "law" ? "النص الكامل للقانون (سيُفصَّل تلقائياً إلى مواد: مادة 1، مادة 2...)"
    : type === "template" ? "نص النموذج الكامل (بالصيغة المتبعة أمام المحاكم الكويتية)"
    : "نص الحكم/المبدأ (يمكن آلاف الكلمات)";
  updateExtractPreview();
}
el("srcType").addEventListener("change", updateFormForType);

/* ---------- بيانات الطعن التلقائية ---------- */
function updateCircuitPrefix() { el("circuitPrefix").value = `${el("branch").value.trim()}/`; }
function buildMeta() {
  const b = el("branch").value.trim();
  const c = el("circuitNo").value.trim();
  const dt = formatDateDDMMYYYY(el("sessionDate").value);
  let left = `${b}/`;
  if (c) left += c;
  const right = dt ? `جلسة ${dt}` : "";
  return [left, right].filter(Boolean).join(" ").trim();
}
function updateMetaPreview() { el("metaPreview").value = buildMeta(); }
el("branch").addEventListener("change", () => { updateCircuitPrefix(); updateMetaPreview(); });
el("circuitNo").addEventListener("change", updateMetaPreview);
el("sessionDate").addEventListener("change", updateMetaPreview);

/* ---------- المواضيع (chips) ---------- */
function renderTopicChips() {
  const wrap = el("topicChips");
  wrap.innerHTML = "";
  if (!selectedTopics.length) {
    wrap.innerHTML = `<span class="muted" style="font-size:12px">لا مواضيع بعد — اكتب موضوعاً أو استخدم الاقتراح التلقائي.</span>`;
    return;
  }
  selectedTopics.forEach((t, i) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.innerHTML = `${escapeHTML(t)} <button type="button" class="chip-x" data-i="${i}">×</button>`;
    chip.querySelector(".chip-x").addEventListener("click", () => {
      selectedTopics.splice(i, 1);
      renderTopicChips();
    });
    wrap.appendChild(chip);
  });
}
el("topicInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    const v = el("topicInput").value.trim();
    if (v && !selectedTopics.includes(v)) { selectedTopics.push(v); renderTopicChips(); }
    el("topicInput").value = "";
  }
});
el("btnSuggestTopics").addEventListener("click", () => {
  const body = el("bodyText").value;
  if (!body.trim()) { setSaveStatus("الصق النص أولاً ثم اطلب الاقتراح.", true); return; }
  const suggested = classifyTopics(body, 5);
  let added = 0;
  for (const t of suggested) {
    if (!selectedTopics.includes(t)) { selectedTopics.push(t); added++; }
  }
  renderTopicChips();
  // اقتراح الفرع أيضاً إن كان "عام"
  if (el("branch").value === "عام") {
    const b = suggestBranch(body);
    if (b !== "عام") { el("branch").value = b; updateCircuitPrefix(); updateMetaPreview(); }
  }
  setSaveStatus(added ? `تمت إضافة ${added} موضوعاً مقترحاً ✨` : "لم تُكتشف مواضيع جديدة من النص.");
});

/* ---------- معاينة الاستخلاص أثناء الكتابة ---------- */
let extractTimer = null;
el("bodyText").addEventListener("input", () => {
  clearTimeout(extractTimer);
  extractTimer = setTimeout(updateExtractPreview, 600);
});
function updateExtractPreview() {
  const type = el("srcType").value;
  const body = el("bodyText").value;
  const box = el("extractPreview");
  if (!body.trim()) { box.hidden = true; return; }

  if (type === "law") {
    const parsed = parseLawArticles(body);
    if (parsed.articles.length) {
      box.hidden = false;
      box.innerHTML = `📑 تم التعرف تلقائياً على <b>${parsed.articles.length}</b> مادة (من المادة ${escapeHTML(parsed.articles[0].no)} إلى المادة ${escapeHTML(parsed.articles[parsed.articles.length - 1].no)}). كل مادة ستصبح وحدة بحث واستشهاد مستقلة.`;
    } else {
      box.hidden = false;
      box.innerHTML = `⚠️ لم يتم التعرف على مواد. تأكد أن كل مادة تبدأ بسطر جديد بصيغة: <b>مادة 1</b> أو <b>المادة (1)</b>. سيُحفظ النص كوحدة واحدة إن لم تُكتشف مواد.`;
    }
  } else if (type === "ruling") {
    const refs = extractArticleRefs(body);
    if (refs.length) {
      const shown = refs.slice(0, 8).map((r) => {
        const law = r.lawKey || r.lawHint || "قانون غير محدد";
        return `المادة ${r.article}${r.extra ? " " + r.extra : ""} (${escapeHTML(law)})`;
      }).join("، ");
      box.hidden = false;
      box.innerHTML = `🔗 مواد قانونية مُشار إليها في الحكم (ستُربط تلقائياً بالنصوص المرفوعة): ${shown}${refs.length > 8 ? ` <span class="muted">+${refs.length - 8} أخرى</span>` : ""}`;
    } else {
      box.hidden = true;
    }
  } else {
    box.hidden = true;
  }
}

/* ---------- الحفظ ---------- */
function setSaveStatus(msg, isError = false) {
  const n = el("saveStatus");
  n.textContent = msg;
  n.style.color = isError ? "var(--danger)" : "";
}

function buildSourceFromForm() {
  const type = el("srcType").value;
  const body = el("bodyText").value.trim();
  const branch = el("branch").value.trim();
  const now = Date.now();

  const base = { type, branch, topics: [...selectedTopics], body, updatedAt: now };

  if (type === "ruling") {
    return {
      ...base,
      kind: el("entryKind").value,
      court: el("court").value,
      appealNo: el("appealNo").value.trim(),
      circuitNo: el("circuitNo").value.trim(),
      sessionDate: el("sessionDate").value || "",
      meta: buildMeta(),
      title: el("appealNo").value.trim() ? `طعن ${el("appealNo").value.trim()}` : (el("entryKind").value + " قضائي"),
      citedArticles: extractArticleRefs(body),
    };
  }
  if (type === "law") {
    const title = el("lawTitle").value.trim();
    const parsed = parseLawArticles(body);
    return { ...base, title, preamble: parsed.preamble, articles: parsed.articles };
  }
  return {
    ...base,
    title: el("templateTitle").value.trim(),
    templateCategory: el("templateCategory").value,
  };
}

el("entryForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  setSaveStatus("جارٍ الحفظ...");
  try {
    const source = buildSourceFromForm();

    if (!source.body) { setSaveStatus("لم يتم الحفظ: النص فارغ.", true); return; }
    if (source.type === "law" && !source.title) { setSaveStatus("لم يتم الحفظ: اسم القانون مطلوب.", true); return; }
    if (source.type === "template" && !source.title) { setSaveStatus("لم يتم الحفظ: اسم النموذج مطلوب.", true); return; }

    if (editingId != null) {
      const old = allSources.find((s) => s.id === editingId);
      source.id = editingId;
      source.createdAt = old ? old.createdAt : Date.now();
      await dbUpdateSource(source);
      exitEditMode();
      setSaveStatus("تم حفظ التعديل بنجاح ✅");
    } else {
      source.createdAt = Date.now();
      await dbAddSource(source);
      resetFormAfterSave();
      setSaveStatus("تم الحفظ بنجاح ✅ يمكنك إدخال مصدر جديد الآن.");
    }

    await refreshData();
  } catch (err) {
    console.error("SAVE ERROR:", err);
    setSaveStatus("فشل الحفظ ❌ " + (err?.message || "المتصفح يمنع التخزين — جرّب الخروج من التصفح الخاص."), true);
  }
});

function resetFormAfterSave() {
  el("appealNo").value = "";
  el("circuitNo").value = "";
  el("sessionDate").value = "";
  el("bodyText").value = "";
  el("lawTitle").value = "";
  el("templateTitle").value = "";
  selectedTopics = [];
  renderTopicChips();
  updateCircuitPrefix();
  updateMetaPreview();
  el("extractPreview").hidden = true;
}

el("btnClearForm").addEventListener("click", () => {
  resetFormAfterSave();
  setSaveStatus("تم تفريغ الحقول.");
});

/* ---------- التعديل ---------- */
function enterEditMode(src) {
  editingId = src.id;
  el("addTitle").textContent = `تعديل مصدر #${src.id}`;
  el("btnSave").textContent = "حفظ التعديل";
  el("btnCancelEdit").hidden = false;

  el("srcType").value = src.type;
  updateFormForType();
  el("branch").value = src.branch || "عام";
  selectedTopics = [...(src.topics || [])];
  renderTopicChips();
  el("bodyText").value = src.body || "";

  if (src.type === "ruling") {
    el("entryKind").value = src.kind || "مبدأ";
    el("court").value = KUWAIT_COURTS.includes(src.court) ? src.court : "أخرى";
    el("appealNo").value = src.appealNo || "";
    el("circuitNo").value = src.circuitNo || "";
    el("sessionDate").value = src.sessionDate || "";
  } else if (src.type === "law") {
    el("lawTitle").value = src.title || "";
  } else {
    el("templateTitle").value = src.title || "";
    el("templateCategory").value = src.templateCategory || "أخرى";
  }
  updateCircuitPrefix();
  updateMetaPreview();
  updateExtractPreview();
  switchTab("add");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function exitEditMode() {
  editingId = null;
  el("addTitle").textContent = "إضافة مصدر جديد";
  el("btnSave").textContent = "حفظ";
  el("btnCancelEdit").hidden = true;
  resetFormAfterSave();
}
el("btnCancelEdit").addEventListener("click", () => { exitEditMode(); setSaveStatus("تم إلغاء التعديل."); });

/* ---------- تحديث البيانات والفهرس ---------- */
async function refreshData() {
  allSources = await dbGetAllSources();
  invalidateIndex();
  refreshTopicFilter();
  await runLibrarySearch();
  updateDBSize();
}

function refreshTopicFilter() {
  const topics = new Set();
  for (const s of allSources) for (const t of s.topics || []) topics.add(t);
  const sel = el("filterTopic");
  const current = sel.value;
  sel.innerHTML = `<option value="" selected>الكل</option>`;
  for (const t of [...topics].sort()) {
    const o = document.createElement("option");
    o.value = t; o.textContent = t;
    sel.appendChild(o);
  }
  if ([...topics].includes(current)) sel.value = current;
}

/* ---------- بحث المكتبة ---------- */
function matchesLibraryFilters(src) {
  if (el("filterType").value && src.type !== el("filterType").value) return false;
  if (el("filterBranch").value && src.branch !== el("filterBranch").value) return false;
  if (el("filterTopic").value && !(src.topics || []).includes(el("filterTopic").value)) return false;
  return true;
}

async function runLibrarySearch() {
  const query = el("q").value.trim();
  let list = allSources.filter(matchesLibraryFilters);

  if (query) {
    const qNorm = normalizeArabic(query);
    const qTokens = tokenize(query);
    list = list
      .map((src) => {
        const hay = normalizeArabic([src.title, src.kind, src.court, src.appealNo, src.meta, (src.topics || []).join(" "), src.body].filter(Boolean).join(" "));
        let score = 0;
        if (hay.includes(qNorm)) score += 10;
        for (const t of qTokens) if (hay.includes(t)) score += 1;
        return { src, score };
      })
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score)
      .map((x) => x.src);
  } else {
    list = list.sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0));
  }

  const counts = { ruling: 0, law: 0, template: 0 };
  for (const s of allSources) counts[s.type] = (counts[s.type] || 0) + 1;
  el("resultsInfo").textContent =
    `النتائج: ${list.length} — المكتبة: ${counts.ruling} حكم/مبدأ، ${counts.law} نص قانوني، ${counts.template} نموذج`;

  const container = el("results");
  container.innerHTML = "";
  if (!list.length) {
    container.innerHTML = `<div class="muted">لا توجد نتائج. أضف مصادر من تبويب "إضافة مصدر".</div>`;
    return;
  }
  list.slice(0, 100).forEach((src) => container.appendChild(renderSourceCard(src)));
  if (list.length > 100) {
    const more = document.createElement("div");
    more.className = "muted";
    more.textContent = `تم عرض أول 100 نتيجة من ${list.length}.`;
    container.appendChild(more);
  }
}

el("btnSearch").addEventListener("click", runLibrarySearch);
el("q").addEventListener("keydown", (e) => { if (e.key === "Enter") runLibrarySearch(); });
["filterType", "filterBranch", "filterTopic"].forEach((id) => el(id).addEventListener("change", runLibrarySearch));
el("btnResetSearch").addEventListener("click", async () => {
  el("q").value = ""; el("filterType").value = ""; el("filterBranch").value = ""; el("filterTopic").value = "";
  await runLibrarySearch();
});

/* ---------- بطاقات المصادر ---------- */
function typeBadge(src) {
  if (src.type === "law") return `<span class="badge badge-law">نص قانوني</span>`;
  if (src.type === "template") return `<span class="badge badge-template">نموذج${src.templateCategory ? ": " + escapeHTML(src.templateCategory) : ""}</span>`;
  return `<span class="badge badge-ruling">${escapeHTML(src.kind || "حكم")}</span>`;
}

function renderSourceCard(src) {
  const div = document.createElement("div");
  div.className = "item";
  div.dataset.sourceId = src.id;

  const badges = [typeBadge(src)];
  if (src.branch) badges.push(`<span class="badge">${escapeHTML(src.branch)}</span>`);
  if (src.type === "ruling") {
    if (src.court) badges.push(`<span class="badge">${escapeHTML(src.court)}</span>`);
    if (src.appealNo) badges.push(`<span class="badge">طعن: ${escapeHTML(src.appealNo)}</span>`);
    if (src.meta) badges.push(`<span class="badge">${escapeHTML(src.meta)}</span>`);
  }
  const topicChips = (src.topics || [])
    .map((t) => `<span class="chip chip-topic" data-topic="${escapeHTML(t)}">${escapeHTML(t)}</span>`)
    .join("");

  let linksHTML = "";
  if (src.type === "ruling" && (src.citedArticles || []).length) {
    const laws = allSources.filter((s) => s.type === "law");
    const links = linkRulingToLaws(src, laws);
    const chips = links.slice(0, 10).map((l) => {
      const label = `المادة ${l.article}${l.extra ? " " + l.extra : ""}${l.lawTitle ? " — " + escapeHTML(l.lawTitle) : ""}`;
      if (l.lawId && l.found) {
        return `<button type="button" class="chip chip-link" data-law="${l.lawId}" data-article="${escapeHTML(l.article)}" title="عرض نص المادة">🔗 ${label}</button>`;
      }
      return `<span class="chip chip-unlinked" title="النص القانوني غير مرفوع في المكتبة بعد">${label}</span>`;
    }).join("");
    linksHTML = `<div class="links-row"><span class="links-label">النصوص القانونية المُشار إليها:</span>${chips}</div>`;
  }

  let lawArticlesHTML = "";
  if (src.type === "law" && (src.articles || []).length) {
    lawArticlesHTML = `
      <div class="law-info muted">📑 ${src.articles.length} مادة ${citingCountLabel(src)}</div>
      <button type="button" class="btn btn-mini toggle-articles">عرض المواد</button>
      <div class="articles-list" hidden></div>`;
  }

  const bodyPreview = (src.body || "").slice(0, 500);
  const hasMore = (src.body || "").length > 500;
  const title = src.type !== "ruling" && src.title ? `<div class="src-title">${escapeHTML(src.title)}</div>` : "";

  div.innerHTML = `
    <div class="item-top">
      <div>
        <div class="badges">${badges.join("")}</div>
        ${title}
        ${topicChips ? `<div class="topics-row">${topicChips}</div>` : ""}
        <div class="meta">أُضيف: ${escapeHTML(new Date(src.createdAt).toLocaleString("ar-KW"))}</div>
      </div>
      <div class="item-actions">
        <button class="btn btn-edit" type="button" data-act="edit">تعديل</button>
        <button class="btn btn-danger" type="button" data-act="del">حذف</button>
      </div>
    </div>
    ${linksHTML}
    ${lawArticlesHTML}
    <div class="body">${escapeHTML(bodyPreview)}${hasMore ? `<button type="button" class="btn btn-mini show-more">... عرض الكل</button>` : ""}</div>
  `;

  div.querySelector('[data-act="edit"]').addEventListener("click", () => enterEditMode(src));
  div.querySelector('[data-act="del"]').addEventListener("click", async () => {
    if (!confirm(`تأكيد حذف هذا المصدر؟\n${src.title || src.meta || ""}`)) return;
    await dbDeleteSource(src.id);
    if (editingId === src.id) exitEditMode();
    await refreshData();
  });

  const showMore = div.querySelector(".show-more");
  if (showMore) showMore.addEventListener("click", () => {
    div.querySelector(".body").innerHTML = escapeHTML(src.body || "");
  });

  const toggleArts = div.querySelector(".toggle-articles");
  if (toggleArts) toggleArts.addEventListener("click", () => {
    const listDiv = div.querySelector(".articles-list");
    if (listDiv.hidden) {
      renderLawArticles(src, listDiv);
      listDiv.hidden = false;
      toggleArts.textContent = "إخفاء المواد";
    } else {
      listDiv.hidden = true;
      toggleArts.textContent = "عرض المواد";
    }
  });

  div.querySelectorAll(".chip-topic").forEach((c) => c.addEventListener("click", () => {
    el("filterTopic").value = c.dataset.topic;
    switchTab("library");
    runLibrarySearch();
  }));

  div.querySelectorAll(".chip-link").forEach((c) => c.addEventListener("click", () => {
    openLawArticle(parseInt(c.dataset.law, 10), c.dataset.article);
  }));

  return div;
}

/* عدد الأحكام التي تستشهد بهذا القانون */
function citingCountLabel(law) {
  let count = 0;
  for (const s of allSources) {
    if (s.type !== "ruling") continue;
    const links = linkRulingToLaws(s, [law]);
    if (links.some((l) => l.lawId === law.id)) count++;
  }
  return count ? `· يستشهد به ${count} حكم/مبدأ في المكتبة` : "";
}

function renderLawArticles(law, container) {
  container.innerHTML = "";
  const rulings = allSources.filter((s) => s.type === "ruling");
  for (const art of law.articles || []) {
    const artNo = String(art.no).split(" ")[0];
    // الأحكام التي تشير لهذه المادة من هذا القانون
    const citing = rulings.filter((r) =>
      linkRulingToLaws(r, [law]).some((l) => l.lawId === law.id && String(l.article) === artNo)
    );
    const d = document.createElement("div");
    d.className = "law-article";
    d.dataset.articleNo = artNo;
    d.innerHTML = `
      <div class="law-article-head"><b>المادة ${escapeHTML(art.no)}</b>
        ${citing.length ? `<span class="badge badge-cite">⚖️ ${citing.length} حكم يطبّقها</span>` : ""}
      </div>
      <div class="law-article-text">${escapeHTML(art.text)}</div>
      ${citing.length ? `<div class="citing-list">${citing.map((r) =>
        `<button type="button" class="chip chip-link" data-ruling="${r.id}">${escapeHTML(r.kind || "حكم")}${r.appealNo ? " — طعن " + escapeHTML(r.appealNo) : ""}${r.meta ? " — " + escapeHTML(r.meta) : ""}</button>`
      ).join("")}</div>` : ""}
    `;
    d.querySelectorAll("[data-ruling]").forEach((btn) => btn.addEventListener("click", () => {
      scrollToSourceInLibrary(parseInt(btn.dataset.ruling, 10));
    }));
    container.appendChild(d);
  }
}

function openLawArticle(lawId, articleNo) {
  switchTab("library");
  el("q").value = ""; el("filterType").value = ""; el("filterBranch").value = ""; el("filterTopic").value = "";
  runLibrarySearch().then(() => {
    const card = document.querySelector(`.item[data-source-id="${lawId}"]`);
    if (!card) return;
    const toggle = card.querySelector(".toggle-articles");
    const listDiv = card.querySelector(".articles-list");
    if (toggle && listDiv && listDiv.hidden) toggle.click();
    card.scrollIntoView({ behavior: "smooth", block: "start" });
    const artDiv = card.querySelector(`.law-article[data-article-no="${CSS.escape(String(articleNo))}"]`);
    if (artDiv) {
      artDiv.classList.add("flash");
      artDiv.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => artDiv.classList.remove("flash"), 2500);
    }
  });
}

function scrollToSourceInLibrary(id) {
  switchTab("library");
  el("q").value = ""; el("filterType").value = ""; el("filterBranch").value = ""; el("filterTopic").value = "";
  runLibrarySearch().then(() => {
    const card = document.querySelector(`.item[data-source-id="${id}"]`);
    if (card) {
      card.classList.add("flash");
      card.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => card.classList.remove("flash"), 2500);
    }
  });
}

/* ---------- المستشار القانوني (سؤال وجواب) ---------- */
function setQaStatus(msg, isError = false) {
  const n = el("qaStatus");
  n.textContent = msg;
  n.style.color = isError ? "var(--danger)" : "";
}

el("btnAsk").addEventListener("click", handleAsk);
el("qaQuestion").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleAsk();
});
el("btnStopAsk").addEventListener("click", () => { if (askAbort) askAbort.abort(); });

async function handleAsk() {
  const question = el("qaQuestion").value.trim();
  if (!question) { setQaStatus("اكتب سؤالك أولاً.", true); return; }
  if (!allSources.length) {
    setQaStatus("المكتبة فارغة — أضف نصوصاً قانونية وأحكاماً ونماذج أولاً من تبويب «إضافة مصدر».", true);
    return;
  }

  const settings = loadSettings();
  const topK = parseInt(settings.topK || "12", 10);
  const filters = {};
  if (el("qaBranch").value) filters.branch = el("qaBranch").value;

  // 1) الاسترجاع
  setQaStatus("🔎 جارٍ البحث في مصادرك...");
  el("qaAnswer").hidden = true; el("qaAnswer").innerHTML = "";
  el("qaVerification").hidden = true; el("qaVerification").innerHTML = "";
  el("qaSources").innerHTML = ""; el("qaSourcesHead").hidden = true;

  const results = retrieve(question, allSources, topK, filters);
  if (!results.length) {
    setQaStatus("لا توجد مقاطع ذات صلة بسؤالك في المصادر المرفوعة. جرّب صياغة أخرى أو ارفع مصادر في هذا الموضوع.", true);
    return;
  }

  renderQaSources(results, new Set());

  // 2) بدون مفتاح: وضع الاسترجاع الاستنادي
  if (!settings.apiKey) {
    setQaStatus(`عرضت لك أدق ${results.length} مقطعاً من مصادرك (وضع الاسترجاع الاستنادي). لتفعيل الإجابة الذكية أدخل مفتاح API من الإعدادات.`);
    el("qaSourcesHead").hidden = false;
    return;
  }

  // 3) الإجابة الذكية
  askAbort = new AbortController();
  el("btnAsk").disabled = true;
  el("btnStopAsk").hidden = false;
  setQaStatus("⚖️ المستشار يحلل المصادر ويعدّ الرأي القانوني...");
  el("qaAnswer").hidden = false;

  try {
    const answer = await askClaude({
      apiKey: settings.apiKey,
      model: settings.model || AI_MODELS[0].id,
      question,
      results,
      signal: askAbort.signal,
      onDelta: (_delta, full) => {
        el("qaAnswer").innerHTML = renderAnswerHTML(full, results, null);
      },
    });

    // التحقق من الاقتباسات وإبراز المصادر المستشهد بها
    const quotes = verifyQuotes(answer, results);
    const cited = new Set(extractCitedSourceNumbers(answer, results.length));
    el("qaAnswer").innerHTML = renderAnswerHTML(answer, results, quotes);
    renderQaSources(results, cited);
    el("qaSourcesHead").hidden = false;
    renderVerification(quotes, cited, results.length);
    setQaStatus("✅ اكتمل الرأي القانوني — كل معلومة موثقة بمصدرها أدناه.");
  } catch (err) {
    if (err.name === "AbortError") {
      setQaStatus("تم إيقاف الإجابة.");
    } else {
      console.error(err);
      setQaStatus("تعذر توليد الإجابة: " + (err.message || err), true);
      el("qaSourcesHead").hidden = false;
    }
  } finally {
    el("btnAsk").disabled = false;
    el("btnStopAsk").hidden = true;
    askAbort = null;
  }
}

/* تحويل نص الإجابة إلى HTML آمن مع توثيق تفاعلي */
function renderAnswerHTML(text, results, quotes) {
  let html = escapeHTML(text);

  // عناوين غامقة **...**
  html = html.replace(/\*\*([^*\n]{1,80})\*\*/g, "<strong>$1</strong>");

  // الاستشهادات 【N】 → أزرار
  html = html.replace(/【(?:المصدر\s*)?(\d{1,2})】/g, (m, n) => {
    const num = parseInt(n, 10);
    if (num >= 1 && num <= results.length) {
      return `<button type="button" class="cite" data-cite="${num}" title="عرض المصدر ${num}">${num}</button>`;
    }
    return m;
  });

  // الاقتباسات «...» مع حالة التحقق
  let qi = 0;
  html = html.replace(/«([^»]{8,})»/g, (m, q) => {
    let cls = "quote";
    if (quotes && quotes[qi]) cls += quotes[qi].verified ? " quote-ok" : " quote-warn";
    qi++;
    return `<span class="${cls}" title="${quotes && quotes[qi - 1] ? (quotes[qi - 1].verified ? "اقتباس متحقق منه حرفياً ✓" : "تعذر التحقق الآلي من هذا الاقتباس — راجع المصدر") : ""}">«${q}»</span>`;
  });

  html = html.replace(/\n/g, "<br>");

  // تفعيل أزرار الاستشهاد بعد الإدراج
  setTimeout(() => {
    el("qaAnswer").querySelectorAll(".cite").forEach((btn) => {
      btn.onclick = () => {
        const card = el("qaSources").querySelector(`[data-qa-source="${btn.dataset.cite}"]`);
        if (card) {
          card.classList.add("flash");
          card.scrollIntoView({ behavior: "smooth", block: "center" });
          setTimeout(() => card.classList.remove("flash"), 2500);
        }
      };
    });
  }, 0);

  return html;
}

function renderQaSources(results, citedSet) {
  const container = el("qaSources");
  container.innerHTML = "";
  results.forEach((r, i) => {
    const n = i + 1;
    const src = r.chunk.source;
    const d = document.createElement("div");
    d.className = "item qa-source" + (citedSet.has(n) ? " qa-source-cited" : "");
    d.dataset.qaSource = n;
    d.innerHTML = `
      <div class="item-top">
        <div>
          <div class="badges">
            <span class="badge badge-num">${n}</span>
            ${typeBadge(src)}
            ${citedSet.has(n) ? `<span class="badge badge-cite">✓ استُشهد به في الإجابة</span>` : ""}
          </div>
          <div class="src-title">${escapeHTML(r.chunk.label)}</div>
        </div>
        <button class="btn btn-mini" type="button" data-open="${src.id}">فتح في المكتبة</button>
      </div>
      <div class="body qa-source-text">${escapeHTML(r.chunk.text)}</div>
    `;
    d.querySelector("[data-open]").addEventListener("click", () => scrollToSourceInLibrary(src.id));
    container.appendChild(d);
  });
}

function renderVerification(quotes, cited, totalSources) {
  const box = el("qaVerification");
  const okCount = quotes.filter((q) => q.verified).length;
  const warnCount = quotes.length - okCount;
  const parts = [];
  parts.push(`🛡️ <b>فحص مضاد للهلوسة:</b> استُشهد بـ ${cited.size} من ${totalSources} مصدراً مسترجعاً.`);
  if (quotes.length) {
    parts.push(`الاقتباسات الحرفية: <span class="v-ok">${okCount} متحقق ✓</span>${warnCount ? ` · <span class="v-warn">${warnCount} يحتاج مراجعة يدوية ⚠</span>` : ""}.`);
  }
  if (!cited.size) {
    parts.push(`<span class="v-warn">⚠ الإجابة لم تستشهد بأي مصدر — تعامل معها بحذر وراجع المقاطع أدناه بنفسك.</span>`);
  }
  box.innerHTML = parts.join(" ");
  box.hidden = false;
}

/* ---------- الإعدادات ---------- */
(function initSettings() {
  const s = loadSettings();
  if (s.apiKey) el("apiKey").value = s.apiKey;
  if (s.model) el("aiModel").value = s.model;
  if (s.topK) el("topK").value = s.topK;
})();

el("btnShowKey").addEventListener("click", () => {
  const inp = el("apiKey");
  inp.type = inp.type === "password" ? "text" : "password";
});

el("btnSaveSettings").addEventListener("click", () => {
  saveSettings({
    apiKey: el("apiKey").value.trim(),
    model: el("aiModel").value,
    topK: el("topK").value,
  });
  const n = el("settingsStatus");
  n.textContent = "تم حفظ الإعدادات ✅" + (el("apiKey").value.trim() ? " — المستشار الذكي مفعّل." : " — لا يوجد مفتاح: وضع الاسترجاع الاستنادي.");
});

/* ---------- تصدير / استيراد ---------- */
el("btnExport").addEventListener("click", async () => {
  const sources = await dbGetAllSources();
  if (!sources.length) { alert("لا توجد بيانات لتصديرها."); return; }
  const blob = new Blob([JSON.stringify({ version: 2, app: "LegalMind", exportedAt: new Date().toISOString(), sources }, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `LegalMind_export_${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

el("btnImport").addEventListener("click", () => el("importFile").click());
el("importFile").addEventListener("change", async () => {
  const file = el("importFile").files?.[0];
  if (!file) return;
  try {
    const data = JSON.parse(await file.text());
    let items = [];
    if (Array.isArray(data)) items = data;                    // مصفوفة خام
    else if (Array.isArray(data.sources)) items = data.sources; // تصدير v2
    else if (Array.isArray(data.entries)) items = data.entries; // تصدير v1 القديم
    else throw new Error("صيغة الملف غير معروفة.");

    let added = 0;
    for (const item of items) {
      let source;
      if (item.type === "law" || item.type === "template" || item.type === "ruling") {
        source = { ...item };
        delete source.id;
        source.createdAt = item.createdAt || Date.now();
        source.updatedAt = Date.now();
        if (source.type === "ruling" && !source.citedArticles) source.citedArticles = extractArticleRefs(source.body || "");
        if (source.type === "law" && !source.articles) {
          const parsed = parseLawArticles(source.body || "");
          source.articles = parsed.articles;
          source.preamble = parsed.preamble;
        }
        if (!source.topics) source.topics = classifyTopics(source.body || "");
      } else {
        source = migrateOldEntry(item); // سجل من الإصدار الأول
      }
      if (!(source.body || "").trim()) continue;
      await dbAddSource(source);
      added++;
    }
    alert(`تم الاستيراد بنجاح: ${added} مصدراً.`);
    await refreshData();
  } catch (err) {
    alert("فشل الاستيراد: " + (err?.message || err));
  } finally {
    el("importFile").value = "";
  }
});

/* ---------- المسح الكامل ---------- */
el("btnWipe").addEventListener("click", async () => {
  if (!confirm("تحذير: سيتم مسح المكتبة بالكامل من هذا الجهاز (نصوص + أحكام + نماذج). هل أنت متأكد؟")) return;
  if (!confirm("تأكيد أخير: لا يمكن التراجع. هل صدّرت نسخة احتياطية؟")) return;
  await dbClearAll();
  await refreshData();
  alert("تم مسح القاعدة.");
});

/* ---------- حجم القاعدة ---------- */
function formatBytes(bytes) {
  if (!bytes) return "0 بايت";
  const units = ["بايت", "كيلوبايت", "ميغابايت", "غيغابايت"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 2)} ${units[i]}`;
}
function updateDBSize() {
  try {
    const size = new Blob([JSON.stringify(allSources)]).size;
    const counts = { ruling: 0, law: 0, template: 0 };
    let articleCount = 0;
    for (const s of allSources) {
      counts[s.type] = (counts[s.type] || 0) + 1;
      if (s.type === "law") articleCount += (s.articles || []).length;
    }
    el("dbSizeInfo").textContent =
      `المكتبة: ${counts.ruling} حكم/مبدأ · ${counts.law} قانون (${articleCount} مادة) · ${counts.template} نموذج — الحجم: ${formatBytes(size)}`;
  } catch (_) {
    el("dbSizeInfo").textContent = "تعذر حساب الحجم";
  }
}

/* ---------- الإقلاع ---------- */
(async function init() {
  updateFormForType();
  updateCircuitPrefix();
  updateMetaPreview();
  renderTopicChips();
  try {
    await refreshData();
    setSaveStatus("جاهز للإدخال.");
  } catch (err) {
    console.error("INIT ERROR:", err);
    setSaveStatus("تعذر فتح قاعدة البيانات: " + (err?.message || err), true);
  }
})();
