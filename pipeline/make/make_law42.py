#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني law42_2014_parsed.json — القانون رقم 42 لسنة 2014 بشأن حماية البيئة، من DOCX. 181 مادة + م143مكرر
(=182) + ديباجةٌ غنيّةٌ بالإحالات + أبوابٌ وفصول. النصّ نظيفٌ (لا إسقاطَ حروفٍ منهجيّ؛ «فى/إو» رسمٌ إملائيّ
يعالجه المطبِّع)، والتلفُ كلُّه حتميّ: أقواسٌ معكوسةٌ حول أرقام «) 59 (»، وتشكيلٌ مضاعف، وعلاماتُ «) ))»
و«__» دخيلة — تُصوَّب آليًّا. يُستبعَد الفهرسُ (فقرات TOC ذاتُ أرقام الصفحات). الفرع «إداري» (تنظيمٌ بيئيٌّ
بعقوباتٍ ملحقة). يُمسَح قبل الإخراج للتأكّد من التسلسل وخلوّه من التلف."""
import zipfile, re, html, json, pathlib

H = pathlib.Path(__file__).parent
RAW = zipfile.ZipFile(H / "new_law14.docx").read("word/document.xml").decode("utf-8")
_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
PARAS = [x for x in (html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p))).strip()
                     for p in re.findall(r"<w:p[ >].*?</w:p>", RAW, re.S)) if x]

HDR = re.compile(r"^(?:المادة|مادة)\s*([٠-٩0-9]+)\s*(مكرر[ً-ْ]*ا?)?\s*[).\s]*$")
# ترويساتُ الأقسام (باب/فصل/تمهيدي/فرعيّ) — قصيرةٌ وبلا أرقام صفحاتٍ (بخلاف الفهرس):
SEC = re.compile(r"^(الباب\s+\S+|باب\s+تمهيد\S*|الفصل\s+\S+|أولا|ثانيا|ثالثا|رابعا|خامسا|سادسا)[\sً-ْ]*(?::\s*(.*))?$")
# سطرُ الفهرس: ينتهي برقمَي صفحةٍ/بندٍ «... 305 118»
TOC = re.compile(r"\d+\s+\d+\s*$")


def clean(t):
    t = re.sub(r"\)\s*([٠-٩0-9]{1,4}(?:\s*[،,/]\s*[٠-٩0-9]{1,4})*)\s*\(", r"(\1)", t)  # أقواسٌ معكوسةٌ حول أرقام
    t = re.sub(r"_+", " ", t)                                     # علاماتُ «__» دخيلة
    t = re.sub(r"[ً-ْ]{2,}", lambda m: m.group()[0], t)          # تشكيلٌ مضاعف
    t = re.sub(r"\s{2,}", " ", t).strip(" .:؛,")
    return t


# ── حدودُ الديباجة والمتن ──
first_art = next(i for i, x in enumerate(PARAS) if HDR.match(x) and HDR.match(x).group(1).translate(_AR) == "1")
recital_start = next(i for i, x in enumerate(PARAS[:first_art]) if x.startswith("بعد الإطلاع") or x.startswith("بعد الاطلاع"))
recital_end = next(i for i, x in enumerate(PARAS[:first_art]) if "وافق مجلس الأمة" in x or "وافق مجلس الامة" in x)
preamble = clean(" ".join(PARAS[recital_start:recital_end + 1]))

# ── تجميعُ المواد مع تتبّع الأقسام (باب/فصل/فرعيّ) ──
# نبدأ من أوّل ترويسة قسمٍ قبل المادة 1 (الفصل الأول: تعاريف) لالتقاط سياق الأقسام.
sec_scan_start = next((i for i in range(first_art - 1, recital_end, -1) if SEC.match(PARAS[i]) and not TOC.search(PARAS[i])), first_art)

A, ORDER, SECTIONS = {}, [], {}
cur_bab, cur_fasl, cur_sub = "", "", ""
i = sec_scan_start
n = len(PARAS)
pending_key = None
pending_sec = ""
buf = []


def flush(key):
    if key is not None:
        A[key] = clean(" ".join(buf))
        SECTIONS[key] = pending_sec                          # القسمُ مُلتقَطٌ لحظةَ بدء المادة، لا عند flush
        ORDER.append(key)


while i < n:
    x = PARAS[i]
    mh = HDR.match(x)
    ms = SEC.match(x) if not mh else None
    if mh:
        flush(pending_key); buf = []
        num = mh.group(1).translate(_AR)
        pending_key = "m%s%s" % (num, "-mukarrar" if mh.group(2) else "")
        pending_sec = " — ".join(p for p in (cur_bab, cur_fasl, cur_sub) if p)   # لقطةُ السياق الآن
    elif ms and not TOC.search(x):
        # ترويسةُ قسم: نُحدّث السياق (لا نضيفها لنصّ المادة)
        head = ms.group(1); title = (ms.group(2) or "").strip()
        lbl = (head + (": " + title if title else "")).strip()
        if head.startswith(("الباب", "باب")):
            cur_bab, cur_fasl, cur_sub = lbl, "", ""
        elif head.startswith("الفصل"):
            cur_fasl, cur_sub = lbl, ""
        else:                                                    # أولاً/ثانياً…
            cur_sub = lbl
    else:
        if pending_key is not None:
            buf.append(x)
    i += 1
flush(pending_key)

data = {"title": "القانون رقم 42 لسنة 2014 بشأن حماية البيئة",
        "preamble_text": preamble, "articles": A, "sections": SECTIONS, "order": ORDER}
(H / "law42_2014_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

# ── verification ──
blob = preamble + " " + " ".join(A.values())
nums = [int(re.match(r"m(\d+)", k).group(1)) for k in ORDER]
mukarrar = [k for k in ORDER if "mukarrar" in k]
print("law42/2014 parsed: articles", len(A), "| مكرر:", mukarrar)
print("range:", min(nums), "-", max(nums), "| unique base nums:", len(set(nums)))
missing = sorted(set(range(1, 182)) - set(nums))
print("مواد ناقصة (1-181):", missing or "لا")
print("� :", blob.count("�"), "| _:", blob.count("_"), "| ) )) :", blob.count(") ))"),
      "| residual reversed-paren:", len(re.findall(r"\)\s*[٠-٩0-9]+\s*\(", blob)),
      "| doubled-diac:", len(re.findall(r"[ً-ْ]{2,}", blob)))
empty = [k for k, v in A.items() if len(v) < 8]
print("short/empty:", empty or "لا")
print("preamble head:", preamble[:150])
print("preamble laws cited:", len(re.findall(r"قانون رقم", preamble)))
print("sections sample:", sorted(set(SECTIONS.values()))[:6])
for k in ("m1", "m143", "m143-mukarrar", "m181"):
    if k in A:
        print(f"\n--- {k} (قسم={SECTIONS[k][:45]}) ---\n{A[k][:160]}")
