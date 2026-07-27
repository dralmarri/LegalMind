#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني law12_2020_parsed.json — القانون رقم 12 لسنة 2020 في شأن حق الاطلاع على المعلومات.
17 مادة في سبعة فصول + ديباجة + بيان الإصدار. صدر 31/8/2020، ويُعمل به بعد ستة أشهر من نشره.

**شاهدان مستقلّان، ولا واحدَ منهما الجريدةُ الرسمية:**
 (أ) ملفُّ DOCX — طبقتُه النصّية سليمةُ البنية لكنّ بها سقوطَ حروفٍ في ثمانية مواضع.
 (ب) ملفُّ PDF (نسخةُ محامٍ عليها علامةٌ مائية) — طبقتُه النصّية معكوسةُ الترتيب فلا يُنقَل منها،
     لكنّ **صورَ صفحاتها تُقرأ**، فاستُعملت شاهدًا على مواضع السقوط لا مصدرًا للنقل.

والقاعدةُ المتّبعة كما هي: لا يُصحَّح إلّا ما هو **لا-كلمةٌ في العربية**، وكلُّ تصحيحٍ له شاهدُه.
والمواضعُ الثمانيةُ كلُّها كذلك: «عى» و«الأعال» و«للباد» و«سامته» و«عر» ليست كلماتٍ، و«طب ق �ًا»
و«مرف ق �ًا» و«ممك ن �ًا» نمطُ تلفٍ معروفٌ سبق أن عولج في 88/1995 (حرفٌ مفصولٌ + تنوينٌ مشوَّه).
وستّةٌ من الثمانية مؤكَّدةٌ بصورة الشاهد (ب) نصًّا صريحًا.

★ ومع ذلك: المصدرُ ليس الجريدةَ الرسمية، فيُوسَم الكائنُ بذلك ويبقى الاستشهادُ مشروطًا بالمقابلة.
"""
from __future__ import annotations
import html, json, pathlib, re, zipfile

H = pathlib.Path(__file__).parent
SRC = pathlib.Path("/root/.claude/uploads/51a36a7b-3508-590f-af5f-27bfda80b244/"
                   "facaae60-______________________________.docx")

# (القديم، الجديد، السند) — لا يُطبَّق تصحيحٌ لم يُوجَد قديمُه، ويُبلَّغ عن كلٍّ منها بعدده.
FIX = [
    ("طب ق �ًا", "طبقًا",  "لا-كلمة؛ نمطُ «حرفٌ مفصولٌ + �» المعروف. شاهدٌ: PDF ص2 «سريا و محميا طبقا للقانون»."),
    ("مرف ق �ًا", "مرفقًا", "لا-كلمة؛ النمطُ نفسُه. والسياقُ قاطع: «مرفقًا به البيانات والمستندات»."),
    ("ممك ن �ًا", "ممكنًا", "لا-كلمة؛ النمطُ نفسُه. شاهدٌ: PDF ص5 «متى كان ذلك ممكنا والا تم رفضة»."),
    ("بناءً عى عرض", "بناءً على عرض", "«عى» لا-كلمة. شاهدٌ: PDF ص5 «بناء على عرض الوزير المعني»."),
    ("أو عى الصحة", "أو على الصحة", "«عى» لا-كلمة. شاهدٌ: PDF ص6 «او على الصحة العامة او البيئة»."),
    ("خطرًا عى حياة فرد أو عى صحته أو", "خطرًا على حياة فرد أو على صحته أو",
     "«عى» ×2 لا-كلمة. شاهدٌ: PDF ص6 «يسبب خطرا على حياة فرد او على صحته او سلامته»."),
    ("سامته", "سلامته", "لا-كلمة؛ سقوطُ لام. شاهدٌ: PDF ص6 «او سلامته»."),
    ("الأعال العدوانية", "الأعمال العدوانية", "لا-كلمة؛ سقوطُ ميم. شاهدٌ: PDF ص5 «باحباط الاعمال العدوانية»."),
    ("للباد", "للبلاد", "لا-كلمة؛ سقوطُ لام. شاهدٌ: PDF ص5 «المصالح الاستراتيجية للبلاد»."),
    ("الدولة عر دولة أخرى", "الدولة عبر دولة أخرى", "«عر» لا-كلمة هنا. شاهدٌ: PDF ص6 «وصلت الى الدولة عبر دولة اخرى»."),
]

raw = zipfile.ZipFile(SRC).read("word/document.xml").decode("utf-8")
P = [html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p))).strip()
     for p in re.findall(r"<w:p[ >].*?</w:p>", raw, re.S)]
P = [x for x in P if x]

applied = []
for i, x in enumerate(P):
    for old, new, sanad in FIX:
        if old in x:
            P[i] = P[i].replace(old, new)
            applied.append((old, new, sanad))
missing = [f[0] for f in FIX if not any(a[0] == f[0] for a in applied)]
assert not missing, "تصحيحاتٌ لم يُوجَد قديمُها (المصدرُ ليس ما نظنّ): %s" % missing

_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def clean(t):
    t = t.replace("-_", "-")                      # علامةُ بندٍ مشوَّهة
    t = re.sub(r"([ً-ْ])\1+", r"\1", t)            # تشكيلٌ مضاعف: «موظفًًا» ⇒ «موظفًا»
    t = t.replace("�", "")
    return re.sub(r"\s{2,}", " ", t).strip()


HDR_ART = re.compile(r"^(?:المادة|مادة)\s*(\d+)\s*$")
HDR_CH = re.compile(r"^الفصل\s+\S+\s*$")

marks = [(i, int(m.group(1))) for i, x in enumerate(P) for m in [HDR_ART.match(x.translate(_AR))] if m]
assert [n for _, n in marks] == list(range(1, 18)), "خللٌ في تسلسل المواد"

chapters = []
for i, x in enumerate(P):
    if HDR_CH.match(x):
        nxt = P[i + 1].strip()
        title = nxt if not HDR_ART.match(nxt.translate(_AR)) and len(nxt) <= 70 else ""
        chapters.append((i, x + (" — " + title if title else "")))
assert len(chapters) == 7, len(chapters)
CH_TITLES = {t.split(" — ")[1] for _, t in chapters if " — " in t}


def unwrap(seg):
    BUL = re.compile(r"^(?:\d+\s*-|-\s|[أ-ي]\s*-|أولًا|ثانيًا|ثالثًا)")
    out = []
    for x in (clean(y) for y in seg if y.strip()):
        if out and not out[-1].endswith((".", ":", "؛")) and not BUL.match(x):
            out[-1] += " " + x
        else:
            out.append(x)
    return "\n".join(out).strip()


pre_end = chapters[0][0]
preamble = unwrap(P[:pre_end])
sig_i = next(i for i, x in enumerate(P) if x.strip() == "نائب أمير الكويت")
ARTS, ORDER = {}, []
for j, (s, num) in enumerate(marks):
    e = marks[j + 1][0] if j + 1 < len(marks) else sig_i
    seg = [x for x in P[s + 1:e] if not HDR_CH.match(x) and x.strip() not in CH_TITLES]
    ARTS[num] = {"num": num, "text": unwrap(seg),
                 "chapter": next(t for i, t in reversed(chapters) if i < s)}
    ORDER.append(num)
issuance = unwrap(P[sig_i:])

data = {"preamble_text": preamble, "issuance": issuance,
        "articles": {str(n): ARTS[n] for n in ORDER}, "order": [str(n) for n in ORDER],
        "chapters": [t for _, t in chapters],
        "corrections": [{"from": o, "to": n, "basis": s} for o, n, s in
                        {(a[0], a[1], a[2]) for a in applied}]}
(H / "law12_2020_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                          encoding="utf-8")

print("== قانون 12/2020 — حق الاطلاع على المعلومات ==")
print("موادّ:", len(ORDER), "| فصول:", len(chapters))
assert len(ORDER) == 17
blob = preamble + " " + " ".join(a["text"] for a in ARTS.values()) + " " + issuance
print("محارف تالفة �:", blob.count("�"), "| «-_»:", blob.count("-_"),
      "| تشكيلٌ مضاعف:", len(re.findall(r"([ً-ْ])\1", blob)))
assert blob.count("�") == 0 and "-_" not in blob and not re.findall(r"([ً-ْ])\1", blob)
for bad in ("عى ", "الأعال", "للباد", "سامته", " عر "):
    assert bad not in blob, "بقي تلف: %s" % bad
print("لا-كلماتٌ متبقّية: لا ✓")
short = [n for n in ORDER if len(ARTS[n]["text"]) < 40]
print("موادُّ قصيرة:", short or "لا"); assert not short
print("\nالفصول:")
for t in data["chapters"]:
    r = [n for n in ORDER if ARTS[n]["chapter"] == t]
    print("   %-40s م%d-م%d" % (t, r[0], r[-1]))
print("\nتصحيحاتٌ مطبَّقة: %d" % len(data["corrections"]))
for c in sorted(data["corrections"], key=lambda x: x["from"]):
    print("   «%s» ⇐ «%s»" % (c["from"], c["to"]))
print("\nبيان الإصدار: " + issuance.replace("\n", " "))
for n in (1, 12, 14, 17):
    print("\n--- م%d | %s ---\n%s" % (n, ARTS[n]["chapter"], ARTS[n]["text"][:230]))
print("\n✓ كُتب law12_2020_parsed.json")
