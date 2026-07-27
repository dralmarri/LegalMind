# -*- coding: utf-8 -*-
"""استخراج الإحالات الصريحة بين القوانين من نصّ المواد.
يلتقط أنماط «المادة (N) من قانون كذا / من القانون رقم X لسنة Y» ويحلّها إلى بادئة المعرّف.
يتجاهل الإحالات الداخلية («هذا القانون») والإحالات المجرّدة (بلا تحديد قانون آخر)."""
import re

# تطبيع خفيف للمطابقة الاسمية
def _norm(t):
    t = re.sub(r"[أإآ]", "ا", t)
    t = re.sub(r"[ىی]", "ي", t)
    t = t.replace("ة", "ه").replace("ـ", "")
    t = re.sub(r"[ً-ْٰ]", "", t)
    return t

# أرقام هندية/فارسية → لاتينية
_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# ترتيبيات → أرقام
_ORD = {
    "الاولى": 1, "الاول": 1, "الثانيه": 2, "الثاني": 2, "الثالثه": 3, "الثالث": 3,
    "الرابعه": 4, "الرابع": 4, "الخامسه": 5, "الخامس": 5, "السادسه": 6, "السادس": 6,
    "السابعه": 7, "السابع": 7, "الثامنه": 8, "الثامن": 8, "التاسعه": 9, "التاسع": 9,
    "العاشره": 10, "العاشر": 10,
}

# أسماء القوانين المعروفة → بادئة المعرّف (تُطبَّق على النصّ المطبّع)
# ملاحظة: تُبقى فقط الأهداف الموجودة فعلًا في القاعدة (تُصفّى لاحقًا server-side).
_LAW_NAMES = [
    # (نمط مطبّع, بادئة)
    (r"قانون المرافعات(?: المدنيه والتجاريه)?", "legis-38-1980"),
    (r"المرافعات المدنيه والتجاريه", "legis-38-1980"),
    (r"قانون الاثبات(?: في المواد المدنيه والتجاريه)?", "legis-39-1980"),
    (r"القانون المدني", "legis-67-1980"),
    (r"قانون التجاره", "legis-68-1980"),
    (r"قانون الشركات", "legis-1-2016"),
    (r"قانون الجزاء", "legis-16-1960"),
    (r"قانون الاجراءات والمحاكمات الجزائيه", "legis-17-1960"),
    (r"قانون الخدمه المدنيه", "legis-15-1979"),
    (r"قانون التامينات الاجتماعيه", "legis-61-1976"),
    (r"قانون العمل في القطاع الاهلي", "legis-6-2010"),
    (r"قانون تنظيم الخبره", "legis-40-1980"),
    (r"قانون تنظيم القضاء", "legis-23-1990"),
    (r"قانون المحاماه", "legis-42-1964"),
    (r"قانون التوثيق", "legis-10-2020"),
    (r"قانون دعم(?: و?تشجيع)? العماله الوطنيه", "legis-19-2000"),
    (r"قانون حقوق الاشخاص ذوي الاعاقه", "legis-8-2010"),
]
_LAW_NAMES = [(re.compile(p), pre) for p, pre in _LAW_NAMES]

# «هذا القانون / ذات القانون / القانون المرافق / القانون المشار اليه» = إحالة داخلية
_SELF = re.compile(r"^(هذا|ذات|هذه|القانون المرافق|القانون المشار)")

# محدّد القانون بالرقم/السنة داخل مقطع «من ...»
_NUMYEAR = re.compile(r"رقم\s*\(?\s*(\d+)\s*\)?\s*لسنه\s*(\d+)")

_ARTNUM = r"\(?\s*(\d+)\s*\)?\s*(مكررا?)?"
_ORDWORD = "|".join(_ORD)

# أنماط الالتقاط: مفردة/ترتيبية/مثنّاة/متعدّدة، متبوعة بـ«من <محدّد القانون>»
_PATTS = [
    re.compile(r"الماده\s*" + _ARTNUM + r"\s*من\s+([^\.،؛\n]{3,80})"),
    re.compile(r"الماده\s+(" + _ORDWORD + r")\s+من\s+([^\.،؛\n]{3,80})"),
    re.compile(r"المادتين\s*\(?\s*(\d+)\s*،?\s*و?\s*(\d+)\s*\)?\s*من\s+([^\.،؛\n]{3,80})"),
    re.compile(r"المواد\s*\(?\s*([\d\s،و]+?)\)?\s*من\s+([^\.،؛\n]{3,80})"),
]


def _resolve_prefix(ident_norm):
    """يحوّل مقطع «القانون ...» إلى بادئة، أو None إن كان داخليًّا/غير محلول."""
    ident_norm = ident_norm.strip()
    if _SELF.match(ident_norm):
        return None
    m = _NUMYEAR.search(ident_norm)
    if m:
        return f"legis-{int(m.group(1))}-{int(m.group(2))}"
    for rx, pre in _LAW_NAMES:
        if rx.search(ident_norm):
            return pre
    return None


def extract_refs(text):
    """يعيد قائمة (target_prefix, article_number:str) لكل إحالة خارجية."""
    t = _norm(text.translate(_DIG))
    out = []

    def add(pre, num, mkr=None):
        if pre and num:
            key = str(int(num)) + ("mkr" if mkr else "")
            out.append((pre, key))

    for m in _PATTS[0].finditer(t):        # مفردة رقمية
        pre = _resolve_prefix(m.group(3) if m.lastindex >= 3 else "")
        # المجموعة الثالثة هي مقطع القانون
        ident = m.group(m.lastindex)
        pre = _resolve_prefix(ident)
        add(pre, m.group(1), m.group(2))
    for m in _PATTS[1].finditer(t):        # ترتيبية
        pre = _resolve_prefix(m.group(2))
        n = _ORD.get(m.group(1))
        if n:
            add(pre, str(n))
    for m in _PATTS[2].finditer(t):        # مثنّاة
        pre = _resolve_prefix(m.group(3))
        add(pre, m.group(1)); add(pre, m.group(2))
    for m in _PATTS[3].finditer(t):        # متعدّدة
        ident = m.group(2)
        pre = _resolve_prefix(ident)
        for nn in re.findall(r"\d+", m.group(1)):
            add(pre, nn)

    # إزالة التكرار مع الحفاظ على الترتيب
    seen = set(); uniq = []
    for x in out:
        if x not in seen:
            seen.add(x); uniq.append(x)
    return uniq
