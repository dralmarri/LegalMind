#!/usr/bin/env python3
"""LegalMind legislation ingestion pipeline.

Accepts .docx, .txt, or .md; preserves extracted source text, detects articles,
creates article objects, and writes a batch report. It does not declare OCR text
human-verified. Python standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ARTICLE_RE = re.compile(r"(?m)^\s*(?:المادة|مادة)\s+([0-9٠-٩]+(?:\s+مكرر(?:اً|ا|ة)?(?:\s*\([^)]*\))?)?)\s*$")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paras = []
    for p in root.findall(".//w:p", ns):
        text = "".join((t.text or "") for t in p.findall(".//w:t", ns)).strip()
        if text:
            paras.append(text)
    return "\n".join(paras)


def read_source(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        return read_docx(path)
    return path.read_text(encoding="utf-8")


def normalize_article_number(raw: str) -> str:
    return re.sub(r"\s+", "-", raw.translate(ARABIC_DIGITS).strip())


def split_articles(text: str) -> list[dict[str, str]]:
    matches = list(ARTICLE_RE.finditer(text))
    articles = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        raw_no = match.group(1).strip()
        articles.append({
            "article_number": normalize_article_number(raw_no),
            "article_label": raw_no,
            "text": text[start:end].strip(),
        })
    return articles


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--law-id", required=True)
    parser.add_argument("--law-name", required=True)
    parser.add_argument("--branch", default="personal-status")
    parser.add_argument("--function", required=True,
                        choices=["substantive", "procedural", "special_procedural", "mixed"])
    parser.add_argument("--output-root", type=Path, default=Path("knowledge-system"))
    args = parser.parse_args()

    text = read_source(args.source)
    digest = hashlib.sha256(args.source.read_bytes()).hexdigest()
    articles = split_articles(text)
    if not articles:
        raise SystemExit("No articles detected; inspect source formatting.")

    now = datetime.now(timezone.utc).isoformat()
    source_dir = args.output_root / "sources" / args.branch / "legislation"
    data_dir = args.output_root / "data" / args.branch / "legislation" / args.law_id
    source_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    immutable_path = source_dir / f"{args.law_id}-extracted-source.md"
    immutable_path.write_text(
        f"# {args.law_name}\n\n"
        f"```yaml\nsource_sha256: {digest}\nsource_file: {args.source.name}\n"
        f"extraction_status: source_extracted_needs_official_text_check\n"
        f"ingested_at: {now}\n```\n\n{text}\n", encoding="utf-8")

    index = {
        "law_id": args.law_id,
        "law_name": args.law_name,
        "branch": args.branch,
        "legal_function": args.function,
        "article_count_detected": len(articles),
        "source_sha256": digest,
        "verification_status": "operationally_accepted",
        "articles": [],
    }
    for article in articles:
        object_id = f"LEG-{args.law_id}-ART-{article['article_number']}"
        article_path = data_dir / f"{object_id}.md"
        article_path.write_text(
            f"# {object_id}\n\n```yaml\n"
            f"id: {object_id}\ntype: legislation\nlaw_id: {args.law_id}\n"
            f"article_number: '{article['article_label']}'\nbranch: أحوال شخصية\n"
            f"legal_function: {args.function}\nverification_status: operationally_accepted\n"
            f"source_sha256: {digest}\n```\n\n> {article['text']}\n",
            encoding="utf-8",
        )
        index["articles"].append({"id": object_id, "path": str(article_path)})

    (data_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"law_id": args.law_id, "articles": len(articles), "sha256": digest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
