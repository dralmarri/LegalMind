#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import embedding
from normalizer import SUPPORTED_EXTENSIONS, normalize, normalize_text

ARTICLE_RE = re.compile(r"(?m)^\s*(?:المادة|مادة)\s+([0-9٠-٩]+(?:\s+مكرر(?:اً|ا|ة)?(?:\s*\([^)]*\))?)?)\s*$")
PRINCIPLE_RE = re.compile(r"(?m)^\s*(\d+)\s*[-–.)]\s+")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# اسم الـcollection وحجم المتجه يأتيان من engine/embedding.py وحده. لا تُكرَّر هنا.
VECTOR_SIZE = embedding.VECTOR_SIZE
COLLECTION = embedding.COLLECTION


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(value: str) -> str:
    value = normalize_text(value).translate(ARABIC_DIGITS)
    value = re.sub(r"[^\w\-]+", "-", value, flags=re.UNICODE)
    return value.strip("-").upper() or "OBJECT"


def content_digest(text: str) -> str:
    """\u0628\u0635\u0645\u0629 \u0645\u0646\u0639 \u0627\u0644\u062A\u0643\u0631\u0627\u0631: \u0639\u0644\u0649 \u0627\u0644\u0646\u0635 \u0628\u0639\u062F \u0627\u0644\u062A\u0637\u0628\u064A\u0639 \u0627\u0644\u062A\u0642\u0646\u064A\u060C \u0644\u0627 \u0639\u0644\u0649 \u0628\u0627\u064A\u062A\u0627\u062A \u0627\u0644\u0645\u0644\u0641.

    \u0627\u0644\u062A\u0637\u0628\u064A\u0639 \u0627\u0644\u062A\u0642\u0646\u064A \u0644\u0627 \u064A\u063A\u064A\u0651\u0631 \u0627\u0644\u0645\u062D\u062A\u0648\u0649 \u0627\u0644\u0642\u0627\u0646\u0648\u0646\u064A\u060C \u0641\u0645\u0644\u0641 DOCX \u0648\u0646\u0635 \u0645\u0644\u0635\u0642 \u064A\u062D\u0645\u0644\u0627\u0646 \u0627\u0644\u0646\u0635
    \u0646\u0641\u0633\u0647 \u064A\u0639\u0637\u064A\u0627\u0646 \u0627\u0644\u0628\u0635\u0645\u0629 \u0646\u0641\u0633\u0647\u0627 \u2014 \u0648\u0647\u0645\u0627 \u062A\u0643\u0631\u0627\u0631 \u0641\u0639\u0644\u064B\u0627.
    """
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


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


VERIFICATION_STATUSES = {
    "source_verified", "operationally_accepted", "machine_pending_human",
    "historical_only", "requires_post_2026_reassessment", "superseded",
}
# ما لا يُوثَّق من مصدره لا يُستشهد به. القاعدة هنا وفي قيود قاعدة البيانات معًا.
CITABLE_STATUSES = {"source_verified", "operationally_accepted"}


def authority_for(object_type: str, verification_status: str) -> tuple[str, bool]:
    """يشتق سلطة الكائن من حالة توثيقه. لا يُترك ذلك لمن يرفع المصدر.

    القيم مقيدة بـ ko_authority_status_valid. والقاعدة المستنبطة آليًا
    (synthesized_rule) لا تكون سلطة ولا يُستشهد بها البتة — قيد قاعدة بيانات لا عُرف.
    """
    if object_type == "synthesized_rule":
        return "non_authoritative", False
    if verification_status == "source_verified":
        return "source_authority", True
    if verification_status == "operationally_accepted":
        return "human_verified_authority", True
    return "non_authoritative", False


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
        qdrant_request(
            "PUT",
            f"/collections/{COLLECTION}",
            {"vectors": {"size": VECTOR_SIZE, "distance": embedding.DISTANCE}},
        )


def build_points(rows: list[tuple[str, str, str]], common: dict) -> list[dict]:
    """(object_id, title, text) → نقاط Qdrant. التضمين دفعة واحدة، لا نصًا نصًا."""
    vectors = embedding.embed_passages([text for _, _, text in rows])
    points = []
    for (object_id, title, text), vector in zip(rows, vectors):
        points.append({
            "id": embedding.point_id(object_id),
            "vector": vector,
            "payload": {**common, "object_id": object_id, "title": title,
                        **embedding.meta_for(object_id, text).as_payload()},
        })
    return points


def find_duplicate(cur, branch: str, topic: str | None, digest: str) -> dict | None:
    """يعيد الدفعة السابقة إن كان النص نفسه مُدخلًا تحت الفرع والموضوع نفسيهما."""
    cur.execute(
        """SELECT source_key, first_batch_id, title, created_at
           FROM sources
           WHERE content_sha256=%s AND branch=%s AND topic IS NOT DISTINCT FROM %s""",
        (digest, branch, topic),
    )
    row = cur.fetchone()
    if not row:
        return None
    source_key, first_batch_id, title, created_at = row
    cur.execute(
        "SELECT COUNT(*) FROM knowledge_objects WHERE source_key=%s", (source_key,)
    )
    return {
        "source_key": source_key,
        "first_batch_id": first_batch_id,
        "title": title,
        "ingested_at": created_at.isoformat() if created_at else None,
        "object_count": cur.fetchone()[0],
    }


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def ingest_file(path: Path, archive_root: Path, failed_root: Path) -> dict:
    started = now_iso()
    metadata = load_metadata(path)

    # طبقة التطبيع: أي صيغة → Canonical Markdown. ما بعدها لا يعرف صيغة المصدر.
    # المصدر غير المقروء (PDF ممسوح ضوئيًا مثلًا) يُنقل إلى failed فورًا:
    # لو بقي في inbox لأعاد المراقب محاولته إلى ما لا نهاية.
    try:
        canonical = normalize(path)
    except Exception as exc:
        # تُسجَّل دفعة فاشلة تحمل سبب الرفض بالعربية ليقرأه المستخدم في الواجهة.
        # وهي أثر تدقيق فحسب: لا مصدر ولا كائن معرفي يُنشأ — لا سجل فارغ.
        reason = str(exc)
        raw_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        batch_id = f"BATCH-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{raw_sha[:8].upper()}"
        try:
            with psycopg.connect(database_url()) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO ingestion_batches(batch_id, status, report, completed_at)
                           VALUES (%s,'failed',%s,now())
                           ON CONFLICT (batch_id) DO NOTHING""",
                        (batch_id, Jsonb({"file": path.name, "error": reason,
                                          "rejected_at": "normalization"})),
                    )
                conn.commit()
        except Exception:
            pass
        failed_root.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), failed_root / path.name)
        sidecar = path.with_suffix(path.suffix + ".json")
        if sidecar.exists():
            shutil.move(str(sidecar), failed_root / sidecar.name)
        raise RuntimeError(f"{path.name}: {reason}") from exc

    digest = canonical.source_sha256
    text = canonical.body
    # بصمة المحتوى: مفتاح منع التكرار الحاكم (مستقل عن الصيغة).
    content_sha = content_digest(text)

    object_type, chunks = classify(path, text, metadata)
    branch = metadata.get("branch", "أحوال شخصية")
    topic = metadata.get("topic")
    subtopic = metadata.get("subtopic") or metadata.get("classification_title")
    micro_issue = metadata.get("micro_issue")
    title = metadata.get("title", path.stem)
    verification_status = metadata.get("verification_status") or "source_verified"
    if verification_status not in VERIFICATION_STATUSES:
        raise ValueError(f"حالة توثيق غير معروفة: {verification_status}")
    authority_status, usable_as_citation = authority_for(object_type, verification_status)
    source_key = metadata.get("source_key", f"SRC-{content_sha[:20].upper()}")
    law_id = metadata.get("law_id", slug(path.stem))
    batch_id = f"BATCH-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{content_sha[:8].upper()}"
    inserted_ids: list[str] = []

    # منع التكرار قبل أي كتابة: التكرار يُظهر الدفعة السابقة ولا يُنشئ نسخة.
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            duplicate = find_duplicate(cur, branch, topic, content_sha)
            if duplicate:
                cur.execute(
                    """INSERT INTO ingestion_batches(batch_id, source_key, status, report, completed_at)
                       VALUES (%s,%s,'duplicate',%s,now())
                       ON CONFLICT (batch_id) DO NOTHING""",
                    (batch_id, duplicate["source_key"],
                     Jsonb({"file": path.name, "content_sha256": content_sha,
                            "duplicate_of": duplicate})),
                )
            conn.commit()
    if duplicate:
        archive_root.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), archive_root / f"{batch_id}__DUPLICATE__{path.name}")
        sidecar = path.with_suffix(path.suffix + ".json")
        if sidecar.exists():
            shutil.move(str(sidecar), archive_root / f"{batch_id}__DUPLICATE__{sidecar.name}")
        return {"batch_id": batch_id, "status": "duplicate",
                "content_sha256": content_sha, "duplicate_of": duplicate,
                "message": "النص مُدخل مسبقًا تحت الفرع والموضوع نفسيهما. لم تُنشأ نسخة."}

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
                    """INSERT INTO sources(source_key, source_type, title, file_name, sha256,
                                          content_sha256, branch, topic, first_batch_id,
                                          verification_status, metadata)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (source_key) DO UPDATE SET title=EXCLUDED.title,file_name=EXCLUDED.file_name,
                       sha256=EXCLUDED.sha256,metadata=EXCLUDED.metadata,updated_at=now()""",
                    (source_key, object_type, title, path.name, digest, content_sha,
                     branch, topic, batch_id, verification_status,
                     Jsonb({**metadata, "source_format": canonical.source_format,
                            "normalizer_version": canonical.normalizer_version,
                            "normalizer_warnings": canonical.warnings})),
                )
                embed_rows: list[tuple[str, str, str]] = []
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
                    obj_metadata = {**metadata, **{k: v for k, v in chunk.items() if k not in {"text", "title", "local_id"}}, "batch_id": batch_id, "sha256": digest, "content_sha256": content_sha}
                    # حالة التوثيق تأتي من المصدر، والسلطة تُشتق منها لا تُعلن.
                    # المستنبط آليًا لا يصير مستشهدًا به بمجرد رفعه من الواجهة.
                    cur.execute(
                        """INSERT INTO knowledge_objects(id,object_type,branch,topic,subtopic,micro_issue,title,original_text,normalized_text,source_key,verification_status,authority_status,usable_as_citation,metadata)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (id) DO UPDATE SET original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                           source_key=EXCLUDED.source_key,metadata=EXCLUDED.metadata,updated_at=now()""",
                        (object_id, object_type, branch, topic, subtopic, micro_issue, chunk["title"], chunk["text"], normalize_text(chunk["text"]), source_key, verification_status, authority_status, usable_as_citation, Jsonb(obj_metadata)),
                    )
                    inserted_ids.append(object_id)
                    embed_rows.append((object_id, chunk["title"], chunk["text"]))
                cur.execute(
                    """UPDATE ingestion_batches SET status='completed',object_count=%s,report=%s,completed_at=now() WHERE batch_id=%s""",
                    (len(inserted_ids), Jsonb({
                        "file": path.name,
                        "sha256": digest,
                        "content_sha256": content_sha,
                        "objects": inserted_ids,
                        "source_type": metadata.get("source_type"),
                        "source_format": canonical.source_format,
                        "upload_origin": metadata.get("upload_origin"),
                        "normalizer_warnings": canonical.warnings,
                        "embedding_model": embedding.MODEL_ID,
                    }), batch_id),
                )
            conn.commit()
        # الفهرسة بعد إتمام PostgreSQL: قاعدة البيانات مصدر الحقيقة، وQdrant مشتق منها.
        # فشل الفهرسة لا يفقد المعرفة — تُعاد بناؤها بأمر reindex.
        if embed_rows:
            points = build_points(embed_rows, {
                "object_type": object_type, "branch": branch, "topic": topic,
                "subtopic": subtopic, "micro_issue": micro_issue, "source_key": source_key,
            })
            qdrant_request("PUT", f"/collections/{COLLECTION}/points?wait=true", {"points": points})

        archive_root.mkdir(parents=True, exist_ok=True)
        # الصيغة الموحدة تُؤرشف بجوار الأصل: أثر تدقيق لما رآه المستخرج فعلًا.
        (archive_root / f"{batch_id}__{path.stem}.canonical.md").write_text(
            canonical.to_markdown(), encoding="utf-8"
        )
        shutil.move(str(path), archive_root / f"{batch_id}__{path.name}")
        sidecar = path.with_suffix(path.suffix + ".json")
        if sidecar.exists():
            shutil.move(str(sidecar), archive_root / f"{batch_id}__{sidecar.name}")
        return {"batch_id": batch_id, "source_key": source_key, "status": "completed",
                "object_type": object_type, "source_format": canonical.source_format,
                "content_sha256": content_sha, "verification_status": verification_status,
                "object_count": len(inserted_ids), "objects": inserted_ids,
                "warnings": canonical.warnings}
    except Exception as exc:
        # الدفعة الفاشلة تُوسم فاشلة في قاعدة البيانات. دفعة عالقة على 'started' كذبة إحصائية.
        try:
            with psycopg.connect(database_url()) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE ingestion_batches SET status='failed',report=%s,completed_at=now()
                           WHERE batch_id=%s AND status<>'completed'""",
                        (Jsonb({"file": path.name, "error": str(exc)}), batch_id),
                    )
                conn.commit()
        except Exception:
            pass
        failed_root.mkdir(parents=True, exist_ok=True)
        if path.exists():
            shutil.move(str(path), failed_root / path.name)
        raise RuntimeError(f"Ingestion failed for {path.name}: {exc}") from exc


def watch(inbox: Path, archive: Path, failed: Path, interval: int) -> None:
    inbox.mkdir(parents=True, exist_ok=True)
    print(f"Watching {inbox} — formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}", flush=True)
    while True:
        files = [p for p in sorted(inbox.iterdir()) if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
        for path in files:
            try:
                result = ingest_file(path, archive, failed)
                print(json.dumps(result, ensure_ascii=False), flush=True)
            except Exception as exc:
                print(str(exc), file=sys.stderr, flush=True)
        time.sleep(interval)


def reindex(batch_size: int = 64) -> dict:
    """يعيد بناء Qdrant من PostgreSQL بالكامل.

    PostgreSQL مصدر الحقيقة. Qdrant فهرس مشتق: يُحذف ويُعاد بناؤه بلا فقد معرفة.
    """
    qdrant_request("DELETE", f"/collections/{COLLECTION}")
    qdrant_request("PUT", f"/collections/{COLLECTION}",
                   {"vectors": {"size": VECTOR_SIZE, "distance": embedding.DISTANCE}})
    total = 0
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,title,original_text,object_type,branch,topic,subtopic,micro_issue,source_key
                   FROM knowledge_objects ORDER BY id"""
            )
            rows = cur.fetchall()
    for start in range(0, len(rows), batch_size):
        window = rows[start:start + batch_size]
        # التضمين دفعة واحدة لكل نافذة. الحمولة تُبنى لكل نقطة على حدة لأن
        # الكائنات في النافذة نفسها قد تختلف في الفرع والموضوع والمصدر.
        vectors = embedding.embed_passages([row[2] for row in window])
        points = []
        for row, vector in zip(window, vectors):
            object_id, title, text, object_type, branch, topic, subtopic, micro_issue, source_key = row
            points.append({
                "id": embedding.point_id(object_id),
                "vector": vector,
                "payload": {"object_type": object_type, "branch": branch, "topic": topic,
                            "subtopic": subtopic, "micro_issue": micro_issue,
                            "source_key": source_key, "object_id": object_id,
                            "title": title or "",
                            **embedding.meta_for(object_id, text).as_payload()},
            })
        qdrant_request("PUT", f"/collections/{COLLECTION}/points?wait=true", {"points": points})
        total += len(points)
    # العدّ الدقيق لا الحقل المخزّن مؤقتًا: points_count يتأخر عن الحقيقة بعد الكتابة
    # مباشرةً، فالاعتماد عليه يعطي «عدم اتساق» كاذبًا.
    indexed = qdrant_request(
        "POST", f"/collections/{COLLECTION}/points/count", {"exact": True}
    )["result"]["count"]
    return {"status": "reindexed", "collection": COLLECTION, "model": embedding.MODEL_ID,
            "postgres_objects": len(rows), "qdrant_points": indexed,
            "consistent": len(rows) == indexed}


def main() -> int:
    parser = argparse.ArgumentParser(description="LegalMind automatic knowledge ingestion engine")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("ingest")
    one.add_argument("file", type=Path)
    watch_cmd = sub.add_parser("watch")
    watch_cmd.add_argument("--interval", type=int, default=10)
    sub.add_parser("reindex")
    args = parser.parse_args()
    if args.command == "reindex":
        print(json.dumps(reindex(), ensure_ascii=False, indent=2))
        return 0
    root = Path(os.getenv("LEGALMIND_INGEST_ROOT", "/opt/legalmind-ingest"))
    inbox, archive, failed = root / "inbox", root / "archive", root / "failed"
    if args.command == "ingest":
        print(json.dumps(ingest_file(args.file, archive, failed), ensure_ascii=False, indent=2))
    else:
        watch(inbox, archive, failed, args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
