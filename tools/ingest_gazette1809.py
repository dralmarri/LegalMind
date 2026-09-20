# -*- coding: utf-8 -*-
"""
دفعة الكويت اليوم — العدد 1809، السنة الثانية والسبعون، الأحد 9 ربيع الآخر 1448هـ
الموافق 2026/9/20م.

ما تُدخله هذه الدفعة:
  (أ) مرسوم بقانون رقم 91 لسنة 2026 بتعديل بعض أحكام القانون رقم (7) لسنة 2010
      بشأن إنشاء هيئة أسواق المال وتنظيم نشاط الأوراق المالية — النص كاملًا
      (ديباجة + أربع مواد + التوقيعات) ومذكرته الإيضاحية. ص8-9.
  (ب) تطبيق قاعدة التحديث على القانون 7/2010:
      - م1: استبدال تعريفَي (الوزير المختص) و(المحكمة المختصة) على المعرّف نفسه،
        والنص القديم يُحفظ في metadata.previous_versions[] — لا يُمحى نص قط.
      - المواد 108، 109، 110، 111، 112، 113، 116: توسم superseded/repealed_by
        ولا تُحذف (نموذج §10 المعتمد في إلغاء 23/1990).
  (ج) المذكرة الإيضاحية للمرسوم بقانون رقم 93 لسنة 2026 بتعديل المادة (11) من
      القانون (النظام) الموحد لمكافحة الغش التجاري الصادر بالقانون 20/2019. ص12.
      **نص المرسوم نفسه غير متاح في المصدر المرفوع** — تُدخل المذكرة وحدها،
      ويوسم legis-20-2019-m11 بأنه معدَّل بانتظار النص الرسمي. لا يُصطنع نص.

ما لا تُدخله هذه الدفعة عمدًا:
  - المرسوم بقانون بشأن الصكوك الحكومية: المرفوع لا يحمل منه إلا ذيل مذكرته
    الإيضاحية (الفصلان السادس والسابع) بلا رقمه ولا متنه — لا يُسكّ معرّف لرقم
    غير معلوم ولا تُدخل شذرة مذكرة.
  - القرار الوزاري 590/2026 (اللائحة التنفيذية لقانون التوثيق 10/2020): مُدخَل
    فعلًا وكاملًا في القاعدة تحت البادئة regl-10-2020 (67 كائنًا) — تتحقق منه
    هذه الدفعة ولا تعيد إدخاله.

النقل: بصري من صور الجريدة الرسمية بدقة 200dpi، مقابَلًا بطبقة نص الـPDF
(المعطوبة بإسقاط حروف — النمط الموثق في §9). كل فرق حُسم لصالح القراءة البصرية.
"""

import sys, os, re, json, hashlib, datetime

sys.path.insert(0, "/opt/LegalMind")
os.chdir("/opt/LegalMind")

import psycopg
from psycopg.types.json import Jsonb
from engine.normalizer.canonical import normalize_text

GAZETTE_REF = ("الكويت اليوم، العدد 1809، السنة الثانية والسبعون، "
               "الأحد 9 ربيع الآخر 1448هـ الموافق 2026/9/20م")
GAZETTE_DATE = "2026-09-20"
UPLOAD_ORIGIN = "gazette_official_2026-09-20_issue_1809"

# ═══════════════ بوابة تنقية الناشر (§9 قاعدة 2) ═══════════════
PUBLISHER_MARKS = [
    "جمعية المحامين", "Mohamedsale", "mohamedsale", "60477772", "+965",
    "المرجاح", "almirjah", "Lawskw", "Mojconcourt", "DASMAN",
]

def pubscrub_assert(records):
    bad = []
    for r in records:
        blob = " ".join([str(r.get("title") or ""), str(r.get("original_text") or "")])
        for mark in PUBLISHER_MARKS:
            if mark in blob:
                bad.append((r["id"], mark))
    if bad:
        for rid, mark in bad:
            print("PUBSCRUB_FAIL:", rid, "->", mark)
        raise SystemExit("PUBSCRUB_FAIL: علامة ناشر في نص مُعدّ للإدخال")
    print("PUBSCRUB_OK: %d كائنًا نظيفًا من علامات الناشر" % len(records))


# ═══════════════ (أ) مرسوم بقانون 91/2026 ═══════════════
D91_NUM, D91_YEAR = 91, 2026
D91_INSTRUMENT = "مرسوم بقانون رقم 91 لسنة 2026"
D91_LONGTITLE = ("مرسوم بقانون رقم 91 لسنة 2026 بتعديل بعض أحكام القانون رقم (7) لسنة 2010 "
                 "بشأن إنشاء هيئة أسواق المال وتنظيم نشاط الأوراق المالية")
D91_ISSUED_DATE = "2026-09-14"   # صدر بقصر السيف — 3 ربيع الآخر 1448هـ

D91_PREAMBLE = """- بعد الاطلاع على الدستور،
وعلى الأمر الأميري الصادر بتاريخ 2 ذو القعدة 1445هـ الموافق 10 مايو 2024م،
- وعلى قانون الجزاء الصادر بالقانون رقم (16) لسنة 1960، والقوانين المعدلة له،
- وعلى قانون الإجراءات والمحاكمات الجزائية الصادر بالقانون رقم (17) لسنة 1960، والقوانين المعدلة له،
- وعلى قانون المرافعات المدنية والتجارية الصادر بالمرسوم بقانون رقم (38) لسنة 1980، والقوانين المعدلة له،
- وعلى القانون رقم (7) لسنة 2010 بشأن إنشاء هيئة أسواق المال وتنظيم نشاط الأوراق المالية، والقوانين المعدلة له،
- وعلى قانون تنظيم القضاء الصادر بالمرسوم بقانون رقم (80) لسنة 2026،
- وعلى قانون إنشاء الدوائر الاقتصادية الصادر بالمرسوم بقانون رقم (88) لسنة 2026،
- وعلى المرسوم رقم 84 لسنة 2024 في شأن الحلول والإنابات الوزارية، والمراسيم المعدلة له.
- وبناء على عرض وزير الدولة للشؤون الاقتصادية والاستثمار،
- وبعد موافقة مجلس الوزراء،
- أصدرنا المرسوم بقانون الآتي نصه:"""

D91_A1 = """مادة أولى
يستبدل بتعريف (الوزير المختص) وتعريف (المحكمة المختصة) الواردين في المادة (1) من القانون رقم (7) لسنة 2010 المشار إليه، التعريفان الآتيان:
(الوزير المختص): " الوزير الذي يحدده مجلس الوزراء ".
(المحكمة المختصة): " الدائرة الاقتصادية المدنية والتجارية أو الإدارية المنشأة بالمرسوم بقانون رقم (88) لسنة 2026، والمحكمة المختصة وفقا للقواعد المقررة في قانون الإجراءات والمحاكمات الجزائية بحسب الأحوال ".
وتستبدل عبارتا "الوزير المختص" و "المحكمة المختصة"، بعبارتي "وزير التجارة والصناعة" و "محكمة أسواق المال" أينما وردتا في القانون رقم (7) لسنة 2010 المشار إليه."""

D91_A2 = """مادة ثانية
تستمر محكمة أسواق المال في نظر الدعاوى والطعون المقيدة لديها قبل تاريخ العمل بأحكام هذا المرسوم بقانون لحين الفصل فيها."""

D91_A3 = """مادة ثالثة
تلغى المواد (108، 109، 110، 111، 112، 113، 116) من القانون رقم (7) لسنة 2010 المشار إليه.
كما يلغى كل حكم يخالف أحكام هذا المرسوم بقانون."""

D91_A4 = """مادة رابعة
على الوزراء - كل فيما يخصه - تنفيذ هذا المرسوم بقانون، وينشر في الجريدة الرسمية، ويعمل به اعتباراً من تاريخ العمل بالمرسوم بقانون رقم (88) لسنة 2026 بإصدار قانون في شأن إنشاء الدوائر الاقتصادية."""

D91_SIGN = """أمير الكويت
مشعل الأحمد الجابر الصباح

رئيس مجلس الوزراء بالنيابة
فهد يوسف سعود الصباح

وزير الدولة للشؤون الاقتصادية والاستثمار
عبد العزيز ناصر عبد العزيز المرزوق

صدر بقصر السيف في: 3 ربيع الآخر 1448هـ
الموافق: 14 سبتمبر 2026م"""

D91_MEMO = """أفرد القانون رقم (7) لسنة 2010 بشأن إنشاء هيئة أسواق المال وتنظيم نشاط الأوراق المالية تنظيماً خاصاً للمنازعات الناشئة عن تطبيق أحكامه، فأنشأ محكمة أسواق المال، وبين اختصاصها، ونظم بعض الإجراءات المتبعة أمامها، وذلك بالنظر إلى الطبيعة الخاصة لمنازعات أسواق المال وما تتطلبه من عناية وسرعة في الفصل.
ولما كان قد صدر مرسوم بقانون رقم (88) لسنة 2026 بإصدار قانون في شأن إنشاء الدوائر الاقتصادية والذي عهد بموجبه إلى هذه الدوائر بنظر المنازعات غير الجزائية الناشئة عن تطبيق القانون رقم (7) لسنة 2010 المشار إليه، فقد أضحى من اللازم إجراء تعديل تشريعي على هذا القانون.
وإذ صدر الأمر الأميري بتاريخ 10/5/2024 ونص في مادته (4) على أن تصدر القوانين بمراسيم بقوانين، ومن ثم أعد هذا المرسوم بقانون بتعديل بعض أحكام القانون رقم (7) لسنة 2010 المشار إليه.
ونصت المادة الأولى من مرسوم بقانون الماثل على استبدال تعريفي (الوزير المختص)، و(المحكمة المختصة) الواردين في المادة (1) من القانون رقم (7) لسنة 2010 سالف الذكر، بأن يكون تعريف (الوزير المختص) هو الوزير الذي يحدده مجلس الوزراء بدلاً من وزير التجارة والصناعة، وذلك لتفادي الحاجة إلى تعديل التشريع مستقبلاً حال نقل التبعية الإدارية لهيئة أسواق المال إلى وزير آخر أو حقيبة وزارية مختلفة.
كما أصبح تعريف (المحكمة المختصة) هي الدائرة الاقتصادية بالمنازعات المدنية والتجارية أو الإدارية المنشأة بمرسوم بقانون رقم (88) لسنة 2026، أو المحكمة الجزائية المختصة بنظر الجرائم الجزائية المنصوص عليها في القانون رقم (7) لسنة 2010 وفقاً للقواعد العامة المنصوص عليها في قانون الإجراءات والمحاكمات الجزائية الصادر بالقانون رقم (17) لسنة 1960.
كما استبدلت الفقرة الثانية من المادة الأولى من مرسوم بقانون الماثل، عبارة (الوزير المختص) بعبارة (وزير التجارة والصناعة)، وعبارة (المحكمة المختصة) بعبارة (محكمة أسواق المال)، أينما وردتا في القانون رقم (7) لسنة 2010 سالف الذكر.
وجاءت المادة الثانية من هذا المرسوم بقانون بحكم انتقالي مفاده بقاء الدعاوى والطعون القائمة وقت العمل بالقانون أمام محكمة أسواق المال إلى حين الفصل فيها.
ونصت مادته الثالثة على إلغاء المواد المتعلقة بإنشاء محكمة أسواق المال، وبعض الإجراءات الخاصة بها، والطعن على أحكامها وذلك بعد أن أصبحت المنازعات غير الجزائية الناشئة عن تطبيق القانون رقم (7) لسنة 2010 المشار إليه داخلة في اختصاص الدائرة الاقتصادية، والجرائم المنصوص عليها فيه خاضعة للقواعد العامة في الاختصاص والإجراءات الجزائية.
وألزمت المادة الرابعة من المرسوم بقانون الماثل الوزراء - كل فيما يخصه - بتنفيذ أحكامه، ونشره في الجريدة الرسمية، وحددت تاريخ العمل بأحكامه اعتباراً من تاريخ العمل بالمرسوم بقانون رقم (88) لسنة 2026 بإصدار قانون في شأن إنشاء الدوائر الاقتصادية لارتباط نفاذهما معاً."""

# ═══════════════ (ج) المذكرة الإيضاحية للمرسوم بقانون 93/2026 ═══════════════
D93_NUM, D93_YEAR = 93, 2026
D93_LONGTITLE = ("مرسوم بقانون رقم 93 لسنة 2026 بتعديل المادة (11) من القانون (النظام) الموحد "
                 "لمكافحة الغش التجاري لدول مجلس التعاون لدول الخليج العربية "
                 "الصادر بالقانون رقم (20) لسنة 2019")

D93_MEMO = """صدر القانون رقم (20) لسنة 2019 متضمنا القانون النظام الموحد لمكافحة الغش التجاري لدول مجلس التعاون لدول الخليج العربية، وقد نظم أحكام مكافحة الغش التجاري، وبيّن صور الغش المحظورة، والالتزامات المقررة على المزود والأحكام المتعلقة بضبط البضائع المغشوشة والتصرف فيها، فضلاً عن العقوبات المقررة على مخالفة أحكامه.
وقد نصت المادة (2) من القانون المشار إليه على صور الغش التجاري المحظور، كما ألزمت المادة (3) المزود بسحب البضاعة المغشوشة من الأسواق والمخازن، ونظمت المادة (4) حكم افتراض علم المزود بطبيعة البضاعة المغشوشة، وأوجبت المادة (5) على المزود رد قيمة البضاعة المغشوشة إلى المشتري، في حين نظمت المادة (6) منح الضبطية القضائية لفئة من الموظفين المكلفين بتنفيذ أحكام القانون.
وكانت المادة (11) من القانون المشار إليه قد رتبت العقوبة على مخالفة أحكام المواد (3)، (4)، (6)، والبندين (أ) و(ب) من المادة (8) دون أن تشمل الإحالة إلى المادتين (2) و(5) رغم ما تتضمنانه من أحكام جوهرية تتصل مباشرة بصور الغش التجاري المحظور والالتزام برد قيمة البضاعة المغشوشة إلى المشتري.
كما أن المادتين (4) و(6) لا تتضمنان أفعالاً أو حالات امتناع محظورة تصلح بذاتها محلاً للتجريم والعقاب، إذ تقرر المادة (4) حكما متعلقا بافتراض علم المزود بطبيعة البضاعة المغشوشة، بينما تنظم المادة (6) منح بعض الموظفين صفة الضبطية القضائية.
وقد تبين من مراجعة الصياغة الأصلية للمادة (11) من القانون (النظام) الموحد لمكافحة الغش التجاري لدول مجلس التعاون لدول الخليج العربية - بالشكل الذي تم اعتمادها به من قبل المجلس الأعلى لمجلس التعاون لدول الخليجي العربية المتخذ في دور انعقاده السابع والثلاثين المنعقد في مملكة البحرين في الفترة من 6-7 ديسمبر 2016، ومن خلال ما ورد بكتاب الأمانة العامة لمجلس التعاون لدول الخليج العربية بشأن الخطأ المطبعي الذي شاب نص المادة المذكورة بأن نص المادة (11) جرى استدراكه بما يتفق مع المقصود التشريعي بحيث تشمل العقوبة مخالفة أحكام المواد (2) و(3) و(5) والبندين (أ) و(ب) من المادة (8).
ومن ثم أعد المرسوم بقانون الماثل لتدارك الخطأ الوارد في الإحالات المنصوص عليها في المادة (11) من القانون (النظام) المشار إليه ومواءمة النص الوطني مع النص الصحيح المستدرك للقانون (النظام) الموحد لمكافحة الغش التجاري لدول مجلس التعاون لدول الخليج العربية.
فنصت المادة الأولى منه على استبدال نص المادة (11) منه، بما يترتب عليه شمول العقوبة لمخالفة أحكام المواد (2) و(3) و(5) والبندين (أ) و(ب) من المادة (8)، واستبعاد الإحالة إلى المادتين (4) و(6).
ونصت المادة الثانية على أن يعمل به من تاريخ نشره في الجريدة الرسمية.
وإذ صدر الأمر الأميري بتاريخ 2 ذو القعدة 1445هـ الموافق 10 مايو 2024 ونصت المادة 4 منه على أن تصدر القوانين بمراسيم بقوانين، لذا أعد المرسوم بقانون الماثل."""


# ═══════════════════════════ بناء الكائنات ═══════════════════════════

def _row(rid, otype, branch, topic, subtopic, title, text, extra_meta,
         citable=True, status="source_verified"):
    meta = {
        "gazette_ref": GAZETTE_REF,
        "gazette_date": GAZETTE_DATE,
        "upload_origin": UPLOAD_ORIGIN,
        "extraction_method": "visual_200dpi_vs_pdf_textlayer",
        "extraction_note": ("نُقل بصريًا من صورة الجريدة الرسمية بدقة 200dpi وقوبل بطبقة نص "
                            "الـPDF؛ طبقة النص مصابة بإسقاط حروف (النمط الموثق في §9) "
                            "فحُسم كل فرق لصالح القراءة البصرية."),
    }
    meta.update(extra_meta)
    return {
        "id": rid, "object_type": otype, "branch": branch,
        "topic": topic, "subtopic": subtopic, "micro_issue": None,
        "title": title, "original_text": text,
        "normalized_text": normalize_text(text),
        "source_key": None, "verification_status": status,
        "metadata": meta, "authority_status": "source_authority",
        "usable_as_citation": citable,
    }


D91_BRANCH = "تجاري"       # مطابق للتصنيف الحي لـlegis-7-2010 (تُحقق منه بعيّنة قبل البناء)
D91_TOPIC = "تعديل قانون هيئة أسواق المال — نقل الاختصاص إلى الدوائر الاقتصادية"
D93_BRANCH = "جزائي"       # مطابق للتصنيف الحي لـlegis-20-2019-m11
D93_TOPIC = "مكافحة الغش التجاري — النظام الموحد الخليجي (الجرائم والعقوبات والضبط)"


def build_91_records():
    base = {"law_number": D91_NUM, "law_year": D91_YEAR,
            "instrument": D91_INSTRUMENT, "instrument_rank": "مرسوم بقانون",
            "issued_date": D91_ISSUED_DATE,
            "amends": "القانون رقم (7) لسنة 2010 — legis-7-2010",
            "effective_rule": ("يعمل به اعتبارًا من تاريخ العمل بالمرسوم بقانون رقم (88) "
                               "لسنة 2026 بإصدار قانون في شأن إنشاء الدوائر الاقتصادية "
                               "— لارتباط نفاذهما معًا"),
            "related_laws": ["legis-7-2010", "legis-88-2026", "legis-80-2026", "legis-17-1960"]}
    out = []
    out.append(_row("legis-91-2026-preamble", "legislation_preamble", D91_BRANCH,
                    D91_TOPIC, "الديباجة", "ديباجة %s" % D91_LONGTITLE,
                    D91_PREAMBLE, dict(base, issuing=True)))
    for seq, (label, text) in enumerate(
            [("أولى", D91_A1), ("ثانية", D91_A2), ("ثالثة", D91_A3), ("رابعة", D91_A4)], 1):
        m = dict(base, issuing=True, issuing_seq=seq, issuing_label=label)
        if seq == 3:
            m["repeals"] = ["legis-7-2010-m%d" % n for n in (108, 109, 110, 111, 112, 113, 116)]
        if seq == 4:
            m["signatories_text"] = D91_SIGN
            m["is_effective_article"] = True
        out.append(_row("legis-91-2026-issue-%d" % seq, "legislation_issuing_article",
                        D91_BRANCH, D91_TOPIC, "مواد الإصدار",
                        "مادة %s — %s" % (label, D91_INSTRUMENT), text, m))
    out.append(_row("legis-91-2026-memo-1", "legislation_preamble", D91_BRANCH,
                    D91_TOPIC, "المذكرة الإيضاحية",
                    "المذكرة الإيضاحية — %s" % D91_LONGTITLE, D91_MEMO,
                    dict(base, document_kind="explanatory_memorandum", issuing=False)))
    return out


def build_93_records():
    base = {"law_number": D93_NUM, "law_year": D93_YEAR,
            "instrument": "مرسوم بقانون رقم 93 لسنة 2026",
            "instrument_rank": "مرسوم بقانون",
            "amends": "المادة (11) من القانون رقم (20) لسنة 2019 — legis-20-2019-m11",
            "document_kind": "explanatory_memorandum",
            "decree_text_missing": True,
            "decree_text_missing_note": (
                "المصدر المرفوع يحمل المذكرة الإيضاحية وحدها (ص12 من العدد 1809)؛ "
                "متن المرسوم (المادتان الأولى والثانية) على صفحة أخرى لم تُرفع. "
                "لم يُصطنع نص المادة (11) الجديدة ولم تُعدَّل legis-20-2019-m11 نصًّا — "
                "مطلوب تصوير صفحة المرسوم لاستكمال الإدخال."),
            "related_laws": ["legis-20-2019"]}
    return [_row("legis-93-2026-memo-1", "legislation_preamble", D93_BRANCH,
                 D93_TOPIC, "المذكرة الإيضاحية",
                 "المذكرة الإيضاحية — %s" % D93_LONGTITLE, D93_MEMO, base)]


# ═══════════════════ قاعدة التحديث على القانون 7/2010 ═══════════════════

OLD_DEF_MINISTER = "الوزير المختص : وزير التجارة والصناعة"
NEW_DEF_MINISTER = "الوزير المختص : الوزير الذي يحدده مجلس الوزراء"
OLD_DEF_COURT = "المحكمة المختصة : محكمة أسواق المال المنصوص عليها في هذا القانون."
NEW_DEF_COURT = ("المحكمة المختصة : الدائرة الاقتصادية المدنية والتجارية أو الإدارية "
                 "المنشأة بالمرسوم بقانون رقم (88) لسنة 2026، والمحكمة المختصة وفقا "
                 "للقواعد المقررة في قانون الإجراءات والمحاكمات الجزائية بحسب الأحوال.")

REPEALED_7_2010 = [108, 109, 110, 111, 112, 113, 116]


def update_7_2010_m1(cur):
    """استبدال التعريفين على معرّف م1 نفسه، والنص القديم إلى previous_versions[]."""
    cur.execute("SELECT original_text, metadata FROM knowledge_objects WHERE id=%s",
                ("legis-7-2010-m1",))
    row = cur.fetchone()
    if not row:
        raise SystemExit("M1_MISSING: legis-7-2010-m1 غير موجودة — أوقفت الدفعة.")
    old_text, meta = row[0], (row[1] or {})

    # مرساة صارمة: كل تعريف يجب أن يرد مرة واحدة بالضبط، وإلا نتوقف (لا رقعة عمياء)
    for needle in (OLD_DEF_MINISTER, OLD_DEF_COURT):
        n = old_text.count(needle)
        if n != 1:
            raise SystemExit("ANCHOR_FAIL: «%s» وردت %d مرة (المتوقع 1) — أوقفت الدفعة."
                             % (needle[:40], n))

    new_text = old_text.replace(OLD_DEF_MINISTER, NEW_DEF_MINISTER)
    new_text = new_text.replace(OLD_DEF_COURT, NEW_DEF_COURT)
    assert new_text != old_text

    prev = list(meta.get("previous_versions") or [])
    prev.append({
        "text": old_text,
        "sha256": hashlib.sha256(old_text.encode("utf-8")).hexdigest(),
        "superseded_on": GAZETTE_DATE,
        "superseded_by": "مرسوم بقانون رقم 91 لسنة 2026 — legis-91-2026-issue-1",
        "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "note": "النص السابق لاستبدال تعريفَي (الوزير المختص) و(المحكمة المختصة).",
    })
    meta["previous_versions"] = prev
    meta["amended_by"] = "legis-91-2026-issue-1"
    meta["amendment_date"] = GAZETTE_DATE
    meta["amendment_scope"] = "استبدال تعريفَي (الوزير المختص) و(المحكمة المختصة) دون سائر التعريفات"

    cur.execute("""UPDATE knowledge_objects
                   SET original_text=%s, normalized_text=%s, metadata=%s, updated_at=now()
                   WHERE id=%s""",
                (new_text, normalize_text(new_text), Jsonb(meta), "legis-7-2010-m1"))
    print("M1_UPDATED: legis-7-2010-m1 — التعريفان استُبدلا، والنص القديم محفوظ في previous_versions[%d]"
          % len(prev))
    return True


def mark_repealed_7_2010(cur):
    done = []
    for n in REPEALED_7_2010:
        rid = "legis-7-2010-m%d" % n
        cur.execute("SELECT metadata FROM knowledge_objects WHERE id=%s", (rid,))
        row = cur.fetchone()
        if not row:
            raise SystemExit("REPEAL_TARGET_MISSING: %s غير موجودة — أوقفت الدفعة." % rid)
        meta = row[0] or {}
        meta["repealed_by"] = "مرسوم بقانون رقم 91 لسنة 2026 — legis-91-2026-issue-3"
        meta["repeal_date"] = GAZETTE_DATE
        meta["repeal_instrument"] = "legis-91-2026-issue-3"
        meta["repeal_note"] = ("أُلغيت بالمادة الثالثة من المرسوم بقانون 91/2026 بعد نقل "
                               "المنازعات غير الجزائية إلى الدوائر الاقتصادية المنشأة "
                               "بالمرسوم بقانون 88/2026. النص باقٍ كاملًا — لا يُمحى نص قط.")
        cur.execute("""UPDATE knowledge_objects
                       SET verification_status='superseded', usable_as_citation=false,
                           metadata=%s, updated_at=now()
                       WHERE id=%s""", (Jsonb(meta), rid))
        done.append(rid)
    print("REPEAL_MARKED: %d مادة وُسمت superseded (النصوص باقية):" % len(done))
    print("   ", ", ".join(done))
    return done


def flag_20_2019_m11(cur):
    """توسيم فقط — لا تعديل نص: متن المرسوم 93/2026 غير متاح في المصدر المرفوع."""
    rid = "legis-20-2019-m11"
    cur.execute("SELECT metadata FROM knowledge_objects WHERE id=%s", (rid,))
    row = cur.fetchone()
    if not row:
        raise SystemExit("M11_MISSING: %s غير موجودة — أوقفت الدفعة." % rid)
    meta = row[0] or {}
    meta["amended_by"] = "مرسوم بقانون رقم 93 لسنة 2026 (المذكرة الإيضاحية: legis-93-2026-memo-1)"
    meta["amendment_date"] = GAZETTE_DATE
    meta["amendment_pending_official_text"] = True
    meta["amendment_note"] = (
        "استُبدل نص هذه المادة بالمادة الأولى من المرسوم بقانون 93/2026 (الكويت اليوم 1809، "
        "2026/9/20) بحيث تشمل العقوبة مخالفة أحكام المواد (2) و(3) و(5) والبندين (أ) و(ب) من "
        "المادة (8)، واستُبعدت الإحالة إلى المادتين (4) و(6). النص المعروض هنا هو النص "
        "السابق على التعديل — متن المرسوم لم يَرد في المصدر المرفوع فلم يُصطنع. "
        "عند الاستشهاد بهذه المادة يجب التنبيه إلى التعديل.")
    cur.execute("UPDATE knowledge_objects SET metadata=%s, updated_at=now() WHERE id=%s",
                (Jsonb(meta), rid))
    print("M11_FLAGGED: %s وُسمت معدَّلة بانتظار النص الرسمي (النص لم يُمس)." % rid)


# ═══════════════════════════ مسابر وتحقق ═══════════════════════════

def prefix_collision_probe(cur, prefixes):
    """قاعدة دائمة من حادثة legis-11-2026 (§9): مسبار SELECT قبل سكّ أي معرّف."""
    clean = True
    for p in prefixes:
        cur.execute("SELECT id FROM knowledge_objects WHERE id LIKE %s ORDER BY id", (p,))
        rows = [r[0] for r in cur.fetchall()]
        if rows:
            clean = False
            print("PREFIX_COLLISION: %s -> %d كائنًا موجودًا:" % (p, len(rows)))
            for r in rows[:20]:
                print("     -", r)
        else:
            print("PREFIX_CLEAN: %s" % p)
    return clean


def verify_regl_10_2020(cur):
    """القرار 590/2026 (اللائحة التنفيذية لقانون التوثيق) مُدخَل سلفًا — تحقق لا إدخال."""
    # ملاحظة: كل LIKE يُمرَّر وسيطًا دائمًا — psycopg بوسائط فارغة يفعّل محلل
    # العلامات فيتعثر على % الحرفية (درس موثق في §6، بند MCP رقم 3).
    cur.execute("""SELECT object_type, count(*) FROM knowledge_objects
                   WHERE id LIKE %s GROUP BY 1 ORDER BY 2 DESC""", ("regl-10-2020-%",))
    by_type = cur.fetchall()
    cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE %s",
                ("regl-10-2020-%",))
    total = cur.fetchone()[0]
    print("REGL_10_2020_PRESENT: %d كائنًا — %s" % (total, by_type))
    missing = []
    for n in range(1, 61):
        cur.execute("SELECT 1 FROM knowledge_objects WHERE id=%s", ("regl-10-2020-m%d" % n,))
        if not cur.fetchone():
            missing.append(n)
    for ax in (1, 2, 3):
        cur.execute("SELECT 1 FROM knowledge_objects WHERE id=%s", ("regl-10-2020-annex-%d" % ax,))
        if not cur.fetchone():
            missing.append("annex-%d" % ax)
    if missing:
        print("REGL_10_2020_GAPS:", missing)
    else:
        print("REGL_10_2020_COMPLETE: المواد 1-60 والجداول الثلاثة كلها حاضرة "
              "— لا إعادة إدخال للملف الثالث.")
    return missing


def report_term_blast_radius(cur):
    """قياس فقط، بلا تعديل: كم مادة في 7/2010 تحمل العبارتين المستبدَلتين؟
    الاستبدال الشامل «أينما وردتا» تغييرٌ كاسح في نص مُوثَّق — يُقاس هنا ويُقرَّر
    في جولة مستقلة بأمر المالك، ولا يُطبَّق آليًا في هذه الدفعة."""
    out = {}
    for label, phrase in (("وزير التجارة والصناعة", "وزير التجارة والصناعة"),
                          ("محكمة أسواق المال", "محكمة أسواق المال"),
                          ("محكمة سوق المال", "محكمة سوق المال")):
        cur.execute("""SELECT count(*) FROM knowledge_objects
                       WHERE id LIKE 'legis-7-2010-%%' AND original_text LIKE %s""",
                    ("%" + phrase + "%",))
        out[label] = cur.fetchone()[0]
    print("TERM_BLAST_RADIUS (قياس فقط — لم يُغيَّر أي نص):")
    for k, v in out.items():
        print("    «%s» ترد في %d كائنًا من legis-7-2010" % (k, v))
    print("    القرار في الاستبدال الشامل «أينما وردتا» مؤجَّل لجولة مستقلة بأمر المالك.")
    return out


INSERT_SQL = """
    INSERT INTO knowledge_objects
        (id, object_type, branch, topic, subtopic, micro_issue, title,
         original_text, normalized_text, source_key, verification_status,
         metadata, authority_status, usable_as_citation)
    VALUES (%(id)s, %(object_type)s, %(branch)s, %(topic)s, %(subtopic)s,
            %(micro_issue)s, %(title)s, %(original_text)s, %(normalized_text)s,
            %(source_key)s, %(verification_status)s, %(metadata)s,
            %(authority_status)s, %(usable_as_citation)s)
    ON CONFLICT (id) DO UPDATE SET
        object_type = EXCLUDED.object_type, branch = EXCLUDED.branch,
        topic = EXCLUDED.topic, subtopic = EXCLUDED.subtopic,
        micro_issue = EXCLUDED.micro_issue, title = EXCLUDED.title,
        original_text = EXCLUDED.original_text,
        normalized_text = EXCLUDED.normalized_text,
        verification_status = EXCLUDED.verification_status,
        metadata = EXCLUDED.metadata, authority_status = EXCLUDED.authority_status,
        usable_as_citation = EXCLUDED.usable_as_citation,
        updated_at = now()
"""


def main():
    dsn = os.environ["DATABASE_URL"]

    records = build_91_records() + build_93_records()
    ids = [r["id"] for r in records]
    assert len(ids) == len(set(ids)), "معرفات مكررة!"
    assert len(records) == 7, "العدد غير متوقع: %d (المتوقع 7)" % len(records)
    pubscrub_assert(records)

    # كل ما يلي داخل معاملة واحدة: أي بوابة تفشل ترجع بالقاعدة كما كانت (لا كتابة جزئية).
    try:
      with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            print("\n──── مسابر ما قبل الإدخال ────")
            prefix_collision_probe(cur, ["legis-91-2026-%", "legis-93-2026-%"])
            print()
            verify_regl_10_2020(cur)
            print()
            report_term_blast_radius(cur)

            print("\n──── الإدخال ────")
            for r in records:
                row = dict(r)
                row["metadata"] = Jsonb(row["metadata"])
                cur.execute(INSERT_SQL, row)
            print("INSERT_OK: %d كائنًا (91/2026 = 6، 93/2026 = 1)" % len(records))

            print("\n──── قاعدة التحديث على legis-7-2010 ────")
            update_7_2010_m1(cur)
            mark_repealed_7_2010(cur)

            print("\n──── توسيم legis-20-2019-m11 ────")
            flag_20_2019_m11(cur)
        conn.commit()
    except SystemExit:
        print("\nROLLED_BACK: بوابة فشلت — لم تُكتب أي تغييرات على القاعدة.")
        raise

    print("\n──── تحقق بعد الإدخال ────")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for p, expect in (("legis-91-2026-%", 6), ("legis-93-2026-%", 1)):
            cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE %s", (p,))
            got = cur.fetchone()[0]
            print("  %s = %d (المتوقع %d)" % (p, got, expect))
            assert got == expect, "عدد غير متوقع لـ%s" % p

        cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-7-2010-m1'")
        t = cur.fetchone()[0]
        assert NEW_DEF_MINISTER in t and NEW_DEF_COURT in t, "م1: التعريفان الجديدان غائبان"
        assert OLD_DEF_MINISTER not in t and OLD_DEF_COURT not in t, "م1: تعريف قديم باقٍ"
        cur.execute("""SELECT jsonb_array_length(metadata->'previous_versions')
                       FROM knowledge_objects WHERE id='legis-7-2010-m1'""")
        print("  legis-7-2010-m1: التعريفان محدَّثان، previous_versions = %d" % cur.fetchone()[0])

        cur.execute("""SELECT count(*) FROM knowledge_objects
                       WHERE id LIKE %s
                         AND verification_status='superseded'
                         AND metadata->>'repeal_instrument'=%s""",
                    ("legis-7-2010-m%", "legis-91-2026-issue-3"))
        n_rep = cur.fetchone()[0]
        print("  مواد 7/2010 الموسومة بالإلغاء = %d (المتوقع 7)" % n_rep)
        assert n_rep == 7

        cur.execute("""SELECT original_text FROM knowledge_objects WHERE id='legis-20-2019-m11'""")
        m11 = cur.fetchone()[0]
        assert "(3)،(4)،(6)" in m11.replace(" ", "") or "(3)" in m11, "م11: النص تغيّر وما كان ينبغي!"
        cur.execute("""SELECT metadata->>'amendment_pending_official_text'
                       FROM knowledge_objects WHERE id='legis-20-2019-m11'""")
        print("  legis-20-2019-m11: النص لم يُمس، amendment_pending_official_text = %s"
              % cur.fetchone()[0])

        cur.execute("SELECT count(*) FROM knowledge_objects")
        print("  إجمالي كائنات القاعدة =", cur.fetchone()[0])

    print("\nINGEST_1809_OK")


if __name__ == "__main__":
    main()
