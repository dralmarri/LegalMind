#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني law20_2019_parsed.json — القانون 20/2019 بإصدار النظام الموحد لمكافحة الغش التجاري لدول مجلس
التعاون الخليجي، من DOCX. 18 مادة (النظام المرافق) + 4 مواد إصدار + ديباجة. التلف حتميّ (أقواس معكوسة،
تشكيلٌ مضاعف، حروفٌ مكرّرة، تنوينٌ مبعثر) — يُصوَّب آليًّا؛ ويُمسَح للتأكد من خلوّه بعد التنظيف."""
import zipfile, re, html, json, pathlib

H = pathlib.Path(__file__).parent
RAW = zipfile.ZipFile(H / "new_law6.docx").read("word/document.xml").decode("utf-8")
_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
PARAS = [x for x in (html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p))).strip()
                     for p in re.findall(r"<w:p[ >].*?</w:p>", RAW, re.S)) if x]

_ISSUE_RE = re.compile(r"^\)?\s*مادة\s+(أولى|ثانية|ثالثة|رابعة|خامسة)\s*\(?\s*(?:اصدار|إصدار)?\s*$")
_ART_RE = re.compile(r"^المادة\s*([٠-٩0-9]+)\s*$")


def clean(t):
    # الأقواس مبعثرةُ الاتجاه في كامل المصدر (RTL): كل قوسٍ مقلوبٌ عن موضعه الصحيح — فالتصويب الصحيح
    # الوحيد هو مبادلةٌ عامّةٌ «(» ⇄ «)». (المطابقةُ بالنمط تُخطئ إذ تخلط «)…(» المقلوبة بما ينشأ طبيعيًّا
    # بين قوسين صحيحين متتاليين «(أ) … (ب)».) ترويسات مواد الإصدار تُكتشَف قبل التنظيف فلا تتأثّر.
    t = t.translate(str.maketrans("()", ")("))
    t = t.replace("وف اًقً", "وفقاً").replace("وف اقً", "وفقاً")     # تبعثر «وفقاً»
    t = t.replace("مخالفا ًل", "مخالفاً ل")                          # تنوينٌ منفصل قبل لام
    t = t.replace("تححدده", "تحدده").replace("لصالححه", "لصالحه")   # حرفٌ مكرّر (حتميّ)
    t = t.replace("وامدد", "والمدد")                                 # حرفٌ ساقط: «والمدد» (م3) — «امدد» غير كلمة
    t = t.replace("ويكون مسؤولة بالتضامن", "ويكون مسؤولاً بالتضامن")  # م14: الصواب «مسؤولاً» (يعود على «المسؤول») — مؤكَّدٌ من صور الجريدة
    t = re.sub(r"([ء-ي])\s+([ًٌٍ])", r"\1\2", t)                     # لصق تنوينٍ منفصلٍ بحرفه
    t = re.sub(r"[ً-ْ]{2,}", lambda m: m.group()[0], t)              # جمع تشكيلٍ مضاعف
    t = re.sub(r"_+", " ", t)
    t = re.sub(r"\(\s+", "(", t); t = re.sub(r"\s+\)", ")", t)       # لصق محتوى القوس: «( 5000 )» ⇒ «(5000)»
    t = re.sub(r"\s{2,}", " ", t).strip(" .:؛")
    return t


# boundaries: issuance headers + numbered article headers
marks = []  # (kind, key, index)
for i, x in enumerate(PARAS):
    mi = _ISSUE_RE.match(x)
    ma = _ART_RE.match(x)
    if mi:
        marks.append(("issue", {"أولى": 1, "ثانية": 2, "ثالثة": 3, "رابعة": 4, "خامسة": 5}[mi.group(1)], i))
    elif ma:
        marks.append(("art", int(ma.group(1).translate(_AR)), i))

first = marks[0][2]
preamble = clean(" ".join(PARAS[:first]))

ISSUE, ARTS, ORDER = {}, {}, []
for j, (kind, key, i) in enumerate(marks):
    end = marks[j + 1][2] if j + 1 < len(marks) else len(PARAS)
    body = clean(" ".join(PARAS[i + 1:end]))
    if kind == "issue":
        ISSUE["issue-%d" % key] = body
    else:
        ARTS["m%d" % key] = body
        ORDER.append("m%d" % key)

data = {"preamble_text": preamble, "issuance": ISSUE, "articles": ARTS, "order": ORDER}
(H / "law20_2019_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- verification ----
allblob = preamble + " " + " ".join(ISSUE.values()) + " " + " ".join(ARTS.values())
assert "�" not in allblob
rev = re.findall(r"\)\s*[٠-٩0-9أ-ي]\s*\(", allblob)
print("law20 parsed: articles", len(ARTS), "| issuance", len(ISSUE), "| order", len(ORDER))
print("sequential 1-18:", [int(k[1:]) for k in ORDER] == list(range(1, 19)))
print("reversed-paren residue:", rev or "لا", "| doubled-diac:", len(re.findall(r"[ً-ْ]{2,}", allblob)), "| underscores:", allblob.count("_"))
print("issuance keys:", sorted(ISSUE))
print("preamble head:", preamble[:110])
for k in ("m2", "m11", "m12", "m15"):
    print(f"\n--- {k} ---\n{ARTS[k][:200]}")
