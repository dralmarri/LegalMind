#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني law49_2016_parsed.json — القانون رقم 49 لسنة 2016 بشأن المناقصات العامة (م1–م97 + م62 مكرر).

مصادرُ النصّ ثلاثةٌ، مرتّبةٌ بحجّيّتها:
 1. law49_2016_raw.txt   — نقلٌ بصريٌّ صفحةً صفحة من صور الملفّ (ص1–ص55) ⇒ م1–م65. وهو الأحجّ
    للنصف الأول لأنّه من الصورة مباشرةً لا من نصٍّ مجمَّع.
 2. law49_tail.txt       — م66–م97، مصدرُها النصُّ المجمَّع مقابَلًا بصور ص55–ص76 (صفرُ اختلافات
    عدا م94، انظر أدناه)، مع تصحيح عنوان م67 وترويسة الباب العاشر.
 3. law49_2016_amendments.txt — نصوصُ 74/2019 و1/2024 وبها يُستبدَل النافذُ من المواد.

والقاعدةُ المتّبعة في التعديل صريحةٌ ولا تخمين فيها:
 • **استبدالٌ كامل** (م5، م26، م31، م61، م62، م78، م87): متنُ الكائن هو النصُّ المعدَّل، ويُحفَظ
   نصُّ 2016 في `metadata.superseded_text_2016` — فلا يضيع الأصل ولا يُقدَّم على النافذ.
 • **تعديلٌ جزئيّ** (م1، م2، م18، م19، م25، م39): لا يُدمَج الشقُّ المعدَّل في المتن الأصليّ
   دمجًا تقديريًّا — لأنّ الدمج تأليفٌ لا نقل. بل يبقى متنُ 2016 كما هو، ويُلحَق به الشقُّ
   المعدَّل تحت عنوانٍ صريح، ويُبيَّن في الميتاداتا أيُّ بندٍ مُسَّ.
 • **إضافة** (م62 مكرر، وتعريفُ «المنتج المحلي» في م1): كائنٌ/شقٌّ مستقلٌّ موسومٌ بالإضافة.

والتصحيحاتُ المطبَّقة — كلُّها موثَّقةٌ في law49_divergences.md:
 [1] م2/ثالثًا/1 «عرض رئيس مجلس الوزراء»  — من الصورة، فهو في النقل البصريّ سلفًا.
 [2] م27 «التظلّم أمام لجنة التصنيف»       — من الصورة، سلفًا.
 [3] م64 «أو بناءً على مذكرة… في الحالتين» — من الصورة، سلفًا.
 [4] ترويسةُ الباب العاشر بلا «وعقد الشراء» ولا «الفصل الأول» — بالاستدراك الثاني (ع1307).
 [5] لا تكرارَ لتعريف «المشروع الصغير» — النقلُ البصريّ يحمل صيغة 2016 وحدَها، والمعدَّلةُ تأتي
     من ملفّ التعديلات موسومةً.
 [6] عنوانُ م67 عربيّ «تنفيذ العقد قبل أداء التأمين» — مطبَّقٌ في الذيل.
 [7] م94: «القانون رقم (37) لسنة 1964» بالاستدراك الأوّل (ع1303 ص32) — والملفُّ يحمل «(73)»
     غيرَ مصحَّح، فلا يُتَّخذ مرجعًا وحدَه هنا. والذيلُ يحمل الصيغةَ المصحَّحة.
"""
from __future__ import annotations
import json, pathlib, re, sys

H = pathlib.Path(__file__).parent
RAW = (H / "law49_2016_raw.txt").read_text(encoding="utf-8")
TAIL = (H / "law49_tail.txt").read_text(encoding="utf-8")
AMD = (H / "law49_2016_amendments.txt").read_text(encoding="utf-8")

# ---------------------------------------------------------------- الهيكل
# خريطةُ الأبواب والفصول — كلُّها مقروءةٌ من صور الصفحات، لا مستنبَطة.
# (رقمُ أوّل مادة، عنوانُ الباب، عنوانُ الفصل/القسم)
# م1–م65: تُستخرَج ترويساتُها من النقل البصريّ نفسِه (لا تُخمَّن) — انظر build_struct_from_raw أدناه.
# م66–م97: مقروءةٌ من صور ص55–ص76 مادّةً مادّة.
STRUCT_TAIL = [
    (74, "الباب السابع", None),
    (77, "الباب الثامن — النظر في الشكاوى والتظلمات", "أولًا: الشكاوى"),
    (78, "الباب الثامن — النظر في الشكاوى والتظلمات", "ثانيًا: التظلمات"),
    (79, "الباب الثامن — النظر في الشكاوى والتظلمات", None),
    (82, "الباب التاسع — منع تضارب المصالح والمساءلة والجزاءات", "الفصل الأول — منع تضارب المصالح"),
    (83, "الباب التاسع — منع تضارب المصالح والمساءلة والجزاءات", "الفصل الثاني — مساءلة موظفي الجهات العامة"),
    (84, "الباب التاسع — منع تضارب المصالح والمساءلة والجزاءات", "الفصل الثالث — السلوك الواجب على المناقصين"),
    (85, "الباب التاسع — منع تضارب المصالح والمساءلة والجزاءات", "الفصل الرابع — الجزاءات"),
    (86, "الباب العاشر", None),          # الترويسةُ مصحَّحةٌ بالاستدراك الثاني: بلا عنوانٍ فرعيّ
    (87, "الباب الحادي عشر — أحكام ختامية", None),
]


# ---------------------------------------------------------------- تنظيف
_PAGE = re.compile(r"^⟦ص\d+⟧$")
_CONT = re.compile(r"\s*\[يتبع ص\d+\]\s*$")
_NOTE = re.compile(r"^(?:###|⚠️)")


def _clean_lines(lines):
    out = []
    for ln in lines:
        s = ln.rstrip()
        if not s.strip() or _PAGE.match(s.strip()) or _NOTE.match(s.strip()):
            continue
        out.append(_CONT.sub("", s).strip())
    return out


def _join(lines):
    """يوصل السطرَ المقطوعَ بعلامة [يتبع صN] بما بعده، ويُبقي الفقراتِ الأخرى أسطرًا."""
    return "\n".join(lines).strip()


# ---------------------------------------------------------------- تفكيك النصف الأول
RAW_HDR = re.compile(r"^(?:الفصل\s+\S+\s+)?\(مادة\s+(\d+)\)\s*$")
STRUCT_HDR = re.compile(r"^(?:الباب|الفصل)\s")

raw_lines = RAW.split("\n")
marks = []
for i, ln in enumerate(raw_lines):
    m = RAW_HDR.match(ln.strip())
    if m:
        marks.append((i, int(m.group(1))))
assert [n for _, n in marks] == list(range(1, 66)), "خللٌ في تسلسل مواد النقل البصريّ"

# ترويساتُ الأبواب والفصول في النصف الأول تُقرأ من النقل البصريّ نفسِه: سطرُ «الباب/الفصل …»
# ويليه عنوانُه في سطرٍ أو سطرين حتى أوّل فراغٍ أو ترويسةِ مادة. فلا يُخمَّن عنوانٌ ولا يُختلَق.
_HDR_ONLY = re.compile(r"^(?:الباب|الفصل)\s+\S+$")
_HDR_INLINE = re.compile(r"^(الفصل\s+\S+)\s+\(مادة\s+\d+\)$")   # «الفصل الأول (مادة 1)»


def _title_after(idx):
    out = []
    for x in raw_lines[idx + 1:idx + 6]:
        st = x.strip()
        if len(st) > 90:                    # سطرٌ طويل ⇒ متنٌ لا عنوان
            break
        if not st:                          # فراغٌ قبل العنوان (عبورُ صفحة) يُتخطّى، وبعده يقطع
            if out:
                break
            continue
        if _PAGE.match(st):                 # عبورُ صفحةٍ لا يقطع العنوان
            continue
        if (_NOTE.match(st) or RAW_HDR.match(st) or _HDR_ONLY.match(st)
                or _HDR_INLINE.match(st)):  # ترويسةٌ تالية أو ملاحظة ⇒ انتهى العنوان
            break
        out.append(st)
        if len(out) == 2:                   # عنوانُ الباب سطرانِ على الأكثر
            break
    return " ".join(out)


STRUCT_HEAD, _bab, _fasl = [], None, None
for i, ln in enumerate(raw_lines):
    st = ln.strip()
    mi = _HDR_INLINE.match(st)
    if st.startswith("الباب ") and _HDR_ONLY.match(st):
        t = _title_after(i)
        _bab, _fasl = (st + (" — " + t if t else "")), None
    elif mi:                                   # «الفصل الأول (مادة 1)» — ترويسةٌ ومادّةٌ في سطر
        t = _title_after(i)
        _fasl = mi.group(1) + (" — " + t if t else "")
    elif st.startswith("الفصل ") and _HDR_ONLY.match(st):
        t = _title_after(i)
        _fasl = st + (" — " + t if t else "")
    m = RAW_HDR.match(st)
    if m:
        STRUCT_HEAD.append((int(m.group(1)), _bab, _fasl))
assert len(STRUCT_HEAD) == 65 and STRUCT_HEAD[0][1], "لم تُلتقط ترويساتُ النصف الأول"

first = marks[0][0]
# الديباجة: ما قبل أوّل ترويسةِ باب
pre_end = next(i for i, ln in enumerate(raw_lines) if ln.strip().startswith("الباب الأول"))
preamble = _join(_clean_lines(raw_lines[:pre_end]))

ARTS: dict[str, dict] = {}
ORDER: list[str] = []

for j, (s, num) in enumerate(marks):
    e = marks[j + 1][0] if j + 1 < len(marks) else len(raw_lines)
    seg = raw_lines[s + 1:e]
    # علاماتُ الصفحات والملاحظاتُ تُفرَّغ (لا تُحذَف) كي لا تفصل ترويسةَ البابِ التاليةَ عن كتلتها
    seg = ["" if (_PAGE.match(x.strip()) or _NOTE.match(x.strip())) else x for x in seg]
    # ترويسةُ البابِ/الفصلِ التي تسبق المادةَ التالية تخصُّ تلك لا هذه، فتُقتطع من الذيل هي وما
    # بعدها (عنوانُ الباب قد يقع في سطرٍ تالٍ، وربّما فصلَه عنها عبورُ صفحة). والترويسةُ سطرٌ
    # قائمٌ بذاته من كلمتين («الفصل الثاني»/«الباب السادس») — لا تلتبس بإحالةٍ داخل جملة.
    # قد تتراكب ترويستان (باب ثمّ فصل) بعنوانَيهما، فيُؤخَذ أوّلُ موضعٍ يصير ما بعده كلُّه
    # ترويساتٍ قصيرة (≤6 أسطر، كلٌّ ≤90 حرفًا) — فلا يُقتطع متنٌ حقيقيّ بالخطأ.
    hdr_only = re.compile(r"^(?:الباب|الفصل)\s+\S+$")
    cands = [i for i, x in enumerate(seg) if hdr_only.match(x.strip())]
    for i in cands:
        rest = [x.strip() for x in seg[i:] if x.strip()]
        if len(rest) <= 6 and all(len(x) <= 90 for x in rest):
            del seg[i:]
            break
    while seg and not seg[-1].strip():
        seg.pop()
    body = _clean_lines(seg)
    # العنوانُ: الأسطرُ الأولى قبل أوّل سطرٍ فارغ (بعد تخطّي علامات الصفحات/الملاحظات)
    title_lines, k = [], 0
    for k, ln in enumerate(seg):
        st = ln.strip()
        if not st:
            break
        if _PAGE.match(st) or _NOTE.match(st):
            continue
        title_lines.append(st)
    title = " ".join(title_lines) if title_lines else ""
    text = _join(_clean_lines(seg[k:]))
    if not text:                      # مادّةٌ بلا عنوانٍ منفصل: كلُّ الجسم متنٌ
        title, text = "", _join(body)
    key = "m%d" % num
    ARTS[key] = {"num": num, "title": title, "text": text}
    ORDER.append(key)

# ---------------------------------------------------------------- تفكيك الذيل
TAIL_HDR = re.compile(r"^\[م(\d+)\]\s*(.*)$")
tail_lines = TAIL.split("\n")
tmarks = [(i, int(m.group(1)), m.group(2).strip())
          for i, ln in enumerate(tail_lines) for m in [TAIL_HDR.match(ln.strip())] if m]
assert [n for _, n, _ in tmarks] == list(range(66, 98)), "خللٌ في تسلسل مواد الذيل"

for j, (s, num, title) in enumerate(tmarks):
    e = tmarks[j + 1][0] if j + 1 < len(tmarks) else len(tail_lines)
    seg = tail_lines[s + 1:e]
    cut = next((i for i, x in enumerate(seg) if x.strip().startswith("=== ")), len(seg))
    seg = seg[:cut]   # ما بعد ترويسةِ «=== » (بيانُ الإصدار/ترويسةُ باب) ليس متنَ المادة
    key = "m%d" % num
    ARTS[key] = {"num": num, "title": title, "text": _join(_clean_lines(seg))}
    ORDER.append(key)

# ---------------------------------------------------------------- التعديلات
AMD_HDR = re.compile(r"^مادة\s*\((\d+)\)(\s*مكرر)?\s*(.*)$")
amd_lines = AMD.split("\n")
amarks = [(i, m.group(1), bool(m.group(2)))
          for i, ln in enumerate(amd_lines) for m in [AMD_HDR.match(ln.strip())] if m]
AMD_TXT: dict[str, str] = {}
for j, (s, num, mk) in enumerate(amarks):
    e = amarks[j + 1][0] if j + 1 < len(amarks) else len(amd_lines)
    seg = amd_lines[s + 1:e]
    # الملاحظاتُ (⚠️ ★ --- ===) تجيء دائمًا في ذيل القسم وقد تمتدّ أسطرًا، فيُقطَع عندها لا تُرشَّح
    cut = next((i for i, x in enumerate(seg) if x.strip().startswith(("⚠️", "---", "===", "★"))),
               len(seg))
    # ملفُّ التعديلات ملفوفٌ عند ~100 حرفًا، فتُعاد الفقراتُ إلى سطرٍ واحد: يُوصَل السطرُ بسابقه
    # ما لم ينتهِ السابقُ بنقطةٍ/نقطتين أو يبدأ الحاليُّ بعلامةِ بندٍ (1- أ- أولًا: «).
    _BULLET = re.compile(r"^(?:[0-9]+\s*-|[أ-ي]\s*-|أولًا|ثانيًا|ثالثًا|رابعًا|خامسًا|«|المادة)")
    para = []
    for x in (y.strip() for y in seg[:cut] if y.strip()):
        if para and not para[-1].endswith((".", ":", "،")) and not _BULLET.match(x):
            para[-1] += " " + x
        else:
            para.append(x)
    txt = _join(para)
    k = "m%s%s" % (num, "-mukarrar" if mk else "")
    if k in AMD_TXT:                    # م1 يردُ مرّتين: البندان المعدَّلان ثمّ البندُ المضاف
        AMD_TXT[k] += "\n" + txt
    else:
        AMD_TXT[k] = txt

# م31 نصُّها في قانون 1/2024 داخل «(المادة الثانية)» بين قوسين معقوفين لا بترويسة «مادة (31)»
m31 = re.search(r"«المادة \(31\)[^»]*»", AMD, re.S)
assert m31, "لم يُعثَر على نصّ م31 المستبدَل بـ1/2024"
_m31 = [x.strip() for x in m31.group(0).strip("«»").strip().split("\n") if x.strip()]
M31_TITLE = _m31[0].split("—", 1)[1].strip(" :") if "—" in _m31[0] else ""
_p = []                                    # فكُّ اللفّ نفسُه، ثمّ إسقاطُ سطر «المادة (31) — …»
for x in _m31[1:]:
    if _p and not _p[-1].endswith((".", ":", "،")) and not re.match(
            r"^(?:[0-9]+\s*-|[أ-ي]\s*-|أولًا|ثانيًا|ثالثًا|وفي)", x):
        _p[-1] += " " + x
    else:
        _p.append(x)
AMD_TXT["m31"] = "\n".join(_p)

FULL = {  # استبدالٌ كامل: (المفتاح، القانونُ المعدِّل)
    "m5": "74/2019", "m26": "74/2019", "m61": "74/2019", "m62": "74/2019",
    "m78": "74/2019", "m87": "74/2019", "m31": "1/2024",
}
PARTIAL = {  # تعديلٌ جزئيّ: (المفتاح، القانون، وصفُ الشقّ الممسوس)
    "m1":  ("74/2019", "بندا «المشروع الصغير أو المتوسط» و«المنتج الوطني»، وإضافةُ بند «المنتج المحلي»"),
    "m2":  ("74/2019", "الفقرةُ الأولى من البند (3) — مؤسسة البترول الكويتية"),
    "m18": ("74/2019", "البند (6)"),
    "m19": ("74/2019", "الفقرةُ الأولى (أولًا)"),
    "m25": ("74/2019", "إضافةُ البند (8) — ممثل الصندوق الوطني"),
    "m39": ("74/2019", "البند (2)"),
}
for k in list(FULL) + list(PARTIAL) + ["m62-mukarrar"]:
    assert k in AMD_TXT, "نصُّ التعديل مفقود: %s" % k

AMEND_STATUS: dict[str, dict] = {}
if M31_TITLE and not ARTS["m31"]["title"]:
    ARTS["m31"]["title"] = M31_TITLE      # عنوانُ م31 من نصّ 1/2024 نفسِه، لا من تخمين

for k, law in FULL.items():
    orig = ARTS[k]["text"]
    ARTS[k]["text"] = AMD_TXT[k]
    AMEND_STATUS[k] = {"amendment_status": "مستبدلة بالكامل بالقانون %s" % law,
                       "in_force_source": law, "superseded_text_2016": orig}
for k, (law, what) in PARTIAL.items():
    ARTS[k]["text"] = (ARTS[k]["text"] + "\n\nـــ الشقُّ المعدَّل بالقانون %s (النافذ) ـــ\n" % law
                       + AMD_TXT[k])
    AMEND_STATUS[k] = {"amendment_status": "معدَّلة جزئيًا بالقانون %s" % law,
                       "amended_part": what, "in_force_source": "2016 + %s" % law}

# م62 مكرر — مادّةٌ مضافةٌ بالقانون 74/2019، تُدرَج بعد م62
ARTS["m62-mukarrar"] = {"num": 62.5, "title": "أفضلية عطاءات المشروعات الصغيرة والمتوسطة",
                        "text": AMD_TXT["m62-mukarrar"]}
AMEND_STATUS["m62-mukarrar"] = {"amendment_status": "مضافة بالقانون 74/2019",
                                "in_force_source": "74/2019"}
ORDER.insert(ORDER.index("m62") + 1, "m62-mukarrar")

# ---------------------------------------------------------------- الهيكل لكلّ مادة
_HEAD_MAP = {n: (b, f) for n, b, f in STRUCT_HEAD}


def struct_of(num):
    if num in _HEAD_MAP:                      # م1–م65: من النقل البصريّ
        return _HEAD_MAP[num]
    bab = fasl = None                         # م66–م97: من صور ص55–ص76
    for start, b, f in STRUCT_TAIL:
        if num >= start:
            bab, fasl = b, f
        else:
            break
    if bab is None:                           # م66–م73 امتدادُ الفصل الرابع من الباب السادس
        return _HEAD_MAP[65]
    return bab, fasl


for k in ORDER:
    b, f = struct_of(int(ARTS[k]["num"]))
    ARTS[k]["bab"], ARTS[k]["fasl"] = b, f

# ---------------------------------------------------------------- بيانُ الإصدار
ISSUANCE = ("نائب أمير الكويت — نواف الأحمد الجابر الصباح.\n"
            "صدر بقصر السيف في: 15 شوال 1437هـ، الموافق: 20 يوليو 2016م.")

data = {"preamble_text": preamble, "issuance": ISSUANCE,
        "articles": {k: ARTS[k] for k in ORDER}, "order": ORDER,
        "amendments": AMEND_STATUS}
(H / "law49_2016_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                          encoding="utf-8")

# ---------------------------------------------------------------- تحقّق
print("== law49_2016 ==")
print("موادّ:", len(ORDER), "| متوقَّع 98 (م1–م97 + م62 مكرر)")
assert len(ORDER) == 98, len(ORDER)
blob = preamble + " " + " ".join(a["text"] for a in ARTS.values())
print("محارف بديلة �:", blob.count("�"), "| علاماتُ صفحات متبقّية:", blob.count("⟦"),
      "| علاماتُ متابعة:", blob.count("[يتبع"))
assert blob.count("�") == 0 and "⟦" not in blob and "[يتبع" not in blob
short = [k for k in ORDER if len(ARTS[k]["text"]) < 40]
print("موادُّ قصيرةٌ (<40 حرفًا):", short or "لا")
assert not short, short
print("الديباجة:", len(preamble), "حرفًا | سطورُها:", preamble.count("\n") + 1)
print("مصحَّحاتٌ مؤكَّدة:",
      "م94→(37)1964" if "(37) لسنة 1964" in ARTS["m97"]["text"] + ARTS["m94"]["text"] else "✗م94",
      "| م27→لجنة التصنيف" if "يتظلم أمام لجنة التصنيف" in ARTS["m27"]["text"] else "| ✗م27",
      "| م64→أو بناء" if "أو بناء على مذكرة" in ARTS["m64"]["text"] else "| ✗م64",
      "| م2→عرض رئيس" if "عرض رئيس مجلس الوزراء" in ARTS["m2"]["text"] else "| ✗م2",
      "| م67→عربيّ" if ARTS["m67"]["title"] == "تنفيذ العقد قبل أداء التأمين" else "| ✗م67")
assert "(37) لسنة 1964" in ARTS["m94"]["text"] and "(73)" not in ARTS["m94"]["text"]
assert "يتظلم أمام لجنة التصنيف" in ARTS["m27"]["text"]
assert "أو بناء على مذكرة" in ARTS["m64"]["text"]
assert "عرض رئيس مجلس الوزراء" in ARTS["m2"]["text"]
assert ARTS["m67"]["title"] == "تنفيذ العقد قبل أداء التأمين"
assert ARTS["m86"]["bab"] == "الباب العاشر" and ARTS["m86"]["fasl"] is None
print("حالةُ التعديل:", len(AMEND_STATUS), "مادّة —",
      ", ".join(sorted(AMEND_STATUS, key=lambda x: ARTS[x]["num"])))
print("م31 (1/2024):", ARTS["m31"]["text"][:90], "…")
print("م62 مكرر:", ARTS["m62-mukarrar"]["text"][:90], "…")
for k in ("m1", "m48", "m79", "m85", "m97"):
    print("\n--- %s | %s | %s ---\n%s" % (k, ARTS[k]["bab"], ARTS[k]["title"] or "(بلا عنوان)",
                                          ARTS[k]["text"][:160]))
print("\n✓ كُتب law49_2016_parsed.json")
