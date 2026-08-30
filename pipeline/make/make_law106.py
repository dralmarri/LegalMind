#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني law106_2013_parsed.json — القانون 106/2013 (مكافحة غسل الأموال وتمويل الإرهاب) من DOCX
بتلفٍ حتميّ (38 محرف � كلها تنوين/شدّة في كلماتٍ مقطّعة بمسافات) — نُظّف آليًّا (إزالة �، لمّ المسافات
الدخيلة، تصويب مكرّرات) فصار خاليًا من � ومن التلف؛ المحتوى العمليّ (العقوبات/المبالغ/الإحالات) سليم.
يُستخرَج نصّ المواد من المصدر المُنظَّف مباشرةً (أدقّ من النقل اليدويّ). 45 مادة + م33مكرر + ديباجة."""
import zipfile, re, html, json, pathlib

H = pathlib.Path(__file__).parent
raw = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ",
      zipfile.ZipFile(H / "new_law4.docx").read("word/document.xml").decode("utf-8"))))


def clean(t):
    # rejoin ONLY around a � (so legitimate word boundaries like "أن يُفوّض" are never merged):
    # "<letter> <letter> �<diacritics><alef?>" -> "<letter><letter><diacritics><alef?>"
    t = re.sub(r"([ء-ي])\s*([ء-ي])\s*�([ًٌٍَُِّْ]{0,2})([اى]?)", r"\1\2\3\4", t)
    t = t.replace("التظ لمّ", "التظلّم").replace("التظل مّ", "التظلّم")
    t = t.replace("و حتُح دّدّ", "وتُحدّد").replace("حتُح دّدّ", "تُحدّد")
    t = t.replace("�", "")                                        # remove any stray remainder
    t = re.sub(r"[ً-ْ]{2,}", lambda m: m.group()[0], t)          # collapse doubled diacritics
    t = t.replace("الاتججار", "الاتجار").replace("امقترنين بهها", "المقترنين بها").replace("١٠٦لسنة", "١٠٦ لسنة")
    t = t.replace("متحصات الجريمة", "متحصلات الجريمة")  # حرف ساقط منفرد بالمصدر (الصواب متحصلات، ترد 8 مرات صحيحة)
    # حروف ساقطة منتظمة تنتج كلماتٍ غير موجودة (فتُكشَف قطعًا): عى←على، غر←غير، با←بما — بحدود الكلمة
    t = re.sub(r"(?<![ء-ي])الغر(?![ء-ي])", "الغير", t)
    # حروف ساقطة تنتج كلماتٍ غير موجودة — تُصوَّب بمطابقة الجذر مع وعيٍ بالسوابق (ال/و/ف/ب/ك/ل)
    # فلا تُفوَّت «والأعال/التدابر»، ولا تُصيب كلمةً سليمة («يتعين» لا يُمَسّ لأنّ «ي» ليست سابقة).
    _PFX = r"(?:وال|فال|بال|كال|لل|ال|و|ف|ب|ك|ل)?"
    _STEMS = {"عى": "على", "غر": "غير", "با": "بما", "أعال": "أعمال", "اعال": "أعمال", "ضان": "ضمان",
              "موظفن": "موظفين", "تدابر": "تدابير", "قوانن": "قوانين", "ركات": "شركات", "فعلين": "فعليين",
              "معامات": "معاملات", "إباغ": "إبلاغ", "اباغ": "إبلاغ", "خرة": "خبرة", "ماك": "ملاك",
              "معاير": "معايير", "مادتن": "مادتين", "تعليات": "تعليمات", "داخي": "داخلي", "كبرة": "كبيرة",
              "فرة": "فترة", "خمسائة": "خمسمائة", "فيا": "فيما", "تعين": "تعيين"}
    for w, c in sorted(_STEMS.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(r"(?<![ء-ي])(" + _PFX + r")" + re.escape(w) + r"(?![ء-ي])", r"\1" + c, t)
    t = t.replace("بتوفر أي معلومات", "بتوفير أي معلومات")   # توفر↔توفير: تصويبٌ سياقيّ منفرد
    t = re.sub(r"\)\)\)", "", t)
    t = re.sub(r"\)\s*([٠-٩0-9]{1,4}(?:\s*[،,]\s*[٠-٩0-9]{1,4})*)\s*\(", r"(\1)", t)  # ) N ( -> (N) incl. years
    t = re.sub(r"\)([أ-ي])\s*\(", r"(\1)", t)  # )ب( -> (ب) letter bullets (no leading space: not a connector)
    t = re.sub(r"_+", " ", t)  # علاماتٌ دخيلة بالمصدر (19 «_» وسط الجُمَل: «من __ هذا القانون») — لا معنى قانونيّ
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def ar2en(s):
    return s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))


c = clean(raw)
HDR = re.compile(r"المادة\s*([٠-٩0-9]+)(\s*مكرر)?")

# collect real headers (skip in-text references)
reals = []
for m in HDR.finditer(c):
    n = int(ar2en(m.group(1))); mk = bool(m.group(2))
    after = c[m.end():m.end()+16].lstrip()
    before = c[max(0, m.start()-8):m.start()].rstrip()
    is_ref = after.startswith("من هذا القانون") or before.endswith(
        ("في", "بالمادة", "لأحكام", "وفقا", "وفقاً", "بالمواد", "المادتين", "بالبند"))
    if not is_ref:
        reals.append((m.start(), m.end(), n, mk))

preamble = c[:reals[0][0]].strip()

_SEC = re.compile(r"(الباب|الفصل)\s+[^:]{1,40}?(?=\s*المادة|\s*:)")


def split_section(body):
    """يفصل ترويسة باب/فصل زائدة في نهاية جسم المادة (تسبق المادة التالية)."""
    sec = None
    m = list(re.finditer(r"(الباب\s+\S+|الفصل\s+\S+)[^.]{0,60}$", body))
    return body, sec


A, ORDER, secs = {}, [], []
cur_sec = None
for i, (s, e, n, mk) in enumerate(reals):
    end = reals[i+1][0] if i+1 < len(reals) else len(c)
    body = c[e:end].strip()
    # strip a trailing باب/فصل heading (belongs to next article) and record it.
    # BOUNDED (≤60 chars) + exclude "الفصل/الباب ... من" (a reference, not a heading) so it can
    # never consume body text (e.g. "الفصل السابع من ميثاق الأمم المتحدة ..." inside م25).
    ms = re.search(r"\s((?:الباب|الفصل)\s+(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع)(?!\s+من)\b[^.]{0,55})$", body)
    next_sec = None
    if ms:
        next_sec = re.sub(r"\s+", " ", ms.group(1)).strip(" :.")
        body = body[:ms.start()].strip()
    key = "m%d%s" % (n, "-mukarrar" if mk else "")
    A[key] = {"text": body.strip(" .:"), "sec": cur_sec}
    ORDER.append(key)
    if next_sec:
        cur_sec = next_sec

data = {"articles": A, "order": ORDER, "preamble_text": preamble}
(H / "law106_2013_parsed.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- verification ----
blob = json.dumps(data, ensure_ascii=False)
assert "�" not in blob, "residual �!"
assert len(A) == 46, "expected 46 articles, got %d" % len(A)
empty = [k for k, v in A.items() if len(v["text"]) < 10]
print("law106 parsed:", len(A), "articles; order", len(ORDER), "; no �")
print("short/empty bodies:", empty or "لا")
print("preamble head:", preamble[:90])
for k in ("m1", "m2", "m3", "m32", "m33-mukarrar", "m45"):
    print(f"\n--- {k} (sec={A[k]['sec']}) ---\n{A[k]['text'][:150]}")
