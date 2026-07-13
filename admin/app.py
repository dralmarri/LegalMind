#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import secrets
import shutil
from pathlib import Path
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

APP_ROOT = Path(__file__).resolve().parent
INGEST_ROOT = Path(os.getenv("LEGALMIND_INGEST_ROOT", "/opt/legalmind-ingest"))
INBOX = INGEST_ROOT / "inbox"
ARCHIVE = INGEST_ROOT / "archive"
FAILED = INGEST_ROOT / "failed"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://legalmind:legalmind@127.0.0.1:55432/legalmind")
ADMIN_USER = os.getenv("LEGALMIND_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("LEGALMIND_ADMIN_PASSWORD", "change-me")
MAX_UPLOAD_MB = int(os.getenv("LEGALMIND_MAX_UPLOAD_MB", "100"))
ALLOWED_EXTENSIONS = {".docx", ".txt", ".md"}

app = FastAPI(title="LegalMind Admin", docs_url=None, redoc_url=None)
security = HTTPBasic()
app.mount("/static", StaticFiles(directory=APP_ROOT / "static"), name="static")


def require_auth(credentials: Annotated[HTTPBasicCredentials, Depends(security)]) -> str:
    user_ok = secrets.compare_digest(credentials.username, ADMIN_USER)
    password_ok = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="بيانات الدخول غير صحيحة",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def db_rows(query: str, params: tuple = ()) -> list[dict]:
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                columns = [d.name for d in cur.description] if cur.description else []
                return [dict(zip(columns, row)) for row in cur.fetchall()] if columns else []
    except Exception as exc:
        raise HTTPException(503, f"تعذر الاتصال بقاعدة البيانات: {exc}") from exc


@app.get("/", response_class=HTMLResponse)
def index(_: str = Depends(require_auth)) -> HTMLResponse:
    return HTMLResponse((APP_ROOT / "static" / "index.html").read_text(encoding="utf-8"))


@app.get("/api/stats")
def stats(_: str = Depends(require_auth)) -> dict:
    rows = db_rows("SELECT object_type, COUNT(*) AS count FROM knowledge_objects GROUP BY object_type")
    batches = db_rows("SELECT status, COUNT(*) AS count FROM ingestion_batches GROUP BY status")
    return {
        "objects": {r["object_type"]: r["count"] for r in rows},
        "batches": {r["status"]: r["count"] for r in batches},
        "inbox": len(list(INBOX.glob("*"))) if INBOX.exists() else 0,
        "archive": len([p for p in ARCHIVE.glob("*") if not p.name.endswith(".json")]) if ARCHIVE.exists() else 0,
        "failed": len(list(FAILED.glob("*"))) if FAILED.exists() else 0,
    }


@app.get("/api/jobs")
def jobs(limit: int = 100, _: str = Depends(require_auth)) -> list[dict]:
    limit = max(1, min(limit, 500))
    return db_rows(
        """SELECT batch_id, source_key, status, object_count, relationship_count,
                  started_at, completed_at, report
           FROM ingestion_batches ORDER BY started_at DESC LIMIT %s""",
        (limit,),
    )


@app.get("/api/topics")
def topics(_: str = Depends(require_auth)) -> list[dict]:
    return db_rows(
        """SELECT branch, topic, subtopic, micro_issue, COUNT(*) AS object_count
           FROM knowledge_objects
           GROUP BY branch, topic, subtopic, micro_issue
           ORDER BY branch, topic NULLS LAST, subtopic NULLS LAST, micro_issue NULLS LAST"""
    )


@app.get("/api/documents")
def documents(limit: int = 200, _: str = Depends(require_auth)) -> list[dict]:
    limit = max(1, min(limit, 1000))
    return db_rows(
        """SELECT id, object_type, branch, topic, subtopic, micro_issue, title,
                  verification_status, source_key, created_at
           FROM knowledge_objects ORDER BY created_at DESC LIMIT %s""",
        (limit,),
    )


@app.post("/api/upload")
async def upload(
    files: Annotated[list[UploadFile], File(...)],
    source_type: Annotated[str, Form(...)],
    branch: Annotated[str, Form(...)],
    topic: Annotated[str, Form(...)],
    classification_title: Annotated[str, Form(...)],
    micro_issue: Annotated[str, Form()] = "",
    court_level: Annotated[str, Form()] = "",
    circuit: Annotated[str, Form()] = "",
    _: str = Depends(require_auth),
) -> JSONResponse:
    valid_source_types = {
        "full_judgment",
        "judicial_principles_collection",
        "single_judicial_principle",
        "legislation",
        "judicial_template",
        "legal_memorandum",
    }
    if source_type not in valid_source_types:
        raise HTTPException(400, "نوع المصدر غير مدعوم")
    if not branch.strip() or not topic.strip() or not classification_title.strip():
        raise HTTPException(400, "الفرع والموضوع وعنوان التصنيف حقول إلزامية")

    INBOX.mkdir(parents=True, exist_ok=True)
    accepted: list[dict] = []
    for item in files:
        original_name = Path(item.filename or "upload").name
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"الملف {original_name}: النوع {suffix} غير مدعوم حاليًا")

        target = INBOX / original_name
        if target.exists() or target.with_suffix(target.suffix + ".json").exists():
            target = INBOX / f"{target.stem}-{secrets.token_hex(4)}{target.suffix}"

        total = 0
        with target.open("wb") as output:
            while chunk := await item.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_MB * 1024 * 1024:
                    output.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(413, f"الملف {original_name} يتجاوز {MAX_UPLOAD_MB} ميغابايت")
                output.write(chunk)

        metadata = {
            "source_type": source_type,
            "object_type": "judicial_principle" if source_type in {"judicial_principles_collection", "single_judicial_principle"} else source_type,
            "branch": branch.strip(),
            "topic": topic.strip(),
            "subtopic": classification_title.strip(),
            "classification_title": classification_title.strip(),
            "micro_issue": micro_issue.strip() or None,
            "court_level": court_level.strip() or None,
            "circuit": circuit.strip() or None,
            "title": Path(original_name).stem,
            "upload_origin": "legalmind_admin",
            "drafting_status": "blocked_missing_authorities" if source_type in {"judicial_template", "legal_memorandum"} else None,
        }
        sidecar = target.with_suffix(target.suffix + ".json")
        sidecar.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        accepted.append({"file": target.name, "size": total, "metadata": metadata})

    return JSONResponse({"status": "queued", "files": accepted})


@app.post("/api/requeue/{batch_id}")
def requeue(batch_id: str, _: str = Depends(require_auth)) -> dict:
    matches = list(ARCHIVE.glob(f"{batch_id}__*"))
    source_files = [p for p in matches if not p.name.endswith(".json")]
    if not source_files:
        raise HTTPException(404, "لم يوجد ملف مصدر لهذه الدفعة")
    INBOX.mkdir(parents=True, exist_ok=True)
    moved = []
    for src in source_files:
        original = src.name.split("__", 1)[-1]
        target = INBOX / original
        shutil.copy2(src, target)
        sidecar = ARCHIVE / f"{batch_id}__{original}.json"
        if sidecar.exists():
            shutil.copy2(sidecar, target.with_suffix(target.suffix + ".json"))
        moved.append(target.name)
    return {"status": "requeued", "files": moved}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
