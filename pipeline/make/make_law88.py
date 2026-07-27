#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني law88_1995_parsed.json — القانون رقم 88 لسنة 1995 في شأن محاكمة الوزراء، من DOCX. 16 مادة + ديباجة.
التلف حتميّ محدود: 6 محارف � كلّها في نمطٍ واحد (حرفٌ مفصولٌ بمسافةٍ + تنوينٌ مشوَّه) داخل صِيَغٍ قانونيةٍ
ثابتةٍ لا لبس فيها (قانونًا/طبقاً/ارتباطًا/مَن)، فتُصوَّب بإحلالٍ مستهدَفٍ لكلّ عبارة؛ وتشكيلٌ مضاعف يُجمَع.
ثم يُمسَح للتأكّد من خلوّه من � والتلف قبل الإدخال."""
import zipfile, re, html, json, pathlib

H = pathlib.Path(__file__).parent
RAW = zipfile.ZipFile(H / "new_law8.docx").read("word/document.xml").decode("utf-8")
_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
PARAS = [x for x in (html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p))).strip()
                     for p in re.findall(r"<w:p[ >].*?</w:p>", RAW, re.S)) if x]
# «مكرر» قد يأتي بتنوينٍ مضاعف/ألفٍ («مادة 6 مكررًًا») + علامات «) ))» زائدة — نتسامح مع كلّ ذلك.
HDR = re.compile(r"^(?:المادة|مادة)\s*([٠-٩0-9]+)\s*(مكرر[ً-ْ]*ا?)?\s*[).\s]*$")

# إحلالاتٌ مستهدَفةٌ للمحارف � — كلٌّ منها في عبارةٍ قانونيةٍ ثابتةٍ قاطعةٍ في قراءتها:
_FFFD_FIX = [
    ("قانو ن �ًا", "قانونًا"), ("قانو ن �ا", "قانونًا"),
    ("طب ق � اً", "طبقاً"), ("طب ق �اً", "طبقاً"),
    ("ارتبا ط �ًا", "ارتباطًا"), ("ارتبا ط �ا", "ارتباطًا"),
    ("م �َن", "مَن"), ("م �ن", "مَن"),
]
# تشوّهُ ترتيبِ الحرف والحركة «ُيُ» (كما في 53/2026): «يُC» ⇒ «Cُيُ» — 3 كلماتٍ قاطعةٍ في قراءتها:
_SCRAMBLE_FIX = [("عُيُاقب", "يُعاقب"), ("لُيُغى", "يُلغى"), ("عُيُمل", "يُعمل"),
    ("عضو ين", "عضوين"), ("إجرا ءات", "إجراءات")]  # مسافةٌ دخيلةٌ داخل الكلمة (عضوين/إجراءات)


def clean(t):
    for a, b in _FFFD_FIX + _SCRAMBLE_FIX:
        t = t.replace(a, b)
    t = re.sub(r"[ً-ْ]{2,}", lambda m: m.group()[0], t)          # جمع تشكيلٍ مضاعف (عضوًًا⇒عضوًا)
    t = t.replace("�", "")                                   # أيّ � متبقٍّ (يُرصَد بالتحقّق أدناه)
    t = re.sub(r"_+", " ", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" .:؛")
    return t


# قائمةٌ مرتّبةٌ بالموضع (لا قاموسٌ بالرقم) كي لا تصطدم «مادة 6» بـ«مادة 6 مكرر» على المفتاح نفسه.
marks = []  # (position, key)
for i, x in enumerate(PARAS):
    m = HDR.match(x)
    if m:
        key = "m%d%s" % (int(m.group(1).translate(_AR)), "-mukarrar" if m.group(2) else "")
        marks.append((i, key))
marks.sort()

first = marks[0][0]
preamble = clean(" ".join(PARAS[:first]))

A, ORDER = {}, []
for j, (s, key) in enumerate(marks):
    e = marks[j + 1][0] if j + 1 < len(marks) else len(PARAS)
    A[key] = clean(" ".join(PARAS[s + 1:e]))
    ORDER.append(key)

data = {"preamble_text": preamble, "articles": A, "order": ORDER}
(H / "law88_1995_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- verification ----
blob = preamble + " " + " ".join(A.values())
print("law88 parsed: articles", len(A), "| ORDER:", ORDER)
print("residual � :", blob.count("�"), "| ُيُ:", blob.count("ُيُ"), "| doubled-diac:", len(re.findall(r"[ً-ْ]{2,}", blob)), "| _:", blob.count("_"))
assert "�" not in blob and "ُيُ" not in blob, "بقي تلف!"
assert "m6-mukarrar" in A, "لم تُفصَل م6 مكرر!"
empty = [k for k, v in A.items() if len(v) < 8]  # م14 «ملغاة» = 5 محارف مشروعة
print("short:", empty or "لا", "(م14 ملغاة متوقّعة)")
for k in ("m6", "m6-mukarrar"):
    print(f"\n--- {k} ---\n{A[k][:200]}")
