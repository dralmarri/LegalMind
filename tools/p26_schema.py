#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.6 — Legal Issue & Dependency Planner: مخطط المخرج المجمَّد (JSON Schema) + مدقق بنيوي +
كاشف تسرّب معرِّفات (IDs) و/أو استشهاد سلطة صريح. **الملف كله يُقرَّأ فقط من لحظة التجميد —
أي تعديل عليه بعد `freeze_hash()` يُبطل مقارنة Dev/Gold.**

قرار تصميمي مُسجَّل: حقول `issue`/`dimension` نص حر (لا enum مغلق) — الغاية من التجربة اختبار
اكتشاف حر بلغة طبيعية، لا مطابقة لقائمة مقفلة (ذاك عيب B2-R الذي نحاول تجاوزه). المطابقة مع
الحقيقة الأرضية تتم لاحقًا بتكافؤ دلالي (`p26_evaluator.py`) لا بمطابقة نصية حرفية ولا بقائمة
مقفلة في هذه الطبقة."""
import re

SCHEMA_VERSION = "p26-schema-v1"

# --- المخطط (توثيقي + مرجع بنية) ---
OUTPUT_SCHEMA_EXAMPLE = {
    "primary_issue": "string",
    "issues": [
        {
            "issue": "string",
            "issue_type": "substantive|procedural|evidentiary|temporal|jurisdictional",
            "triggering_facts": ["string", "..."],
            "required_dimensions": [
                {
                    "dimension": "string",
                    "why_required": "string",
                    "status": "required|conditional|possible",
                    "condition": "string أو null",
                    "triggering_facts": ["string", "..."],
                }
            ],
        }
    ],
    "cross_issue_dependencies": ["string", "..."],
    "uncertainties": ["string", "..."],
}

_ISSUE_TYPES = {"substantive", "procedural", "evidentiary", "temporal", "jurisdictional"}
_STATUS_VALUES = {"required", "conditional", "possible"}


def validate_structure(obj):
    """تحقق بنيوي صارم — يُعيد (ok: bool, errors: list[str])."""
    errors = []
    if not isinstance(obj, dict):
        return False, ["root ليس كائن JSON"]

    if "primary_issue" not in obj or not isinstance(obj.get("primary_issue"), str) or not obj["primary_issue"].strip():
        errors.append("primary_issue مفقود أو فارغ")

    issues = obj.get("issues")
    if not isinstance(issues, list) or not issues:
        errors.append("issues مفقودة أو فارغة أو ليست قائمة")
        issues = []

    for i, iss in enumerate(issues):
        if not isinstance(iss, dict):
            errors.append(f"issues[{i}] ليس كائنًا")
            continue
        if not isinstance(iss.get("issue"), str) or not iss["issue"].strip():
            errors.append(f"issues[{i}].issue مفقود أو فارغ")
        it = iss.get("issue_type")
        if it not in _ISSUE_TYPES:
            errors.append(f"issues[{i}].issue_type غير صالح: {it!r}")
        tf = iss.get("triggering_facts")
        if not isinstance(tf, list) or not tf:
            errors.append(f"issues[{i}].triggering_facts مفقودة أو فارغة")
        dims = iss.get("required_dimensions")
        if not isinstance(dims, list):
            errors.append(f"issues[{i}].required_dimensions ليست قائمة")
            dims = []
        for j, d in enumerate(dims):
            if not isinstance(d, dict):
                errors.append(f"issues[{i}].required_dimensions[{j}] ليس كائنًا")
                continue
            if not isinstance(d.get("dimension"), str) or not d["dimension"].strip():
                errors.append(f"issues[{i}].dimensions[{j}].dimension مفقود")
            if d.get("status") not in _STATUS_VALUES:
                errors.append(f"issues[{i}].dimensions[{j}].status غير صالح: {d.get('status')!r}")
            if d.get("status") == "conditional" and not d.get("condition"):
                errors.append(f"issues[{i}].dimensions[{j}] status=conditional بلا condition")
            if not isinstance(d.get("why_required"), str) or not d["why_required"].strip():
                errors.append(f"issues[{i}].dimensions[{j}].why_required مفقود")
            dtf = d.get("triggering_facts")
            if not isinstance(dtf, list) or not dtf:
                errors.append(f"issues[{i}].dimensions[{j}].triggering_facts مفقودة أو فارغة")

    if "cross_issue_dependencies" not in obj or not isinstance(obj["cross_issue_dependencies"], list):
        errors.append("cross_issue_dependencies مفقودة أو ليست قائمة")
    if "uncertainties" not in obj or not isinstance(obj["uncertainties"], list):
        errors.append("uncertainties مفقودة أو ليست قائمة")

    return (len(errors) == 0), errors


# --- كاشف تسرّب المعرِّفات/الاستشهاد الصريح — يُفحَص على نص JSON الخام كاملًا ---
_ID_LEAK_PATTERNS = [
    (re.compile(r"legis-[a-z0-9\-]+", re.I), "internal_legislation_id"),
    (re.compile(r"jprin-[a-z0-9\-]+", re.I), "internal_principle_id"),
    (re.compile(r"judgment-[a-z0-9\-]+", re.I), "internal_judgment_id"),
    (re.compile(r"\b(regl|lreg)-[a-z0-9\-]+", re.I), "internal_regulation_id"),
    (re.compile(r"\bLEG-[A-Z0-9\-]+", re.I), "internal_LEG_id"),
    (re.compile(r"(?:المادة|مادة)\s*\(?\d+\)?"), "explicit_article_number_citation"),
    (re.compile(r"الطعن\s*(?:رقم)?\s*\(?\d+\)?\s*(?:/|لسنة)\s*\d+"), "explicit_appeal_citation"),
]


def detect_id_leakage(raw_json_text):
    """يفحص نص JSON الخام (لا الكائن المفكوك) بحثًا عن أي معرِّف داخلي أو استشهاد صريح برقم
    مادة/طعن — كلاهما ممنوع على Planner بنص المواصفة (اكتشاف لا حلّ سلطة)."""
    hits = []
    for rx, label in _ID_LEAK_PATTERNS:
        for m in rx.finditer(raw_json_text or ""):
            hits.append({"label": label, "match": m.group(0)})
    return hits


def freeze_hash():
    import hashlib
    material = (SCHEMA_VERSION + str(sorted(_ISSUE_TYPES)) + str(sorted(_STATUS_VALUES))
                + str([p[1] for p in _ID_LEAK_PATTERNS]))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    print("schema freeze_hash =", freeze_hash())
    ok, errs = validate_structure(OUTPUT_SCHEMA_EXAMPLE)
    print("example validates (expected False — placeholders):", ok, errs[:3])
