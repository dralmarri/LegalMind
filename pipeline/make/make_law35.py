#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني law35_1985_parsed.json — القانون رقم 35 لسنة 1985 بشأن جرائم المفرقعات، من DOCX. 11 مادة + عنوان.
النصّ نظيفٌ (لا � ولا «_» ولا أقواس معكوسة)، والتلف محصورٌ في 5 أخطاء OCR حتميّة (حرفٌ ساقطٌ/مضاعَف داخل
عباراتٍ قانونيةٍ قاطعةٍ في قراءتها) تُصوَّب بإحلالٍ مستهدَف. يُستبعَد ذيلُ الإصدار (التوقيع/التاريخ) من م11.
الفرع «جزائي». يُمسَح قبل الإخراج للتأكّد من التسلسل وخلوّه من التلف."""
import zipfile, re, html, json, pathlib

H = pathlib.Path(__file__).parent
RAW = zipfile.ZipFile(H / "new_law11.docx").read("word/document.xml").decode("utf-8")
_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
PARAS = [x for x in (html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p))).strip()
                     for p in re.findall(r"<w:p[ >].*?</w:p>", RAW, re.S)) if x]
HDR = re.compile(r"^(?:المادة|مادة)\s*([٠-٩0-9]+)\s*$")
# ذيلُ الإصدار (توقيعُ الأمير والتاريخ) — ليس من متن م11:
FOOTER = re.compile(r"^(?:أمير الكويت|جابر الأحمد|صدر بقصر السيف|الموافق)")

# إحلالاتٌ مستهدَفةٌ لأخطاء OCR — كلٌّ في عبارةٍ قاطعةٍ في قراءتها لا لبس فيها:
_FIX = [
    ("الناس أو أمواهم للخطر", "الناس أو أموالهم للخطر"),     # م2: ساقط ل
    ("بقصد الاستعانة هم في", "بقصد الاستعانة بهم في"),        # م4: ساقط ب
    ("السابقة أو بقوعها", "السابقة أو بوقوعها"),              # م5: ساقط و
    ("للاستعمال في ارتكاها", "للاستعمال في ارتكابها"),       # م5: ساقط ب
    ("عن الححد الاقصى", "عن الحد الاقصى"),                   # م8: ح مضاعَفة
]


def clean(t):
    for a, b in _FIX:
        t = t.replace(a, b)
    t = re.sub(r"\s{2,}", " ", t).strip(" .:؛,")
    return t


marks = [(i, "m%d" % int(HDR.match(x).group(1).translate(_AR))) for i, x in enumerate(PARAS) if HDR.match(x)]
first = marks[0][0]
# العنوان (ما قبل المادة 1) ديباجةً مختصرة:
preamble = clean(" ".join(PARAS[:first]))
# موضع بداية ذيل الإصدار (لاستبعاده من آخر مادة):
foot_at = next((i for i, x in enumerate(PARAS) if FOOTER.match(x)), len(PARAS))

A, ORDER = {}, []
for j, (s, key) in enumerate(marks):
    e = marks[j + 1][0] if j + 1 < len(marks) else len(PARAS)
    e = min(e, foot_at)                                    # لا نتجاوز ذيلَ الإصدار
    A[key] = clean(" ".join(PARAS[s + 1:e]))
    ORDER.append(key)

issue_tail = clean(" ".join(PARAS[foot_at:]))
data = {"preamble_text": preamble, "issue_tail": issue_tail, "articles": A, "order": ORDER}
(H / "law35_1985_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- verification ----
blob = preamble + " " + " ".join(A.values())
print("law35/1985 parsed: articles", len(A), "| ORDER:", ORDER)
seqok = [int(k[1:]) for k in ORDER] == list(range(1, 12))
print("sequential 1-11:", seqok, "| � :", blob.count("�"), "| _:", blob.count("_"))
assert "�" not in blob and seqok, "تلف/تسلسل!"
# تأكيد أنّ التصويبات وقعت وأنّ التالف لم يبقَ:
for bad in ("أمواهم", "الاستعانة هم", "بقوعها", "ارتكاها", "الححد"):
    assert bad not in blob, f"بقي تالف: {bad}"
print("تصويبات OCR الخمسة: تمّت | ذيل الإصدار مُستبعَد:", "أمير الكويت" not in blob)
empty = [k for k, v in A.items() if len(v) < 10]
print("short/empty:", empty or "لا")
print("preamble:", preamble)
print("issue_tail:", issue_tail)
for k in ("m1", "m2", "m4", "m5", "m8", "m9", "m11"):
    print(f"\n--- {k} ---\n{A[k]}")
