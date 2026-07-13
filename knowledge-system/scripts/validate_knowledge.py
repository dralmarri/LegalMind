#!/usr/bin/env python3
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
LEGISLATION_DIR = ROOT / "data" / "personal-status" / "legislation"


def main() -> int:
    errors: list[str] = []
    total = 0
    index_count = 0

    for index_path in sorted(LEGISLATION_DIR.glob("KW-*.index.json")):
        index_count += 1
        index = json.loads(index_path.read_text(encoding="utf-8"))
        jsonl_path = ROOT.parent / index["jsonl_path"]
        if not jsonl_path.exists():
            errors.append(f"Missing JSONL file: {jsonl_path}")
            continue

        seen: set[str] = set()
        count = 0
        for line_number, line in enumerate(jsonl_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{jsonl_path}:{line_number}: {exc}")
                continue
            object_id = obj.get("id")
            if not object_id:
                errors.append(f"{jsonl_path}:{line_number}: missing id")
            elif object_id in seen:
                errors.append(f"Duplicate object id: {object_id}")
            seen.add(object_id)
            count += 1

        expected = index.get("article_count_detected")
        if expected is None:
            errors.append(f"{index_path}: missing article_count_detected")
        elif count != expected:
            errors.append(f"{index_path}: expected {expected}, got {count}")
        total += count

    report_path = LEGISLATION_DIR / "INGESTION_REPORT.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        expected_total = report.get("total_legislation_objects", report.get("total_articles"))
        if expected_total is None:
            errors.append("INGESTION_REPORT.json: missing total_legislation_objects/total_articles")
        elif expected_total != total:
            errors.append(f"Expected total {expected_total}, got {total}")

    if index_count == 0:
        errors.append(f"No legislation indexes found in {LEGISLATION_DIR}")

    if errors:
        print("\n".join(errors))
        return 1

    print(f"OK: {total} legislation objects validated across {index_count} laws")
    return 0


if __name__ == "__main__":
    sys.exit(main())
