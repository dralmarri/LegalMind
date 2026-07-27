#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إدخال القانون المدني الكويتي (٦٧/١٩٨٠) هرميًّا إلى knowledge_objects.
- يحترم التبويب الأصلي: قسم ← كتاب ← باب ← فصل ← فرع.
- أنواع: legislation_preamble / legislation_issuing_article / legislation_article.
- المعرّفات: legis-67-1980-preamble | -issue-N | -m{رقم}[-mukarrar|-altK]
- لا يختلق نصوصًا؛ يحفظ النص كما هو، ويوثّق الفجوات والتكرارات في تقرير النزاهة.

الاستعمال:
  python3 ingest_civil.py <civil.docx> --dry-run        # تقرير + معاينة بلا إدخال
  python3 ingest_civil.py <civil.docx>                  # إدخال فعلي (يتطلب DATABASE_URL)
"""
from __future__ import annotations
import argparse, json, os, re, sys, zipfile
from collections import OrderedDict, Counter

LAW_NUMBER, LAW_YEAR = 67, 1980
LAW_ID = f"legis-{LAW_NUMBER}-{LAW_YEAR}"
LAW_NAME = "القانون رقم 67 لسنة 1980 بإصدار القانون المدني"
LAW_SHORT = "القانون المدني"
BRANCH = "مدني"

LEVEL = {"القسم": 1, "الجزء": 1, "الكتاب": 2, "الباب": 3, "الفصل": 4, "الفرع": 5, "المبحث": 6}
_KW = "|".join(LEVEL)
# رتبة عددية عربية (تحتمل ي/ى) — لا تُعدّ ترويسةً كلمةُ تبويب لا تتبعها رتبة (تفاديًا لالتقاط جمل المتن)
_ORD = (r"(?:الأول|الاول|الثان[يى]|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر"
        r"|(?:الحاد[يى]|الثان[يى]|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع)\s+عشر"
        r"|العشرون|العشرين|التمهيد[يى])")
HEAD = re.compile(r"^(" + _KW + r")\s+" + _ORD + r"\b")
ORD_ONLY = re.compile(r"^(?:" + _KW + r")\s+" + _ORD + r"\s*:?\s*$")
ART = re.compile(r"^(?:المادة|المادّة|مادة)\s*(?:رقم\s*)?\(?\s*(\d+)\s*\)?(\s*مكرر(?:\s*[)(﴾﴿]?\s*([أ-ي0-9٠-٩]))?)?\b(.*)$")
# علامة مادة صِرفة مسبوقة بترقيم/نقطة ملتصقة من ذيل المادة السابقة (مثل «. مادة 462»)
BARE_MARK = re.compile(r"^[.،؛\-\s]+((?:المادة|المادّة|مادة)\s*\(?\s*\d+\s*\)?(?:\s*مكرر\s*[)(﴾﴿]?\s*[أ-ي0-9٠-٩]?\s*[)(﴾﴿]?)?)\s*$")
# علامات أقسام فرعية بترتيب عربي مثل «(رابعا): المقاصة:» — حدود لا تُدرَج في نصّ المادة
PAREN = re.compile(r"^[()]?\s*(?:أولا|ثانيا|ثالثا|رابعا|خامسا|سادسا|سابعا|ثامنا|تاسعا|عاشرا)\s*ً*\s*[()]?\s*[:：]?\s*.{0,40}$")
LETTER_TRANSLIT = {"أ": "a", "ا": "a", "ب": "b", "ج": "c", "د": "d", "هـ": "e", "ه": "e", "و": "f", "ز": "g", "ح": "h"}
KEEP_FIRST = set()  # أرقام مواد: تكرارها إشارة مرجعية/شظية — تُبقى النسخة الأولى فقط (مراجَعة يدويًّا)
M1_HEADING = ""     # عنوان يقوم مقام «مادة 1» غير المرقّمة (مثل «التعريفات») — يُحقَن كمادة 1
INJECT_MARKERS = [] # [(رقم, نصّ مرساة)] لحقن علامة «مادة N» أمام فقرة فقدت علامتها في المصدر
ISSUE = re.compile(r"^(?:المادة|مادة)\s+(?:ال)?(أولى|ثانية|ثالثة|رابعة|خامسة|سادسة|سابعة)\b(.*)$")

_HRK = re.compile(r"[ً-ْٰـ]")  # تنوين/حركات/تطويل — تُزال للكشف فقط لا للتخزين
def _dz(s):
    return _HRK.sub("", s)

def read_paras(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    out = []
    for p in re.findall(r"<w:p\b.*?</w:p>", xml, re.S):
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            out.append(t)
    return out

def merge_titles(paras):
    """يدمج العنوان المنفصل مع ترويسة التبويب المجرّدة (مثل «الباب الأول» + «القانون»)."""
    out = []; i = 0
    while i < len(paras):
        t = paras[i]
        if HEAD.match(_dz(t)) and ORD_ONLY.match(_dz(t)) and i + 1 < len(paras):
            nx = paras[i + 1]
            if not HEAD.match(_dz(nx)) and not ART.match(nx) and not ISSUE.match(nx) and not PAREN.match(_dz(nx)) and len(nx) < 60:
                out.append(t + " — " + nx); i += 2; continue
        out.append(t); i += 1
    return out

def clean_label(s):
    s = s.strip()
    m = re.match(r"^(?:القسم|الجزء|الكتاب|الباب|الفصل|الفرع|المبحث)\s+\S+(?:\s+عشر)?\s*[—:\-–ـ]*\s*(.*)$", s)
    if m:
        rest = m.group(1).strip(" -–—:ـ")
        return rest if rest else s
    return s

def _is_xref(m, seen, curmax):
    """علامة مادة تشير لرقم سابق أقل من أعلى رقم بدأناه ⇒ إحالة داخل المتن لا عنوان."""
    n = int(m.group(1)); muk = bool(m.group(2))
    return (not muk) and (n in seen) and (n < curmax)

def parse(path):
    paras = merge_titles(read_paras(path))
    # 0) تنظيف علامات المواد الملتصقة بترقيم ذيل المادة السابقة («. مادة 462» ⇒ «مادة 462»)
    #    يُطبَّق فقط على السطور التي هي علامة مادة صِرفة (لا كلام بعدها) فلا يلتقط إحالات المتن.
    paras = [BARE_MARK.sub(r"\1", p) for p in paras]
    # 0-أ) حقن علامات مواد فقدت في المصدر (رقم@مرساة): تُسبَق الفقرة المرساة بـ«مادة N»
    for _num, _anchor in INJECT_MARKERS:
        for idx, p in enumerate(paras):
            if p.startswith(_anchor) and not ART.match(p):
                paras[idx] = f"مادة {_num} " + p
                break
    # 0-ب) حقن «مادة 1» إن غابت ووُجد عنوانٌ يقوم مقامها (مثل «التعريفات» في قانون الشركات)
    if M1_HEADING:
        has_m1 = any(ART.match(p) and int(ART.match(p).group(1)) == 1 and not ART.match(p).group(2)
                     for p in paras)
        if not has_m1:
            for idx, p in enumerate(paras):
                if p.strip() == M1_HEADING:
                    paras[idx] = "مادة 1 " + M1_HEADING
                    break
    # 1) الديباجة: من البداية حتى أول «مادة أولى»
    first_issue = next((i for i, t in enumerate(paras) if ISSUE.match(t)), None)
    first_art = next((i for i, t in enumerate(paras) if ART.match(t)), None)
    preamble = "\n".join(paras[:first_issue]) if first_issue else ""
    # 2) مواد الإصدار
    issuing = []
    if first_issue is not None:
        i = first_issue
        while i < (first_art or len(paras)):
            m = ISSUE.match(paras[i])
            if m:
                body = [m.group(2).strip()] if m.group(2).strip() else []
                j = i + 1
                while j < (first_art or len(paras)) and not ISSUE.match(paras[j]) and not HEAD.match(paras[j]):
                    body.append(paras[j]); j += 1
                issuing.append((m.group(1), "\n".join(x for x in body if x).strip()))
                i = j
            else:
                i += 1
    # 3) مواد القانون + التبويب
    stack = {}; articles = []
    seen_nums = set(); maxnum = 0
    i = first_art if first_art is not None else len(paras)
    while i < len(paras):
        t = paras[i]
        ma = ART.match(t); mh = HEAD.match(_dz(t))
        if ma and not _is_xref(ma, seen_nums, maxnum):
            num = int(ma.group(1)); muk = bool(ma.group(2)); letter = (ma.group(3) or "").strip()
            body = [ma.group(4).strip()] if ma.group(4).strip() else []
            cmax = max(maxnum, num); cseen = seen_nums | {num}
            j = i + 1
            while j < len(paras):
                mj = ART.match(paras[j])
                if (mj and not _is_xref(mj, cseen, cmax)) or HEAD.match(_dz(paras[j])) or PAREN.match(_dz(paras[j])):
                    break
                body.append(paras[j]); j += 1
            lv = {k: clean_label(v) for k, v in stack.items()}
            articles.append({"num": num, "mukarrar": muk, "letter": letter,
                             "text": "\n".join(x for x in body if x).strip(),
                             "levels": lv,
                             "path_raw": [stack[k] for k in sorted(stack)]})
            seen_nums.add(num); maxnum = max(maxnum, num)
            i = j
        elif mh:
            L = LEVEL[mh.group(1)]
            stack = {k: v for k, v in stack.items() if k < L}
            stack[L] = t
            i += 1
        else:
            # يشمل علامات الأقسام الفرعية «(رابعا) …» — حدود تُتخطّى ولا تُدرَج
            i += 1
    return preamble, issuing, articles

def map_fields(lv):
    qism, kitab, bab, fasl, fara = lv.get(1), lv.get(2), lv.get(3), lv.get(4), lv.get(5)
    topic = kitab or qism or bab or "أحكام عامة"
    subtopic = None
    for c in (bab, fasl):
        if c and c != topic:
            subtopic = c; break
    micro = None
    for c in (fasl, fara):
        if c and c not in (topic, subtopic):
            micro = c; break
    return topic, subtopic, micro, {"qism": qism, "kitab": kitab, "bab": bab, "fasl": fasl, "fara": fara}

def build_rows(preamble, issuing, articles):
    rows = []
    if preamble:
        rows.append({"id": f"{LAW_ID}-preamble", "object_type": "legislation_preamble",
                     "branch": BRANCH, "topic": "ديباجة", "subtopic": None, "micro_issue": None,
                     "title": f"ديباجة — {LAW_SHORT}", "text": preamble,
                     "meta": {"law_name": LAW_NAME, "law_year": LAW_YEAR, "law_number": LAW_NUMBER,
                              "upload_origin": "docx_legislation_import"}})
    ord_map = {"أولى": 1, "ثانية": 2, "ثالثة": 3, "رابعة": 4, "خامسة": 5, "سادسة": 6}
    for label, text in issuing:
        k = ord_map.get(label, len(rows))
        rows.append({"id": f"{LAW_ID}-issue-{k}", "object_type": "legislation_issuing_article",
                     "branch": BRANCH, "topic": "مواد الإصدار", "subtopic": None, "micro_issue": None,
                     "title": f"مادة الإصدار ({label}) — {LAW_SHORT}", "text": text,
                     "meta": {"law_name": LAW_NAME, "law_year": LAW_YEAR, "law_number": LAW_NUMBER,
                              "upload_origin": "docx_legislation_import", "issuing_article": label}})
    # dedup/disambiguation
    # حسم تعارضات مؤكَّدة من الجريدة الرسمية: نُبقي النسخة النافذة ونوثّق التعديل
    RESOLVE = {
        132: {"keep": "الوصية",
              "version_note": "معدَّلة بالقانون رقم 15 لسنة 1996 (الكويت اليوم 22/5/1996). "
                              "النص قبل التعديل كان «بطريق الميراث أو التبرع، واشترط المورث أو المتبرع…»."},
    }
    report = {"identical_dropped": [], "conflicts": [], "mukarrar": [], "resolved": []}
    groups = OrderedDict()
    for a in articles:
        key = (a["num"], a["mukarrar"], a["letter"])
        groups.setdefault(key, []).append(a)
    for (num, muk, letter), items in groups.items():
        distinct = []
        for it in items:
            if not any(it["text"] == d["text"] for d in distinct):
                distinct.append(it)
        n_ident = len(items) - len(distinct)
        resolved_note = None
        if num in KEEP_FIRST and len(distinct) > 1:
            distinct = [distinct[0]]
            resolved_note = "تكرار (إشارة مرجعية/شظية في المصدر) — أُبقيت النسخة الأصلية الأولى بعد مراجعة يدوية"
            report["resolved"].append({"article": num, "kept": "first"})
        if num in RESOLVE and len(distinct) > 1:
            kept = [d for d in distinct if RESOLVE[num]["keep"] in d["text"]]
            if len(kept) == 1:
                distinct = kept
                resolved_note = RESOLVE[num]["version_note"]
                report["resolved"].append({"article": num, "kept_contains": RESOLVE[num]["keep"]})
        arlabel = f"{num}" + (" مكرر" if muk else "") + (f" {letter}" if letter else "")
        if n_ident:
            report["identical_dropped"].append({"article": arlabel, "dropped": n_ident})
        if muk:
            report["mukarrar"].append(arlabel)
        for idx, it in enumerate(distinct):
            suffix = ""
            if muk:
                suffix += "-mukarrar"
            if letter:
                suffix += "-" + LETTER_TRANSLIT.get(letter, letter)
            if idx > 0:
                suffix += f"-alt{idx+1}"
            topic, subtopic, micro, tab = map_fields(it["levels"])
            meta = {"law_name": LAW_NAME, "law_year": LAW_YEAR, "law_number": LAW_NUMBER,
                    "upload_origin": "docx_legislation_import",
                    "article_number": arlabel,
                    "tabweeb": {k: v for k, v in tab.items() if v},
                    "tabweeb_path": it["path_raw"]}
            if it.get("supplemented"):
                meta["supplemented"] = True
                meta["source_note"] = "مستكمَلة من الجريدة الرسمية (e.gov.kw — QanoonMadani) لأنها غائبة عن ملف DOCX المصدر — نقل من صورة"
            if resolved_note:
                meta["version_note"] = resolved_note
            if len(distinct) > 1:
                meta["duplicate_conflict"] = True
                meta["source_note"] = ("نُسختان مختلفتان لرقم المادة نفسه في ملف المصدر — تحتاج مراجعة بشرية ومطابقة بالجريدة الرسمية")
                if idx == 1:
                    report["conflicts"].append({"article": arlabel, "variants": len(distinct)})
            # إزالة شظية أقواس مكرّرة في صدر النص (مثل «)))» من «مادة 1 )))») دون المساس ببنود «(1)»
            art_text = re.sub(r"^\s*[)(﴾﴿]{2,}\s*", "", it["text"]).strip()
            # مواد ملغاة: نصّها في المصدر شاهد إلغاء ملفوف بأقواس — نبسّطه ونضع علمًا
            _depar = re.sub(r"[)(﴾﴿\s]+", " ", art_text).strip()
            if _depar.startswith("ملغا") or _depar.replace(" ", "").startswith("ملغا"):
                art_text = _depar
                meta["repealed"] = True
            rows.append({"id": f"{LAW_ID}-m{num}{suffix}", "object_type": "legislation_article",
                         "branch": BRANCH, "topic": topic, "subtopic": subtopic, "micro_issue": micro,
                         "title": f"المادة {arlabel} — {LAW_SHORT}",
                         "text": art_text, "meta": meta})
    return rows, report

def normalize_text(text):
    try:
        sys.path.insert(0, "/opt/LegalMind/engine")
        from normalizer.canonical import normalize_text as nt
        return nt(text)
    except Exception:
        import unicodedata
        t = unicodedata.normalize("NFKC", text).replace("ـ", "")
        t = re.sub(r"[ \t]+", " ", t); t = re.sub(r" *\n *", "\n", t)
        return re.sub(r"\n{3,}", "\n\n", t).strip()

def main():
    global LAW_NUMBER, LAW_YEAR, LAW_ID, LAW_NAME, LAW_SHORT, BRANCH, KEEP_FIRST, M1_HEADING, INJECT_MARKERS
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--supplement", help="ملف JSON {رقم المادة: نص} للمواد الغائبة عن المصدر")
    ap.add_argument("--law-number", type=int, default=LAW_NUMBER)
    ap.add_argument("--law-year", type=int, default=LAW_YEAR)
    ap.add_argument("--law-name", default=LAW_NAME)
    ap.add_argument("--law-short", default=LAW_SHORT)
    ap.add_argument("--branch", default=BRANCH)
    ap.add_argument("--keep-first", default="", help="أرقام مواد (مفصولة بفواصل) تُبقى نسختها الأولى عند التكرار")
    ap.add_argument("--m1-heading", default="", help="عنوان يقوم مقام «مادة 1» غير المرقّمة (مثل «التعريفات»)")
    ap.add_argument("--inject-marker", action="append", default=[], help="حقن علامة مادة مفقودة بصيغة «رقم@نصّ بداية الفقرة»")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--samples", type=int, default=6)
    args = ap.parse_args()

    LAW_NUMBER, LAW_YEAR = args.law_number, args.law_year
    LAW_ID = f"legis-{LAW_NUMBER}-{LAW_YEAR}"
    LAW_NAME, LAW_SHORT, BRANCH = args.law_name, args.law_short, args.branch
    KEEP_FIRST = {int(x) for x in args.keep_first.split(",") if x.strip()}
    M1_HEADING = args.m1_heading.strip()
    INJECT_MARKERS = [(int(s.split("@", 1)[0]), s.split("@", 1)[1]) for s in args.inject_marker if "@" in s]

    preamble, issuing, articles = parse(args.source)

    # دمج المواد المستكمَلة (من الجريدة الرسمية) بوراثة تبويب أقرب مادة سابقة موجودة
    if args.supplement:
        sup = json.load(open(args.supplement, encoding="utf-8"))
        present = {a["num"]: a for a in articles if not a["mukarrar"] and not a["letter"]}
        base = [a for a in articles if not a["mukarrar"] and not a["letter"]]
        added = corrected = 0
        for k, text in sup.items():
            n = int(k)
            if n in present:                              # تصحيح نصّ مادة مشوّهة في المصدر
                present[n]["text"] = text.strip()
                present[n]["supplemented"] = True
                corrected += 1
                continue
            prev = max((a for a in base if a["num"] < n), key=lambda a: a["num"], default=None)
            articles.append({"num": n, "mukarrar": False, "letter": "",
                             "text": text.strip(),
                             "levels": dict(prev["levels"]) if prev else {},
                             "path_raw": list(prev["path_raw"]) if prev else [],
                             "supplemented": True})
            added += 1
        articles.sort(key=lambda a: (a["num"], a["mukarrar"], a["letter"]))
        print(f"[supplement] أُضيفت {added} مادة مستكمَلة، وصُحّح نصّ {corrected} مادة.\n")
    rows, report = build_rows(preamble, issuing, articles)

    nums = sorted(set(a["num"] for a in articles))
    missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
    art_rows = [r for r in rows if r["object_type"] == "legislation_article"]

    print("=" * 60)
    print(f"القانون: {LAW_NAME}")
    print(f"الفرع: {BRANCH} | معرّف القانون: {LAW_ID}")
    print(f"الديباجة: {'نعم' if preamble else 'لا'} | مواد الإصدار: {len(issuing)}")
    print(f"مواد القانون (بعد المعالجة): {len(art_rows)} | إجمالي الكائنات: {len(rows)}")
    print(f"أرقام المواد: 1 → {max(nums)} | مميّزة: {len(nums)}")
    print(f"إجمالي الكائنات المُدخَلة (بديباجة+إصدار): {len(rows)}")
    print("-" * 60)
    print("== تقرير النزاهة ==")
    print(f"• تكرارات متطابقة أُسقطت: {report['identical_dropped'] or 'لا شيء'}")
    print(f"• تعارضات محسومة (أُبقيت النسخة النافذة ووُثّق التعديل): {report['resolved'] or 'لا شيء'}")
    print(f"• تعارضات متبقّية للمراجعة: {report['conflicts'] or 'لا شيء'}")
    print(f"• مواد مكرر: {report['mukarrar'] or 'لا شيء'}")
    print(f"• أرقام مواد غائبة عن المصدر ({len(missing)}): {missing}")
    print("-" * 60)
    print(f"== عيّنة صفوف ({args.samples}) ==")
    for r in art_rows[:args.samples]:
        print(f"[{r['id']}]")
        print(f"   العنوان: {r['title']}")
        print(f"   topic={r['topic']} | subtopic={r['subtopic']} | micro={r['micro_issue']}")
        print(f"   النص: {r['text'][:80]}...")
    print("-" * 60)
    # tree by mapped topic/subtopic
    tree = OrderedDict()
    for r in art_rows:
        tp = r["topic"]; st = r["subtopic"] or "—"
        tree.setdefault(tp, Counter())[st] += 1
    print("== الشجرة حسب (topic ← subtopic) + العدد ==")
    for tp, sts in tree.items():
        print(f"• {tp}  [{sum(sts.values())}]")
        for st, c in sts.items():
            print(f"    - {st}: {c}")

    if args.dry_run:
        print("\n[dry-run] لم يُدخَل شيء.")
        return 0

    import psycopg
    from psycopg.types.json import Jsonb
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    ins = 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(
                    """INSERT INTO knowledge_objects
                       (id,object_type,branch,topic,subtopic,micro_issue,title,original_text,normalized_text,
                        source_key,verification_status,authority_status,usable_as_citation,metadata)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,'source_verified','source_authority',TRUE,%s)
                       ON CONFLICT (id) DO UPDATE SET
                        object_type=EXCLUDED.object_type,branch=EXCLUDED.branch,topic=EXCLUDED.topic,
                        subtopic=EXCLUDED.subtopic,micro_issue=EXCLUDED.micro_issue,title=EXCLUDED.title,
                        original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                        metadata=EXCLUDED.metadata,updated_at=now()""",
                    (r["id"], r["object_type"], r["branch"], r["topic"], r["subtopic"], r["micro_issue"],
                     r["title"], r["text"], normalize_text(r["text"]), Jsonb(r["meta"])))
                ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل الآن: python -m engine.legalmind_engine reindex")
    return 0

if __name__ == "__main__":
    sys.exit(main())
