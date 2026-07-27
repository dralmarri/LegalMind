#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""law13_2026_parsed.json — المرسوم بقانون رقم 13 لسنة 2026 بشأن تأمين وحماية المصالح العليا للجهات
العسكرية. 34 مادة متسلسلة + 6 فصول + ديباجة. التلف حتميّ: أقواسٌ معكوسةٌ حول أرقام «) 16 (» (اتجاه)
+ علامات «__» دخيلة — تُصوَّب آليًّا (الأقواس كلّها حول أرقامٍ فالتصويب مأمون). الفرع «جزائي»."""
import zipfile, re, html, json, pathlib

H = pathlib.Path(__file__).parent
RAW = zipfile.ZipFile(H / "new_law10.docx").read("word/document.xml").decode("utf-8")
_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
PARAS = [x for x in (html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p))).strip()
                     for p in re.findall(r"<w:p[ >].*?</w:p>", RAW, re.S)) if x]
_ART = re.compile(r"^(?:المادة|مادة)\s*([٠-٩0-9]+)(\s*مكرر[ً-ْ]*ا?)?\s*[).\s]*$")
_CH = re.compile(r"^(?:الفصل|الباب)\s+(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن)\s*:?\s*$")


def clean(t):
    # أقواسٌ معكوسةُ الاتجاه حول أرقام (وقوائم أرقام): «) 16 (» / «) 27 ، 26 ، 5 (» ⇒ «(16)» — مأمونٌ
    # لاقتصاره على محتوًى رقميّ فلا يمسّ نصّ الجُمَل (بخلاف المبادلة العامّة).
    t = re.sub(r"\)\s*([٠-٩0-9]{1,4}(?:\s*[،,/]\s*[٠-٩0-9]{1,4})*)\s*\(", r"(\1)", t)
    t = re.sub(r"\)\s*([أ-ي])\s*\(", r"(\1)", t)                 # )ب( تعدادٌ حرفيّ
    t = re.sub(r"_+", " ", t)                                     # علامات «__» دخيلة
    t = re.sub(r"[ً-ْ]{2,}", lambda m: m.group()[0], t)
    t = re.sub(r"\s{2,}", " ", t).strip(" .:؛")
    return t


# boundaries: article headers + chapter headings
marks = []
for i, x in enumerate(PARAS):
    ma = _ART.match(x); mc = _CH.match(x)
    if ma:
        marks.append(("art", "m%d%s" % (int(ma.group(1).translate(_AR)), "-mukarrar" if ma.group(2) else ""), i))
    elif mc:
        marks.append(("ch", x, i))

art_pos = [p for k, _, p in marks if k == "art"]
ch_pos = [p for k, _, p in marks if k == "ch"]
boundaries = sorted(art_pos + ch_pos)
first = boundaries[0]
preamble = clean(" ".join(PARAS[:first]))

# chapter label = «الفصل X» + following non-article paragraphs until next article header
section_at = {}
for c in ch_pos:
    nxt = min([a for a in art_pos if a > c], default=len(PARAS))
    section_at[nxt] = re.sub(r"\s+", " ", " ".join(PARAS[c:nxt])).strip(" :")

A, ORDER, cur_sec = {}, [], None
for k, key, pos in [m for m in marks if m[0] == "art"]:
    if pos in section_at:
        cur_sec = section_at[pos]
    nxt = min([b for b in boundaries if b > pos], default=len(PARAS))
    A[key] = {"text": clean(" ".join(PARAS[pos + 1:nxt])), "sec": cur_sec}
    ORDER.append(key)

data = {"preamble_text": preamble, "articles": {k: v["text"] for k, v in A.items()},
        "sections": {k: v["sec"] for k, v in A.items()}, "order": ORDER}
(H / "law13_2026_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- verification ----
blob = preamble + " " + " ".join(v["text"] for v in A.values())
assert "�" not in blob
seqok = [int(k[1:]) for k in ORDER] == list(range(1, 35))
rev = re.findall(r"\)\s*[٠-٩0-9أ-ي]\s*\(", blob)
print("law13/2026 parsed: articles", len(A), "| sequential 1-34:", seqok)
print("residual reversed-paren:", rev or "لا", "| _:", blob.count("_"), "| � :", blob.count("�"))
print("sections:", sorted(set(v["sec"] for v in A.values() if v["sec"])))
empty = [k for k, v in A.items() if len(v["text"]) < 10]
print("short/empty:", empty or "لا")
print("preamble head:", preamble[:110])
for k in ("m1", "m2", "m10", "m34"):
    print(f"\n--- {k} (sec={A[k]['sec']}) ---\n{A[k]['text'][:200]}")
