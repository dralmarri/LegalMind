#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.1 Closure — بوابة عزل آلية (بأمر المالك: required_dimensions يجب أن تكون benchmark-only
ومتحققة بصورة مستقلة، ولا يقرأها Backbone أو Shadow runtime). فحص نصي مباشر على الملفات الحية:

1. **الملفات الأربعة الحاكمة للقرار** (p2_backbone/p2_evidence_classification/
   p2_admission_policy/p2_coverage_checker): صفر ورود لأي من required_dimensions أو
   ground_truth_authority_ids أو ground_truth_status أو must_find أو must_not_miss — هذه
   الطبقة هي التي تقرر ماذا يُصنَّف ويُحجَز ويُقبَل، فيجب أن تكون عمياء تمامًا عن الحقيقة
   الأرضية القياسية.
2. **مُشغِّلا Shadow** (shadow_a_runner/shadow_b_runner): required_dimensions ممنوعة كليًا
   (لا سبب لهما لقراءتها أصلًا)، أما must_find/must_not_miss فمسموحة **حصرًا** لأنها مستعملة
   فعليًا هناك لبناء حقول الإخراج البعدي (must_find_rescued/must_find_lost) — قياس بعد وقوع
   القرار لا مدخل له؛ يُتحقَّق من ذلك بفحص أن كل سطر يحوي 'must_find' لا يقع داخل أي نداء فعلي
   لدوال القرار الأربع (compute_backbone/classify_candidates/admit/check_coverage)."""
import ast
import re
import sys


def _strip_prose(src):
    """يُزيل التعليقات (#...) والنصوص الثلاثية (docstrings) قبل الفحص — الغاية عزل *الكود
    التنفيذي* لا منع ذكر هذه الكلمات في التوثيق التاريخي (مثال: تعليق يشرح علة سابقة استعملت
    must_find في اسم حقل إخراج). لا يُخفي استعمالًا فعليًا في التعبيرات (نصوص عادية بسيطة
    من نوع 'x' تبقى مفحوصة لأنها خارج الأنماط الثلاثية المحذوفة). **يحافظ على عدّ الأسطر**
    (يستبدل المطابقة بعدد مطابق من الأسطر الفارغة) حتى تبقى أرقام الأسطر متطابقة مع
    ast.parse(src) الأصلي، وإلا انحرف check_runner_file عن مواضعه الحقيقية."""
    def _blank(m):
        return "\n" * m.group(0).count("\n")
    no_triple = re.sub(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', _blank, src)
    no_comments = re.sub(r"#.*", "", no_triple)
    return no_comments

CORE_DECISION_FILES = [
    "p2_backbone.py", "p2_evidence_classification.py",
    "p2_admission_policy.py", "p2_coverage_checker.py",
]
RUNNER_FILES = ["shadow_a_runner.py", "shadow_b_runner.py"]

FORBIDDEN_ANYWHERE = ["required_dimensions", "ground_truth_authority_ids", "ground_truth_status"]
FORBIDDEN_IN_CORE_ONLY = ["must_find", "must_not_miss"]
DECISION_FN_NAMES = {"compute_backbone", "classify_candidates", "admit", "check_coverage"}


def _string_hits(src, forbidden):
    return [f for f in forbidden if f in src]


def _decision_call_lines(src):
    """يُعيد مجموعة أرقام الأسطر التي تقع ضمن أي نداء فعلي لإحدى دوال القرار الأربع."""
    tree = ast.parse(src)
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else None)
            if name in DECISION_FN_NAMES:
                end = getattr(node, "end_lineno", node.lineno)
                lines.update(range(node.lineno, end + 1))
    return lines


def check_core_file(path):
    src = open(path, encoding="utf-8").read()
    return _string_hits(_strip_prose(src), FORBIDDEN_ANYWHERE + FORBIDDEN_IN_CORE_ONLY)


def check_runner_file(path):
    src = open(path, encoding="utf-8").read()
    code_only = _strip_prose(src)
    violations = list(_string_hits(code_only, FORBIDDEN_ANYWHERE))
    # must_find/must_not_miss مسموحة إلا داخل سطور نداء دوال القرار الأربع فعليًا — الفحص
    # على الكود الأصلي (لا المُجرَّد) لأن أرقام الأسطر يجب أن تطابق ast.parse(src)
    decision_lines = _decision_call_lines(src)
    for i, line in enumerate(code_only.split("\n"), start=1):
        if i in decision_lines and ("must_find" in line or "must_not_miss" in line):
            violations.append(f"must_find/must_not_miss داخل نداء دالة قرار (سطر {i}): {line.strip()}")
    return violations


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "/opt/LegalMind/tools"
    violations = []
    for f in CORE_DECISION_FILES:
        hits = check_core_file(f"{base}/{f}")
        if hits:
            violations.append((f, hits))
    for f in RUNNER_FILES:
        hits = check_runner_file(f"{base}/{f}")
        if hits:
            violations.append((f, hits))

    print("=== بوابة عزل required_dimensions/must_find عن منطق القرار ===")
    if violations:
        for f, hits in violations:
            print(f"  !! {f}: {hits}")
        print("BENCHMARK_ISOLATION_FAIL")
        return 1
    print("صفر انتهاك: required_dimensions ممنوعة كليًا من الملفات الستة كلها؛ "
          "must_find/must_not_miss ممنوعة من ملفات القرار الأربعة كليًا، ومسموحة في "
          "مُشغِّلَي Shadow حصرًا خارج نداءات دوال القرار (إخراج بعدي فقط).")
    print("BENCHMARK_ISOLATION_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
