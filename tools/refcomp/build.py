# يبني سجلات الإدخال من extracted.json — كل تصحيح آلي معدود، وكل اضطراب باقٍ موسوم ظاهرًا
import json, re, sys, os, collections, hashlib
D = sys.argv[1]
exec(open(D + "/extract.py", encoding="utf-8").read().split("if __name__")[0])
R = json.load(open(D + "/extracted.json", encoding="utf-8"))

META = {
 "legis-12-1963": dict(id="legis-12-1963", num=12, year=1963, branch="دستوري",
    short="اللائحة الداخلية لمجلس الأمة (12/1963)", instrument="القانون رقم 12 لسنة 1963 في شأن اللائحة الداخلية لمجلس الأمة"),
 "legis-120-2023": dict(id="legis-120-2023", num=120, year=2023, branch="دستوري",
    short="قانون انتخابات أعضاء مجلس الأمة (120/2023)", instrument="القانون رقم 120 لسنة 2023 بشأن انتخابات أعضاء مجلس الأمة"),
 "legis-15-1959": dict(id="legis-15-1959", num=15, year=1959, branch="دستوري",
    short="قانون الجنسية الكويتية (15/1959)", instrument="المرسوم الأميري رقم 15 لسنة 1959 بقانون الجنسية الكويتية"),
 "legis-63-2015": dict(id="legis-63-2015", num=63, year=2015, branch="جزائي",
    short="قانون مكافحة جرائم تقنية المعلومات (63/2015)", instrument="القانون رقم 63 لسنة 2015 في شأن مكافحة جرائم تقنية المعلومات"),
 "legis-37-2014": dict(id="legis-37-2014", num=37, year=2014, branch="إداري",
    short="قانون إنشاء هيئة تنظيم الاتصالات وتقنية المعلومات (37/2014)", instrument="القانون رقم 37 لسنة 2014 بإنشاء هيئة تنظيم الاتصالات وتقنية المعلومات"),
 "legis-6-2015": dict(id="legis-61-2015", num=61, year=2015, branch="إداري",
    short="قانون تنظيم وتركيب كاميرات وأجهزة المراقبة الأمنية (61/2015)", instrument="القانون رقم 61 لسنة 2015 بشأن تنظيم وتركيب كاميرات وأجهزة المراقبة الأمنية",
    title_note=("رقم القانون في متن المرجع نفسه (صفحة العنوان وسطر الإصدار) «61 لسنة 2015»، بينما فهرس المرجع "
                "وترويسة صفحاته تقول «6 لسنة 2015» — اعتُمد رقم المتن (قاعدة: رقم الصك يُقرأ من متنه لا من فهرسه)، "
                "وتؤكده حاشية المرجع ص571 التي تسمّيه «القانون رقم ٦١ لسنة ٢٠١٥» في سند المرسوم بقانون 76/2026 "
                "المعدِّل له (صورة الصفحة، 2026-10-10)؛ ويُتحقق منه بالجريدة الرسمية.")),
 "legis-70-2020": dict(id="legis-70-2020", num=70, year=2020, branch="إداري",
    short="قانون مزاولة مهنة الطب والمهن المساعدة وحقوق المرضى والمنشآت الصحية (70/2020)",
    instrument="القانون رقم 70 لسنة 2020 بشأن مزاولة مهنة الطب والمهن المساعدة لها وحقوق المرضى والمنشآت الصحية"),
}
PROVENANCE = ("المرجع المجمّع «مجموعة من التشريعات الكويتية» (التعديلات حتى 2026/10/5) — نسخة Markdown "
              "مستخرجة آليًا من طبقة نص PDF (1710 صفحة)، نُقّيت بقواعد آلية معدودة (أرقام هندية مقلوبة، "
              "أقواس الأرقام، تشكيل مشقوق، حواشٍ مدسوسة)؛ غير مقابَلة بالجريدة الرسمية.")
NOTE_UNCERTAIN = ("نُقل هذا النص من مرجع مجمّع عبر طبقة نص PDF، وبقي فيه أثر اضطراب آلي ({why}) — "
                  "قد تكون كلمةٌ مشقوقة أو منقولة عن موضعها. يُراجع بالجريدة الرسمية قبل الاقتباس الحرفي.")
WHY = {"standalone_diacritic": "تشكيل منفصل عن حرفه", "split_tanween_fragment": "مقطع كلمة منفصل",
       "split_letter": "حرف منفصل عن كلمته", "ref_marker": "علامة إحالة", "footnote_residue": "بقية حاشية",
       "dangling_paren_number": "قوس رقم فارغ"}
LET = {"أ": "a", "ا": "a", "ب": "b", "ج": "c", "د": "d", "ه": "e", "و": "f"}

_MUK = re.compile(r"^(\d+)(?:\s+مكرر(?:\s*\(?\s*/?\s*([أ-ي])\s*\)?|[ًا]{0,2}\s+(\d+)|[ًا]{0,2}))?$")
def sid(num):
    m = _MUK.match(num)
    base, mk, md = m.group(1), m.group(2), m.group(3)
    s = "m" + base
    if "مكرر" in num:
        s += "-mukarrar" + ("-" + LET[mk] if mk else "") + ("-" + md if md else "")
    return s

def label(num):
    m = _MUK.match(num)
    if "مكرر" not in num:
        return m.group(1)
    mk, md = m.group(2), m.group(3)
    return m.group(1) + " مكرر" + ((" " + ("أ" if mk == "ا" else mk)) if mk else "") + ((" " + md) if md else "")

def chapters(T):
    """الفهرس ← مدى كل باب/فصل وكل قسم فرعي بأرقام المواد."""
    ents = []
    for i, (t, st) in enumerate(T):
        if st is None:
            st = next((s for _, s in T[i + 1:] if s is not None), None)
        if st is None:
            continue
        main = bool(re.match(r"^\s*(الباب|الفصل)", t)) or t.startswith("ديباج")
        ents.append((t.strip(" -"), st, main))
    return ents

HEAD_TAIL = []
def _hnorm(s):
    return "".join(re.sub(r"^ال", "", w) for w in re.findall(r"[ء-ي]+", s))

def chap_of(ents, base):
    bab = fasl = sub = None
    for t, st, main in ents:
        if st <= base and not t.startswith("ديباج"):
            if t.startswith("الباب"):
                bab, fasl, sub = t, None, None
            elif main:
                fasl, sub = t, None
            else:
                sub = t
    return " — ".join([x for x in (bab, fasl, sub) if x]) or None

import difflib
VIS = json.load(open(sys.argv[2], encoding="utf-8")) if len(sys.argv) > 2 else {}
# مواد غائبة عن المرجع المطبوع نفسه وصلت من مصدر آخر — لا تُقبل إلا لرقمٍ غائبٍ فعلًا (لا تكتب فوق مادة قائمة)
# وبشرط أن يطابق ما يسبقها في المصدر الآخر ذيلَ المادة السابقة عندنا (شاهدٌ على أنه القانون نفسه)
_SUPP_PATH = os.path.join(os.path.dirname(sys.argv[2]), "supplementary_articles.json") if len(sys.argv) > 2 else ""
SUPP = json.load(open(_SUPP_PATH, encoding="utf-8")) if _SUPP_PATH and os.path.exists(_SUPP_PATH) else {}
SUPP_APPLIED = []
def _letters(t):
    return re.sub(r"[^ء-ي]", "", re.sub("[%s]" % DIAC, "", t))
VIS_NOTE = ("قوبل نص هذه المادة بصورة صفحة المرجع (صفحة PDF {pages}) وصُحّح على الصورة — أُزيل اضطراب "
            "طبقة النص (كلمات مشقوقة أو منقولة عن مواضعها). نسبة تطابق كيس الحروف مع المستخرج آليًا {ratio:.3f}.")
# حاشية المرجع على م16 (حكم دستوري) — تُظهر للمحامي ولا تمسّ النص
CONST_NOTES = {"legis-12-1963-m16": ("حاشية المرجع المجمّع: «حكمت المحكمة الدستورية في الطعن رقم 6 لسنة 2018 بعدم "
    "دستورية المادة 16 من اللائحة الداخلية لمجلس الأمة الصادر بالقانون رقم 12 لسنة 1963 مع ما يترتب على ذلك "
    "من آثار». يُراجع منطوق الحكم ونطاقه قبل الاستناد إلى المادة.")}
records, report = [], {}
VIS_APPLIED = []
for k, r in R.items():
    M = META[k]; pfx = M["id"] + "-"
    ents = chapters(r["toc"])
    fixes = r.get("fix_counts", {})
    foot_by_page = collections.defaultdict(list)
    for f in r["footnotes"]:
        foot_by_page[f["page"]].append(f["text"])
    arts = [dict(x) for x in r["articles"]]
    special = {}
    if k == "legis-120-2023":
        # عنوان المادة 35 جاء بعد نصّها في طبقة النص (م34 تنتهي بفقرتها، ثم «### المادة 35» فارغة)
        a34 = next(x for x in arts if x["num"] == "34"); a35 = next(x for x in arts if x["num"] == "35")
        paras = a34["text"].split("\n\n")
        assert a35["text"] == "" and paras[-1].strip() == "يكون الانتخاب عامًا وسريًا ومباشرًا."
        a35["text"] = paras[-1].strip(); a34["text"] = "\n\n".join(paras[:-1]).strip()
        corr = ("نُقلت الفقرة «يكون الانتخاب عامًا وسريًا ومباشرًا.» من ذيل المادة 34 إلى المادة 35: في طبقة نص "
                "المرجع جاء عنوان المادة 35 بعد هذه الفقرة مباشرةً وبلا نص، فهي نصّها الذي سبق عنوانَه.")
        special["35"] = special["34"] = corr
    # عنوان القسم التالي عالقٌ في ذيل المادة السابقة (سطرًا مستقلًا أو ملتصقًا بآخر جملة) لأن صيغته تخالف الفهرس
    # قليلًا («مزاول»/«مزاولة»، «أخلاقيتها»/«أخلاقياتها») فلم يُعرف عنوانًا — والقسم مسجَّل أصلًا في تبويب المادة التالية
    if ents:
        for i in range(len(arts) - 1):
            cur_ch, nx_ch = chap_of(ents, arts[i]["base"]), chap_of(ents, arts[i + 1]["base"])
            if not nx_ch or nx_ch == cur_ch:
                continue
            cur_parts = (cur_ch or "").split(" — ")
            removed = []
            for comp in reversed(nx_ch.split(" — ")):
                if comp in cur_parts:
                    break  # مستوى مشترك مع المادة الحالية — ليس عنوانًا جديدًا
                leaf = comp.split(":", 1)[-1].strip()
                t = arts[i]["text"].rstrip()
                n = len(leaf.split())
                mt = re.search(r"((?:\S+[ \t]+){%d}\S+)$" % (n - 1), t)  # آخر n كلمات على السطر الأخير وحده
                if not mt or mt.start() == 0:
                    break
                tail = mt.group(1)
                if difflib.SequenceMatcher(None, _hnorm(tail), _hnorm(leaf)).ratio() < 0.85:
                    break
                arts[i]["text"] = t[:mt.start()].rstrip()
                removed.insert(0, tail)
            if removed:
                fixes["heading_tail_removed"] = fixes.get("heading_tail_removed", 0) + 1
                HEAD_TAIL.append((M["id"], arts[i]["num"], " | ".join(removed)))
    common = {"law_number": M["num"], "law_year": M["year"], "instrument": M["instrument"],
              "source": "reference_compilation_20261005", "text_provenance": PROVENANCE,
              "extraction_method": "pdf_text_layer_markdown_auto_cleaned"}
    if M.get("title_note"):
        common["title_note"] = M["title_note"]
    n_flag = 0
    vis = VIS.get(M["id"], {})
    for x in arts:
        vfix = vis.get(label(x["num"])) or vis.get(x["num"])
        vratio = None
        if vfix:
            # مقياس بكيس الحروف لا بتسلسلها: الاضطراب ينقل المقاطع عن مواضعها، والنقل الصحيح يحفظ الحروف نفسها
            ca, cb = collections.Counter(_letters(x["text"])), collections.Counter(_letters(vfix["text"]))
            vratio = sum((ca & cb).values()) / max(sum(ca.values()), sum(cb.values()))
            assert vratio >= 0.97, ("VISUAL_MISMATCH", M["id"], x["num"], round(vratio, 3))
            x["text"] = vfix["text"]
            VIS_APPLIED.append((M["id"], x["num"], round(vratio, 3)))
        # النص المقابَل بصورة الأصل محكومٌ بالعين لا بكاشف البقايا (الذي يَعُدّ «البند أ» حرفًا منفصلًا)
        why = [] if vfix else residue(x["text"])
        ch = chap_of(ents, x["base"]) if ents else None
        lab = label(x["num"])
        repealed = x["text"].strip(" .") in ("ملغاة", "مُلغاة", "ملغاه")
        meta = dict(common, article_number=lab, pdf_page=x["page"], chapter=ch)
        if repealed:
            meta["repealed"] = True
            meta["repeal_note"] = "المادة ملغاة بحسب المرجع المجمّع (التعديلات حتى 2026/10/5)."
        if foot_by_page.get(x["page"]):
            meta["page_footnotes"] = foot_by_page[x["page"]]
            meta["page_footnotes_note"] = "حواشي صفحة المرجع التي وردت فيها المادة — قد لا تخص هذه المادة بعينها."
        if vfix:
            meta["extraction_method"] = "visual_check_against_reference_page_photo"
            meta["source_correction"] = [{"date": "2026-10-10",
                                          "note": VIS_NOTE.format(pages="، ".join(map(str, vfix["pages"])), ratio=vratio)}]
            if vfix.get("corrections"):
                meta["source_correction"][0]["corrections"] = vfix["corrections"]
            if vfix.get("note"):
                meta["source_note"] = vfix["note"]
        if pfx + sid(x["num"]) in CONST_NOTES:
            meta["source_note"] = CONST_NOTES[pfx + sid(x["num"])]
        if x["num"] in special:
            # التصحيح الخاص يبقى موثَّقًا؛ والوسم يُرفع إن قوبلت المادة بصورة الأصل فثبت التصحيح
            meta["source_correction"] = [{"date": "2026-10-09", "note": special[x["num"]]}] + meta.get("source_correction", [])
            if not vfix:
                why = why + ["heading_displacement"]
        if why:
            n_flag += 1
            meta["extraction_uncertain"] = True
            meta["extraction_flags"] = why
            meta["source_note"] = NOTE_UNCERTAIN.format(why="، ".join(WHY.get(w, "ترتيب عنوان") for w in why))
        tch = " — ".join(p for p in (ch or "").split(" — ") if not p.startswith("الباب")) or ch
        title = "المادة (%s) — %s%s" % (lab, (tch + " — ") if tch else "", M["short"])
        records.append({"id": pfx + sid(x["num"]), "object_type": "legislation_article", "branch": M["branch"],
                        "topic": M["short"], "subtopic": ch or "مواد القانون", "title": title,
                        "text": x["text"], "metadata": meta,
                        "verification_status": "machine_pending_human" if why else "operationally_accepted"})
    pm = dict(common, fix_counts=fixes, signatories_text=r["signatories"],
              amendment_footnotes=r["footnotes"], toc=r["toc"])
    gaps = sorted(set(range(1, max(x["base"] for x in arts) + 1)) - {x["base"] for x in arts})
    supplied = []
    for num, sp in sorted(SUPP.get(M["id"], {}).items(), key=lambda kv: int(kv[0])):
        if num.startswith("_"):
            continue
        n = int(num)
        assert n in gaps, ("SUPPLEMENT_NOT_A_GAP", M["id"], n)
        prev = next(rec for rec in records if rec["id"] == pfx + sid(str(n - 1)))
        ctx = _letters(sp["context_prev_tail"])
        assert len(ctx) >= 60 and _letters(prev["text"]).endswith(ctx), ("SUPPLEMENT_CONTEXT_MISMATCH", M["id"], n)
        ch = prev["metadata"].get("chapter")
        meta = dict(common, article_number=str(n), chapter=ch, text_provenance=sp["provenance"],
                    extraction_method=sp["method"], source_note=sp["note"],
                    supplement_context_check=("ما يسبق المادة في المصدر المكمِّل يطابق حرفًا بحرف ذيل المادة %d "
                                              "عندنا (مقارنة الحروف العربية)." % (n - 1)))
        tch = " — ".join(p for p in (ch or "").split(" — ") if not p.startswith("الباب")) or ch
        rec = {"id": pfx + sid(str(n)), "object_type": "legislation_article", "branch": M["branch"],
               "topic": M["short"], "subtopic": ch or "مواد القانون",
               "title": "المادة (%d) — %s%s" % (n, (tch + " — ") if tch else "", M["short"]),
               "text": sp["text"], "metadata": meta, "verification_status": "operationally_accepted"}
        records.insert(records.index(prev) + 1, rec)
        supplied.append(n); SUPP_APPLIED.append((M["id"], n))
    if supplied:
        pm["supplemented_articles"] = supplied
        pm["supplemented_articles_note"] = ("مواد غائبة عن المرجع المطبوع نفسه استُكملت من مصدر آخر موثَّق في "
                                            "text_provenance لكل مادة، وتُراجع بالجريدة الرسمية.")
        gaps = [g for g in gaps if g not in supplied]
    if gaps:
        pm["missing_articles_in_source"] = gaps
        if k == "legis-37-2014":
            pm["missing_articles_photo_check"] = ("المادة 69: صورتا صفحتي المرجع 504–505 تثبتان غياب عنوانها عن المرجع "
                                                  "المطبوع نفسه (2026-10-10).")
        pm["missing_articles_note"] = ("مواد غائبة عن المرجع نفسه (لا عنوان لها في طبقة النص) — لم تُختلق، "
                                       "وتُستكمل من الجريدة الرسمية.")
    if k == "legis-15-1959":
        pm["consolidated_through"] = ["المرسوم بقانون 52/2026 (2026/4/5)", "المرسوم بقانون 79/2026"]
        pm["consolidation_note"] = ("النص منسَّق بتعديلات المرسومين بقانونين 52/2026 و79/2026 كما في المرجع؛ "
                                    "ونصّا المرسومين نفساهما لم يُدخلا مستقلين (نقلُهما في المرجع مضطرب الأرقام).")
    records.append({"id": pfx + "preamble", "object_type": "legislation_preamble", "branch": M["branch"],
                    "topic": M["short"], "subtopic": "الديباجة", "title": "الديباجة — " + M["short"],
                    "text": r["preamble"], "metadata": pm, "verification_status": "operationally_accepted"})
    report[M["id"]] = {"articles": len(arts), "flagged": n_flag, "gaps": gaps, "fixes": fixes,
                       "chapters_from_toc": bool(ents)}
    if gaps and k == "legis-37-2014":
        for rec in records:
            if rec["id"] == pfx + "m68" and rec["metadata"].get("extraction_method", "").startswith("visual"):
                pass  # قوبلت بصورة الصفحتين: الغياب ثابت في المرجع نفسه، وملاحظتها من ملف التصحيحات
            elif rec["id"] == pfx + "m68":
                rec["metadata"]["extraction_uncertain"] = True
                rec["metadata"].setdefault("extraction_flags", []).append("next_heading_missing")
                rec["metadata"]["source_note"] = ("عنوان المادة 69 غائب عن طبقة نص المرجع، فقد يكون آخر هذه المادة "
                                                  "(«وتقضى المحكمة بإلزام المحكوم عليه…») نصَّ المادة 69. يُراجع بالجريدة الرسمية.")
                rec["verification_status"] = "machine_pending_human"
ids = [x["id"] for x in records]
assert len(ids) == len(set(ids)), [i for i, c in collections.Counter(ids).items() if c > 1]
for rec in records:
    for mk in ("جزاء العتيبي", "العتيبي", "مستشار اول", "مستشار أول"):
        assert mk not in rec["text"] and mk not in rec["title"], (rec["id"], mk)
    assert rec["text"].strip(), rec["id"]
json.dump(records, open(D + "/records.json", "w", encoding="utf-8"), ensure_ascii=False)
for k, v in report.items():
    print(k, v)
print("HEADING_TAIL_REMOVED", len(HEAD_TAIL), HEAD_TAIL)
print("VISUAL_APPLIED", len(VIS_APPLIED), VIS_APPLIED)
print("SUPPLEMENT_APPLIED", len(SUPP_APPLIED), SUPP_APPLIED)
print("RECORDS", len(records), "flagged", sum(1 for r in records if r["metadata"].get("extraction_uncertain")))
