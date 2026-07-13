#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
import time
import unicodedata
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import psycopg
from psycopg.types.json import Jsonb

ARTICLE_RE = re.compile(r"(?m)^\s*(?:المادة|مادة)\s+([0-9٠-٩]+(?:\s+مكرر(?:اً|ا|ة)?(?:\s*\([^)]*\))?)?)\s*$")
PRINCIPLE_RE = re.compile(r"(?m)^\s*(\d+)\s*[-–.)]\s+")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
VECTOR_SIZE = 384
COLLECTION = os.getenv("QDRANT_COLLECTION", "legalmind_objects_v1")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paras: list[str] = []
    for p in root.findall(".//w:p", ns):
        text = "".join((t.text or "") for t in p.findall(".//w:t", ns)).strip()
        if text:
            paras.append(text)
    return "\n".join(paras)


def read_source(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx(path)
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    raise ValueError(f"Unsupported file type: {suffix}")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u0640", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def slug(value: str) -> str:
    value = normalize_text(value).translate(ARABIC_DIGITS)
    value = re.sub(r"[^\w\-]+", "-", value, flags=re.UNICODE)
    return value.strip("-").upper() or "OBJECT"


def hash_embedding(text: str, size: int = VECTOR_SIZE) -> list[float]:
    vector = [0.0] * size
    tokens = re.findall(r"[\w\u0600-\u06FF]+", normalize_text(text).lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % size
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def split_articles(text: str) -> list[dict]:
    matches = list(ARTICLE_RE.finditer(text))
    objects: list[dict] = []
    seen: dict[str, int] = {}
    for i, match in enumerate(matches):
        raw_no = match.group(1).strip()
        number = re.sub(r"\s+", "-", raw_no.translate(ARABIC_DIGITS))
        seen[number] = seen.get(number, 0) + 1
        suffix = f"-OCC-{seen[number]}" if seen[number] > 1 else ""
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        objects.append({"local_id": f"ART-{number}{suffix}", "title": f"المادة {raw_no}", "text": body, "article_number": raw_no})
    return objects


def split_principles(text: str) -> list[dict]:
    matches = list(PRINCIPLE_RE.finditer(text))
    if not matches:
        return [{"local_id": "PR-1", "title": "المبدأ 1", "text": text.strip(), "principle_number": 1}]
    objects: list[dict] = []
    for i, match in enumerate(matches):
        number = int(match.group(1))
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        objects.append({"local_id": f"PR-{number}", "title": f"المبدأ {number}", "text": body, "principle_number": number})
    return objects


def load_metadata(path: Path) -> dict:
    sidecar = path.with_suffix(path.suffix + ".json")
    if sidecar.exists():
        return json.loads(sidecar.read_text(encoding="utf-8"))
    return {}


def classify(path: Path, text: str, metadata: dict) -> tuple[str, list[dict]]:
    source_type = metadata.get("source_type")
    object_type = metadata.get("object_type")

    if source_type == "legislation" or (not source_type and ARTICLE_RE.search(text)):
        articles = split_articles(text)
        if not articles:
            return "legislation", [{"local_id": "DOC-1", "title": metadata.get("title", path.stem), "text": text}]
        return "legislation", articles

    if source_type in {"judicial_principles_collection", "single_judicial_principle", "judicial_principle", "principles"}:
        return "judicial_principle", split_principles(text)

    if source_type == "full_judgment":
        return "full_judgment", [{"local_id": "JUD-1", "title": metadata.get("title", path.stem), "text": text}]

    if source_type in {"judicial_template", "legal_memorandum"}:
        return source_type, [{"local_id": "TPL-1", "title": metadata.get("title", path.stem), "text": text}]

    return object_type or "legal_document", [{"local_id": "DOC-1", "title": metadata.get("title", path.stem), "text": text}]


def qdrant_request(method: str, path: str, payload: dict | None = None) -> dict:
    base = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(base + path, data=body, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def ensure_collection() -> None:
    try:
        qdrant_request("GET", f"/collections/{COLLECTION}")
    except Exception:
        qdrant_request("PUT", f"/collections/{COLLECTION}", {"vectors": {"size": VECTOR_SIZE, "distance": "Cosine"}})


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def ingest_file(path: Path, archive_root: Path, failed_root: Path) -> dict:
    started = now_iso()
    raw_bytes = path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    metadata = load_metadata(path)
    text = normalize_text(read_source(path))
    object_type, chunks = classify(path, text, metadata)
    branch = metadata.get("branch", "أحوال شخصية")
    topic = metadata.get("topic")
    subtopic = metadata.get("subtopic") or metadata.get("classification_title")
    micro_issue = metadata.get("micro_issue")
    title = metadata.get("title", path.stem)
    source_key = metadata.get("source_key", f"SRC-{digest[:20].upper()}")
    law_id = metadata.get("law_id", slug(path.stem))
    batch_id = f"BATCH-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{digest[:8].upper()}"
    inserted_ids: list[str] = []

    ensure_collection()
    try:
        with psycopg.connect(database_url()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO ingestion_batches(batch_id, source_key, status, report)
                       VALUES (%s,%s,'started',%s)
                       ON CONFLICT (batch_id) DO NOTHING""",
                    (batch_id, source_key, Jsonb({"file": path.name, "started_at": started})),
                )
                cur.execute(
                    """INSERT INTO sources(source_key, source_type, title, file_name, sha256, verification_status, metadata)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (source_key) DO UPDATE SET title=EXCLUDED.title,file_name=EXCLUDED.file_name,
                       sha256=EXCLUDED.sha256,metadata=EXCLUDED.metadata,updated_at=now()""",
                    (source_key, object_type, title, path.name, digest, "operationally_accepted", Jsonb(metadata)),
                )
                points: list[dict] = []
                for chunk in chunks:
                    default_prefixes = {
                        "legislation": f"LEG-{law_id}",
                        "judicial_principle": f"JUR-{slug(branch)}-{slug(topic or title)}",
                        "full_judgment": f"JUD-{slug(branch)}-{slug(topic or title)}",
                        "judicial_template": f"TPL-{slug(branch)}-{slug(topic or title)}",
                        "legal_memorandum": f"MEMO-{slug(branch)}-{slug(topic or title)}",
                    }
                    prefix = metadata.get("id_prefix", default_prefixes.get(object_type, f"OBJ-{slug(branch)}-{slug(topic or title)}"))
                    object_id = prefix + "-" + chunk["local_id"]
                    obj_metadata = {**metadata, **{k: v for k, v in chunk.items() if k not in {"text", "title", "local_id"}}, "batch_id": batch_id, "sha256": digest}
                    cur.execute(
                        """INSERT INTO knowledge_objects(id,object_type,branch,topic,subtopic,micro_issue,title,original_text,normalized_text,source_key,verification_status,metadata)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (id) DO UPDATE SET original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                           source_key=EXCLUDED.source_key,metadata=EXCLUDED.metadata,updated_at=now()""",
                        (object_id, object_type, branch, topic, subtopic, micro_issue, chunk["title"], chunk["text"], normalize_text(chunk["text"]), source_key, "operationally_accepted", Jsonb(obj_metadata)),
                    )
                    inserted_ids.append(object_id)
                    point_id = int.from_bytes(hashlib.sha256(object_id.encode()).digest()[:8], "big") & ((1 << 63) - 1)
                    points.append({"id": point_id, "vector": hash_embedding(chunk["text"]), "payload": {"object_id": object_id, "object_type": object_type, "branch": branch, "topic": topic, "subtopic": subtopic, "micro_issue": micro_issue, "title": chunk["title"], "source_key": source_key}})
                cur.execute(
                    """UPDATE ingestion_batches SET status='completed',object_count=%s,report=%s,completed_at=now() WHERE batch_id=%s""",
                    (len(inserted_ids), Jsonb({"file": path.name, "sha256": digest, "objects": inserted_ids, "source_type": source_type}), batch_id),
                )
            conn.commit()
        if points:
            qdrant_request("PUT", f"/collections/{COLLECTION}/points?wait=true", {"points": points})
        archive_root.mkdir(parents=True, exist_ok=True)
        destination = archive_root / f"{batch_id}__{path.name}"
        shutil.move(str(path), destination)
        sidecar = path.with_suffix(path.suffix + ".json")
        if sidecar.exists():
            shutil.move(str(sidecar), archive_root / f"{batch_id}__{sidecar.name}")
        return {"batch_id": batch_id, "source_key": source_key, "status": "completed", "object_type": object_type, "object_count": len(inserted_ids), "objects": inserted_ids}
    except Exception as exc:
        failed_root.mkdir(parents=True, exist_ok=True)
        if path.exists():
            shutil.move(str(path), failed_root / path.name)
        raise RuntimeError(f"Ingestion failed for {path.name}: {exc}") from exc


def watch(inbox: Path, archive: Path, failed: Path, interval: int) -> None:
    inbox.mkdir(parents=True, exist_ok=True)
    print(f"Watching {inbox}", flush=True)
    while True:
        files = [p for p in sorted(inbox.iterdir()) if p.is_file() and p.suffix.lower() in {".docx", ".txt", ".md"}]
        for path in files:
            try:
                result = ingest_file(path, archive, failed)
                print(json.dumps(result, ensure_ascii=False), flush=True)
            except Exception as exc:
                print(str(exc), file=sys.stderr, flush=True)
        time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="LegalMind automatic knowledge ingestion engine")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("ingest")
    one.add_argument("file", type=Path)
    watch_cmd = sub.add_parser("watch")
    watch_cmd.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()
    root = Path(os.getenv("LEGALMIND_INGEST_ROOT", "/opt/legalmind-ingest"))
    inbox, archive, failed = root / "inbox", root / "archive", root / "failed"
    if args.command == "ingest":
        print(json.dumps(ingest_file(args.file, archive, failed), ensure_ascii=False, indent=2))
    else:
        watch(inbox, archive, failed, args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
