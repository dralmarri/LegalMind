/* ============================================================
   search.js — محرك الاسترجاع (BM25 على مقاطع المصادر)
   - النصوص القانونية: مقطع لكل مادة
   - الأحكام والنماذج: تقطيع بحدود الجمل مع تداخل
   ============================================================ */

const CHUNK_SIZE = 900;
const CHUNK_OVERLAP = 150;
const BM25_K1 = 1.5;
const BM25_B = 0.75;

let _index = null; // { chunks, df, avgLen, N }

function invalidateIndex() { _index = null; }

/* تقطيع نص طويل عند حدود الجمل */
function splitTextToChunks(text) {
  const t = String(text || "").trim();
  if (t.length <= CHUNK_SIZE) return t ? [t] : [];
  const chunks = [];
  let start = 0;
  while (start < t.length) {
    let end = Math.min(start + CHUNK_SIZE, t.length);
    if (end < t.length) {
      // ابحث عن أقرب نهاية جملة قبل الحد
      const window = t.slice(start + Math.floor(CHUNK_SIZE * 0.6), end);
      const lastBreak = Math.max(
        window.lastIndexOf("."), window.lastIndexOf("؛"),
        window.lastIndexOf("،"), window.lastIndexOf("\n")
      );
      if (lastBreak > 0) end = start + Math.floor(CHUNK_SIZE * 0.6) + lastBreak + 1;
    }
    chunks.push(t.slice(start, end).trim());
    if (end >= t.length) break;
    start = Math.max(end - CHUNK_OVERLAP, start + 1);
  }
  return chunks.filter(Boolean);
}

function sourceLabel(src) {
  if (src.type === "law") return `نص قانوني: ${src.title || "قانون"}`;
  if (src.type === "template") return `نموذج قانوني: ${src.title || ""}${src.templateCategory ? ` (${src.templateCategory})` : ""}`;
  const parts = [src.kind || "حكم", src.court || "", src.branch || ""];
  if (src.appealNo) parts.push(`الطعن ${src.appealNo}`);
  if (src.sessionDate) parts.push(`جلسة ${formatDateDDMMYYYY(src.sessionDate)}`);
  return parts.filter(Boolean).join(" — ");
}

function buildChunksForSource(src) {
  const out = [];
  if (src.type === "law" && Array.isArray(src.articles) && src.articles.length) {
    if (src.preamble) {
      for (const piece of splitTextToChunks(src.preamble)) {
        out.push({ sourceId: src.id, label: `${sourceLabel(src)} — الديباجة`, ref: { articleNo: null }, text: piece });
      }
    }
    for (const art of src.articles) {
      const artText = `المادة ${art.no}: ${art.text}`;
      for (const piece of splitTextToChunks(artText)) {
        out.push({ sourceId: src.id, label: `المادة ${art.no} من ${src.title || "القانون"}`, ref: { articleNo: art.no }, text: piece });
      }
    }
  } else {
    for (const piece of splitTextToChunks(src.body)) {
      out.push({ sourceId: src.id, label: sourceLabel(src), ref: {}, text: piece });
    }
  }
  return out;
}

function rebuildIndex(sources) {
  const chunks = [];
  for (const src of sources) {
    for (const ch of buildChunksForSource(src)) {
      ch.source = src;
      ch.tokens = tokenize(ch.text + " " + ch.label);
      ch.tf = new Map();
      for (const tok of ch.tokens) ch.tf.set(tok, (ch.tf.get(tok) || 0) + 1);
      ch.len = ch.tokens.length || 1;
      chunks.push(ch);
    }
  }
  const df = new Map();
  for (const ch of chunks) {
    for (const term of ch.tf.keys()) df.set(term, (df.get(term) || 0) + 1);
  }
  const avgLen = chunks.length ? chunks.reduce((s, c) => s + c.len, 0) / chunks.length : 1;
  _index = { chunks, df, avgLen, N: chunks.length };
  return _index;
}

function ensureIndex(sources) {
  if (!_index) rebuildIndex(sources);
  return _index;
}

/* البحث الاسترجاعي — يعيد أفضل k مقاطع مع درجاتها */
function retrieve(query, sources, k = 10, filters = {}) {
  const idx = ensureIndex(sources);
  const qTokens = [...new Set(tokenize(query))];
  if (!qTokens.length || !idx.N) return [];

  // أرقام واردة في السؤال (لتعزيز مطابقة أرقام المواد والطعون)
  const qNumbers = new Set((normalizeDigits(query).match(/\d{1,4}/g) || []));

  const scored = [];
  for (const ch of idx.chunks) {
    const src = ch.source;
    if (filters.branch && src.branch !== filters.branch) continue;
    if (filters.type && src.type !== filters.type) continue;

    let score = 0;
    for (const term of qTokens) {
      const tf = ch.tf.get(term);
      if (!tf) continue;
      const df = idx.df.get(term) || 1;
      const idf = Math.log(1 + (idx.N - df + 0.5) / (df + 0.5));
      score += idf * ((tf * (BM25_K1 + 1)) / (tf + BM25_K1 * (1 - BM25_B + BM25_B * (ch.len / idx.avgLen))));
    }
    if (score <= 0) continue;

    // تعزيز: مطابقة رقم مادة/طعن مذكور في السؤال
    if (qNumbers.size) {
      if (ch.ref.articleNo && qNumbers.has(String(ch.ref.articleNo).split(" ")[0])) score *= 1.6;
      if (src.appealNo && [...qNumbers].some((n) => src.appealNo.includes(n))) score *= 1.3;
    }
    scored.push({ chunk: ch, score });
  }

  scored.sort((a, b) => b.score - a.score);

  // تنويع النتائج: بحد أقصى 4 مقاطع لكل مصدر
  const perSource = new Map();
  const results = [];
  for (const item of scored) {
    const sid = item.chunk.sourceId;
    const count = perSource.get(sid) || 0;
    if (count >= 4) continue;
    perSource.set(sid, count + 1);
    results.push(item);
    if (results.length >= k) break;
  }
  return results;
}
