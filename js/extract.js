/* ============================================================
   extract.js — الاستخلاص والتصنيف القانوني (النظام الكويتي)
   - استخلاص المواد القانونية المُشار إليها في الأحكام
   - تفصيل النصوص القانونية إلى مواد
   - التصنيف التلقائي للمواضيع القانونية
   - سجل القوانين الكويتية الأساسية للربط الذكي
   ============================================================ */

/* ---------- سجل القوانين الكويتية الأساسية ----------
   يُستخدم للتعرف على القانون المقصود عند ذكره في حكم،
   وربطه بالنص القانوني المرفوع في المكتبة. */
const KUWAIT_LAWS = [
  { key: "الدستور", names: ["الدستور", "دستور الكويت", "الدستور الكويتي"] },
  { key: "القانون المدني", names: ["القانون المدني", "المرسوم بقانون 67/1980", "مرسوم بالقانون رقم 67 لسنة 1980"] },
  { key: "قانون المرافعات المدنية والتجارية", names: ["قانون المرافعات", "المرافعات المدنية والتجارية", "القانون رقم 38 لسنة 1980", "38/1980"] },
  { key: "قانون التجارة", names: ["قانون التجارة", "المرسوم بقانون 68/1980", "مرسوم بالقانون رقم 68 لسنة 1980"] },
  { key: "قانون الجزاء", names: ["قانون الجزاء", "القانون رقم 16 لسنة 1960", "16/1960"] },
  { key: "قانون الإجراءات والمحاكمات الجزائية", names: ["الاجراءات والمحاكمات الجزائية", "قانون الاجراءات الجزائية", "القانون رقم 17 لسنة 1960", "17/1960"] },
  { key: "قانون الأحوال الشخصية", names: ["الاحوال الشخصية", "القانون رقم 51 لسنة 1984", "51/1984"] },
  { key: "قانون العمل في القطاع الأهلي", names: ["قانون العمل", "القطاع الاهلي", "القانون رقم 6 لسنة 2010", "6/2010"] },
  { key: "قانون الإثبات", names: ["قانون الاثبات", "المرسوم بقانون 39/1980", "39/1980"] },
  { key: "قانون الشركات", names: ["قانون الشركات", "القانون رقم 1 لسنة 2016", "1/2016"] },
  { key: "قانون الإيجارات", names: ["ايجار العقارات", "قانون الايجارات", "المرسوم بقانون 35/1978", "35/1978"] },
  { key: "قانون تنظيم القضاء", names: ["تنظيم القضاء", "المرسوم بقانون 23/1990", "23/1990"] },
  { key: "قانون المحاماة", names: ["قانون المحاماة", "القانون رقم 42 لسنة 1964", "42/1964"] },
  { key: "قانون الوكالات التجارية", names: ["الوكالات التجارية", "القانون رقم 13 لسنة 2016"] },
  { key: "قانون حماية الآداب العامة", names: ["الاداب العامة"] },
  { key: "قانون الجرائم الإلكترونية", names: ["تقنية المعلومات", "الجرائم الالكترونية", "القانون رقم 63 لسنة 2015", "63/2015"] },
];

/* ---------- المحاكم الكويتية ---------- */
const KUWAIT_COURTS = [
  "محكمة التمييز",
  "محكمة الاستئناف",
  "المحكمة الكلية",
  "المحكمة الجزئية",
  "المحكمة الدستورية",
  "محكمة الجنايات",
  "محكمة الأسرة",
  "أخرى",
];

/* ---------- أنواع النماذج القانونية المتبعة في المحاكم الكويتية ---------- */
const KUWAIT_TEMPLATE_CATEGORIES = [
  "صحيفة دعوى",
  "لائحة استئناف",
  "صحيفة طعن بالتمييز",
  "مذكرة دفاع",
  "إنذار عدلي",
  "طلب أمر أداء",
  "طلب عارض / إدخال خصم",
  "صحيفة تظلم",
  "طلب استشكال في التنفيذ",
  "عقد",
  "توكيل",
  "إقرار / تنازل",
  "شكوى / بلاغ",
  "أخرى",
];

/* ---------- الفروع القانونية ---------- */
const LEGAL_BRANCHES = ["عام", "مدني", "تجاري", "إداري", "عمالي", "أحوال شخصية", "جزائي", "دستوري", "إيجارات"];

/* ---------- قاموس المواضيع القانونية (بصيغة مطبّعة) ---------- */
const TOPIC_KEYWORDS = {
  "العقود والالتزامات": ["عقد", "تعاقد", "متعاقد", "التزام", "ايجاب", "قبول", "فسخ", "اخلال"],
  "البطلان": ["بطلان", "باطل", "بطلانه", "باطله"],
  "الوكالة": ["وكاله", "وكيل", "توكيل", "موكل"],
  "الإيجار": ["ايجار", "مستاجر", "موجر", "اجره", "اخلاء", "ماجور"],
  "البيع": ["بيع", "مبيع", "بايع", "مشتري", "ثمن"],
  "الملكية والعقار": ["ملكيه", "عقار", "تسجيل عقاري", "حيازه", "شفعه", "قسمه", "شيوع"],
  "الميراث والتركات": ["ارث", "ميراث", "تركه", "ورثه", "وارث"],
  "الوصية": ["وصيه", "موصي", "موصي له"],
  "الزواج والطلاق": ["زواج", "طلاق", "خلع", "عده", "مهر", "زوجيه", "فرقه"],
  "النفقة": ["نفقه", "نفقات زوجيه"],
  "الحضانة": ["حضانه", "محضون", "حاضنه", "رويه"],
  "التعويض والمسؤولية": ["تعويض", "ضرر", "مسووليه", "خطا", "اضرار", "مسوول"],
  "التقادم": ["تقادم", "سقوط الحق", "انقضاء المده"],
  "الإثبات": ["اثبات", "بينه", "شهاده", "شاهد", "قرينه", "يمين", "خبره", "خبير", "محرر", "مستند"],
  "الاختصاص": ["اختصاص", "ولايه قضاييه", "اختصاص نوعي", "اختصاص قيمي"],
  "الطعن والتمييز": ["طعن", "استيناف", "تمييز", "نقض", "معارضه"],
  "الأوراق التجارية والشيك": ["شيك", "كمبياله", "سند لامر", "ورقه تجاريه", "بدون رصيد"],
  "الشركات": ["شركه", "شركاء", "مساهمه", "حصص", "تصفيه الشركه"],
  "الإفلاس": ["افلاس", "مفلس", "توقف عن الدفع", "صلح واق"],
  "العمل والعمال": ["عامل", "صاحب عمل", "اجر", "مكافاه نهايه الخدمه", "فصل تعسفي", "اجازه", "بدل انذار"],
  "الجرائم والعقوبات": ["جريمه", "عقوبه", "جنحه", "جنايه", "قصد جنايي", "سرقه", "قتل", "نصب", "احتيال", "خيانه امانه", "تزوير", "رشوه"],
  "الإجراءات الجزائية": ["تحقيق", "قبض", "حبس احتياطي", "نيابه عامه", "استجواب", "تلبس"],
  "القضاء الإداري": ["قرار اداري", "الغاء القرار", "جهه اداريه", "مناقصه", "ترقيه", "انحراف بالسلطه"],
  "التنفيذ": ["تنفيذ", "سند تنفيذي", "حجز", "استشكال"],
  "التحكيم": ["تحكيم", "محكم", "هييه تحكيم", "شرط التحكيم"],
  "الرهن والتأمينات": ["رهن", "تامين عيني", "كفاله", "كفيل", "امتياز"],
  "التأمين": ["وثيقه تامين", "مومن", "شركه التامين", "مومن له"],
  "الجرائم الإلكترونية": ["الكتروني", "تقنيه المعلومات", "انترنت", "حاسب الي"],
  "المخدرات": ["مخدر", "مخدرات", "موثرات عقليه", "احراز", "تعاطي"],
};

/* ---------- استخلاص الإشارات إلى المواد القانونية ----------
   يعمل على نسخة خفيفة التطبيع من النص (الأرقام موحدة، التشكيل محذوف)
   ويعيد: [{article: "227", extra: "مكرر", lawHint: "القانون المدني", lawKey: "القانون المدني"|null}] */
const ARTICLE_RE = /(?:ال)?ماد(?:ة|ه|تين|تان)\s*(?:رقم\s*)?\(?\s*(\d{1,4})\s*\)?(\s*مكرر(?:ا|اً)?)?/g;
const LAW_AFTER_RE = /^\s*(?:من|في)\s+((?:ال)?(?:قانون|مرسوم|دستور|لايحه|لائحة|قرار)[^.،؛:\n]{0,90})/;

function extractArticleRefs(text) {
  const light = lightNormalize(text);
  const refs = [];
  const seen = new Set();
  let m;
  ARTICLE_RE.lastIndex = 0;
  while ((m = ARTICLE_RE.exec(light)) !== null) {
    const article = m[1];
    const extra = (m[2] || "").trim();
    const after = light.slice(m.index + m[0].length, m.index + m[0].length + 120);
    const lawMatch = after.match(LAW_AFTER_RE);
    const lawHint = lawMatch ? lawMatch[1].trim().replace(/\s+/g, " ") : "";
    const lawKey = lawHint ? matchKuwaitLaw(lawHint) : null;
    const dedupeKey = `${article}|${extra}|${lawKey || lawHint}`;
    if (seen.has(dedupeKey)) continue;
    seen.add(dedupeKey);
    refs.push({ article, extra, lawHint, lawKey });
  }
  return refs;
}

/* مطابقة اسم قانون وارد في النص مع سجل القوانين الكويتية */
function matchKuwaitLaw(hint) {
  const normHint = normalizeArabic(hint);
  let best = null, bestScore = 0;
  for (const law of KUWAIT_LAWS) {
    for (const name of law.names) {
      const normName = normalizeArabic(name);
      if (normHint.includes(normName) || normName.includes(normHint)) {
        const score = normName.length;
        if (score > bestScore) { bestScore = score; best = law.key; }
      }
    }
  }
  return best;
}

/* ---------- تفصيل نص قانوني إلى مواد ----------
   يتعرف على سطور تبدأ بـ "مادة 5" / "المادة (5)" / "مادة 5 مكرر" */
const LAW_ARTICLE_LINE_RE = /^\s*\(?\s*(?:ال)?ماد(?:ة|ه)\s*\(?\s*([0-9٠-٩]{1,4})\s*\)?\s*(مكرر(?:ا|اً)?(?:\s*[أ-ي])?)?\s*[:\-–—.)]?\s*/;

function parseLawArticles(body) {
  const lines = String(body || "").split(/\r?\n/);
  const articles = [];
  let current = null;
  let preamble = [];
  for (const line of lines) {
    const m = line.match(LAW_ARTICLE_LINE_RE);
    if (m) {
      if (current) articles.push(current);
      const no = normalizeDigits(m[1]);
      const extra = (m[2] || "").trim();
      const rest = line.slice(m[0].length);
      current = { no: extra ? `${no} ${extra}` : no, text: rest ? rest + "\n" : "" };
    } else if (current) {
      current.text += line + "\n";
    } else {
      preamble.push(line);
    }
  }
  if (current) articles.push(current);
  return {
    preamble: preamble.join("\n").trim(),
    articles: articles.map((a) => ({ no: a.no, text: a.text.trim() })).filter((a) => a.text),
  };
}

/* ---------- التصنيف التلقائي للمواضيع ---------- */
function classifyTopics(text, maxTopics = 4) {
  const norm = normalizeArabic(text);
  const scores = [];
  for (const [topic, keywords] of Object.entries(TOPIC_KEYWORDS)) {
    let score = 0;
    for (const kw of keywords) {
      // عدّ مرات الظهور (بحد أقصى 5 لكل كلمة لتفادي الطغيان)
      let idx = 0, count = 0;
      while ((idx = norm.indexOf(kw, idx)) !== -1 && count < 5) { count++; idx += kw.length; }
      score += count * (kw.length > 6 ? 2 : 1);
    }
    if (score >= 2) scores.push([topic, score]);
  }
  scores.sort((a, b) => b[1] - a[1]);
  return scores.slice(0, maxTopics).map(([t]) => t);
}

/* اقتراح فرع قانوني من النص */
const BRANCH_HINTS = {
  "جزائي": ["جريمه", "عقوبه", "جنحه", "جنايه", "متهم", "نيابه عامه", "قصد جنايي"],
  "عمالي": ["عامل", "صاحب عمل", "مكافاه نهايه الخدمه", "فصل تعسفي"],
  "أحوال شخصية": ["طلاق", "نفقه", "حضانه", "زوجيه", "مهر", "عده"],
  "تجاري": ["شيك", "شركه", "تجاري", "كمبياله", "افلاس", "ورقه تجاريه"],
  "إداري": ["قرار اداري", "جهه اداريه", "الغاء القرار", "مناقصه"],
  "إيجارات": ["ايجار", "مستاجر", "موجر", "اخلاء"],
  "مدني": ["عقد", "تعويض", "ملكيه", "التزام", "ضرر"],
};

function suggestBranch(text) {
  const norm = normalizeArabic(text);
  let best = "عام", bestScore = 0;
  for (const [branch, kws] of Object.entries(BRANCH_HINTS)) {
    let score = 0;
    for (const kw of kws) if (norm.includes(kw)) score++;
    if (score > bestScore) { bestScore = score; best = branch; }
  }
  return bestScore >= 2 ? best : "عام";
}

/* ---------- ربط حكم بالنصوص القانونية المرفوعة ----------
   يعيد روابط: [{lawId, lawTitle, articleNo, found:bool}] */
function linkRulingToLaws(ruling, lawSources) {
  const links = [];
  const refs = ruling.citedArticles || [];
  for (const ref of refs) {
    let matched = null;
    for (const law of lawSources) {
      const lawNorm = normalizeArabic(law.title || "");
      const keyMatch = ref.lawKey && normalizeArabic(ref.lawKey) &&
        (lawNorm.includes(normalizeArabic(ref.lawKey)) || normalizeArabic(ref.lawKey).includes(lawNorm));
      const hintMatch = ref.lawHint && lawNorm && (
        lawNorm.includes(normalizeArabic(ref.lawHint)) ||
        normalizeArabic(ref.lawHint).includes(lawNorm)
      );
      if (keyMatch || hintMatch) { matched = law; break; }
    }
    // إن لم يُذكر قانون صراحة، جرّب المطابقة بالفرع نفسه إذا كان قانون وحيد بالفرع
    if (!matched && !ref.lawHint) {
      const sameBranch = lawSources.filter((l) => l.branch === ruling.branch);
      if (sameBranch.length === 1) matched = sameBranch[0];
    }
    const articleExists = matched && Array.isArray(matched.articles) &&
      matched.articles.some((a) => String(a.no).split(" ")[0] === String(ref.article));
    links.push({
      article: ref.article,
      extra: ref.extra || "",
      lawHint: ref.lawHint || "",
      lawKey: ref.lawKey || "",
      lawId: matched ? matched.id : null,
      lawTitle: matched ? matched.title : (ref.lawKey || ref.lawHint || ""),
      found: !!articleExists,
    });
  }
  return links;
}
