#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import os
import re
import secrets
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from admin.security import verify_password

APP_ROOT = Path(__file__).resolve().parent
INGEST_ROOT = Path(os.getenv("LEGALMIND_INGEST_ROOT", "/opt/legalmind-ingest"))
INBOX = INGEST_ROOT / "inbox"
ARCHIVE = INGEST_ROOT / "archive"
FAILED = INGEST_ROOT / "failed"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://legalmind:legalmind@127.0.0.1:55432/legalmind")
ADMIN_USER = os.getenv("LEGALMIND_ADMIN_USER", "admin")
ADMIN_PASSWORD_HASH = os.getenv("LEGALMIND_ADMIN_PASSWORD_HASH", "")
MAX_UPLOAD_MB = int(os.getenv("LEGALMIND_MAX_UPLOAD_MB", "100"))
ALLOWED_EXTENSIONS = {".docx", ".pdf", ".html", ".htm", ".txt", ".md"}

# حدود النص الملصق. الحد الأدنى يمنع الإدخال العابث، والأعلى يمنع إغراق الخادم.
PASTE_MIN_CHARS = 20
PASTE_MAX_CHARS = int(os.getenv("LEGALMIND_PASTE_MAX_CHARS", "500000"))

SOURCE_TYPES = {
    "full_judgment",
    "judicial_principles_collection",
    "single_judicial_principle",
    "legislation",
    "judicial_template",
    "legal_memorandum",
}
# النص الوارد حرفيًا من مصدره = source_verified. ما يُستنبط آليًا = machine_pending_human.
# القيم مطابقة لقيد قاعدة البيانات في 003. لا تُوسَّع من الواجهة.
VERIFICATION_STATUSES = {
    "source_verified",
    "operationally_accepted",
    "machine_pending_human",
    "historical_only",
    "requires_post_2026_reassessment",
}
PRINCIPLE_TYPES = {"judicial_principles_collection", "single_judicial_principle"}
DEFAULT_SOURCE_TYPE = "single_judicial_principle" if "single_judicial_principle" in SOURCE_TYPES else next(iter(SOURCE_TYPES))

app = FastAPI(title="LegalMind Admin", docs_url=None, redoc_url=None)
security = HTTPBasic()
app.mount("/static", StaticFiles(directory=APP_ROOT / "static"), name="static")


def require_auth(credentials: Annotated[HTTPBasicCredentials, Depends(security)]) -> str:
    if not ADMIN_PASSWORD_HASH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="لم تُضبط تجزئة كلمة مرور المدير (LEGALMIND_ADMIN_PASSWORD_HASH)",
        )
    user_ok = secrets.compare_digest(credentials.username, ADMIN_USER)
    # التحقق يعمل دائمًا حتى مع اسم مستخدم خاطئ حتى لا يسرّب الزمنُ وجودَ الحساب.
    password_ok = verify_password(credentials.password, ADMIN_PASSWORD_HASH)
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


def safe_stem(value: str, fallback: str) -> str:
    """اسم ملف آمن: لا مسارات ولا محارف تحكم. يقبل العربية ويرفض ما عداها من رموز."""
    value = unicodedata.normalize("NFKC", value).strip()
    value = re.sub(r"[^\w؀-ۿ \-]+", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_]+", "-", value).strip("-.")
    return value[:80] or fallback


def build_metadata(
    *, source_type: str, branch: str, topic: str, classification_title: str,
    title: str, micro_issue: str, court_level: str, circuit: str,
    verification_status: str, source_notes: str, upload_origin: str,
) -> dict:
    """حقول التصنيف الإلزامية والاختيارية. مصدر واحد للحقيقة للمسارين معًا."""
    if not source_type.strip():
        source_type = DEFAULT_SOURCE_TYPE
    if source_type not in SOURCE_TYPES:
        raise HTTPException(400, "نوع المصدر غير مدعوم")
    if verification_status not in VERIFICATION_STATUSES:
        raise HTTPException(400, "حالة التوثيق غير معروفة")
    if not branch.strip() or not topic.strip():
        raise HTTPException(400, "الفرع والموضوع حقلان إلزاميان")
    # عنوان التصنيف اختياري: إن غاب يُشتق من الموضوع، ويبقى تحليلًا معلقًا للمراجعة.
    if not classification_title.strip():
        classification_title = topic.strip()
    return {
        "source_type": source_type,
        "object_type": "judicial_principle" if source_type in PRINCIPLE_TYPES else source_type,
        "branch": branch.strip(),
        "topic": topic.strip(),
        "subtopic": classification_title.strip(),
        "classification_title": classification_title.strip(),
        "micro_issue": micro_issue.strip() or None,
        "court_level": court_level.strip() or None,
        "circuit": circuit.strip() or None,
        "title": title.strip(),
        "verification_status": verification_status,
        "source_notes": source_notes.strip() or None,
        "upload_origin": upload_origin,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "drafting_status": "blocked_missing_authorities" if source_type in {"judicial_template", "legal_memorandum"} else None,
    }


def reserve_inbox_path(stem: str, suffix: str) -> Path:
    """مسار فريد داخل inbox. لا يدهس ملفًا قائمًا ولا ينتظر دفعة قيد المعالجة."""
    INBOX.mkdir(parents=True, exist_ok=True)
    target = INBOX / f"{stem}{suffix}"
    if target.exists() or target.with_suffix(target.suffix + ".json").exists():
        target = INBOX / f"{stem}-{secrets.token_hex(4)}{suffix}"
    return target


@app.post("/api/upload")
async def upload(
    files: Annotated[list[UploadFile], File(...)],
    source_type: Annotated[str, Form(...)],
    branch: Annotated[str, Form(...)],
    topic: Annotated[str, Form(...)],
    classification_title: Annotated[str, Form(...)],
    source_title: Annotated[str, Form()] = "",
    micro_issue: Annotated[str, Form()] = "",
    court_level: Annotated[str, Form()] = "",
    circuit: Annotated[str, Form()] = "",
    verification_status: Annotated[str, Form()] = "source_verified",
    source_notes: Annotated[str, Form()] = "",
    _: str = Depends(require_auth),
) -> JSONResponse:
    if not files or all(not (f.filename or "").strip() for f in files):
        raise HTTPException(400, "لم يُرفَع أي ملف")

    accepted: list[dict] = []
    for item in files:
        original_name = Path(item.filename or "upload").name
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                400,
                f"الملف {original_name}: الامتداد {suffix or '(بلا امتداد)'} غير مدعوم. "
                f"الصيغ المقبولة: {'، '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        metadata = build_metadata(
            source_type=source_type, branch=branch, topic=topic,
            classification_title=classification_title,
            title=source_title or Path(original_name).stem,
            micro_issue=micro_issue, court_level=court_level, circuit=circuit,
            verification_status=verification_status, source_notes=source_notes,
            upload_origin="file_upload",
        )
        metadata["original_filename"] = original_name

        target = reserve_inbox_path(safe_stem(Path(original_name).stem, "source"), suffix)
        total = 0
        with target.open("wb") as output:
            while chunk := await item.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_MB * 1024 * 1024:
                    output.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(413, f"الملف {original_name} يتجاوز الحد المسموح ({MAX_UPLOAD_MB} ميغابايت)")
                output.write(chunk)
        if total == 0:
            target.unlink(missing_ok=True)
            raise HTTPException(400, f"الملف {original_name} فارغ")

        # الـsidecar يُكتب بعد الملف: وجوده يعني أن المصدر مكتمل وجاهز للمعالجة.
        target.with_suffix(target.suffix + ".json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        accepted.append({"file_id": target.name, "size_bytes": total, "status": "queued",
                         "metadata": metadata})

    return JSONResponse({"status": "queued", "files": accepted})


@app.post("/api/paste-text")
async def paste_text(
    content: Annotated[str, Form(...)],
    branch: Annotated[str, Form(...)],
    topic: Annotated[str, Form(...)],
    source_type: Annotated[str, Form()] = "",
    classification_title: Annotated[str, Form()] = "",
    source_title: Annotated[str, Form()] = "",
    micro_issue: Annotated[str, Form()] = "",
    court_level: Annotated[str, Form()] = "",
    circuit: Annotated[str, Form()] = "",
    verification_status: Annotated[str, Form()] = "source_verified",
    source_notes: Annotated[str, Form()] = "",
    _: str = Depends(require_auth),
) -> JSONResponse:
    """لصق نص قانوني مباشرة. يمرّ على محرك الإدخال نفسه الذي يمرّ عليه الملف."""
    text = content.strip()
    if not text:
        raise HTTPException(400, "النص فارغ. الصق نص المصدر القانوني قبل الحفظ.")
    if len(text) < PASTE_MIN_CHARS:
        raise HTTPException(
            400,
            f"النص قصير جدًا ({len(text)} حرفًا). الحد الأدنى {PASTE_MIN_CHARS} حرفًا "
            "حتى لا يُنشأ مصدر بلا مضمون.",
        )
    if len(text) > PASTE_MAX_CHARS:
        raise HTTPException(
            413,
            f"النص يتجاوز الحد المسموح ({len(text):,} حرفًا والحد {PASTE_MAX_CHARS:,}). "
            "قسّمه إلى مصادر أصغر أو ارفعه ملفًا.",
        )
    if not source_title.strip():
        _first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        source_title = (_first[:120] if _first
                        else "مصدر-ملصوق-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12])

    metadata = build_metadata(
        source_type=source_type, branch=branch, topic=topic,
        classification_title=classification_title, title=source_title,
        micro_issue=micro_issue, court_level=court_level, circuit=circuit,
        verification_status=verification_status, source_notes=source_notes,
        upload_origin="pasted_text",
    )
    metadata["pasted_chars"] = len(text)

    # الأصل يُحفظ Markdown كما لُصق حرفيًا — لا تحرير ولا تشذيب ولا إعادة صياغة.
    # التطبيع يجري لاحقًا في المحرك على نسخة، ويبقى هذا الملف أثرًا غير قابل للتغيير.
    target = reserve_inbox_path(safe_stem(source_title, "pasted-source"), ".md")
    target.write_text(text + "\n", encoding="utf-8")
    target.chmod(0o444)
    target.with_suffix(target.suffix + ".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return JSONResponse({
        "status": "queued",
        "file_id": target.name,
        "chars": len(text),
        "upload_origin": "pasted_text",
        "metadata": metadata,
        "message": "حُفظ النص وبدأت معالجته.",
    })


@app.get("/api/file-status/{file_id}")
def file_status(file_id: str, _: str = Depends(require_auth)) -> dict:
    """حالة معالجة مصدر بعينه — تتبعها الواجهة بالاستقصاء بعد الحفظ."""
    file_id = Path(file_id).name
    rows = db_rows(
        """SELECT batch_id, status, object_count, report, started_at, completed_at
           FROM ingestion_batches
           WHERE report->>'file' = %s ORDER BY started_at DESC LIMIT 1""",
        (file_id,),
    )
    if rows:
        row = rows[0]
        report = row.get("report") or {}
        return {
            "file_id": file_id,
            "status": row["status"],
            "batch_id": row["batch_id"],
            "object_count": row["object_count"],
            "duplicate_of": report.get("duplicate_of"),
            "error": report.get("error"),
            "content_sha256": report.get("content_sha256"),
        }
    if (INBOX / file_id).exists():
        return {"file_id": file_id, "status": "queued"}
    if (FAILED / file_id).exists():
        return {"file_id": file_id, "status": "failed",
                "error": "فشلت المعالجة. راجع سجل الخدمة legalmind-ingest."}
    return {"file_id": file_id, "status": "unknown"}


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


# ─── البحث الدلالي (استرجاع لا توليد) ───────────────────────────────────────
import subprocess
import urllib.request as _urlreq

QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
COLLECTION = os.getenv("LEGALMIND_COLLECTION", "legalmind_multilingual_e5_base_v1")
ENGINE_PY = "/opt/LegalMind/.venv/bin/python"
EMBED_CLI = "/opt/LegalMind/engine/embed_query_cli.py"


def _embed_query(text: str) -> list[float]:
    """يولّد متجه السؤال عبر مفسّر المحرّك (حيث sentence_transformers)."""
    proc = subprocess.run([ENGINE_PY, EMBED_CLI], input=text,
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise HTTPException(500, f"تعذّر توليد متجه السؤال: {proc.stderr[-300:]}")
    vec = json.loads(proc.stdout.strip() or "[]")
    if not vec:
        raise HTTPException(400, "سؤال فارغ")
    return vec


def _qdrant_search(vector: list[float], limit: int, flt: dict | None) -> list[dict]:
    body = {"vector": vector, "limit": limit, "with_payload": True}
    if flt:
        body["filter"] = flt
    data = json.dumps(body).encode("utf-8")
    req = _urlreq.Request(f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
                          data=data, method="POST",
                          headers={"Content-Type": "application/json"})
    with _urlreq.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read()).get("result", [])


@app.get("/api/search")
def search(q: str, branch: str = "", topic: str = "", limit: int = 10,
           _: str = Depends(require_auth)) -> dict:
    """بحث دلالي: يُرجع النص الأصلي الموثّق مرتّبًا بالتشابه. لا يولّد استنباطًا."""
    q = (q or "").strip()
    if len(q) < 2:
        raise HTTPException(400, "اكتب سؤالًا لا يقل عن حرفين")
    limit = max(1, min(limit, 50))
    vector = _embed_query(q)

    must = []
    if branch.strip():
        must.append({"key": "branch", "match": {"value": branch.strip()}})
    if topic.strip():
        must.append({"key": "topic", "match": {"value": topic.strip()}})
    flt = {"must": must} if must else None

    hits = _qdrant_search(vector, limit, flt)
    if not hits:
        return {"query": q, "count": 0, "results": []}

    # اجلب النصوص الكاملة من PostgreSQL (مصدر الحقيقة) بمعرّفات النتائج
    ids = [h["payload"].get("object_id") for h in hits if h.get("payload", {}).get("object_id")]
    rows = db_rows(
        """SELECT id, object_type, branch, topic, subtopic, micro_issue, title,
                  original_text, source_key, verification_status, authority_status,
                  usable_as_citation
           FROM knowledge_objects WHERE id = ANY(%s)""",
        (ids,),
    )
    by_id = {r["id"]: r for r in rows}
    results = []
    for h in hits:
        oid = h["payload"].get("object_id")
        row = by_id.get(oid)
        if not row:
            continue
        results.append({
            "score": round(h.get("score", 0), 4),
            "object_id": oid,
            "object_type": row["object_type"],
            "branch": row["branch"], "topic": row["topic"],
            "subtopic": row["subtopic"], "micro_issue": row["micro_issue"],
            "title": row["title"],
            "text": row["original_text"],
            "source_key": row["source_key"],
            "verification_status": row["verification_status"],
            "authority_status": row["authority_status"],
            "usable_as_citation": row["usable_as_citation"],
        })
    return {"query": q, "count": len(results), "results": results}
