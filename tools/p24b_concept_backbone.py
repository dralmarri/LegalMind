#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.4B — Deterministic Legal Concept & Dependency Backbone v2 (MVP).

الفرضية المعمارية محل الاختبار: FACTS/REQUEST → LEGAL CONCEPTS → LEGAL DEPENDENCIES →
SEARCH SCOPE → AUTHORITY RESOLUTION، بطبقة **حتمية بالكامل** (بلا Haiku في مسار القرار)،
وHaiku يبقى قناة توسعة إضافية فقط في الاسترجاع الفعلي، لا شرطًا لتفعيل أي تبعية حتمية.

**قيود ملزمة (بأمر المالك، P2.4B):**
- صفر بناء من الإخفاقات: لا `case_id`، لا معرفات `must_find`، لا `required_dimensions` وقت
  التشغيل، لا معرفات سلطات الإخفاقات المعروفة، لا نص Gold Set حرفيًا، ولا تسمية أي قاعدة باسم
  مادة/حالة بعينها (`m337`، `gs-0011`، إلخ). Gold Set **للتقييم فقط** — لم يُطَّلع عليه أثناء
  تصميم المفاهيم/القواعد أدناه (صُمِّمت من معرفة عامة بالإجراءات الكويتية + تحقق مباشر عبر
  Legal Mind MCP بعبارات من صياغتي الخاصة، لا من نص أي حالة Gold Set).
- الحتمية: نفس الوقائع ← نفس المفاهيم/التبعيات/النطاق في 5/5 — محقَّقة **بالبناء نفسه** هنا
  (منطق بايثون صرف: تطبيع + تجذيع + regex، صفر نداء نموذج لغوي في مسار القرار).
- فصل الاعتراف عن حسم السلطة: كل تبعية تُنتج **نطاق بحث** (عبارات لغة طبيعية) لا معرِّف مادة
  مباشرًا — حسم السلطة الفعلي يتم لاحقًا عبر قناة البحث الحقيقية (تضمين + Qdrant)، لا جدول
  «كلمة مفتاحية ← معرِّف مادة».
- بروتوكول قبول القواعد: كل تبعية تُختبر على مجموعة تطوير (Development Set) مستقلة تمامًا عن
  Gold Set — تحوي نظائر إيجابية بصياغات مختلفة، نقائض حادة (hard negatives) بنفس المفردات
  الشكلية، مسائل مجاورة (neighboring issues)، وحالات ملتبسة — بحساب TP/FP/TN/FN وprecision/
  recall/false_activation_rate. أي تبعية بمعدل تفعيل كاذب خطير تُرفض ولو ارتفع استدعاؤها.
"""
import hashlib
import json
import re

# ============================================================
# 1) فئات المفاهيم العامة (verbatim من مواصفة المالك — عشر فئات قابلة لإعادة الاستعمال)
# ============================================================
CONCEPT_CATEGORIES = [
    "LEGAL_ENTITY", "LEGAL_RELATIONSHIP", "PROCEDURAL_POSTURE", "CLAIM_OR_REMEDY",
    "DOCUMENT_OR_INSTRUMENT", "TEMPORAL_EVENT", "JURISDICTIONAL_FACT", "PARTY_STATUS",
    "MANDATORY_PRECONDITION", "EXCEPTION_TRIGGER",
]

# ============================================================
# 2) تطبيع وتجذيع حتميان بالكامل (بلا أي نداء نموذج لغوي)
# ============================================================
_TASHKEEL_RE = re.compile(r"[ً-ٰٟ]")
_SUFFIXES = ("ات", "ون", "ين", "ان", "يه", "ي")


def normalize_ar(text):
    if not text:
        return ""
    t = _TASHKEEL_RE.sub("", text)
    t = (t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
         .replace("ة", "ه").replace("ى", "ي"))
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _strip_al(word):
    """نزع أداة التعريف المدمجة (ال/بال/فال/كال/لل) بشرط بقاء 3 أحرف على الأقل — نفس نمط
    `_chap_tok` الموثَّق في المشروع."""
    for pref in ("بال", "فال", "كال", "لل", "وال", "ال"):
        if word.startswith(pref) and len(word) - len(pref) >= 3:
            return word[len(pref):]
    return word


def _stem(word):
    """تجذيع أخف — نفس نمط `_chap_stem` الموثَّق في المشروع (لواحق شائعة بشرط بقاء 3 أحرف)."""
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)]
    return word


def raw_tokens(text):
    """رموز مطبَّعة بلا تجذيع (بعد نزع أداة التعريف فقط) — للمطابقات الدقيقة التي يُخشى عليها
    من تصادم التجذيع (مثال حي وُجد فعليًا: «نسبية» تتجذّع خطأً إلى «نسب»، انظر دفتر التطوير)."""
    return {_strip_al(w) for w in normalize_ar(text).split() if len(w) >= 2}


def tokenize(text):
    return {_stem(_strip_al(w)) for w in normalize_ar(text).split() if len(w) >= 2}


def canon(word):
    """يُطبِّق **نفس** خط الأنابيب المستعمَل على النص المُدخَل وقت التشغيل (normalize_ar ثم
    strip_al) على كل كلمة كانونية في جداول المطابقة أدناه — درس مركزي وُجد أثناء بناء دفتر
    التطوير: بناء الجداول بـ`_stem(w)` مباشرة على النص المصدري (بلا normalize_ar/strip_al أولًا)
    يُنتج قيمًا لا تطابق أبدًا رموز وقت التشغيل (مثال: «الدائرة» في الجدول تبقى بالتاء المربوطة
    وأداة التعريف، بينما رمز الإدخال الفعلي «دائره» بعد التطبيع ونزع «ال»؛ تطابق صفري صامت).
    **بلا تجذيع لواحق هنا** — المطابقة أدناه بادئات (`startswith`) لا تساوٍ حرفي، فتُمتص لواحق
    الجمع/التأنيث/الضمائر المتصلة (ها/ه/هم...) طبيعيًا دون تعداد كل صيغها يدويًا."""
    return _strip_al(normalize_ar(word))


def _any_prefix(rtoks, canon_words):
    """أي رمز في rtoks يبدأ بأي كلمة كانونية — تجذيع بالبادئة بدل التساوي الحرفي، أمتن أمام
    ضمائر الاتصال ولواحق الجمع/التأنيث الشائعة (شيكًا/ينكرها/مطالبتها...). كلمة كانونية بحرفين
    فأقل (مثال: «رد») تُطابَق حرفيًا لا بادئةً — بادئة قصيرة كهذه تصطدم بكلمات لا صلة لها
    («ردود») فتُنتج إيجابًا كاذبًا، مؤكَّد أثناء بناء دفتر التطوير."""
    for t in rtoks:
        for w in canon_words:
            if (t == w) if len(w) <= 2 else t.startswith(w):
                return True
    return False


# ============================================================
# 3) نموذج المفهوم والتبعية
# ============================================================
class Concept:
    def __init__(self, concept_id, category, description, trigger_fn):
        self.concept_id = concept_id
        self.category = category
        self.description = description
        self.trigger_fn = trigger_fn

    def triggered(self, rtoks):
        return self.trigger_fn(rtoks)


class Dependency:
    def __init__(self, dependency_id, triggered_by_concepts, legal_role, mandatory_or_optional,
                 verification_status, source_basis, scope_target, authority_resolution_method):
        self.dependency_id = dependency_id
        self.triggered_by_concepts = triggered_by_concepts  # list[str] — منطق AND بين المفاهيم
        self.legal_role = legal_role
        self.mandatory_or_optional = mandatory_or_optional
        self.verification_status = verification_status
        self.source_basis = source_basis
        self.scope_target = scope_target  # عبارات نطاق بحث بلغة طبيعية — لا معرفات مواد
        self.authority_resolution_method = authority_resolution_method

    def to_dict(self):
        return {k: v for k, v in vars(self).items()}


# ============================================================
# 4) المفاهيم الأربعة — MVP صغير عمدًا، متنوع الفئات، من معرفة عامة لا من إخفاقات Gold Set
# ============================================================
_JUDGE_WORDS = {canon(w) for w in ["قاضي", "قضاة", "دائرة", "قاضيا"]}
_DISQUAL_WORDS = {canon(w) for w in [
    "رد", "تنحي", "تنح", "صلاحية", "قرابة", "مصاهرة", "نسيب", "صهر", "مصلحة", "زوج", "قريب", "أقارب"]}


def _trigger_judicial_disqualification(rtoks):
    return _any_prefix(rtoks, _JUDGE_WORDS) and _any_prefix(rtoks, _DISQUAL_WORDS)


_CHEQUE_WORDS = {canon(w) for w in ["شيك", "شيكات"]}
_CHEQUE_CLAIM_WORDS = {canon(w) for w in [
    "مطالبة", "تحصيل", "صرف", "ارتد", "رجع", "رصيد", "وفاء", "قيمة", "تقادم"]}


def _trigger_cheque_payment_claim(rtoks):
    return _any_prefix(rtoks, _CHEQUE_WORDS) and _any_prefix(rtoks, _CHEQUE_CLAIM_WORDS)


# «نسب» يُطابَق بتعبير دقيق (تساوٍ حرفي أو لاحق ملكية محدود) لا بادئة عامة — البادئة العامة
# تصطدم بـ«نسبية/نسبي» (تبدأ بـ«نسب» فتُطابِق البادئة خطأً) فتولِّد إيجابًا كاذبًا خطيرًا —
# وُجد فعليًا أثناء بناء دفتر التطوير (انظر §الدروس أسفله).
_LINEAGE_RE = re.compile(r"^نسب(ه|ها|هم|هما)?$")
_LINEAGE_ACTION_WORDS = {canon(w) for w in ["اثبات", "نفي", "دعوى", "ابن", "بنوة", "والد"]}


def _trigger_lineage_establishment(rtoks):
    return any(_LINEAGE_RE.match(t) for t in rtoks) and _any_prefix(rtoks, _LINEAGE_ACTION_WORDS)


_MARRIAGE_WORDS = {canon(w) for w in ["زوجية", "زواج"]}
# جذر «الإنكار» ثلاثي (ن-ك-ر) ويتصدَّر الفعل حروف مضارعة (ي/أ/ت/ن) لا تسبقه بادئة التعريف —
# فمطابقة البادئة (startswith) تفشل مع الأفعال («ينكر»/«أنكر» لا تبدآن بـ«نكر») بخلاف الاسم
# («إنكار»)؛ الاحتواء (substring) على الجذر الثلاثي يمتص صيغتي الاسم والفعل معًا. مخاطرة
# التصادم منخفضة في نص قانوني (المتصادمات المحتملة: «منكر/تنكر»، وكلاهما من نفس الجذر فعليًا).
_DENIAL_ROOTS = ("نكر", "جحد")


def _trigger_marital_status_denial(rtoks):
    return _any_prefix(rtoks, _MARRIAGE_WORDS) and any(
        any(root in t for root in _DENIAL_ROOTS) for t in rtoks)


CONCEPTS = [
    Concept("JUDICIAL_DISQUALIFICATION", "PROCEDURAL_POSTURE",
            "قاضٍ + سبب رد/عدم صلاحية (قرابة/مصاهرة/مصلحة) مذكوران معًا",
            _trigger_judicial_disqualification),
    Concept("CHEQUE_PAYMENT_CLAIM", "CLAIM_OR_REMEDY",
            "شيك + فعل مطالبة/تحصيل/تقادم مذكوران معًا",
            _trigger_cheque_payment_claim),
    Concept("LINEAGE_ESTABLISHMENT", "CLAIM_OR_REMEDY",
            "نسب (حرفيًا) + فعل إثبات/نفي/دعوى مذكوران معًا",
            _trigger_lineage_establishment),
    Concept("MARITAL_STATUS_DENIAL", "MANDATORY_PRECONDITION",
            "زواج/زوجية + إنكار مذكوران معًا",
            _trigger_marital_status_denial),
]
CONCEPTS_BY_ID = {c.concept_id: c for c in CONCEPTS}

DEPENDENCIES = [
    Dependency(
        "JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK", ["JUDICIAL_DISQUALIFICATION"],
        legal_role="procedural validity / nullity risk",
        mandatory_or_optional="mandatory",
        verification_status="spot_verified_via_mcp_search (2026-09-17, صياغة مستقلة عن أي نص Gold Set)",
        source_basis="قواعد عدم صلاحية القاضي ورده وإجراءات طلب الرد — قانون المرافعات",
        scope_target=["أسباب رد القاضي وعدم صلاحيته لنظر الدعوى",
                       "إجراءات طلب رد القاضي والفصل فيه",
                       "أثر بطلان الحكم الصادر من قاضٍ غير صالح لنظر الدعوى"],
        authority_resolution_method="deterministic scope phrases fed as extra anchors into the "
                                     "real semantic+lexical search channels — no hardcoded article id",
    ),
    Dependency(
        "CHEQUE_SUBSTANTIVE_RULES_CHECK", ["CHEQUE_PAYMENT_CLAIM"],
        legal_role="substantive claim basis", mandatory_or_optional="mandatory",
        verification_status="spot_verified_via_mcp_search (2026-09-17)",
        source_basis="الأحكام الموضوعية لالتزام الساحب بالوفاء بقيمة الشيك — قانون التجارة",
        scope_target=["التزام الساحب بالوفاء بقيمة الشيك", "امتناع المسحوب عليه عن الصرف"],
        authority_resolution_method="deterministic scope phrases -> real search channels",
    ),
    Dependency(
        "CHEQUE_LIMITATION_CHECK", ["CHEQUE_PAYMENT_CLAIM"],
        legal_role="defence / time-bar risk", mandatory_or_optional="mandatory",
        verification_status="spot_verified_via_mcp_search (2026-09-17)",
        source_basis="تقادم دعوى المطالبة بقيمة الشيك ودعوى الإثراء بلا سبب البديلة",
        scope_target=["تقادم دعوى المطالبة بقيمة الشيك", "دعوى الإثراء بلا سبب بعد سقوط الشيك بالتقادم"],
        authority_resolution_method="deterministic scope phrases -> real search channels",
    ),
    Dependency(
        "LINEAGE_COMMITTEE_MANDATORY_REVIEW", ["LINEAGE_ESTABLISHMENT"],
        legal_role="mandatory prior administrative procedure", mandatory_or_optional="mandatory",
        verification_status="spot_verified_via_mcp_search (2026-09-17)",
        source_basis="وجوب عرض طلب إثبات/نفي النسب على لجنة النسب قبل رفع الدعوى القضائية",
        scope_target=["اختصاص لجنة النسب بالنظر قبل رفع دعوى النسب",
                      "إجراءات تقديم طلب إثبات النسب أو نفيه إلى اللجنة"],
        authority_resolution_method="deterministic scope phrases -> real search channels",
    ),
    Dependency(
        "MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK", ["MARITAL_STATUS_DENIAL"],
        legal_role="mandatory admissibility precondition", mandatory_or_optional="mandatory",
        verification_status="spot_verified_via_mcp_search (2026-09-17)",
        source_basis="عدم سماع دعوى الزوجية عند الإنكار إلا بوثيقة رسمية أو إقرار سابق، والاستثناءات عليها",
        scope_target=["عدم سماع دعوى الزوجية عند الإنكار",
                      "الاستثناءات على عدم سماع دعوى الزوجية"],
        authority_resolution_method="deterministic scope phrases -> real search channels",
    ),
]
DEPENDENCIES_BY_ID = {d.dependency_id: d for d in DEPENDENCIES}


def recognize(facts_text):
    """FACT -> CONCEPT -> DEPENDENCY -> SCOPE، حتمي بالكامل. يُعاد أيضًا concepts_triggered
    للتوثيق (provenance) — الاعتماد يبقى مربوطًا بمعرِّف التبعية لا بكلمة مفتاحية خام."""
    rtoks = raw_tokens(facts_text)
    triggered_concepts = [c.concept_id for c in CONCEPTS if c.triggered(rtoks)]
    triggered_deps = []
    for d in DEPENDENCIES:
        if all(cid in triggered_concepts for cid in d.triggered_by_concepts):
            triggered_deps.append(d.dependency_id)
    scope = []
    for did in triggered_deps:
        scope.extend(DEPENDENCIES_BY_ID[did].scope_target)
    return {
        "concepts_triggered": triggered_concepts,
        "dependencies_triggered": triggered_deps,
        "scope_queries": scope,
    }


def freeze_hash():
    """بصمة حتمية لكل مفهوم/تبعية معتمدة — تُحسَب من الحقول الجوهرية فقط (لا من دوال بايثون
    نفسها، فوقيعها لا يتغير بلا تدخل بشري) لتوثيق نسخة Arm B المجمَّدة بدقة."""
    payload = {
        "concepts": [{"id": c.concept_id, "category": c.category} for c in CONCEPTS],
        "dependencies": [d.to_dict() for d in DEPENDENCIES if True],
    }
    # استبعاد trigger_fn (غير قابلة للتسلسل) من التجزئة عبر تمثيل التبعيات فقط (لا تحمل دوالًا)
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    print("CONCEPTS:", [c.concept_id for c in CONCEPTS])
    print("DEPENDENCIES:", [d.dependency_id for d in DEPENDENCIES])
    print("FREEZE_HASH:", freeze_hash())
