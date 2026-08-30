#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني law51_2026_parsed.json — المرسوم بقانون رقم 51 لسنة 2026 بتخصيص دوائر جزائية لنظر جرائم أمن الدولة
الخارجي والداخلي وجرائم الأعمال الإرهابية، من DOCX. 7 مواد + ديباجة (بديباجاتٍ). التلف حتميّ: أقواسٌ معكوسةُ
الاتجاه حول أرقام «) 16 (» (سمةُ العرض RTL — تُصوَّب بحصر التصويب في المحتوى الرقميّ فلا يمسّ نصَّ الجُمل)
+ 3 تنوينات/حركات مضاعفة تُجمَع. يُستبعَد ذيلُ الإصدار من م7. يُمسَح قبل الإخراج. الفرع «جزائي»."""
import zipfile, re, html, json, pathlib

H = pathlib.Path(__file__).parent
RAW = zipfile.ZipFile(H / "new_law12.docx").read("word/document.xml").decode("utf-8")
_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
PARAS = [x for x in (html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p))).strip()
                     for p in re.findall(r"<w:p[ >].*?</w:p>", RAW, re.S)) if x]
HDR = re.compile(r"^(?:المادة|مادة)\s*([٠-٩0-9]+)\s*$")
FOOTER = re.compile(r"^(?:أمير الكويت|صدر بقصر السيف)")


def clean(t):
    # أقواسٌ معكوسةُ الاتجاه حول أرقام (وقوائم أرقام): «) 16 (» / «) 1(» ⇒ «(16)» — مأمونٌ لاقتصاره على
    # محتوًى رقميّ (بخلاف مبادلةٍ عامّةٍ قد تعكس أقواسًا صحيحة بين مجموعات):
    t = re.sub(r"\)\s*([٠-٩0-9]{1,4}(?:\s*[،,/]\s*[٠-٩0-9]{1,4})*)\s*\(", r"(\1)", t)
    t = re.sub(r"[ً-ْ]{2,}", lambda m: m.group()[0], t)       # جمع تشكيلٍ مضاعف (بناءًً⇒بناءً، يُُلغى⇒يُلغى)
    t = re.sub(r"\s{2,}", " ", t).strip(" .:؛,")
    return t


marks = [(i, "m%d" % int(HDR.match(x).group(1).translate(_AR))) for i, x in enumerate(PARAS) if HDR.match(x)]
first = marks[0][0]
preamble = clean(" ".join(PARAS[:first]))
foot_at = next((i for i, x in enumerate(PARAS) if FOOTER.match(x)), len(PARAS))

A, ORDER = {}, []
for j, (s, key) in enumerate(marks):
    e = marks[j + 1][0] if j + 1 < len(marks) else len(PARAS)
    e = min(e, foot_at)
    A[key] = clean(" ".join(PARAS[s + 1:e]))
    ORDER.append(key)

issue_tail = clean(" ".join(PARAS[foot_at:]))
data = {"preamble_text": preamble, "issue_tail": issue_tail, "articles": A, "order": ORDER}
(H / "law51_2026_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- verification ----
blob = preamble + " " + " ".join(A.values())
print("law51/2026 parsed: articles", len(A), "| ORDER:", ORDER)
seqok = [int(k[1:]) for k in ORDER] == list(range(1, 8))
print("sequential 1-7:", seqok, "| � :", blob.count("�"), "| _:", blob.count("_"))
rev = re.findall(r"\)\s*[٠-٩0-9]+\s*\(", blob)
print("residual reversed-paren:", rev or "لا", "| doubled-diac:", len(re.findall(r"[ً-ْ]{2,}", blob)))
assert "�" not in blob and seqok and not rev, "تلف/تسلسل/أقواس!"
assert "يُلغى" in blob and "يُُلغى" not in blob and "بناءًً" not in blob, "لم تُجمَع الحركات المضاعفة!"
empty = [k for k, v in A.items() if len(v) < 10]
print("short/empty:", empty or "لا")
print("footer excluded (أمير الكويت not in articles):", "أمير الكويت" not in " ".join(A.values()))
print("\npreamble:", preamble[:300])
print("issue_tail:", issue_tail)
for k in ("m1", "m2", "m3", "m6", "m7"):
    print(f"\n--- {k} ---\n{A[k]}")
