#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.1A/B — Deterministic Legal Scope Backbone (Design Only → أول تنفيذ فعلي، Offline Replay
حصرًا). يُعيد استعمال دوال الإنتاج الحقيقية القائمة فعلًا (لا إعادة كتابة رجعية لمنطقها):
`app._draft_direct_ids` و`app._draft_chap_ids` — **بشرط حاسم للحتمية**: يُستدعيان بقائمة
`subqueries=[]` فارغة دومًا، لا محاور Haiku الفعلية — لأن الهدف هو عزل الجزء الحتمي 100% من
هاتين الدالتين (نص السؤال والوقائع وحدهما، لا أي مدخل عشوائي)، تحقيقًا لمعيار Backbone
Determinism المطلوب (§ من مراجعة المالك: 5 تشغيلات → بصمة واحدة).

يضيف فوق ذلك مصدرًا واحدًا جديدًا: مطابقة `SHADOW_CANDIDATE_RULES` (مقروءة من
`shadow_candidate_rules.json` المعزول فيزيائيًا — انظر تحذير العزل أسفله) لإنتاج مرشحات A3.

**تحذير عزل إلزامي (بلا استثناء):** هذا الملف **لا يُستورَد من `admin/app.py` بأي حال** —
عزل فيزيائي كامل، يُتحقَّق منه آليًا بـ`tools/import_isolation_test.py`. لا يُشغَّل إلا من
سياق Offline Replay مستقل (`shadow_a_runner.py`/`shadow_b_runner.py`/
`backbone_determinism_test.py`)."""
from __future__ import annotations
import hashlib
import json
import os

SHADOW_RULES_PATH = os.path.join(os.path.dirname(__file__), "shadow_candidate_rules.json")


def load_shadow_candidate_rules(path=None):
    """يقرأ حصرًا من الملف المعزول فيزيائيًا. لا مسار بديل، لا قراءة احتياطية من أي جدول
    إنتاج. فشل القراءة يُرجع قائمة فارغة (Backbone يستمر بلا قواعد A3 — لا يوقف القياس)."""
    p = path or SHADOW_RULES_PATH
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("rules", [])
    except Exception as e:
        print(f"[p2_backbone] shadow-rules-load-error: {e!r}", flush=True)
        return []


def _rule_triggered(rule, normalized_text, normalize_fn):
    """منطق تفعيل حتمي بحت: مطابقة نصية لمفاهيم مفتاحية (لا نموذج، لا عشوائية).
    **إصلاح مؤكَّد بالاختبار (2026-09-14):** trigger_concepts يجب أن تُطبَّع بنفس الدالة
    التي طُبِّع بها النص قبل المقارنة — النص الخام "أمر أداء" (بالهمزة) لا يُطابِق أبدًا نصًّا
    مطبَّعًا حوَّل الهمزة لألف ("امر اداء")؛ أول تشغيلة للاختبار (الفئات الأربع) كشفت هذا
    حرفيًا: فشلت كل الحالات الإيجابية بما فيها حالة الانحدار الأصلية نفسها قبل هذا الإصلاح."""
    concepts = [normalize_fn(c) for c in rule.get("trigger_concepts", [])]
    logic = rule.get("trigger_logic", "ANY")
    hits = [c for c in concepts if c in normalized_text]
    if logic == "ALL":
        return len(hits) == len(concepts)
    if isinstance(logic, int):
        return len(hits) >= logic
    return len(hits) >= 1  # ANY (افتراضي)


def compute_backbone(app, request_type, facts_ret, shadow_rules=None):
    """يُنتج DeterministicScope. `app` هو وحدة admin.app الحية (أو بديل وهمي للاختبار) —
    تُمرَّر صراحة (Dependency Injection) لا استيراد ثابت، لتيسير اختبار الوحدة المعزول ولمنع
    أي احتمال استيراد دائري مع admin/app.py الحقيقي."""
    rules = shadow_rules if shadow_rules is not None else load_shadow_candidate_rules()

    # 1) الإحالات الصريحة — subqueries=[] إلزاميًا لضمان الحتمية (القسم أعلاه)
    try:
        direct_ids = sorted(set(app._draft_direct_ids(request_type, facts_ret, [])))
    except Exception as e:
        print(f"[p2_backbone] direct-ids-error: {e!r}", flush=True)
        direct_ids = []

    # 2) نطاقات الفصول الحاكمة — نطاق بحث لا مرساة تلقائية (تمييز §2 من P2 v2)
    try:
        chap_ids = sorted(set(app._draft_chap_ids(request_type, facts_ret, [])))
    except Exception as e:
        print(f"[p2_backbone] chap-ids-error: {e!r}", flush=True)
        chap_ids = []

    # 3) قواعد A3 المرشَّحة (Shadow-Only) — مطابقة نصية حتمية بحتة
    try:
        norm = app._draft_norm_ar(f"{request_type} {facts_ret}")
    except Exception as e:
        print(f"[p2_backbone] norm-error: {e!r}", flush=True)
        norm = f"{request_type} {facts_ret}"

    dimensions = []
    anchors_a3 = []
    for rule in rules:
        triggered = _rule_triggered(rule, norm, app._draft_norm_ar)
        dimensions.append({
            "dimension_id": rule["rule_id"],
            "label": rule.get("label", rule["rule_id"]),
            "required": bool(triggered),
            "requires_governing": bool(rule.get("requires_governing", True)),
            "source_rule_id": rule["rule_id"] if triggered else None,
            "status": rule.get("status"),
        })
        if triggered:
            for aid in rule.get("governing_authority_ids", []):
                anchors_a3.append({
                    "authority_id": aid,
                    "dimension_id": rule["rule_id"],
                    "rule_id": rule["rule_id"],
                })

    scope = {
        "dimensions": sorted(dimensions, key=lambda d: d["dimension_id"]),
        "anchors_a1": [{"authority_id": i, "source": "explicit_citation"} for i in direct_ids],
        "anchors_a3": sorted(anchors_a3, key=lambda a: (a["dimension_id"], a["authority_id"])),
        "chapter_scopes": [{"chapter_id": c} for c in chap_ids],
    }
    return scope


def canonical_hash(scope: dict) -> str:
    """بصمة قانونية (canonical) للمخرَج — ترتيب مفاتيح ثابت، لا اعتماد على ترتيب dict عرضي."""
    blob = json.dumps(scope, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
