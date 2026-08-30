#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني law75_2019_parsed.json — القانون رقم 75 لسنة 2019 في شأن حقوق المؤلف والحقوق المجاورة.
51 مادة في ثلاثة أبواب وثمانية فصول + ديباجة + بيان الإصدار. المصدر: DOCX غيرُ رسميّ.

التلفُ في هذا الملفّ محدودٌ ومنمَّط، وكلُّ تصحيحٍ منه حتميٌّ لا يحتمل قراءةً ثانية:
 (1) خمسةُ مواضعَ من نمط «حرفٌ مفصولٌ + � + حركة» في كلماتٍ **معرَّفةٍ في المادة نفسِها**
     («المصنَّف»، «المؤلَّف»، «المصنَّف المشتق»، «بُثَّ»، «المبتكِر») — فالسياقُ يحسمها.
 (2) «أصل ه» ⇐ «أصله» — شطرُ كلمةٍ بمسافة.
 (3) 159 موضعَ تشكيلٍ مضاعف («أيًّا» تُكتب بحركتين متتاليتين) ⇒ تُجمَع.
 (4) 127 علامةَ بندٍ مقلوبةً «-1» ⇒ «1-» — عيبُ اتجاهِ عرضٍ لا عيبُ نصّ.

وما ليس من هذه الأنماط لم يُمَسّ. ومسحُ «لا تزيد/تريد» في مواد العقوبات أظهر ستّةَ مواضعَ
**كلُّها سليمة** («تزيد») — فلا شيءَ فيها يُصحَّح.

★ المصدرُ الأصليُّ ليس الجريدةَ الرسمية، ويُوسَم الكائنُ بذلك.

★★ شاهدٌ ثانٍ لاحق — **صورُ صفحاتِ «الكويت اليوم» ع1455 (السنة الخامسة والستون)**: قابلتُ بها
   الصفحةَ الأولى من الديباجة، والصفحةَ أ16، والصفحةَ الأخيرة (م43–م51 وبيانَ الإصدار). فأفادت:
    (أ) بيانُ الإصدار في الجريدة يزيد **«الموافق 23 يوليــو 2019 م»** على ما في الملفّ —
        فاستُكمِل موسومًا بمصدره، ويوافقه الحسابُ: 20 ذي القعدة 1440 ≈ 22–23 يوليو 2019.
    (ب) م49 (الإلغاء) طابقت الملفَّ حرفًا بحرف — فسقط الشكُّ عنها.
    (ج) ترويسةُ **«أحكام ختامية»** تسبق م48، وقد التصقت في الملفّ بذيل م47 بلا مسافة.
        ففُصلت وأُثبتت قسمًا مستقلًّا — وهو **فصلٌ بنيويٌّ لا تصحيحُ نصّ**، وأثرُه أنّ
        العقوباتِ م41–م47 لا م41–م48، وأنّ م48–م51 أحكامٌ ختامية.
   وما اختلف فيه الشاهدان ولم يكن لا-كلمةً **سُجّل ولم يُغيَّر** — انظر GAZETTE_DIVERGENCES.
"""
from __future__ import annotations
import html, json, pathlib, re, zipfile

H = pathlib.Path(__file__).parent
SRC = pathlib.Path("/root/.claude/uploads/51a36a7b-3508-590f-af5f-27bfda80b244/"
                   "9c90e02d-__________________________________.docx")

FIX = [
    ("المص �نَف", "المصنَّف", "نمطُ «حرفٌ مفصولٌ + �»؛ والكلمةُ هي المعرَّفةُ في البند نفسِه."),
    ("المؤ ل �َف", "المؤلَّف", "النمطُ نفسُه؛ والبندُ يعرّف «المؤلَّف»."),
    ("المص ن �َف", "المصنَّف", "النمطُ نفسُه؛ والبندُ يعرّف «المصنَّف المشتق»."),
    ("ب �ُث", "بُثَّ", "النمطُ نفسُه؛ السياق: «متى كان برنامج البث قد بُثَّ من جهاز إرسال»."),
    ("المبت ك �ِر", "المبتكِر", "النمطُ نفسُه؛ السياق: «تعود للمؤلف المبتكِر»."),
    ("أصل ه من مصنف", "أصله من مصنف", "شطرُ كلمةٍ بمسافة؛ السياق: «يستمد أصله من مصنف سابق الوجود»."),
]

# ــــ ما أفادته صورُ الجريدة ــــ
GAZETTE = {
    "citation": "الكويت اليوم — العدد 1455، السنة الخامسة والستون، ص أ16 وما بعدها",
    "issued_gregorian": "الموافق 23 يوليو 2019 م",
    "verified_pages": "الصفحةُ الأولى من الديباجة، وص أ16، والصفحةُ الأخيرة (م43–م51 وبيان الإصدار)",
    "verified_articles": ["43", "44", "45", "46", "47", "49", "issuance"],
}

# فصلٌ بنيويّ: ترويسةٌ التصقت بذيلِ مادةٍ بلا مسافة. لا حرفَ يُزاد ولا حرفَ يُنقَص.
SPLIT = [("سجلات يطلبون الاطلاع عليها.أحكام ختامية",
          ["سجلات يطلبون الاطلاع عليها.", "أحكام ختامية"],
          "ترويسةُ «أحكام ختامية» — تسبق م48 في الجريدة، والتصقت في الملفّ بذيل م47 بلا مسافة.")]

# عناوينُ فرعيةٌ داخلَ الفصول، لا لفظَ «باب» فيها ولا «فصل»، فسقطت في متن المادة **السابقة**
# لها لأنّها تتقدّم ترويسةَ المادة التالية. وهي ستّةٌ لا سابعَ لها، ولا تُعَدّ ترويسةً إلّا
# متى تلاها فورًا سطرُ «المادة N» — وإلّا فهي تعدادٌ في صلب المادة («أولاً:» في م6 وم17 مثلًا).
SUBHEAD = ("أولًاً: الحقوق الأدبية", "ثانياًً: الحقوق المالية",
           "مدة حماية الحقوق الأدبية", "مدة حماية الحقوق المالية")
SUBHEAD_N = 6

# خلافٌ بين الشاهدين ليس لا-كلمةً ⇒ يُسجَّل ولا يُغيَّر. «تصحيحُها ترجيحٌ لا نقل».
GAZETTE_DIVERGENCES = [
    {"where": "خاتمة الديباجة",
     "docx": "وافق مجلس الأمة على القانون الآتي نصه :",
     "gazette_reading": "وافق مجلس الأمة على القانون التالي نصه، وقد صدقنا عليه وأصدرناه",
     "action": "لم يُغيَّر — كلا اللفظين عربيٌّ صحيح، وصيغةُ التصديق لا أثرَ لها في حكمٍ موضوعيّ. "
               "يُقابَل على أصل الجريدة قبل الاستشهاد بلفظ الديباجة."},
    {"where": "م48 وم50",
     "docx": "«يُعمل بأحكام القانون المرافق…» و«…لتنفيذ أحكام القانون المرافق…»",
     "gazette_reading": "لم أتبيّن في الصورة مواد إصدارٍ منفصلةً في صدر القانون، والقانونُ يبدأ "
                        "بالباب الأول مباشرةً بعد الديباجة",
     "action": "لم يُغيَّر — لفظُ «المرافق» عبارةٌ صحيحة وقد يكون من صياغة المشرّع. "
               "★ يُقابَل على أصل الجريدة: إن ثبت أنّ م48–م51 موادُّ إصدارٍ موضعُها الصدر لا الذيل، "
               "فذلك ترتيبٌ يُصحَّح بمستندٍ رسميّ لا باجتهاد."},
]

raw = zipfile.ZipFile(SRC).read("word/document.xml").decode("utf-8")
P = [html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p))).strip()
     for p in re.findall(r"<w:p[ >].*?</w:p>", raw, re.S)]
P = [x for x in P if x]

applied = set()
for i, x in enumerate(P):
    for old, new, sanad in FIX:
        if old in x:
            P[i] = P[i].replace(old, new); applied.add(old)
missing = [f[0] for f in FIX if f[0] not in applied]
assert not missing, "تصحيحاتٌ لم يُوجَد قديمُها: %r" % missing

for old, parts, sanad in SPLIT:                            # فصلُ ترويسةٍ ملتصقة
    hit = [i for i, x in enumerate(P) if x.strip() == old]
    assert len(hit) == 1, "الفصلُ البنيويّ لم يُصِب موضعًا واحدًا: %r ⇒ %r" % (old, hit)
    P[hit[0]:hit[0] + 1] = parts

_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def clean(t):
    t = t.translate(_AR)
    t = re.sub(r"([ً-ْ])\1+", r"\1", t)                    # تشكيلٌ مضاعف
    t = re.sub(r"ً([اى])ً", r"\1ً", t)                     # تنوينٌ مضاعفٌ شطره الألف: «أولًاً» ⇒ «أولاً»
    t = re.sub(r"(?<![\d.،])-(\d+)(?=\s|$)", r"\1-", t)    # «-1» ⇒ «1-» (عكسُ اتجاه)
    t = t.replace("�", "")
    return re.sub(r"\s{2,}", " ", t).strip()


HDR_ART = re.compile(r"^(?:المادة|مادة)\s*(\d+)\s*$")
HDR_STRUCT = re.compile(r"^(الباب|الفصل)\s+\S+\s*:?\s*(.*)$")
HDR_SEC = re.compile(r"^(أحكام ختامية)$")           # ترويسةٌ بلا لفظ «باب» أو «فصل»

marks = [(i, int(m.group(1))) for i, x in enumerate(P) for m in [HDR_ART.match(x.translate(_AR))] if m]
assert [n for _, n in marks] == list(range(1, 52)), "خللٌ في تسلسل المواد"

SUB = []                                    # (موضع، عنوانٌ فرعيّ) — ترويسةٌ متى تلاها «المادة N»
for i, x in enumerate(P):
    if x in SUBHEAD and i + 1 < len(P) and HDR_ART.match(P[i + 1].translate(_AR)):
        SUB.append((i, clean(x)))
assert len(SUB) == SUBHEAD_N, "العناوينُ الفرعية %d لا %d — راجِع المصدر" % (len(SUB), SUBHEAD_N)
SUB_AT = {i for i, _ in SUB}

STRUCT, ST_TITLES = [], set()
for i, x in enumerate(P):
    if HDR_SEC.match(x):
        STRUCT.append((i, "قسم", x)); ST_TITLES.add(x)
        continue
    m = HDR_STRUCT.match(x)
    if not m:
        continue
    kind, name = m.group(1), x.split()[1].strip(":")
    title = m.group(2).strip(" :")
    if not title:
        # سطرٌ واحدٌ للعنوان، ولا يُضمّ إليه التالي إلّا إذا كان الأوّلُ **ناقصَ التركيب**
        # (ينتهي بحرف جرٍّ أو عطفٍ أو باسمٍ مضافٍ يطلب مضافًا إليه) — وإلّا التُقطت ترويسةٌ
        # فرعيةٌ داخل المادة على أنّها من عنوان الفصل.
        CONT = ("على", "في", "من", "عن", "و", "أو", "حقوق", "حق", "مدة", "أحكام", "بشأن", "لدى")
        parts = []
        nxt = P[i + 1].strip()
        if not (HDR_ART.match(nxt.translate(_AR)) or HDR_STRUCT.match(nxt) or len(nxt) > 90):
            parts.append(nxt); ST_TITLES.add(nxt)
            if nxt.split()[-1] in CONT:
                nx2 = P[i + 2].strip()
                if not (HDR_ART.match(nx2.translate(_AR)) or HDR_STRUCT.match(nx2) or len(nx2) > 90):
                    parts.append(nx2); ST_TITLES.add(nx2)
        title = " ".join(parts)
    STRUCT.append((i, kind, "%s %s%s" % (kind, name, " — " + title if title else "")))
assert len([s for s in STRUCT if s[1] == "الباب"]) == 3, STRUCT
assert len([s for s in STRUCT if s[1] == "الفصل"]) == 7, STRUCT


def unwrap(seg):
    BUL = re.compile(r"^(?:\d+\s*-|-\s*\d|[أ-ي]\s*-|أولًا|ثانيًا|ثالثًا|رابعًا|خامسًا|سادسًا|"
                     r"سابعًا|ثامنًا|تاسعًا|عاشرًا|أولاً|ثانياً)")
    out = []
    for x in (clean(y) for y in seg if y.strip()):
        if out and not out[-1].endswith((".", ":", "؛")) and not BUL.match(x):
            out[-1] += " " + x
        else:
            out.append(x)
    return "\n".join(out).strip()


pre_end = STRUCT[0][0]
preamble = unwrap(P[:pre_end])
sig_i = next(i for i, x in enumerate(P) if x.strip() == "أمير الكويت")
ARTS, ORDER = {}, []
for j, (s, num) in enumerate(marks):
    e = marks[j + 1][0] if j + 1 < len(marks) else sig_i
    seg = [x for i3, x in enumerate(P[s + 1:e], start=s + 1)
           if not HDR_STRUCT.match(x) and x.strip() not in ST_TITLES and i3 not in SUB_AT]
    bab, fasl, last = None, None, -1
    for i2, k2, t2 in STRUCT:                              # الجاريُ عند هذه المادة
        if i2 >= s:
            break
        last = i2
        if k2 == "الباب":
            bab, fasl = t2, None                           # بابٌ جديد يُصفّر فصلَه
        else:
            fasl = t2
    sub = next((t for i2, t in reversed(SUB) if last < i2 < s), None)   # يُصفَّر عند كلّ فصل
    ARTS[num] = {"num": num, "text": unwrap(seg), "bab": bab, "fasl": fasl, "subhead": sub}
    ORDER.append(num)
issuance = unwrap(P[sig_i:])
assert "الموافق" not in issuance, "الملفُّ صار فيه تاريخٌ ميلاديّ — راجِع الاستكمال"
issuance += ("\n" + GAZETTE["issued_gregorian"]
             + "  ⟨مُستكمَلٌ من صورة الجريدة الرسمية: " + GAZETTE["citation"]
             + "؛ ولم يكن في ملفّ DOCX. ويوافقه الحساب: 20 ذي القعدة 1440 ≈ 22–23 يوليو 2019⟩")

data = {"preamble_text": preamble, "issuance": issuance,
        "articles": {str(n): ARTS[n] for n in ORDER}, "order": [str(n) for n in ORDER],
        "structure": [t for _, _, t in STRUCT],
        "corrections": [{"from": o, "to": n, "basis": s} for o, n, s in FIX],
        "structural_splits": [{"from": o, "to": p, "basis": s} for o, p, s in SPLIT],
        "subheadings": [t for _, t in SUB],
        "gazette": GAZETTE, "gazette_divergences": GAZETTE_DIVERGENCES}
(H / "law75_2019_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                          encoding="utf-8")

print("== قانون 75/2019 — حقوق المؤلف والحقوق المجاورة ==")
print("موادّ:", len(ORDER), "| أبواب:", len([s for s in STRUCT if s[1] == "الباب"]),
      "| فصول:", len([s for s in STRUCT if s[1] == "الفصل"]))
assert len(ORDER) == 51
blob = preamble + " " + " ".join(a["text"] for a in ARTS.values()) + " " + issuance
print("محارف تالفة �:", blob.count("�"),
      "| تشكيلٌ مضاعف:", len(re.findall(r"([ً-ْ])\1", blob)),
      "| «-N» مقلوبة:", len(re.findall(r"(?<![\d.،])-\d+(?=\s|$)", blob)))
assert blob.count("�") == 0 and not re.findall(r"([ً-ْ])\1", blob)
short = [n for n in ORDER if len(ARTS[n]["text"]) < 40]
print("موادُّ قصيرة:", short or "لا"); assert not short
print("\nالهيكل:")
for _, k, t in STRUCT:
    r = [n for n in ORDER if (ARTS[n]["fasl"] or ARTS[n]["bab"]) == t]
    print("   %-62s %s" % (t, "م%d-م%d" % (r[0], r[-1]) if r else "—"))
print("\nتصحيحاتٌ مطبَّقة: %d" % len(FIX))
for o, n, _ in FIX:
    print("   «%s» ⇐ «%s»" % (o.replace("�", "�"), n))
print("\nعناوينُ فرعيةٌ انتُزعت من متونٍ سبقتها: %d" % len(SUB))
for t in dict.fromkeys(t for _, t in SUB):
    r = [n for n in ORDER if ARTS[n]["subhead"] == t]
    print("   %-30s %s" % (t, "، ".join("م%d-م%d" % (r[0], r[-1]) for _ in [0]) if r else "—"))
for n in (5, 8, 15, 16, 21, 22):                           # الذيولُ التي تسرّبت إليها
    assert not any(h in ARTS[n]["text"] for h in ("الحقوق الأدبية\n", "الحقوق المالية\n")) \
        and not ARTS[n]["text"].endswith(("الحقوق الأدبية", "الحقوق المالية")), \
        "م%d ما زال ذيلُها عنوانًا: %r" % (n, ARTS[n]["text"][-40:])
print("   ✓ ذيولُ م5 وم8 وم15 وم16 وم21 وم22 خالصةٌ من العناوين")
print("\nفصولٌ بنيويّة (ترويسةٌ ملتصقة): %d" % len(SPLIT))
for o, p, _ in SPLIT:
    print("   «…%s» ⇒ «…%s» + «%s»" % (o[-28:], p[0][-14:], p[1]))
assert "أحكام ختامية" not in ARTS[47]["text"], "الترويسةُ ما زالت في متن م47"
assert ARTS[48]["fasl"] == "أحكام ختامية" and ARTS[51]["fasl"] == "أحكام ختامية", \
    (ARTS[48]["fasl"], ARTS[51]["fasl"])
assert ARTS[47]["fasl"] == "الفصل الثاني — العقوبات", ARTS[47]["fasl"]
print("   ✓ العقوبات م41–م47 · الأحكام الختامية م48–م51")
print("\nخلافُ الشاهدين (سُجّل ولم يُغيَّر): %d" % len(GAZETTE_DIVERGENCES))
for d in GAZETTE_DIVERGENCES:
    print("   ⚠️ %s" % d["where"])
print("\nبيان الإصدار: " + issuance.replace("\n", " "))
for n in (1, 31, 41, 50):
    print("\n--- م%d | %s ---\n%s" % (n, ARTS[n]["fasl"] or ARTS[n]["bab"], ARTS[n]["text"][:200]))
print("\n✓ كُتب law75_2019_parsed.json")
