#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني law33_2016_parsed.json — القانون رقم 33 لسنة 2016 بشأن بلدية الكويت، من DOCX. 53 مادة متسلسلة
+ ديباجةٌ غنيّةٌ بالإحالات + أربعةُ أبواب. النصّ نظيفٌ (لا إسقاطَ حروفٍ منهجيّ؛ لا «عى»/«فى»)، والتلفُ كلُّه
حتميّ: أقواسٌ معكوسةٌ حول أرقام «) 5 (»، وتشكيلٌ مضاعف، وعلاماتُ «__»/«) ))» دخيلة — تُصوَّب آليًّا.
الفرع «إداري» (تنظيمٌ إداريٌّ بلديّ: المجلس البلدي والجهاز التنفيذي والتراخيص والمخالفات). يُمسَح قبل الإخراج."""
import zipfile, re, html, json, pathlib

H = pathlib.Path(__file__).parent
RAW = zipfile.ZipFile(H / "new_law15.docx").read("word/document.xml").decode("utf-8")
_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
PARAS = [x for x in (html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p))).strip()
                     for p in re.findall(r"<w:p[ >].*?</w:p>", RAW, re.S)) if x]
HDR = re.compile(r"^(?:المادة|مادة)\s*([٠-٩0-9]+)\s*(مكرر[ً-ْ]*ا?)?\s*[).\s]*$")
SEC = re.compile(r"^(الباب\s+\S+|باب\s+تمهيد\S*|الفصل\s+\S+)[\sً-ْ]*(?::\s*(.*))?$")
FOOTER = re.compile(r"^(?:أمير الكويت|صدر بقصر السيف)")


def clean(t):
    t = re.sub(r"\)\s*([٠-٩0-9]{1,4}(?:\s*[،,/]\s*[٠-٩0-9]{1,4})*)\s*\(", r"(\1)", t)
    t = re.sub(r"_+", " ", t)
    t = re.sub(r"[ً-ْ]{2,}", lambda m: m.group()[0], t)
    t = re.sub(r"\s{2,}", " ", t).strip(" .:؛,")
    return t


first_art = next(i for i, x in enumerate(PARAS) if HDR.match(x) and HDR.match(x).group(1).translate(_AR) == "1")
recital_start = next((i for i, x in enumerate(PARAS[:first_art]) if x.startswith("بعد الاطلاع") or x.startswith("بعد الإطلاع")), 0)
preamble = clean(" ".join(PARAS[recital_start:first_art]))
foot_at = next((i for i, x in enumerate(PARAS) if FOOTER.match(x)), len(PARAS))

A, ORDER, SECTIONS = {}, [], {}
cur_bab, cur_fasl = "", ""
pending_key, pending_sec, buf = None, "", []


def flush(key):
    if key is not None:
        A[key] = clean(" ".join(buf))
        SECTIONS[key] = pending_sec
        ORDER.append(key)


# نبدأ المسحَ من أوّل ترويسةِ بابٍ قبل المادة 1 (إن وُجدت) لالتقاط السياق
scan = next((i for i in range(first_art - 1, recital_start, -1) if SEC.match(PARAS[i])), first_art)
i = scan
while i < min(len(PARAS), foot_at):
    x = PARAS[i]
    mh = HDR.match(x)
    ms = SEC.match(x) if not mh else None
    if mh:
        flush(pending_key); buf = []
        num = mh.group(1).translate(_AR)
        pending_key = "m%s%s" % (num, "-mukarrar" if mh.group(2) else "")
        pending_sec = " — ".join(p for p in (cur_bab, cur_fasl) if p)
    elif ms:
        head = ms.group(1); title = (ms.group(2) or "").strip()
        lbl = (head + (": " + title if title else "")).strip()
        if head.startswith(("الباب", "باب")):
            cur_bab, cur_fasl = lbl, ""
        else:
            cur_fasl = lbl
    else:
        if pending_key is not None:
            buf.append(x)
    i += 1
flush(pending_key)

issue_tail = clean(" ".join(PARAS[foot_at:]))
data = {"title": "القانون رقم 33 لسنة 2016 بشأن بلدية الكويت", "preamble_text": preamble,
        "issue_tail": issue_tail, "articles": A, "sections": SECTIONS, "order": ORDER}
(H / "law33_2016_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- verification ----
blob = preamble + " " + " ".join(A.values())
nums = [int(re.match(r"m(\d+)", k).group(1)) for k in ORDER]
print("law33/2016 parsed: articles", len(A), "| range", min(nums), "-", max(nums))
print("sequential 1-53:", nums == list(range(1, 54)))
print("� :", blob.count("�"), "| _:", blob.count("_"), "| ) )):", blob.count(") ))"),
      "| residual rev-paren:", len(re.findall(r"\)\s*[٠-٩0-9]+\s*\(", blob)),
      "| doubled-diac:", len(re.findall(r"[ً-ْ]{2,}", blob)))
assert "�" not in blob and nums == list(range(1, 54))
empty = [k for k, v in A.items() if len(v) < 8]
print("short/empty:", empty or "لا")
print("sections:", sorted(set(SECTIONS.values())))
print("preamble laws cited:", len(re.findall(r"قانون رقم|بالقانون رقم", preamble)))
print("footer excluded:", "أمير الكويت" not in blob)
for k in ("m1", "m2", "m53"):
    print(f"\n--- {k} (قسم={SECTIONS[k]}) ---\n{A[k][:170]}")
