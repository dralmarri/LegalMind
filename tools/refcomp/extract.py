# استخراج القوانين الغائبة من «مجموعة التشريعات» (Markdown مستخرج من طبقة نص PDF)
import pickle, re, json, sys, collections, unicodedata
D = sys.argv[1] if len(sys.argv) > 1 else "."
P = pickle.load(open(D + "/pages.pkl", "rb"))
LAWS = {  # key: (first_page, last_page, toc_page)
    "legis-12-1963": (53, 82, 52),
    "legis-120-2023": (84, 99, 83),
    "legis-15-1959": (101, 105, 100),   # 106-111 نصّا المرسومين المعدِّلين ومذكرة — خارج النطاق
    "legis-63-2015": (479, 486, 478),
    "legis-37-2014": (488, 514, 487),
    "legis-6-2015": (575, 577, 574),
    "legis-70-2020": (762, 788, 761),
}
DIAC = "ًٌٍَُِّْ"
FIX = collections.Counter()
TERMINAL = re.compile(r"[.:؛!؟]\s*$|-:\s*$")

def sub(name, pat, rep, s, flags=0):
    s2, n = re.subn(pat, rep, s, flags=flags)
    FIX[name] += n
    return s2

def clean(s):
    # الأرقام الهندية مقلوبة في طبقة النص (تحقق: «٤١»=14، «٩٧ لسنة ٦٢٠٢»=79/2026، فهرس الصفحات)
    s = sub("arabic_indic_reversed", r"[٠-٩](?:[٠-٩،,/]*[٠-٩])?", lambda m: m.group(0)[::-1], s)
    # واتجاه السطر يعكس طرفَي المدى («80 - 67» = 67 إلى 80، «2011 - 2010») بالهندية واللاتينية معًا: المدى التنازلي
    # لا وجود له، فيُعاد تصاعديًا — بشرط شرطة بمسافتين («13-1» المضطربة في م16 جنسية لا تُمسّ)
    def _rng(m):
        if ai2int(m.group(1)) > ai2int(m.group(3)):
            FIX["range_reversed"] += 1
            return m.group(3) + m.group(2) + m.group(1)
        return m.group(0)
    s = re.sub(r"(?<![0-9٠-٩])([0-9٠-٩]+)(\s+[-–]\s+)([0-9٠-٩]+)(?![0-9٠-٩])", _rng, s)
    s = sub("paren_number", r"\(\s*\)\s?([0-9٠-٩]{1,4}(?:[،,][0-9٠-٩]{1,4})*)", r"(\1)", s)
    s = sub("year_comma", r"لسنة\s*،\s*([0-9]{4})", r"لسنة \1،", s)
    s = sub("diac_split_a", r"([ء-ي]) ([%s])([ء-ي])\2" % DIAC, r"\1\3\2", s)
    s = sub("diac_split_b", r"(^|[\s(«])([%s])([ء-ي])\2 ?([ء-ي])" % DIAC, r"\1\3\2\4", s, re.M)
    s = sub("diac_split_c", r"([ء-ي]) ([%s]) ([ء-ي]+[%s])" % (DIAC, DIAC), r"\1\3", s)
    # «إهمالا ً» ← «إهمالاً»
    s = sub("alef_tanween_split", r"([ء-ي]ا) ([ًٌٍ])", r"\1\2", s)
    s = sub("ref_markers", r"\s*\(\(\(\s*", " ", s)
    # حروف فارسية في طبقة النص (ی ک) تطابق العربية رسمًا وتخالفها ترميزًا فتُعمي البحث («تاریخ» لا يطابق «تاريخ»):
    # ی في آخر الكلمة تُرسم بلا نقط فهي ى («المرضی»)، وفي غيره ي («میلاد»)؛ وک ← ك
    s = sub("persian_letters", r"\u06cc(?![\u0600-\u06ff])", "\u0649", s)
    s = sub("persian_letters", r"\u06cc", "\u064a", s)
    s = sub("persian_letters", r"\u06a9", "\u0643", s)
    # «لدها» ليست كلمة عربية: طبقة النص أسقطت ياء «لديها» (صورتا م6 وم11 من 70/2020 تثبتانها مطبوعةً «لديها»)
    s = sub("ladayha_restored", r"(?<![ء-ي])لدها(?![ء-ي])", "لديها", s)
    # طبقة النص تُسقط اللام المتصلة بما بعدها في «الـ» قبل الحروف التي تتركب معها رسمًا (م، ج) وتاءَ «لاتخاذ» —
    # مقصورٌ على صيغ ليست كلمات أو مقيَّدة بسياقها («اجزاء» كلمة صحيحة بمعنى الأجزاء، فلا تُمسّ إلا في «قانون اجزاء»)
    for _bad, _good in (("لاخاذ", "لاتخاذ"), ("امشترك", "المشترك"), ("امرضى", "المرضى")):
        s = sub("ligature_letter_restored", r"(?<![ء-ي])%s(?![ء-ي])" % _bad, _good, s)
    s = sub("ligature_letter_restored", r"قانون اجزاء(?![ء-ي])", "قانون الجزاء", s)
    return s.strip()

def ai2int(x):
    return int(x.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))

ART = re.compile(r"^###\s*(?:ال)?ماد[ةه]\s*\(?\s*([0-9٠-٩]+)\s*\)?\s*(مكرر[ًا]*(?:\s*\(?\s*/?\s*[أ-ي]\s*\)?)?)?\s*[-–:]?\s*$")
MUK = re.compile(r"^(?:\(\(\(\s*)?مكرر[ًا]*\s*(?:\(?\s*[أ-ي]\s*\)?)?$")
FOOT_LINE = re.compile(r"^(?:\)\s*[0-9٠-٩]|-\s*[0-9٠-٩]+\s+(?:الفقرة|المادة|البند|البنود)\b.*(?:مستبدلة|مضافة|معدلة|ملغاة|عدلت)\s+(?:وفق|بموجب|بالقانون|بالمرسوم))")
FOOT_INLINE = re.compile(r"\)\s*[0-9٠-٩][0-9٠-٩\s\-]*\s+((?:حكمت|تم|عدل|عدلت|معدلة|مضافة|أضيفت|اضيفت|مستبدلة|استبدلت|ألغيت|الغيت|ملغاة|البند|البنود|الفقرة)[^\n]*?لسنة\s*(?:لسنة\s*)?[0-9٠-٩]{3,4}(?:\s*و(?:ال)?(?:بند|فقرة|مادة|تم|عدل)[^\n]*?لسنة\s*[0-9٠-٩]{3,4})*(?:\s*(?:بشأن|في شأن|بتعديل|مع ما يترتب)[^\n]*)?)")
SIG = re.compile(r"\s*((?:ولي العهد|أمير الكويت|امير الكويت|نحن)\s.*صدر\s*بقصر.*)$", re.S)

def norm_titles(s):
    out = {norm_title(s)}
    if ":" in s:
        out.add(norm_title(s.split(":", 1)[1]))
    m = re.match(r"^\s*(?:الباب|الفصل)\s+\S+(?:\s+عشر)?\s*[:\-–]?\s*(.+)$", s)
    if m:
        out.add(norm_title(m.group(1)))
    return {x for x in out if len(x) >= 4}

def norm_title(s):
    s = re.sub("[%sـ]" % DIAC, "", s)
    s = re.sub(r"^\s*(أولا|ثانيا|ثالثا|رابعا|خامسا|سادسا|سابعا|ثامنا|تاسعا|عاشرا)\s*[:\-–]?\s*", "", s)
    s = re.sub(r"^[\s\-–]+", "", s)
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"[^ء-ي0-9]", "", s)

def toc(n):
    out = []
    for l in P[n].splitlines():
        m = re.match(r"^\|\s*([^|]+?)\s*\|\s*([0-9٠-٩\-]*)\s*\|\s*([0-9٠-٩]*)\s*\|$", l.strip())
        if m and m.group(1) not in ("الفهرس", "---"):
            st = m.group(2).strip()
            out.append((m.group(1).strip(), ai2int(st) if st and st != "-" else None))
    return out

def page_lines(n, hdrs):
    ls = P[n].splitlines()
    out, started = [], False
    for l in ls:
        t = l.strip()
        if not started:
            if not t or t in hdrs:
                continue
            started = True
        out.append(l.rstrip())
    while out and (not out[-1].strip() or out[-1].strip() in ("---", "القانون")):
        out.pop()
    if out and out[-1].strip().endswith(" القانون"):
        out[-1] = out[-1].rstrip()[:-len(" القانون")]
    return out

def extract(key):
    a, b, tp = LAWS[key]
    hdrs = set()
    for n in range(a, min(a + 3, b + 1)):
        hdrs.update([l.strip() for l in P[n].splitlines() if l.strip()][:2])
    T = toc(tp)
    tnorm = {}
    for t, _ in T:
        for k in norm_titles(t):
            tnorm.setdefault(k, t)
    pre, arts, foots, cur, muk, heads = [], [], [], None, False, []
    for n in range(a, b + 1):
        # حدّ الصفحة: فاصل الحواشي «---» في ذيل الصفحة السابقة ليس فقرة — يُزال، ويُقرَّر اللحام عند أول سطر
        seam = False
        if n > a and cur and cur["lines"]:
            while cur["lines"] and cur["lines"][-1] == "":
                cur["lines"].pop()
            seam = bool(cur["lines"])
        for l in page_lines(n, hdrs):
            raw = l.strip()
            if not raw or raw == "---":
                (cur["lines"] if cur else pre).append("")
                continue
            if FOOT_LINE.match(raw):
                foots.append({"page": n, "text": clean(raw.lstrip(") "))})
                continue
            t = clean(raw)
            was_seam, seam = seam, False
            if MUK.match(t):
                muk = True
                continue
            m = ART.match(t)
            if m:
                suf = (m.group(2) or "")
                if muk and not suf:
                    suf = "مكرر"
                muk = False
                num = str(ai2int(m.group(1))) + ((" " + re.sub(r"\s+", " ", suf.strip())) if suf else "")
                cur = {"num": num, "base": ai2int(m.group(1)), "page": n, "lines": [], "chapter": heads[-1] if heads else None}
                arts.append(cur)
                continue
            if t.startswith("###"):
                h = t.lstrip("#").strip()
                heads.append(h)
                continue
            # عنوان قسم غير موسوم يطابق الفهرس
            nt = norm_title(t)
            if len(t) < 70 and nt and nt in tnorm:
                heads.append(tnorm[nt])
                continue
            # حاشية مدسوسة في سطر
            def _f(mm):
                foots.append({"page": n, "text": mm.group(1).strip(), "inline": True})
                return ""
            t2 = FOOT_INLINE.sub(_f, t)
            if t2 != t:
                FIX["footnote_inline_removed"] += 1
                t = t2.strip()
            if was_seam and cur and cur["lines"]:
                if TERMINAL.search(cur["lines"][-1]):
                    cur["lines"].append("")
                else:  # جملة تعبر حدّ الصفحة — تُلحم بمسافة لا بفقرة
                    cur["lines"][-1] = cur["lines"][-1].rstrip() + " " + t
                    FIX["page_seam_joined"] += 1
                    continue
            (cur["lines"] if cur else pre).append(t)
    out = []
    sig = None
    for x in arts:
        txt = "\n".join(x["lines"]).strip()
        txt = re.sub(r"\n{3,}", "\n\n", txt)
        ms = SIG.search(txt)
        if ms:
            sig = ms.group(1).strip()
            # اتجاه السطر يقدّم الرقم على النقطتين: «في 9: رجب» والمطبوع «في: ٩ رجب» (وكذا «الموافق»)
            sig, nsc = re.subn(r"(في|الموافق)\s+([0-9٠-٩]+):", r"\1: \2", sig)
            FIX["signature_colon"] += nsc
            txt = txt[:ms.start()].strip()
        out.append({"num": x["num"], "base": x["base"], "page": x["page"], "text": txt, "head": x["chapter"]})
    pretxt = re.sub(r"\n{3,}", "\n\n", "\n".join(pre)).strip()
    return {"key": key, "toc": T, "preamble": pretxt, "articles": out, "footnotes": foots, "signatories": sig, "heads": heads}

RESIDUE = [
    ("standalone_diacritic", re.compile(r"(^|\s)[%s]" % DIAC)),
    ("split_tanween_fragment", re.compile(r"(^|\s)[ء-ي][ًٌٍ]ا?(?=\s|$|[.،])")),
    ("ref_marker", re.compile(r"\(\(\(")),
    ("footnote_residue", re.compile(r"\)\s*[0-9]\s+(?:عدلت|معدلة|مضافة|مستبدلة|ملغاة)")),
    ("dangling_paren_number", re.compile(r"\(\s*\)")),
    ("misplaced_paren", re.compile(r"\(\s*[.،]?\s*\)|\)\s+[0-9٠-٩]")),
    ("split_letter", re.compile(r"(?<=[ء-ي]) (?![وأ-ي] ?[-–])([ء-يى])(?= )")),
]
def residue(t):
    return [n for n, rx in RESIDUE if rx.search(t)]

if __name__ == "__main__":
    allres = {}
    for key in LAWS:
        FIX.clear()
        r = extract(key)
        arts = r["articles"]
        nums = [x["num"] for x in arts]
        bases = sorted(set(x["base"] for x in arts))
        dup = [k for k, v in collections.Counter(nums).items() if v > 1]
        gaps = sorted(set(range(1, max(bases) + 1)) - set(bases))
        flagged = {x["num"]: residue(x["text"]) for x in arts if residue(x["text"])}
        empty = [x["num"] for x in arts if len(x["text"]) < 15]
        r["fix_counts"] = dict(FIX)
        allres[key] = r
        print("==", key, "art:", len(arts), "max:", max(bases), "dups:", dup, "gaps:", gaps,
              "foots:", len(r["footnotes"]), "flagged:", len(flagged), "empty:", empty,
              "sig:", bool(r["signatories"]), "pre:", len(r["preamble"]))
        print("   fixes:", dict(FIX))
    json.dump(allres, open(D + "/extracted.json", "w"), ensure_ascii=False, indent=1)
