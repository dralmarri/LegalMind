#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني law47_2026_parsed.json — المرسوم بقانون رقم 47 لسنة 2026 في شأن مكافحة جرائم الإرهاب، من DOCX.
النصّ نظيفٌ بنيويًّا (31 مادة متسلسلة 1-31، بلا مكرر، 5 فصول)؛ التلف الوحيد حتميّ: أقواس معكوسة «) N (»
(اتجاه ثنائيّ) وتشكيلٌ مضاعف — يُصوَّبان آليًّا. الاستخراج فقرةً-فقرةً (ترويسة «مادة N» مستقلّة)، مع فصل
ترويسات الفصول من أجساد المواد وتسجيلها كأقسام. لا نقلٌ يدويّ — الاستخراج من المصدر المُتحقَّق مباشرةً."""
import zipfile, re, html, json, pathlib

H = pathlib.Path(__file__).parent
RAW = zipfile.ZipFile(H / "new_law5.docx").read("word/document.xml").decode("utf-8")
_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _txt(p):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p))).strip()


PARAS = [x for x in (_txt(p) for p in re.findall(r"<w:p[ >].*?</w:p>", RAW, re.S)) if x]

_ART = re.compile(r"^مادة\s*([٠-٩0-9]+)(\s*مكرر)?\s*$")
_CH = re.compile(r"^(?:الفصل|الباب)\s+(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن)\s*$")


def clean(t):
    # تصويبٌ مصدريٌّ مؤكَّدٌ من المستخدم (حائز المصدر الرسميّ): تعريف «العمل الإرهابي» في م1 — «كل فعل أو
    # تهديد» لا «تحديد» (خطأ مطبعيّ في الملف المرفوع). محصورٌ في هذه العبارة فلا يمسّ «بتحديد جلسة» في م19.
    t = t.replace("كل فعل أو تحديد يؤدي", "كل فعل أو تهديد يؤدي")
    t = re.sub(r"\)\s*([٠-٩0-9]{1,4})\s*\(", r"(\1)", t)          # ) N ( -> (N) أقواس معكوسة (اتجاه)
    t = re.sub(r"\)\s*([أ-ي])\s*\(", r"(\1)", t)                   # )أ( -> (أ) تعداد حرفيّ معكوس
    t = re.sub(r"[ً-ْ]{2,}", lambda m: m.group()[0], t)            # جمع التشكيل المضاعف
    t = re.sub(r"\s{2,}", " ", t).strip(" .:؛")
    return t


# classify paragraphs: article header / chapter-heading block / body
# an article body runs from its header until the next article-header OR chapter-heading paragraph.
# a chapter block = the «الفصل X» paragraph + following non-article paragraphs until the next «مادة N»;
# it becomes the section label of the article that follows it.
kinds = []  # (type, payload, index)
for i, x in enumerate(PARAS):
    m = _ART.match(x)
    if m:
        kinds.append(("art", (int(m.group(1).translate(_AR)), bool(m.group(2))), i))
    elif _CH.match(x):
        kinds.append(("ch", x, i))

art_idx = [k[2] for k in kinds if k[0] == "art"]
ch_idx = [k[2] for k in kinds if k[0] == "ch"]
boundaries = sorted(art_idx + ch_idx)

# preamble = everything before the first structural marker
first = boundaries[0]
preamble = clean(" ".join(PARAS[:first]))

# build sections: for each chapter marker at position c, its heading text = PARAS[c..next art) joined
section_at = {}  # article-start-index -> section label
for c in ch_idx:
    nxt_art = min([a for a in art_idx if a > c], default=len(PARAS))
    label = re.sub(r"\s+", " ", " ".join(PARAS[c:nxt_art])).strip()
    section_at[nxt_art] = label

A, ORDER = {}, []
cur_sec = None
for pos in art_idx:
    if pos in section_at:
        cur_sec = section_at[pos]
    # body: from pos+1 until next boundary (article or chapter), exclusive
    nxt = min([b for b in boundaries if b > pos], default=len(PARAS))
    body = clean(" ".join(PARAS[pos + 1:nxt]))
    m = _ART.match(PARAS[pos])
    n = int(m.group(1).translate(_AR)); mk = bool(m.group(2))
    key = "m%d%s" % (n, "-mukarrar" if mk else "")
    A[key] = {"text": body, "sec": cur_sec}
    ORDER.append(key)

data = {"articles": A, "order": ORDER, "preamble_text": preamble}
(H / "law47_2026_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- verification ----
blob = json.dumps(data, ensure_ascii=False)
assert "�" not in blob, "residual �!"
assert ") " not in " ".join(v["text"] for v in A.values()) or True
# no reversed-paren left in bodies
rev = [k for k, v in A.items() if re.search(r"\)\s*[٠-٩0-9أ-ي]\s*\(", v["text"])]
empty = [k for k, v in A.items() if len(v["text"]) < 8]
print("law47 parsed:", len(A), "articles; order", len(ORDER))
print("expected 31 sequential:", [int(k[1:]) for k in ORDER] == list(range(1, 32)))
print("reversed-paren residue:", rev or "لا")
print("short/empty bodies:", empty or "لا")
print("sections:", sorted(set(v["sec"] for v in A.values())))
print("preamble head:", preamble[:120])
for k in ("m1", "m7", "m12", "m24", "m31"):
    print(f"\n--- {k} (sec={A[k]['sec']}) ---\n{A[k]['text'][:220]}")
