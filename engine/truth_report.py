#!/usr/bin/env python3
"""T-00 Truth Layer — العدّاد الوحيد المعتمد في المشروع.

قاعدة حاكمة: كل إحصاءة عن المعرفة تأتي من PostgreSQL. لا من Markdown،
ولا من تقرير، ولا من وثيقة، ولا من محادثة.

سبب وجود هذا الملف: أعلن المشروع 869 مادة تشريعية لم توجد قط، لأن العدّ
جاء من تقرير Markdown بدل قاعدة البيانات. لا يتكرر ذلك.

    python3 engine/truth_report.py           # تقرير مقروء
    python3 engine/truth_report.py --json    # للأدوات
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

import psycopg

TABLES = [
    "sources", "knowledge_objects", "relationships", "verification_issues",
    "ingestion_batches", "legal_cases", "case_documents", "case_authorities",
    "case_drafts",
]
TEST_BRANCH = "اختبار"


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def qdrant_points() -> int | None:
    base = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
    collection = os.getenv("QDRANT_COLLECTION", "legalmind_objects_v1")
    request = urllib.request.Request(
        f"{base}/collections/{collection}/points/count",
        data=json.dumps({"exact": True}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read())["result"]["count"]
    except Exception:
        return None


def collect() -> dict:
    with psycopg.connect(database_url(), connect_timeout=5) as conn:
        with conn.cursor() as cur:
            rows = {}
            for table in TABLES:
                cur.execute(f"SELECT count(*) FROM {table}")
                rows[table] = cur.fetchone()[0]

            cur.execute(
                "SELECT object_type, count(*) FROM knowledge_objects GROUP BY 1 ORDER BY 2 DESC"
            )
            by_type = dict(cur.fetchall())

            cur.execute(
                "SELECT branch, count(*) FROM knowledge_objects GROUP BY 1 ORDER BY 2 DESC"
            )
            by_branch = dict(cur.fetchall())

            cur.execute(
                "SELECT count(*) FROM knowledge_objects WHERE branch = %s", (TEST_BRANCH,)
            )
            test_objects = cur.fetchone()[0]

            cur.execute("SELECT status, count(*) FROM ingestion_batches GROUP BY 1")
            batches = dict(cur.fetchall())

    real_objects = rows["knowledge_objects"] - test_objects
    return {
        "tables": rows,
        "objects_by_type": by_type,
        "objects_by_branch": by_branch,
        "batches_by_status": batches,
        "test_objects": test_objects,
        "real_legal_objects": real_objects,
        "qdrant_points": qdrant_points(),
        "knowledge_base_empty": real_objects == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LegalMind truth report (PostgreSQL is the only source)")
    parser.add_argument("--json", action="store_true", help="مخرج JSON")
    args = parser.parse_args()

    truth = collect()
    if args.json:
        print(json.dumps(truth, ensure_ascii=False, indent=2))
        return 0

    print("=== LegalMind — التقرير الحقيقي (المصدر: PostgreSQL) ===\n")
    for table, count in truth["tables"].items():
        print(f"  {table:<22} {count:>6}")

    print(f"\n  كائنات معرفية حقيقية   {truth['real_legal_objects']:>6}")
    print(f"  كائنات تجريبية         {truth['test_objects']:>6}")
    points = truth["qdrant_points"]
    print(f"  نقاط Qdrant            {points if points is not None else 'غير متاح':>6}")

    if truth["objects_by_type"]:
        print("\n  حسب النوع:")
        for name, count in truth["objects_by_type"].items():
            print(f"    {name:<24} {count:>5}")

    if truth["objects_by_branch"]:
        print("\n  حسب الفرع:")
        for name, count in truth["objects_by_branch"].items():
            print(f"    {name:<24} {count:>5}")

    if truth["knowledge_base_empty"]:
        print("\n  ⚠️  قاعدة المعرفة فارغة من أي معرفة قانونية حقيقية.")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
