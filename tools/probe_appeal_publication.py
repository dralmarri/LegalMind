#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys

import psycopg

sys.path.insert(0, "/opt/LegalMind")
from admin.publication_guard import publication_consistency


def env_value(key: str) -> str | None:
    v = os.environ.get(key)
    if v:
        return v
    for path in ("/opt/LegalMind/deploy/.env", "/opt/LegalMind/deploy/admin.env"):
        try:
            for line in open(path, encoding="utf-8"):
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            pass
    return None


def main() -> int:
    number = sys.argv[1] if len(sys.argv) > 1 else "1049"
    year = sys.argv[2] if len(sys.argv) > 2 else "2004"
    dsn = env_value("DATABASE_URL") or "postgresql://legalmind:legalmind@127.0.0.1:55432/legalmind"
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        info = publication_consistency(cur, number, year)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    # unique and multiple_valid are both healthy states. Only missing evidence fails.
    return 0 if info["status"] in {"unique", "multiple_valid"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
