#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""law19_2012_parsed.json — المرسوم بقانون 19/2012 في شأن حماية الوحدة الوطنية. 5 مواد + ديباجة. نصٌّ نظيفٌ
تمامًا (لا � ولا تلف)؛ تنظيفٌ أساسيّ فقط (لمّ المسافات، توحيد الأرقام العربية اختياريّ). الفرع «جزائي»."""
import zipfile, re, html, json, pathlib
H = pathlib.Path(__file__).parent
RAW = zipfile.ZipFile(H / "new_law9.docx").read("word/document.xml").decode("utf-8")
_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
PARAS = [x for x in (html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p))).strip()
                     for p in re.findall(r"<w:p[ >].*?</w:p>", RAW, re.S)) if x]
HDR = re.compile(r"^(?:المادة|مادة)\s*([٠-٩0-9]+)(\s*مكرر[ً-ْ]*ا?)?\s*[).\s]*$")

def clean(t):
    t = t.translate(_AR)                    # توحيد الأرقام العربية-الهندية إلى لاتينية (اتّساقًا مع البقية)
    t = re.sub(r"\s{2,}", " ", t).strip(" .:؛")
    return t

marks = []
for i, x in enumerate(PARAS):
    m = HDR.match(x)
    if m:
        marks.append((i, "m%d%s" % (int(m.group(1).translate(_AR)), "-mukarrar" if m.group(2) else "")))
marks.sort()
preamble = clean(" ".join(PARAS[:marks[0][0]]))
A, ORDER = {}, []
for j, (s, key) in enumerate(marks):
    e = marks[j + 1][0] if j + 1 < len(marks) else len(PARAS)
    A[key] = clean(" ".join(PARAS[s + 1:e])); ORDER.append(key)
data = {"preamble_text": preamble, "articles": A, "order": ORDER}
(H / "law19_2012_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
blob = preamble + " " + " ".join(A.values())
assert "�" not in blob and len(A) == 5
print("natunity parsed:", ORDER, "| � :", blob.count("�"))
for k in ("m1", "m2", "m3"):
    print("\n--- %s ---\n%s" % (k, A[k][:150]))
