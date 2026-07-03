/* ============================================================
   arabic.js — أدوات معالجة النص العربي
   تطبيع + تقطيع + إزالة كلمات الوقف + تجذيع خفيف
   ============================================================ */

const AR_DIACRITICS = /[ً-ْٰـۖ-ۭ]/g; // تشكيل + تطويل
const AR_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩";

// تحويل الأرقام الهندية إلى عربية (لاتينية)
function normalizeDigits(s) {
  return String(s || "").replace(/[٠-٩]/g, (d) => String(AR_INDIC_DIGITS.indexOf(d)));
}

// تطبيع خفيف: يبقي النص مقروءاً (إزالة تشكيل + توحيد أرقام فقط)
function lightNormalize(s) {
  return normalizeDigits(String(s || "").replace(AR_DIACRITICS, ""));
}

// تطبيع كامل للفهرسة والبحث
function normalizeArabic(s) {
  return normalizeDigits(
    String(s || "")
      .replace(AR_DIACRITICS, "")
      .replace(/[أإآٱ]/g, "ا")
      .replace(/ى/g, "ي")
      .replace(/ؤ/g, "و")
      .replace(/ئ/g, "ي")
      .replace(/ة/g, "ه")
  ).toLowerCase();
}

const AR_STOPWORDS = new Set([
  "من","في","علي","الي","عن","ان","انه","انها","اذ","اذا","او","ثم","لا","ما","لم","لن",
  "هو","هي","هم","هن","كان","كانت","يكون","تكون","ذلك","تلك","هذا","هذه","التي","الذي",
  "الذين","مع","كل","بعد","قبل","عند","حتي","كما","لما","فيه","فيها","به","بها","له","لها",
  "الا","غير","بين","وقد","قد","ومن","وفي","وما","لان","لانه","اي","بما","مما","وهو","وهي",
  "عليه","عليها","منه","منها","نحو","لدي","وذلك","ولا","فلا","اما","اذن","بل","حيث","وان",
  "كذلك","ايضا","فان","فانه","لذلك","وعلي","والي","ولم","فما","انما","اليه","اليها","هما",
  "نحن","انت","انا","اني","لك","لكم","بان","علي","الا","ولو","لو","ليس","ليست","سوف","سوي",
]);

const AR_PREFIXES = ["وال","فال","بال","كال","ولل","وبال","والل","لل","ال"];
const AR_SUFFIXES = ["كما","هما","تين","تان","ات","ون","ين","ان","ها","هم","هن","نا","كم","كن","ه","ي","ك","ت"];

// تجذيع خفيف: إزالة أل التعريف وأشهر اللواحق مع الحفاظ على جذر >= 3 أحرف
function lightStem(token) {
  let t = token;
  for (const p of AR_PREFIXES) {
    if (t.startsWith(p) && t.length - p.length >= 3) { t = t.slice(p.length); break; }
  }
  // واو/فاء العطف المنفردة
  if ((t.startsWith("و") || t.startsWith("ف")) && t.length >= 5) t = t.slice(1);
  for (const s of AR_SUFFIXES) {
    if (t.endsWith(s) && t.length - s.length >= 3) { t = t.slice(0, t.length - s.length); break; }
  }
  return t;
}

// تقطيع النص إلى وحدات بحث مجذّعة
function tokenize(s) {
  const norm = normalizeArabic(s);
  const raw = norm.split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  const out = [];
  for (const tok of raw) {
    if (tok.length < 2) continue;
    if (AR_STOPWORDS.has(tok)) continue;
    out.push(lightStem(tok));
  }
  return out;
}

function formatDateDDMMYYYY(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return "";
  return `${d}/${m}/${y}`;
}

function escapeHTML(str) {
  if (str == null) return "";
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
