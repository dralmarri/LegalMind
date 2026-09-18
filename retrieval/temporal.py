# -*- coding: utf-8 -*-
"""طبقة السلطة الزمنية — تمنع نصًّا قديمًا من أن يُقدَّم قاعدةً نافذة بلا تحذير.

الحالة الحيّة التي تفرضها (موثقة في CLAUDE.md §26): مبدأ الطعن 240/2002 يقتبس
«خمسة أيام» من م167 مرافعات والنص النافذ اليوم «عشرة أيام». لا شيء في الخط
القائم يمنع تقديم الاقتباس القديم قاعدةً حالية؛ الالتقاط وقع صدفةً بذكاء
النموذج في جولة واحدة، ولم يقع في غيرها.

السلّم الخماسي (امتداد لسلّم P2.7-K الثلاثي بحالتين صريحتين للمصدر نفسه):

  CURRENT              لا إشارة تعارض ولا إلغاء.
  SUPERSEDED           الكائن نفسه موسوم ملغى/مستبدَل في القاعدة
                       (verification_status='superseded' أو metadata.repealed_by).
  TRANSITION_VERIFIED  القاعدة **تحمل سند الانتقال نفسه** (صك الإلغاء أو
                       previous_versions بسنده) — فيُذكر الانتقال بدليله.
                       **حالة أدلة لا قدرة**: لا تُبلَغ إلا حين تحمل القاعدة
                       provenance الانتقال، ولا يُعاقَب النظام على غيابها.
  HISTORICAL           سلطة قضائية سابقة لتعديل موثَّق للمادة التي تفسّرها.
  CONFLICT_DETECTED    فرق زمني مرصود بين ما يقتبسه المبدأ ونص المادة النافذ،
                       وصك الانتقال غير متاح. **لا يُقدَّم التفصيل القديم
                       بوصفه النافذ، ولا يُدَّعى تاريخ انتقال لا تثبته القاعدة.**
"""
import re
from .model import LAYER_PRINCIPLE

CURRENT = "CURRENT"
SUPERSEDED = "SUPERSEDED"
TRANSITION_VERIFIED = "TRANSITION_VERIFIED"
HISTORICAL = "HISTORICAL"
CONFLICT_DETECTED = "CONFLICT_DETECTED"

# أقصى عدد اختلافات يُقبل قبل اعتبار المصدر ضجيج استخراج لا تعارضًا حقيقيًا
MAX_CLASHES = 2

_AR_NUM = {
    "واحد": 1, "يوم": 1, "يومان": 2, "يومين": 2, "اثنين": 2, "اثنان": 2,
    "ثلاثة": 3, "ثلاث": 3, "اربعة": 4, "أربعة": 4, "اربع": 4, "أربع": 4,
    "خمسة": 5, "خمس": 5, "ستة": 6, "ست": 6, "سبعة": 7, "سبع": 7,
    "ثمانية": 8, "ثمان": 8, "تسعة": 9, "تسع": 9, "عشرة": 10, "عشر": 10,
    "خمسة عشر": 15, "عشرون": 20, "عشرين": 20, "ثلاثون": 30, "ثلاثين": 30,
    "ستون": 60, "ستين": 60, "تسعون": 90, "تسعين": 90,
}
_UNITS = ("يوما", "يوم", "أيام", "ايام", "شهرا", "شهر", "أشهر", "اشهر",
          "سنة", "سنوات", "سنه")
_UNIT_CANON = {"يوما": "يوم", "يوم": "يوم", "أيام": "يوم", "ايام": "يوم",
               "شهرا": "شهر", "شهر": "شهر", "أشهر": "شهر", "اشهر": "شهر",
               "سنة": "سنة", "سنه": "سنة", "سنوات": "سنة"}
_UNIT_RX = "|".join(sorted(_UNITS, key=len, reverse=True))
# فاصل مسموح بين الرقم والوحدة: صياغة الجريدة الرسمية تكتب «عشرة (10) أيام»
# فيفصل بين لفظ العدد ووحدته رقمٌ بين قوسين — بلا هذا الفاصل تسقط نصف المُدد.
_SEP = r"\s*(?:\(\s*\d{1,4}\s*\)\s*)?\s*"
_DIGIT_RX = re.compile(r"(\d{1,4})" + _SEP + r"(" + _UNIT_RX + r")")
_WORD_RX = re.compile(r"(" + "|".join(sorted(_AR_NUM, key=len, reverse=True)) +
                      r")" + _SEP + r"\s*(" + _UNIT_RX + r")")


def periods(text):
    """يستخرج كل المُدد (رقم + وحدة) من نصٍّ عربي، رقمية وكتابية معًا."""
    t = (text or "").replace("٫", ".")
    out = set()
    for m in _DIGIT_RX.finditer(t):
        out.add((int(m.group(1)), _UNIT_CANON.get(m.group(2), m.group(2))))
    for m in _WORD_RX.finditer(t):
        n = _AR_NUM.get(m.group(1))
        if n:
            out.add((n, _UNIT_CANON.get(m.group(2), m.group(2))))
    return out


def classify_object(row):
    """حالة المصدر نفسه من بيانات القاعدة وحدها (لا اجتهاد نصي)."""
    md = (row or {}).get("metadata") or {}
    if isinstance(md, str):
        try:
            import json as _j
            md = _j.loads(md)
        except Exception:
            md = {}
    vs = (row or {}).get("verification_status") or ""
    repealed = md.get("repealed_by") or md.get("repeal_instrument")
    if vs == "superseded" or repealed:
        # الانتقال موثَّق بصكّه؟ فهذه سلطة انتقال مُتحقَّقة لا مجرد ملغاة
        if md.get("repeal_instrument") or md.get("repeal_date"):
            return TRANSITION_VERIFIED, {
                "repealed_by": md.get("repealed_by"),
                "instrument": md.get("repeal_instrument"),
                "date": md.get("repeal_date")}
        return SUPERSEDED, {"repealed_by": md.get("repealed_by")}
    pv = md.get("previous_versions")
    if pv:
        return TRANSITION_VERIFIED, {"previous_versions": len(pv)
                                     if isinstance(pv, list) else 1}
    return CURRENT, {}


def detect_conflict(principle_text, article_text, article_row=None):
    """يرصد تعارضًا زمنيًا بين مُدَّة يقتبسها مبدأ ومُدَّة المادة النافذة.

    الشرط المتعمَّد التحفّظ: لا يُعلَن تعارض إلا حين **تتفق الوحدة وتختلف
    القيمة** (يوم مقابل يوم برقمين مختلفين). اختلاف الوحدة وحده ليس تعارضًا —
    قد يكون المبدأ يناقش مدةً أخرى في المادة نفسها. وغياب مدة في أحد الطرفين
    لا يولّد تنبيهًا: **الفجوة ليست تعارضًا**، وتنبيهٌ كاذب يدفع لحذف استشهاد
    صحيح (درس §6: لا تُبنى طبقة تولّد تنبيهات كاذبة)."""
    pp, ap = periods(principle_text), periods(article_text)
    if not pp or not ap:
        return None
    au = {u: {n for n, uu in ap if uu == u} for _n, u in ap}
    clash = []
    for n, u in sorted(pp):
        vals = au.get(u)
        if vals and n not in vals:
            clash.append({"unit": u, "principle_value": n,
                          "article_values": sorted(vals)})
    if not clash:
        return None
    # التعارض الزمني الحقيقي **مفرد**: مدةٌ عُدِّلت. أما عشرات الاختلافات في
    # مصدر واحد فدليل ضجيج استخراج (نص سردي بأرقام قضايا وتواريخ) لا تعارض.
    if len(clash) > MAX_CLASHES:
        return None
    status, prov = classify_object(article_row or {})
    return {"status": (TRANSITION_VERIFIED if status == TRANSITION_VERIFIED
                       else CONFLICT_DETECTED),
            "clashes": clash, "article_provenance": prov}


def annotate(candidates, row_of, text_of, xref_of=None):
    """يضع `temporal_status` على كل مرشح، ويعيد تقرير الحالات.

    `xref_of(candidate) -> [article_id...]` المواد التي يفسّرها هذا المبدأ
    صراحةً (قناة principle_xref المقيسة) — بها وحدها يُقارَن المبدأ بالمادة
    الصحيحة بدل مقارنة عمياء."""
    report = {}
    for c in candidates:
        st, _prov = classify_object(row_of(c.object_id) or {})
        conflict = None
        # المبادئ وحدها: صياغتها قاعدية مركّزة فمُددها معتبرة. والأحكام الكاملة
        # نصوص وقائعية طويلة، استخراج المدد منها يولّد تنبيهات كاذبة (قيس حيًّا).
        if st == CURRENT and xref_of and c.layer == LAYER_PRINCIPLE:
            ptext = text_of(c.object_id) or ""
            for aid in (xref_of(c) or [])[:4]:
                conflict = detect_conflict(ptext, text_of(aid) or "",
                                           row_of(aid))
                if conflict:
                    conflict["article_id"] = aid
                    break
        c.temporal_status = conflict["status"] if conflict else st
        if conflict:
            c.temporal_conflict = conflict
        report[c.temporal_status] = report.get(c.temporal_status, 0) + 1
    return report
