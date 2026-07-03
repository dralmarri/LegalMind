/* ============================================================
   ai.js — المستشار القانوني الذكي (Claude API)
   - إجابة مقيّدة حصرياً بالمصادر المرفوعة (صفر هلوزة)
   - توثيق إلزامي بأرقام المصادر 【N】
   - تحقق آلي من الاقتباسات الحرفية «...» ضد نصوص المصادر
   ============================================================ */

const ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages";
const ANTHROPIC_VERSION = "2023-06-01";

const AI_MODELS = [
  { id: "claude-opus-4-8", label: "Claude Opus 4.8 — الأدق (موصى به)" },
  { id: "claude-sonnet-5", label: "Claude Sonnet 5 — توازن السرعة والدقة" },
  { id: "claude-haiku-4-5", label: "Claude Haiku 4.5 — الأسرع والأوفر" },
];

const SYSTEM_PROMPT = `أنت "المستشار" — محامٍ كويتي محترف صاحب خبرة جبارة تتجاوز ثلاثين عاماً في الترافع أمام المحاكم الكويتية بجميع درجاتها (الجزئية، الكلية، الاستئناف، التمييز، الدستورية)، ومستشار قانوني فذّ متعمق في التشريعات الكويتية: القانون المدني (67/1980)، والمرافعات المدنية والتجارية (38/1980)، والتجارة (68/1980)، والجزاء (16/1960)، والإجراءات والمحاكمات الجزائية (17/1960)، والأحوال الشخصية (51/1984)، والعمل في القطاع الأهلي (6/2010)، والإثبات (39/1980)، وغيرها. تعرف أعراف صياغة صحف الدعاوى واللوائح والطعون والإنذارات العدلية المتبعة عملياً في المحاكم الكويتية.

⚖️ القاعدة الذهبية المطلقة — صفر هلوسة:
1. أجب حصرياً وفقط من المصادر المرقمة المرفقة مع السؤال. لا تستخدم أي معلومة من معرفتك العامة لتقرير حكم قانوني أو نص مادة أو مبدأ قضائي غير وارد في المصادر — حتى لو كنت متأكداً منها.
2. كل معلومة قانونية في إجابتك يجب أن تُوثَّق فوراً برقم مصدرها بالصيغة 【N】 حيث N رقم المصدر. المعلومة بلا توثيق ممنوعة.
3. عند النقل الحرفي من مصدر ضع النص بين علامتي «...» متبوعاً برقم المصدر. انقل بدقة حرفية تامة دون أي تغيير.
4. لا تخترع أبداً: أرقام مواد، أرقام طعون، تواريخ جلسات، أسماء قوانين، أو مبادئ قضائية غير واردة نصاً في المصادر المرفقة.
5. إذا كانت المصادر لا تكفي للإجابة (كلياً أو جزئياً) فقل بوضوح وصراحة: "لا أجد في المصادر المرفوعة ما يجيب عن هذا الشق"، واذكر ما هو الأقرب للموضوع من المصادر إن وجد، واقترح نوع المصدر الذي يلزم رفعه (نص قانوني معين، أحكام تمييز في موضوع كذا...). النقص المعلَن أفضل ألف مرة من إجابة مخترعة.
6. يجوز لك — بصفتك محامياً خبيراً — تنظيم الإجابة وتحليل المصادر والربط بينها واستنتاج التطبيق العملي، لكن كل لبنة في التحليل يجب أن تستند إلى مصدر موثّق.

📋 هيكل الإجابة (التزم به ما دام السؤال موضوعياً):
**الخلاصة:** جواب مباشر مركّز في سطرين إلى ثلاثة.
**الأساس القانوني:** النصوص القانونية ذات الصلة من المصادر مع أرقام المواد موثقة.
**التطبيق القضائي:** ما استقر عليه قضاء التمييز الكويتي من المصادر المرفقة (المبادئ والأحكام) موثقاً.
**من الناحية العملية:** نصيحة المحامي الخبير: الإجراء المتبع أمام المحاكم الكويتية، والنموذج المناسب من المصادر إن وجد (صحيفة دعوى، لائحة، إنذار...)، والمهل والاشتراطات الواردة في المصادر.
وإن كان السؤال بسيطاً فأجب بإيجاز مباشر مع التوثيق دون تكلف الهيكل.

🗣️ الأسلوب: عربية قانونية فصيحة رصينة بأسلوب المذكرات القانونية الكويتية، واثقة ومباشرة، مع دقة اصطلاحية تامة (تمييز لا نقض، المحكمة الكلية لا الابتدائية).`;

function buildUserMessage(question, results) {
  const parts = [];
  parts.push("المصادر المرفوعة في المكتبة القانونية (أجب حصرياً منها):");
  parts.push("");
  results.forEach((r, i) => {
    const n = i + 1;
    const src = r.chunk.source;
    let header = `【المصدر ${n}】 ${r.chunk.label}`;
    if (src.type === "ruling" && src.meta) header += ` — ${src.meta}`;
    if (src.topics && src.topics.length) header += ` — المواضيع: ${src.topics.join("، ")}`;
    parts.push(header);
    parts.push(r.chunk.text);
    parts.push("");
  });
  parts.push("---");
  parts.push(`سؤال الموكّل: ${question}`);
  return parts.join("\n");
}

/* استدعاء Claude مع بث تدريجي للإجابة */
async function askClaude({ apiKey, model, question, results, onDelta, signal }) {
  const body = {
    model,
    max_tokens: 8000,
    stream: true,
    system: SYSTEM_PROMPT,
    messages: [{ role: "user", content: buildUserMessage(question, results) }],
  };
  // التفكير التكيفي مدعوم على Opus 4.8 و Sonnet 5 (يحسّن دقة التحليل القانوني)
  if (model === "claude-opus-4-8" || model === "claude-sonnet-5") {
    body.thinking = { type: "adaptive" };
  }

  const resp = await fetch(ANTHROPIC_API_URL, {
    method: "POST",
    signal,
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": ANTHROPIC_VERSION,
      "anthropic-dangerous-direct-browser-access": "true",
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    let msg = `خطأ من الخادم (${resp.status})`;
    try {
      const err = await resp.json();
      const apiMsg = err?.error?.message || "";
      if (resp.status === 401) msg = "مفتاح API غير صحيح — راجع الإعدادات.";
      else if (resp.status === 429) msg = "تم تجاوز حد الاستخدام مؤقتاً — انتظر دقيقة ثم أعد المحاولة.";
      else if (resp.status === 400) msg = `طلب غير صالح: ${apiMsg}`;
      else if (resp.status >= 500) msg = "خدمة الذكاء الاصطناعي مشغولة مؤقتاً — أعد المحاولة بعد قليل.";
      else if (apiMsg) msg += `: ${apiMsg}`;
    } catch (_) { /* تجاهل فشل قراءة جسم الخطأ */ }
    throw new Error(msg);
  }

  // قراءة بث SSE
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let fullText = "";
  let stopReason = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop(); // آخر جزء قد يكون ناقصاً

    for (const evt of events) {
      const dataLine = evt.split("\n").find((l) => l.startsWith("data:"));
      if (!dataLine) continue;
      let data;
      try { data = JSON.parse(dataLine.slice(5).trim()); } catch (_) { continue; }

      if (data.type === "content_block_delta" && data.delta?.type === "text_delta") {
        fullText += data.delta.text;
        if (onDelta) onDelta(data.delta.text, fullText);
      } else if (data.type === "message_delta" && data.delta?.stop_reason) {
        stopReason = data.delta.stop_reason;
      } else if (data.type === "error") {
        throw new Error(data.error?.message || "انقطع البث من الخادم.");
      }
    }
  }

  if (stopReason === "refusal") {
    throw new Error("اعتذر النموذج عن الإجابة على هذا الطلب. أعد صياغة السؤال بشكل قانوني مهني.");
  }
  if (stopReason === "max_tokens") {
    fullText += "\n\n(انقطعت الإجابة لبلوغ الحد الأقصى — اطرح سؤالاً أضيق نطاقاً)";
  }
  return fullText;
}

/* ---------- التحقق الآلي من الاقتباسات ----------
   يستخرج كل اقتباس «...» من الإجابة ويتأكد أن نصه موجود فعلاً
   في المصادر المرفقة (بعد التطبيع). */
function verifyQuotes(answerText, results) {
  const corpus = normalizeArabic(results.map((r) => r.chunk.text).join(" ◆ "));
  const quotes = [];
  const re = /«([^»]{8,})»/g;
  let m;
  while ((m = re.exec(answerText)) !== null) {
    const quote = m[1].trim();
    const normQuote = normalizeArabic(quote).replace(/\s+/g, " ");
    // مطابقة مرنة: النص كاملاً، أو أطول مقطع متصل منه (للاقتباسات الطويلة الملتفّة على مقطعين)
    let verified = corpus.replace(/\s+/g, " ").includes(normQuote);
    if (!verified && normQuote.length > 60) {
      const half = normQuote.slice(0, Math.floor(normQuote.length / 2));
      verified = corpus.replace(/\s+/g, " ").includes(half);
    }
    quotes.push({ quote, verified });
  }
  return quotes;
}

/* استخراج أرقام المصادر المستشهد بها في الإجابة */
function extractCitedSourceNumbers(answerText, maxN) {
  const cited = new Set();
  const re = /【(?:المصدر\s*)?(\d{1,2})】/g;
  let m;
  while ((m = re.exec(answerText)) !== null) {
    const n = parseInt(m[1], 10);
    if (n >= 1 && n <= maxN) cited.add(n);
  }
  return [...cited].sort((a, b) => a - b);
}
