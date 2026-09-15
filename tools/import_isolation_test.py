#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.1 — بوابة عزل آلية (بأمر المالك: 'أضف اختبارًا يفشل build/test إن ظهر
shadow_candidate_rules داخل import graph للإنتاج'). فحص مزدوج على admin/app.py الحي:
(1) فحص AST لكل عبارات import — صفر استيراد لأي وحدة من tools/p2_*.
(2) فحص نصي مباشر — صفر ورود لسلسلة 'shadow_candidate_rules' أو 'p2_backbone' في كل
الملف (يغطي حتى الإشارة النصية غير المستوردة، كتعليق أو مسار ملف مكتوب حرفيًا)."""
import ast
import sys

FORBIDDEN_MODULE_PREFIXES = ("p2_backbone", "p2_evidence_classification",
                              "p2_admission_policy", "p2_coverage_checker",
                              "shadow_a_runner", "shadow_b_runner")
FORBIDDEN_STRINGS = ("shadow_candidate_rules", "p2_backbone", "p2_evidence_classification",
                     "p2_admission_policy", "p2_coverage_checker")


def check_ast_imports(path):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name.startswith(p) for p in FORBIDDEN_MODULE_PREFIXES):
                    violations.append(f"import {alias.name} (line {node.lineno})")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if any(mod.startswith(p) for p in FORBIDDEN_MODULE_PREFIXES):
                violations.append(f"from {mod} import ... (line {node.lineno})")
    return violations, src


def check_textual(src):
    violations = []
    for s in FORBIDDEN_STRINGS:
        if s in src:
            idx = src.find(s)
            line_no = src[:idx].count("\n") + 1
            violations.append(f"'{s}' found at line {line_no}")
    return violations


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/opt/LegalMind/admin/app.py"
    ast_violations, src = check_ast_imports(path)
    text_violations = check_textual(src)

    print(f"فحص عزل الاستيراد على: {path}")
    print(f"  انتهاكات AST (استيراد فعلي): {ast_violations or 'لا شيء'}")
    print(f"  انتهاكات نصية (أي إشارة): {text_violations or 'لا شيء'}")

    ok = not ast_violations and not text_violations
    print("ISOLATION_TEST_" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
