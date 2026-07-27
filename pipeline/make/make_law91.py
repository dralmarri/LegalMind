#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني law91_2013_parsed.json — القانون 91/2013 في شأن مكافحة الاتجار بالأشخاص وتهريب المهاجرين، من DOCX.
14 مادة متسلسلة + ديباجة. النصّ نظيفٌ بنيويًّا؛ تلفٌ حتميّ محدود (ترويسة «المادة 13 ) ))» بعلامةٍ زائدة،
تشكيلٌ مضاعف، حرفٌ ساقط «واأشياء»→«والأشياء»). تُحفَظ ملاحظةُ عدم دستورية فقرةٍ من م13 (المحكمة الدستورية
الطعن 7/2018) موسومةً بوضوح داخل م13 لأهميتها القانونية."""
import zipfile, re, html, json, pathlib

H = pathlib.Path(__file__).parent
RAW = zipfile.ZipFile(H / "new_law7.docx").read("word/document.xml").decode("utf-8")
_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
PARAS = [x for x in (html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p))).strip()
                     for p in re.findall(r"<w:p[ >].*?</w:p>", RAW, re.S)) if x]
# ترويسةٌ متسامحةٌ مع علامةٍ زائدة بعد الرقم («المادة 13 ) ))»)
HDR = re.compile(r"^(?:المادة|مادة)\s*([٠-٩0-9]+)(\s*مكرر)?\s*[)\س\s]*$")


def clean(t):
    t = re.sub(r"[)(]{2,}", "", t)                               # علامات «)))» / «(((» زائدة
    t = t.replace("واأشياء", "والأشياء")                        # حرفٌ ساقط (م5): «والأشياء» — «واأشياء» غير كلمة
    t = re.sub(r"[ً-ْ]{2,}", lambda m: m.group()[0], t)          # جمع تشكيلٍ مضاعف
    t = re.sub(r"_+", " ", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" .:؛")
    return t


idx = {}
for i, x in enumerate(PARAS):
    m = HDR.match(x)
    if m:
        idx[int(m.group(1).translate(_AR))] = i

first = min(idx.values())
preamble = clean(" ".join(PARAS[:first]))

A, ORDER = {}, []
skeys = sorted(idx)
for j, n in enumerate(skeys):
    s = idx[n]
    e = idx[skeys[j + 1]] if j + 1 < len(skeys) else len(PARAS)
    body = clean(" ".join(PARAS[s + 1:e]))
    A["m%d" % n] = body
    ORDER.append("m%d" % n)

data = {"preamble_text": preamble, "articles": A, "order": ORDER}
(H / "law91_2013_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- verification ----
blob = preamble + " " + " ".join(A.values())
assert "�" not in blob
print("law91 parsed: articles", len(A), "| sequential 1-14:", [int(k[1:]) for k in ORDER] == list(range(1, 15)))
print("residual )))/(((:", "نعم!" if re.search(r"[)(]{2,}", blob) else "لا",
      "| doubled-diac:", len(re.findall(r"[ً-ْ]{2,}", blob)), "| _:", blob.count("_"))
print("م13 يحوي ملاحظة الدستورية:", "المحكمة الدستورية" in A["m13"] and "الطعن رقم 7 لسنة 2018" in A["m13"])
print("م5 والأشياء مصحّحة:", "والأشياء المضبوطة" in A["m5"])
empty = [k for k, v in A.items() if len(v) < 10]
print("short/empty:", empty or "لا")
print("preamble head:", preamble[:100])
for k in ("m2", "m3", "m5", "m13"):
    print(f"\n--- {k} ---\n{A[k][:220]}")
