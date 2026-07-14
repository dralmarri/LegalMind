#!/usr/bin/env python3
"""مدقق بنيوي — يعمل في CI بلا قاعدة بيانات.

T-00 Truth Layer: هذا المدقق **لا يعدّ** الكائنات المعرفية ولا يعلن إحصاءات.
العدّ يأتي من PostgreSQL وحدها عبر `engine/truth_report.py`.

وظيفته هنا مختلفة: يمنع تكرار العطل الذي وقع فعلًا — وثيقة Markdown تعلن
869 مادة تشريعية لا وجود لها. أي تقرير يدّعي عددًا دون أن توجد مخرجاته
على القرص = فشل.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGISLATION_DIR = ROOT / "data" / "personal-status" / "legislation"
PS_INDEX = ROOT / "data" / "personal-status" / "PS-JURISDICTION-0001.md"
OBJECT_ID_RE = re.compile(r"\b(?:JUR|RULE|LEG|JUD|TPL|MEMO)-[A-Z0-9\-]+\b")


def check_no_phantom_counts(errors: list[str]) -> None:
    """أي تقرير يدّعي عددًا يجب أن تكون مخرجاته موجودة، أو يكون مسحوبًا صراحةً."""
    report_path = LEGISLATION_DIR / "INGESTION_REPORT.json"
    if not report_path.exists():
        return

    report = json.loads(report_path.read_text(encoding="utf-8"))
    if str(report.get("status", "")).startswith("retracted"):
        return

    claimed = report.get("total_legislation_objects", report.get("total_articles"))
    if not claimed:
        return

    artifacts = list(LEGISLATION_DIR.glob("*.jsonl")) + list(LEGISLATION_DIR.glob("KW-*.index.json"))
    if not artifacts:
        errors.append(
            f"{report_path.name}: يدّعي {claimed} كائنًا تشريعيًا ولا توجد أي مخرجات على القرص.\n"
            '  عدد وهمي. إما تُنشأ المخرجات فعلًا، أو يُوسم التقرير "status": "retracted_...".\n'
            "  الإحصاءات المعتمدة تأتي من PostgreSQL: python3 engine/truth_report.py"
        )


def check_object_ids_unique(errors: list[str]) -> None:
    """المعرّفات دائمة ويُستشهد بها في مستندات قانونية — لا يجوز تكرارها."""
    if not PS_INDEX.exists():
        errors.append(f"مفقود: {PS_INDEX}")
        return

    seen: set[str] = set()
    for line in PS_INDEX.read_text(encoding="utf-8").splitlines():
        if not (line.startswith("| JUR-") or line.startswith("| RULE-")):
            continue
        match = OBJECT_ID_RE.search(line)
        if not match:
            continue
        object_id = match.group(0)
        if object_id in seen:
            errors.append(f"معرّف مكرر في فهرس الأحوال الشخصية: {object_id}")
        seen.add(object_id)


def check_no_markdown_counters(errors: list[str]) -> None:
    """ممنوع أن يحمل RESUME_STATE عدّادًا تشريعيًا يزعم أنه حقيقة قاعدة البيانات."""
    resume = ROOT / "RESUME_STATE.md"
    if not resume.exists():
        return
    for line_number, line in enumerate(resume.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("- `legislation_objects_generated`"):
            value = stripped.split(":", 1)[-1].strip().strip("*` ")
            if value != "0":
                errors.append(
                    f"RESUME_STATE.md:{line_number}: عدّاد تشريعي غير صفري في Markdown.\n"
                    "  T-00: الإحصاءات من PostgreSQL فقط (engine/truth_report.py)."
                )


def main() -> int:
    errors: list[str] = []
    check_no_phantom_counts(errors)
    check_object_ids_unique(errors)
    check_no_markdown_counters(errors)

    if errors:
        print("\n".join(errors))
        return 1

    print("OK: البنية سليمة، ولا توجد أعداد وهمية.")
    print("الإحصاءات المعتمدة: python3 engine/truth_report.py (المصدر: PostgreSQL)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
