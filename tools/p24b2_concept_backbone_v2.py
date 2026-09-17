#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.5 — Experiment B2-R: Concept & Dependency Model v2 (Recognition/Dependency ONLY).

معزول تمامًا عن أي استرجاع — صفر استيراد لـ`admin.app`، صفر `_draft_chap_ids`، صفر Qdrant/
مرتِّب/ميزانية. هذا اختبار سببي مستقل لطبقة الاعتراف/التبعية وحدها (B2-R)، منفصل تمامًا عن
B2-I (التكامل)، كما نصَّت المواصفة صراحةً: "لا نغيّر Concept Recognition وIntegration في
تجربة واحدة".

**معالجة فئات القصور المكتشفة فعليًا في Holdout v1** (بالنوع لا بالجملة — صفر نص من Holdout
v1 استُعمل هنا، وصفر قاعدة سُمِّيت أو بُنيت من معرِّف حالة/سلطة):
1. NORMALIZATION_COLLISION: كل تحويل تطبيعي مُدرَج صراحةً بحقل lossy/lossless — لا افتراض أمان.
2. NEGATION_BLINDNESS: حالة نفي صريحة (AFFIRMED/NEGATED) بنطاق أمامي من أداة النفي حتى علامة
   وقف أو حد أقصى من الرموز.
3. MORPHOLOGICAL_MISS: تغطية أوسع (مرادفات مسجَّلة، احتواء لا بادئة للجذور المعرَّضة لحروف
   مضارعة، امتصاص الهمزة/حروف الجر الملتصقة).
4. CONCEPT_OVERTRIGGER (تصادم بين-مفهومي): توقيعات مركَّبة — الكلمة العابرة المشتركة («زوج»)
   وحدها لا تكفي أبدًا؛ يلزم مرساة نوعية (كيان الزواج «زواج/زوجية» لا الطرف «زوج/زوجة» لمفهوم
   الزوجية، وصياغة علائقية متعددة الكلمات لا كلمة مفردة لمفهوم رد القاضي).
5. فصل concept عن dependency: `CHEQUE_LIMITATION_CHECK` له `applicability_condition` مستقلة
   (إشارة زمنية صريحة) — أول حالة concept=true/dependency=false حقيقية في هذا المشروع.
"""
import hashlib
import json
import re

# ============================================================
# فئات المفاهيم العامة (بلا تغيير عن v1 — نفس العشرة المعتمَدة)
# ============================================================
CONCEPT_CATEGORIES = [
    "LEGAL_ENTITY", "LEGAL_RELATIONSHIP", "PROCEDURAL_POSTURE", "CLAIM_OR_REMEDY",
    "DOCUMENT_OR_INSTRUMENT", "TEMPORAL_EVENT", "JURISDICTIONAL_FACT", "PARTY_STATUS",
    "MANDATORY_PRECONDITION", "EXCEPTION_TRIGGER",
]

# ============================================================
# 1) خط أنابيب التطبيع — كل تحويل مُدرَج ومُوثَّق منفردًا (lossy/lossless)
# ============================================================
_TASHKEEL_RE = re.compile(r"[ً-ٰٟ]")

ORTHOGRAPHIC_TRANSFORMS = [
    ("hamza_unification", lambda t: t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا"),
     "lossless — لا تصادم معروف؛ يُطبَّق دومًا"),
    ("alef_maksura", lambda t: t.replace("ى", "ي"), "lossless عمليًا؛ يُطبَّق دومًا"),
    ("tashkeel_strip", lambda t: _TASHKEEL_RE.sub("", t), "lossless (تشكيل زخرفي)؛ يُطبَّق دومًا"),
    ("taa_marbuta", lambda t: t.replace("ة", "ه"),
     "LOSSY — يوحّد «نسبة» و«نسبه» (تصادم موثَّق في v1). يُطبَّق فقط في `full_norm`، "
     "أما `precise_norm` فيُبقي التاء المربوطة صراحةً للمطابقات الحرجة (نسب)."),
]


def full_norm(text):
    """تطبيع كامل (كل التحويلات، بما فيها ة→ه المفقِدة) — للمطابقة العامة فقط."""
    t = text or ""
    for _name, fn, _note in ORTHOGRAPHIC_TRANSFORMS:
        t = fn(t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def precise_norm(text):
    """تطبيع بلا تحويل ة→ه المفقِد — للمطابقات التي يُخشى عليها من تصادم (نسب)."""
    t = text or ""
    for name, fn, _note in ORTHOGRAPHIC_TRANSFORMS:
        if name == "taa_marbuta":
            continue
        t = fn(t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


_SENT_SPLIT_RE = re.compile(r"[.،؛!؟\n]")


def clauses(text):
    """يقسّم النص إلى فقرات/جمل بعلامات الوقف — نطاق تقارب تقريبي لكل مفهوم (بديل غير مكلف
    عن تحليل نحوي كامل، يمنع تشغيل مفهوم من كلمتين في طرفي نص طويل غير مترابطين)."""
    return [c for c in _SENT_SPLIT_RE.split(text or "") if c.strip()]


def _strip_al(word):
    for pref in ("بال", "فال", "كال", "لل", "وال", "ال"):
        if word.startswith(pref) and len(word) - len(pref) >= 3:
            return word[len(pref):]
    return word


def tokenize(text):
    return [_strip_al(w) for w in re.split(r"[^0-9a-zء-ي]+", full_norm(text)) if len(w) >= 2]


# ============================================================
# 2) حالة النفي — نطاق أمامي من أداة النفي حتى علامة وقف أو حد أقصى من الرموز
# ============================================================
_NEG_PARTICLES = {"لا", "لم", "لن", "ما", "ليس", "دون", "بدون", "غير"}
_NEG_SCOPE_MAX_TOKENS = 8
# «دون/بدون/غير» أدوات نفي اسمية تنفي الاسم الذي يليها مباشرة (دون توثيق) لا الفعل البعيد —
# نطاق أمامي واسع (8) لها كان يبتلع محتوى الجملة كله عرضًا حين يرد الفعل المستهدَف لاحقًا في
# نفس الفقرة بلا علاقة فعلية بأداة النفي (وُجد فعليًا أثناء بناء دفتر التطوير v2)؛ أدوات النفي
# الفعلية (لا/لم/لن/ما/ليس) وحدها تُبقي النطاق الواسع.
_NEG_PARTICLES_NARROW = {"دون", "بدون", "غير"}
_NEG_SCOPE_NARROW_TOKENS = 3


def negation_spans(tokens):
    """يُعيد قائمة (start, end) نطاقات نفي نشطة — نطاق أمامي يختلف طوله بحسب نوع الأداة."""
    spans = []
    for i, t in enumerate(tokens):
        if t in _NEG_PARTICLES_NARROW:
            spans.append((i, min(len(tokens), i + 1 + _NEG_SCOPE_NARROW_TOKENS)))
        elif t in _NEG_PARTICLES:
            spans.append((i, min(len(tokens), i + 1 + _NEG_SCOPE_MAX_TOKENS)))
    return spans


def is_negated(tokens, idx, spans):
    return any(s <= idx < e for s, e in spans)


# ============================================================
# 3) معاجم الأدوار (لا قوائم كلمات مسطَّحة — كل كلمة مربوطة بدور نوعي)
# ============================================================
JUDGE_ENTITY = ["قاض", "قضاة", "دائره"]  # «قاض» (لا «قاضي») يمتص الإعراب المنقوص: قاضٍ/قاضي/القاضي معًا
# صيغ علائقية متعددة الكلمات لا كلمة مفردة — تحل تصادم «زوج» المشترك مع مفهوم الزوجية.
# «قرابة/مصاهرة/نسيب/مصلحة» أُبقيت كلمات مفردة (لا يشترط تركيب) لأنها ليست معرَّضة لنفس خطر
# التصادم — «مصلحة» وحدها قُيِّدت أول الأمر إلى عبارة «له مصلحة» فأخفقت مع صيغ مثل «مصلحة
# شخصية لأحد أعضائها»؛ أُعيدت كلمة مفردة كما كانت في v1 (لا خطر تصادم معروف لها) بعد أن كشف
# دفتر التطوير الجديد نفسه هذا التضييق غير المبرَّر.
RELATION_TO_PARTY_PHRASES = [
    re.compile(r"زوج[اهئ]?\s*ل"), re.compile(r"زوجا?\s+\S"),  # «زوجًا لـ» أو تركيب إضافة «زوج X»
    re.compile(r"قريب[اهئ]?\s*ل"), re.compile(r"صهر[اهئ]?\s*ل"),
    re.compile(r"بين(ه|هم)?\s*وبين"),  # يمتص المفرد والجمع معًا («بينه وبين»/«بينهم وبين»)
    re.compile(r"قرابه|مصاهره|نسيب|مصلحه"),
]
DISQUALIFICATION_ACTION = ["رد", "تنحي", "تنح", "صلاحيه"]
PRIOR_INVOLVEMENT_ACTION = ["افتي", "ترافع", "شهاده", "خبيرا"]  # سبب م102-و الموسَّع (اكتُشف عبر Holdout v1)

MARRIAGE_ENTITY = ["زواج", "زوجيه"]  # ليس «زوج/زوجة» بمفردهما — يحل التصادم مع رد القاضي
DENIAL_PREDICATE_ROOTS = ["نكر", "جحد"]  # احتواء لا بادئة — يمتص ينكر/أنكر/تنكر/منكر
DENIAL_PREDICATE_NEG_ACK = [re.compile(r"لا\s*يعترف"), re.compile(r"عدم\s*اعتراف")]  # مرادف اكتُشف عبر Holdout v1

CHEQUE_ENTITY = ["شيك"]
CHEQUE_CLAIM_ACTION = ["تحصيل", "صرف", "ارتد", "رجع", "رصيد", "وفاء", "قيمه"]
# جذر «طلب» يُطابَق احتواءً لا بادئة — الأفعال المضارعة (يطالب/تطالب/نطالب) لا تبدأ بـ«مطالبة»
CHEQUE_CLAIM_ROOTS = ["طالب"]
TIME_ELAPSED_SIGNAL = ["تقادم", "مده", "سنوات", "سنه", "مضي", "انقضت", "منذ"]  # applicability تقادم الشيك

LINEAGE_RE = re.compile(r"^(?:[بلكو])?نسب(ه|ها|هم|هما)?$")  # يمتص حرف الجر الملتصق (بنسب) الآن
LINEAGE_ACTION = ["اثبات", "نفي", "دعوي", "ابن", "بنوه", "والد"]
LINEAGE_ACTION_ROOTS = ["ثبت"]  # يغطي صيغة الفعل «أثبت/يثبت» التي لا يطابقها بادئة الاسم «اثبات»


def _contains_any(tokens, roots):
    return any(any(r in t for r in roots) for t in tokens)


def _prefix_any(tokens, words):
    words = [_strip_al(w) for w in words]
    return any(t.startswith(w) for t in tokens for w in words)


def _entity_present_excluding_negated(tokens, words):
    """مطابقة الكيان مع استبعاد صيغة «غير X» (نفي الهوية لا الفعل — «سند تجاري غير الشيك»
    لا يعني وجود شيك فعليًا). لا يُستدرَك بـ`negation_spans` العامة لأنها موجَّهة لنفي
    الأفعال/المسندات لا نفي هوية الكيان نفسه."""
    words = [_strip_al(w) for w in words]
    for i, t in enumerate(tokens):
        if any(t.startswith(w) for w in words):
            if i > 0 and tokens[i - 1] == "غير":
                continue
            return True
    return False


# ============================================================
# 4) توقيعات المفاهيم — تركيب أدوار + تقارب (الفقرة) + بوابة نفي، لا زوج كلمات مفكَّك
# ============================================================
class ConceptSignal:
    def __init__(self, concept_id, category, matched_clause, negation_state, components):
        self.concept_id = concept_id
        self.category = category
        self.matched_clause = matched_clause
        self.negation_state = negation_state
        self.components = components  # قائمة أوصاف الأدوار التي طابقت (تشخيص)


def _relation_phrase_negated(p_norm, match_start):
    """يفحص أداة نفي ضمن نص الفقرة قبل موضع العبارة العلائقية مباشرة — لازم لأن العبارات
    مبنية على regex على النص الكامل لا على رمز مفرد، فتعذَّر ربطها بفهرس رمز محدَّد كما يفعل
    `negation_spans` على قوائم الرموز؛ فحص حرفي على النطاق المتقدِّم (~8 كلمات) قبل المطابقة."""
    before = p_norm[:match_start]
    before_toks = [w for w in re.split(r"[^0-9a-zء-ي]+", before) if w]
    window = before_toks[-_NEG_SCOPE_MAX_TOKENS:]
    return any(t in _NEG_PARTICLES for t in window)


def _judicial_disqualification_in_clause(clause_text):
    toks = tokenize(clause_text)
    if not _prefix_any(toks, JUDGE_ENTITY):
        return None
    p_norm = full_norm(clause_text)
    relation_match = next((p.search(p_norm) for p in RELATION_TO_PARTY_PHRASES if p.search(p_norm)), None)
    relation_hit = relation_match is not None
    action_hit = _prefix_any(toks, DISQUALIFICATION_ACTION)
    prior_hit = _prefix_any(toks, PRIOR_INVOLVEMENT_ACTION)
    if not (relation_hit or action_hit or prior_hit):
        return None
    spans = negation_spans(toks)
    if action_hit or prior_hit:
        trigger_idx = next((i for i, t in enumerate(toks)
                             if any(t.startswith(w) for w in DISQUALIFICATION_ACTION + PRIOR_INVOLVEMENT_ACTION)), 0)
        neg = "NEGATED" if is_negated(toks, trigger_idx, spans) else "AFFIRMED"
    else:
        neg = "NEGATED" if _relation_phrase_negated(p_norm, relation_match.start()) else "AFFIRMED"
    comps = [c for c, hit in [("relation_phrase", relation_hit), ("disqualification_action", action_hit),
                               ("prior_involvement", prior_hit)] if hit]
    return ConceptSignal("JUDICIAL_DISQUALIFICATION", "PROCEDURAL_POSTURE", clause_text, neg, comps)


def _cheque_payment_claim_in_clause(clause_text):
    toks = tokenize(clause_text)
    if not _entity_present_excluding_negated(toks, CHEQUE_ENTITY):
        return None
    claim_hit = _prefix_any(toks, CHEQUE_CLAIM_ACTION) or _contains_any(toks, CHEQUE_CLAIM_ROOTS)
    if not claim_hit:
        return None
    spans = negation_spans(toks)
    trigger_idx = next((i for i, t in enumerate(toks)
                         if any(t.startswith(w) for w in CHEQUE_CLAIM_ACTION)
                         or any(r in t for r in CHEQUE_CLAIM_ROOTS)), 0)
    neg = "NEGATED" if is_negated(toks, trigger_idx, spans) else "AFFIRMED"
    time_signal = _prefix_any(toks, TIME_ELAPSED_SIGNAL)
    comps = ["cheque_entity", "claim_action"] + (["time_elapsed_signal"] if time_signal else [])
    sig = ConceptSignal("CHEQUE_PAYMENT_CLAIM", "CLAIM_OR_REMEDY", clause_text, neg, comps)
    sig.time_signal = time_signal
    return sig


def _lineage_establishment_in_clause(clause_text):
    ptoks = [_strip_al(w) for w in re.split(r"[^0-9a-zء-ي]+", precise_norm(clause_text)) if len(w) >= 2]
    if not any(LINEAGE_RE.match(t) for t in ptoks):
        return None
    toks = tokenize(clause_text)
    if not (_prefix_any(toks, LINEAGE_ACTION) or _contains_any(toks, LINEAGE_ACTION_ROOTS)):
        return None
    spans = negation_spans(toks)
    neg = "AFFIRMED"  # لا حالة نفي مسجَّلة بعد لهذا المفهوم في التصميم — يُترك AFFIRMED صراحةً
    return ConceptSignal("LINEAGE_ESTABLISHMENT", "CLAIM_OR_REMEDY", clause_text, neg,
                          ["lineage_word_precise", "lineage_action"])


def _marital_status_denial_in_clause(clause_text):
    toks = tokenize(clause_text)
    if not _prefix_any(toks, MARRIAGE_ENTITY):
        return None
    p_norm = full_norm(clause_text)
    root_hit = _contains_any(toks, DENIAL_PREDICATE_ROOTS)
    neg_ack_hit = any(p.search(p_norm) for p in DENIAL_PREDICATE_NEG_ACK)
    if not (root_hit or neg_ack_hit):
        return None
    spans = negation_spans(toks)
    trigger_idx = next((i for i, t in enumerate(toks) if any(r in t for r in DENIAL_PREDICATE_ROOTS)), 0)
    neg = "NEGATED" if is_negated(toks, trigger_idx, spans) else "AFFIRMED"
    if neg_ack_hit and not root_hit:
        neg = "AFFIRMED"  # «لا يعترف» — النفي جزء من الإسناد الإيجابي (إنكار) لا نفي للإنكار نفسه
    comps = [c for c, hit in [("denial_root", root_hit), ("negated_acknowledgement", neg_ack_hit)] if hit]
    return ConceptSignal("MARITAL_STATUS_DENIAL", "MANDATORY_PRECONDITION", clause_text, neg, comps)


_DETECTORS = [_judicial_disqualification_in_clause, _cheque_payment_claim_in_clause,
              _lineage_establishment_in_clause, _marital_status_denial_in_clause]


# ============================================================
# 5) التبعيات — applicability_condition مستقلة عن تفعيل المفهوم (فصل حقيقي)
# ============================================================
class Dependency:
    def __init__(self, dependency_id, concept_id, legal_role, mandatory_or_optional,
                 verification_status, source_basis, scope_target, authority_resolution_method,
                 applicability_fn=None):
        self.dependency_id = dependency_id
        self.concept_id = concept_id
        self.legal_role = legal_role
        self.mandatory_or_optional = mandatory_or_optional
        self.verification_status = verification_status
        self.source_basis = source_basis
        self.scope_target = scope_target
        self.authority_resolution_method = authority_resolution_method
        self.applicability_fn = applicability_fn or (lambda sig: True)

    def to_dict(self):
        d = {k: v for k, v in vars(self).items() if k != "applicability_fn"}
        return d


DEPENDENCIES = [
    Dependency("JUDICIAL_DISQUALIFICATION_VALIDITY_CHECK", "JUDICIAL_DISQUALIFICATION",
               "procedural validity / nullity risk", "mandatory",
               "spot_verified_via_mcp_search (v1، بلا تغيير في الأساس القانوني)",
               "قواعد عدم صلاحية القاضي ورده — قانون المرافعات",
               ["أسباب رد القاضي وعدم صلاحيته لنظر الدعوى", "إجراءات طلب رد القاضي والفصل فيه",
                "أثر بطلان الحكم الصادر من قاضٍ غير صالح لنظر الدعوى"],
               "deterministic scope phrases -> real search channels (غير مفعَّل في B2-R)"),
    Dependency("CHEQUE_SUBSTANTIVE_RULES_CHECK", "CHEQUE_PAYMENT_CLAIM",
               "substantive claim basis", "mandatory",
               "spot_verified_via_mcp_search (v1)",
               "التزام الساحب بالوفاء بقيمة الشيك — قانون التجارة",
               ["التزام الساحب بالوفاء بقيمة الشيك", "امتناع المسحوب عليه عن الصرف"],
               "deterministic scope phrases -> real search channels"),
    Dependency("CHEQUE_LIMITATION_CHECK", "CHEQUE_PAYMENT_CLAIM",
               "defence / time-bar risk — applicability مشروطة لا تلقائية", "conditional",
               "spot_verified_via_mcp_search (v1)",
               "تقادم دعوى المطالبة بقيمة الشيك ودعوى الإثراء بلا سبب البديلة",
               ["تقادم دعوى المطالبة بقيمة الشيك", "دعوى الإثراء بلا سبب بعد سقوط الشيك بالتقادم"],
               "deterministic scope phrases -> real search channels",
               applicability_fn=lambda sig: getattr(sig, "time_signal", False)),
    Dependency("LINEAGE_COMMITTEE_MANDATORY_REVIEW", "LINEAGE_ESTABLISHMENT",
               "mandatory prior administrative procedure", "mandatory",
               "spot_verified_via_mcp_search (v1)",
               "وجوب عرض طلب إثبات/نفي النسب على لجنة النسب قبل رفع الدعوى القضائية",
               ["اختصاص لجنة النسب بالنظر قبل رفع دعوى النسب",
                "إجراءات تقديم طلب إثبات النسب أو نفيه إلى اللجنة"],
               "deterministic scope phrases -> real search channels"),
    Dependency("MARITAL_RELATIONSHIP_DENIAL_HEARING_CHECK", "MARITAL_STATUS_DENIAL",
               "mandatory admissibility precondition", "mandatory",
               "spot_verified_via_mcp_search (v1)",
               "عدم سماع دعوى الزوجية عند الإنكار إلا بوثيقة رسمية أو إقرار سابق",
               ["عدم سماع دعوى الزوجية عند الإنكار", "الاستثناءات على عدم سماع دعوى الزوجية"],
               "deterministic scope phrases -> real search channels"),
]
DEPENDENCIES_BY_CONCEPT = {}
for _d in DEPENDENCIES:
    DEPENDENCIES_BY_CONCEPT.setdefault(_d.concept_id, []).append(_d)


def recognize(facts_text):
    """FACT -> (لكل فقرة) CONCEPT SIGNAL (بحالة نفي) -> DEPENDENCY (بشرط قبول مستقل) -> SCOPE.
    حتمي بالكامل — صفر نداء نموذج لغوي."""
    concepts_triggered, dependencies_triggered, scope_queries = set(), set(), []
    signals = []
    for cl in clauses(facts_text) or [facts_text]:
        for det in _DETECTORS:
            sig = det(cl)
            if sig is not None:
                signals.append(sig)
                if sig.negation_state == "AFFIRMED":
                    concepts_triggered.add(sig.concept_id)

    for cid in concepts_triggered:
        matching_sig = next((s for s in signals if s.concept_id == cid and s.negation_state == "AFFIRMED"), None)
        for dep in DEPENDENCIES_BY_CONCEPT.get(cid, []):
            if dep.applicability_fn(matching_sig):
                dependencies_triggered.add(dep.dependency_id)
                scope_queries.extend(dep.scope_target)

    return {
        "concepts_triggered": sorted(concepts_triggered),
        "dependencies_triggered": sorted(dependencies_triggered),
        "scope_queries": scope_queries,
        "signals": [{"concept_id": s.concept_id, "clause": s.matched_clause,
                     "negation_state": s.negation_state, "components": s.components} for s in signals],
    }


def freeze_hash():
    payload = {
        "orthographic_transforms": [(n, note) for n, _fn, note in ORTHOGRAPHIC_TRANSFORMS],
        "dependencies": [d.to_dict() for d in DEPENDENCIES],
        "concept_ids": sorted({d.concept_id for d in DEPENDENCIES}),
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    print("CONCEPTS:", sorted({d.concept_id for d in DEPENDENCIES}))
    print("DEPENDENCIES:", [d.dependency_id for d in DEPENDENCIES])
    print("FREEZE_HASH:", freeze_hash())
