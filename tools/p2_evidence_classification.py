#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.1A — تصنيف الأدلة (Evidence Classification) طبقًا لـdocs/p2_architecture_design.md §4
و§4-مكرر. يُصنِّف كل مرشح في مجموعة hits إلى A1/A2/A3/S/B/C/D — بلا استيراد من admin/app.py
(عزل فيزيائي تام، يقرأ `app` كوسيط مُمرَّر فقط عند الحاجة لـ_XREF).

**تصحيحان بعد ملاحظتي المالك على نتائج Shadow A الأولى (2026-09-14):**

1. **فصل صحة الوجود عن الدقة الموضوعية — طبقة S جديدة:** `_draft_direct_ids` (مصدر
   anchors_a1) يخلط ثلاثة أسباب: استشهاد صريح برقم مادة، مطابقة عنوان، **ومادة النفاذ
   الأخيرة الحتمية لأي قانون يُذكر** (ضمانة `.bak_hybfix2` الموثَّقة في CLAUDE.md §6) بصرف
   النظر عن صلتها الموضوعية. تصنيف A1 الغُفل السابق كان يُدخل هذه المادة الحتمية بوصفها
   مرساة موضوعية خطأً (رصدها التحقق الحي: 3 من 7 مرشحي A1 الفريدين في دفعة Shadow A الأولى
   كانت مواد نفاذ/إصدار محضة — `legis-159-2025-m84`، `legis-39-1980-m73`، `legis-78-2026-m14`
   — بنص إصدار/تنفيذ حرفي مؤكَّد عبر MCP، بينما البقية الأربعة `m17`/`m1082`/`m227`/`m6`
   موضوعية فعلًا). الآن: أي مرشح في anchors_a1 يُفحص نصه (عبر `texts`) بنمط مواد
   الإصدار/النفاذ القياسية الكويتية (`_ENACTMENT_RE`)؛ إن طابق يُصنَّف **S —
   Structural/Enactment Context** بدل A1: كائن حقيقي يبقى في السياق العادي عند الحاجة
   (يتنافس على الميزانية كـB/C/D) لكنه **لا يدخل الحجز المحدود ولا يُحتسب سندًا حاكمًا لأي
   بُعد** إلا إذا كان البُعد نفسه يتعلق بالنفاذ/السريان/الإلغاء/الانتقال الزمني وفق قاعدة
   قانونية مستقلة موثقة — لا قاعدة من القاعدتين القائمتين تعنى بذلك، فلا ترقية مُفعَّلة الآن.

2. **إزالة حقن المرشحين الغائبين عن hits (كانت تكسر عزل Shadow A):** النسخة السابقة كانت
   تُدخل أي anchor A1/A3 غائب عن `hits` صراحة (`injected_directly`) — وهذا يُبطل تعريف
   Shadow A ('نفس current hits حرفيًا، بلا توليد مرشحين جديد'): سؤال المالك المباشر بعد
   رصد أن `legis-1-2016-m30` (غائبة تاريخيًا — Discovery Failure موثَّق) ظهرت
   `must_find_rescued` في Shadow A رغم كونها **يجب** أن تكون غائبة عن `hits` الحقيقية، كشف
   أن هذا الحقن هو السبب — علة عزل تجريبي حقيقية في الكود، لا نتيجة صحيحة. **أُزيلت
   الحقنتان كليًا.** الدالة الآن **نقية بالكامل**: تُصنِّف فقط ما هو موجود بالفعل في `hits`
   المُمرَّرة إليها، ولا تُنشئ أي معرِّف من فراغ أبدًا. أي 'إنقاذ اكتشاف' حقيقي (مرشح غائب
   عن hits أصلًا) هو حصرًا مسؤولية Shadow B: تجلب مرشح A3 غائبًا بنداء استرجاع/جلب حقيقي
   جديد (خطوة governing_candidate_generated→retrieved_or_fetched في السلسلة السببية)، ثم
   تُلحقه بقائمة hits **قبل** استدعاء classify_candidates — فيُصنَّف عبر المسار العادي هنا
   لا عبر حقن داخلي.

**قرارات تشغيل صريحة (MVP، موثَّقة لا مخفاة، غير مُغيَّرة بهذين التصحيحين):**
- B تُحدَّد حصرًا بمصدر 'chapter' (بوابة فصل حاكم) لأنها القناة الوحيدة المرتبطة فعليًا بنطاق
  بُعد قانوني معروف (`chapter_scopes`) في تركيبة البيانات الحالية؛ لا آلية ربط دقيقة بين نتائج
  'dense' المفردة وبُعد بعينه بعد (يحتاج تطويرًا لاحقًا لو ثبتت الحاجة قياسًا).
- C تُحدَّد لمصادر 'dense'/'bundle' (اكتشاف واسع، بعضه من محاور Haiku).
- D تُحدَّد لكل ما تبقى ('lexical'/'xref'/'sibling_xref'/'principle_xref').
- تصنيف `U` (Unverified Coverage Candidate) **لا** يقع هنا — يتطلب معرفة الأبعاد غير
  المغطاة بعد القبول، فهو مسؤولية p2_coverage_checker.py (طبقة لاحقة، §4-مكرر من P2 v2)."""
from __future__ import annotations
import re

# أنماط مواد الإصدار/النفاذ القياسية في التشريع الكويتي — "ينشر هذا القانون ويعمل به من..."،
# "على الوزراء/رئيس مجلس الوزراء ... تنفيذ هذا القانون/المرسوم"، وتذييل الإصدار (اسم الأمير/
# رئيس الوزراء وتاريخ الصدور). تحقُّق حي على 3 نصوص فعلية (m84 79/2025، m73 39/1980،
# m14 78/2026) أثبت التطابق التام؛ و4 نصوص موضوعية فعلية (m17 12/2015، m1082 وm227 67/1980،
# m6 78/2026) أثبتت عدم التطابق — صفر إيجاب/سلب كاذب على العيّنة المتحقَّقة فعليًا.
_ENACTMENT_RE = re.compile(
    r"(ينشر هذا (القانون|المرسوم)|يعمل به (من|بعد)|"
    r"تنفيذ هذا (القانون|المرسوم)|أمير الكويت\s*:|صدر (بقصر|في)|"
    r"رئيس مجلس الوزراء\s*:)"
)


def _is_enactment_text(text):
    return bool(text) and bool(_ENACTMENT_RE.search(text))


def classify_candidates(hits, scope, xref_map=None, texts=None):
    """hits: قائمة (label, score, payload) كما تُعيدها _draft_build_context (أو Shadow A/B
    المكافئة — في Shadow B تحديدًا، بعد أي إلحاق مرشحين حقيقي مُسبَق، لا حقن هنا). scope:
    مخرَج compute_backbone. xref_map: app._XREF أو ما يعادلها (اختياري — A2 تُهمَل إن غاب).
    texts: {object_id: {"text": ...}} لفحص نمط مواد النفاذ (اختياري — بلا تمييز S إن غاب،
    رجوعًا آمنًا لتصنيف A1 كما كان). يُعيد dict: {object_id: {"tier": ..., "reason": {...}}}.

    **ضمانة عزل صريحة:** لا تُنشئ هذه الدالة أي معرِّف غير موجود في `hits` أصلًا — كل مفتاح
    في المُخرَج مأخوذ حرفيًا من `payload.get("object_id")` لعنصر حقيقي في `hits`."""
    texts = texts or {}
    a1_ids = {a["authority_id"] for a in scope.get("anchors_a1", [])}
    a3_by_id = {a["authority_id"]: a for a in scope.get("anchors_a3", [])}
    chapter_ids = {c["chapter_id"] for c in scope.get("chapter_scopes", [])}

    # A2: أهداف _XREF من أي مرساة A1/A3 مؤكَّدة (عمق واحد فقط، لا تعدٍّ متسلسل)
    a2_ids = {}
    if xref_map:
        for anchor_id in list(a1_ids) + list(a3_by_id.keys()):
            for target in xref_map.get(anchor_id, ()):
                if target not in a1_ids and target not in a3_by_id:
                    a2_ids.setdefault(target, anchor_id)

    result = {}
    for label, score, payload in hits:
        oid = payload.get("object_id")
        if not oid or oid in result:
            continue
        source = payload.get("_source", "dense")

        if oid in a1_ids:
            txt = (texts.get(oid) or {}).get("text")
            if _is_enactment_text(txt):
                result[oid] = {"tier": "S", "reason": {"source": "explicit_citation_channel",
                                                          "enactment_boilerplate": True}}
            else:
                result[oid] = {"tier": "A1", "reason": {"rule_id": None, "source": "explicit_citation"}}
        elif oid in a3_by_id:
            a = a3_by_id[oid]
            result[oid] = {"tier": "A3", "reason": {"rule_id": a["rule_id"], "dimension": a["dimension_id"]}}
        elif oid in a2_ids:
            result[oid] = {"tier": "A2", "reason": {"xref_from": a2_ids[oid]}}
        elif source == "chapter" and payload.get("_chapter_id") in chapter_ids:
            result[oid] = {"tier": "B", "reason": {"chapter_id": payload.get("_chapter_id")}}
        elif source in ("dense", "bundle"):
            result[oid] = {"tier": "C", "reason": {"source": source}}
        else:
            result[oid] = {"tier": "D", "reason": {"source": source}}

    return result
