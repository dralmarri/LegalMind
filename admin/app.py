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
    _html = (APP_ROOT / "static" / "index.html").read_text(encoding="utf-8")
    if "legalmind-edit-inject" not in _html:
        if "</body>" in _html:
            _html = _html.replace("</body>", _EDIT_INJECT + "</body>", 1)
        else:
            _html = _html + _EDIT_INJECT
    return HTMLResponse(_html)


@app.get("/api/stats")
def stats(_: str = Depends(require_auth)) -> dict:
    rows = db_rows("SELECT object_type, COUNT(*) AS count FROM knowledge_objects GROUP BY object_type")
    batches = db_rows("SELECT status, COUNT(*) AS count FROM ingestion_batches GROUP BY status")
    laws = db_rows(
        "SELECT COUNT(DISTINCT substring(id from '^(legis-[0-9]+-[0-9]+)')) AS count "
        "FROM knowledge_objects WHERE object_type IN "
        "('legislation_article','legislation_issuing_article','legislation_preamble')")
    return {
        "objects": {r["object_type"]: r["count"] for r in rows},
        "laws": (laws[0]["count"] if laws else 0),
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


# ─── رفع مستند DOCX هرمي: معاينة ثم اعتماد ثم إدخال ─────────────────────────
import sys as _sys
if "/opt/LegalMind/tools" not in _sys.path:
    _sys.path.insert(0, "/opt/LegalMind/tools")
import kpkg_docx

SESS_DIR = INGEST_ROOT / ".docx_sessions"


_MULTI_EXT = {"docx", "pdf", "txt", "md", "markdown", "json", "html", "htm"}


def _save_session(branch, records):
    SESS_DIR.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(8)
    (SESS_DIR / f"{token}.json").write_text(
        json.dumps({"branch": branch, "records": records}, ensure_ascii=False),
        encoding="utf-8")
    return {"token": token, "branch": branch,
            "principle_count": len(records), "tree": kpkg_docx.tree(records)}


@app.post("/api/docx/preview")
async def docx_preview(file: Annotated[UploadFile, File(...)],
                       branch: str = Form(""),
                       _: str = Depends(require_auth)) -> dict:
    """يرفع مستندًا (docx/pdf/txt/md/json/html) ويحلّله هرميًّا للمعاينة (بلا إدخال)."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"الملف يتجاوز {MAX_UPLOAD_MB} ميغابايت")
    if not data:
        raise HTTPException(400, "ملف فارغ")
    ext = os.path.splitext(file.filename or "")[1].lower().lstrip(".") or "txt"
    if ext not in _MULTI_EXT:
        raise HTTPException(400, f"صيغة غير مدعومة: {ext}")
    try:
        branch2, records = kpkg_docx.parse_any(data, ext, (branch.strip() or None))
    except Exception as exc:
        raise HTTPException(400, f"تعذّر تحليل الملف: {str(exc)[:150]}")
    if not records:
        raise HTTPException(400, "لم تُكتشف عناصر مرقّمة أو مواد في الملف")
    return _save_session(branch2, records)


@app.post("/api/docx/preview-text")
async def docx_preview_text(text: Annotated[str, Form()], branch: str = Form(""),
                            _: str = Depends(require_auth)) -> dict:
    """يحلّل نصًّا ملصوقًا هرميًّا (أول سطر = الفرع، أو مرّر branch)."""
    if not text.strip():
        raise HTTPException(400, "النص فارغ")
    if len(text.encode("utf-8")) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, "النص كبير جدًا")
    try:
        branch2, records = kpkg_docx.parse_text(text, (branch.strip() or None))
    except Exception as exc:
        raise HTTPException(400, f"تعذّر التحليل: {str(exc)[:150]}")
    if not records:
        raise HTTPException(400, "لم تُكتشف عناصر مرقّمة أو مواد في النص")
    return _save_session(branch2, records)


@app.post("/api/docx/ingest")
async def docx_ingest(body: dict, _: str = Depends(require_auth)) -> dict:
    """يعتمد الشجرة (مع تصحيحاتها) ويولّد ملفات inbox ليعالجها المحرّك."""
    token = str(body.get("token", ""))
    overrides = body.get("overrides") or None
    sess = SESS_DIR / f"{token}.json"
    if not token or not sess.exists():
        raise HTTPException(404, "جلسة المعاينة غير موجودة أو انتهت — أعد رفع الملف")
    data = json.loads(sess.read_text(encoding="utf-8"))
    res = kpkg_docx.generate_inbox(data["records"], str(INBOX), overrides=overrides)
    sess.unlink(missing_ok=True)
    return {"status": "queued", "files": res["files"], "principles": res["principles"]}


# ==================== استوديو الصياغة — /api/draft ====================
from pydantic import BaseModel as _DraftBase
from typing import Optional as _DraftOpt
import subprocess as _dsp, json as _djson, os as _dos, urllib.request as _durl

_DRAFT_MODEL = _dos.environ.get("LEGALMIND_DRAFT_MODEL", "claude-fable-5")
_DRAFT_QDRANT = "http://127.0.0.1:6333"
_DRAFT_COLL = "legalmind_multilingual_e5_base_v1"

def _draft_env(key: str):
    v = _dos.environ.get(key)
    if v:
        return v
    try:
        for line in open("/opt/LegalMind/deploy/.env", encoding="utf-8"):
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None

def _draft_embed(text: str):
    env = dict(_dos.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    p = _dsp.run(
        ["/opt/LegalMind/.venv/bin/python", "/opt/LegalMind/engine/embed_query_cli.py"],
        input=text.encode("utf-8"), capture_output=True,
        cwd="/opt/LegalMind", env=env, timeout=240,
    )
    if p.returncode != 0:
        raise RuntimeError("embed failed: " + p.stderr.decode("utf-8", "replace")[-400:])
    return _djson.loads(p.stdout.decode("utf-8"))

def _draft_embed_multi(texts):
    """تضمين عدة استعلامات بتحميل واحد للنموذج."""
    env = dict(_dos.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    p = _dsp.run(
        ["/opt/LegalMind/.venv/bin/python", "/opt/LegalMind/engine/embed_queries_multi.py"],
        input=_djson.dumps(texts, ensure_ascii=False).encode("utf-8"),
        capture_output=True, cwd="/opt/LegalMind", env=env, timeout=300,
    )
    if p.returncode != 0:
        raise RuntimeError("multi-embed failed: " + p.stderr.decode("utf-8", "replace")[-400:])
    return _djson.loads(p.stdout.decode("utf-8"))

def _draft_subqueries(client, request_type, facts, madhab):
    """تفكيك الطلب إلى محاور بحث قانونية عبر Haiku، مع بديل حتمي عند الفشل."""
    try:
        r = client.messages.create(
            model="claude-haiku-4-5", max_tokens=800,
            system=("فكك الطلب القانوني إلى 3-6 استعلامات بحث قصيرة (3-8 كلمات لكل استعلام) "
                    "تغطي المسائل القانونية المتمايزة فيه: سبب الدعوى/الطعن، كل طلب مالي أو موضوعي، "
                    "والإجراءات السابقة الواجبة إن وجدت. استعمل ألفاظ المشرع الكويتي ومرادفاتها "
                    "(مثل: التفريق للإضرار بجانب التطليق للضرر؛ فرقة الزواج بجانب الطلاق). "
                    "أجب بمصفوفة JSON من السلاسل فقط دون أي نص آخر."),
            messages=[{"role": "user", "content": "نوع الطلب: " + request_type
                       + ("\nالمذهب: " + madhab if madhab else "") + "\nالوقائع: " + facts[:2000]}],
        )
        txt = "".join(b.text for b in r.content if b.type == "text").strip()
        if txt.startswith("```"):
            txt = txt.strip("`").lstrip("json").strip()
        arr = _djson.loads(txt)
        subs = [s.strip() for s in arr if isinstance(s, str) and len(s.strip()) > 3][:6]
        if subs:
            return subs
    except Exception:
        pass
    # بديل حتمي: تقطيع الوقائع إلى عبارات
    import re as _re
    parts = [p.strip() for p in _re.split(r"[،.;؛\n]+", facts) if len(p.strip()) > 8]
    return ([request_type] + parts)[:6]

def _draft_search(vector, types, limit):
    body = _djson.dumps({
        "vector": vector, "limit": limit, "with_payload": True,
        "filter": {"must": [{"key": "object_type", "match": {"any": types}}]},
    }).encode("utf-8")
    req = _durl.Request(
        _DRAFT_QDRANT + "/collections/" + _DRAFT_COLL + "/points/search",
        data=body, headers={"Content-Type": "application/json"},
    )
    with _durl.urlopen(req, timeout=30) as r:
        return _djson.loads(r.read())["result"]

def _draft_fetch_texts(ids):
    import psycopg
    dsn = _draft_env("DATABASE_URL") or \
        "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    out = {}
    if not ids:
        return out
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, object_type, branch, topic, subtopic, title, original_text "
            "FROM knowledge_objects WHERE id = ANY(%s)", (list(ids),))
        for i, ot, br, tp, st, ti, tx in cur.fetchall():
            out[i] = {"object_type": ot, "branch": br, "topic": tp,
                      "subtopic": st, "title": ti, "text": tx}
    return out

_AR_DIAC = re.compile("[\u0640\u064B-\u0652\u0670]")
def _draft_norm_ar(t):
    for a, b in [("أ","ا"),("إ","ا"),("آ","ا"),("ى","ي"),("ة","ه"),("ؤ","و"),("ئ","ي")]:
        t = t.replace(a, b)
    # إزالة التشكيل (الفتحة/الضمة/الكسرة/الشدة/السكون/التنوين/الألف الخنجرية) والتطويل
    t = _AR_DIAC.sub("", t)
    return t

# أزواج جذور مترادفة عند المشرع: لفظ المستخدم قد يخالف لفظ النص
_DRAFT_SYN_SUB = [("طليق", "فريق"), ("طلاق", "فريق"), ("طلاق", "فرقه"), ("ضرر", "ضرار")]

def _draft_word_variants(w):
    vs = {w}
    for a, b in _DRAFT_SYN_SUB:
        if a in w:
            vs.add(w.replace(a, b))
        if b in w:
            vs.add(w.replace(b, a))
    return sorted(vs)

def _draft_lexical(subqueries, facts="", per_q=3):
    """بحث معجمي مباشر في مواد التشريعات لضمان حضور المواد المطابقة لفظيًا،
    مع توسيع مرادفات المشرع (تطليق↔تفريق، ضرر↔إضرار) داخل الاستعلام نفسه."""
    import psycopg, re as _re
    dsn = _draft_env("DATABASE_URL") or \
        "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    probes = list(subqueries or [])
    probes += [p.strip() for p in _re.split(r"[،.;؛\n]+", facts or "") if len(p.strip()) > 8][:6]
    ids = []

    def _run(cur, words):
        groups, params = [], []
        for w in words:
            vs = _draft_word_variants(w)
            groups.append("(" + " OR ".join(["normalized_text LIKE %s"] * len(vs)) + ")")
            params += ["%" + v + "%" for v in vs]
        cur.execute(
            "SELECT id FROM knowledge_objects WHERE object_type IN "
            "('legislation_article','legislation_issuing_article') AND "
            + " AND ".join(groups)
            + " ORDER BY length(original_text) ASC LIMIT %s",
            tuple(params) + (per_q,))
        return [r[0] for r in cur.fetchall()]

    try:
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            for q in probes:
                words = [_draft_norm_ar(w.lstrip("الوبفكل")) for w in _re.split(r"\s+", q)
                         if len(w) >= 4]
                words = [w for w in words if len(w) >= 3][:3]
                if len(words) < 2:
                    continue
                ids.extend(_run(cur, words))
                if len(words) == 3:
                    ids.extend(_run(cur, words[:2]))
    except Exception:
        pass
    return ids

# حزم تشريعية حاكمة: أي مطالبة تُطلق كلماتها تجرّ فصلها الحاكم كاملًا،
# فتُضمن المواد ولو لم يطابقها البحث الدلالي أو المعجمي (مثال: نفقة الأولاد فصلها «نفقة الأقارب» 200-207).
# كل حزمة: (الاسم، كلمات الإطلاق، بادئة معرّف القانون، أرقام المواد، النطاق المذهبي).
# النطاق: "both" (للمذهبين) | "sunni" (سنّي فقط) | "jaafari" (جعفري فقط).
_DRAFT_BUNDLES = [
    # إجرائي (قانون محكمة الأسرة 12/2015) — مركز تسوية المنازعات الأسرية، ملزم للسنّي والجعفري معًا
    ("الإجراء المسبق: مركز تسوية المنازعات الأسرية",
     ["ضرر", "تطليق", "تفريق", "طلاق", "فرقه", "خلع", "نفقه", "حضان", "متعه", "عده", "زوج"],
     "legis-12-2015", [8, 9, 10, 11], "both"),
    # موضوعي سنّي (قانون 51/1984)
    ("التفريق للضرر والتحكيم (سنّي)", ["ضرر", "ضرار", "تطليق", "تفريق", "طلاق", "فرقه"],
     "legis-51-1984", list(range(126, 133)), "sunni"),      # 126-132
    ("نفقة الزوجة (سنّي)", ["نفقه زوجيه", "نفقه الزوجه", "نفقه", "امتناع عن الانفاق"],
     "legis-51-1984", [74, 75, 76, 77, 78, 79], "sunni"),
    ("نفقة الأقارب/الأولاد (سنّي)", ["اولاد", "ولد", "ولدين", "صغير", "صغار", "اقارب", "ابناء", "المحضون"],
     "legis-51-1984", list(range(200, 208)), "sunni"),      # 200-207
    ("الحضانة وأجرة المسكن (سنّي)", ["حضان", "حاضنه", "مسكن", "سائق", "سايق", "انتقال", "المحضون"],
     "legis-51-1984", list(range(189, 200)), "sunni"),      # 189-199
    ("المتعة ونفقة العدة (سنّي)", ["متعه", "عده", "عدتها"], "legis-51-1984", [162, 165], "sunni"),
    # موضوعي جعفري (قانون 124/2019) — الفرقة القضائية عبر الشقاق والحكمين لا «التطليق للضرر»
    ("الفرقة القضائية والشقاق (جعفري)", ["ضرر", "ضرار", "تطليق", "تفريق", "طلاق", "فرقه", "شقاق", "عسر", "حرج"],
     "legis-124-2019", [109, 135, 136, 137, 138, 157, 158], "jaafari"),
    ("الخلع (جعفري)", ["خلع", "ايذاء", "اساءه", "ظلم"],
     "legis-124-2019", [185, 186, 193, 195], "jaafari"),
    ("نفقة الزوجة (جعفري)", ["نفقه زوجيه", "نفقه الزوجه", "نفقه", "امتناع عن الانفاق"],
     "legis-124-2019", [99, 105], "jaafari"),
    ("نفقة الأولاد (جعفري)", ["اولاد", "ولد", "ولدين", "صغير", "صغار", "اقارب", "ابناء", "المحضون"],
     "legis-124-2019", [119], "jaafari"),
    ("نفقة العدة (جعفري)", ["عده", "عدتها"], "legis-124-2019", [103, 199], "jaafari"),
    # ── مرسوم بقانون 53/2026: تنظيم إجراءات دعاوى النسب وتصحيح الأسماء (إجرائيّ، للمذهبين) ──
    # لجنةٌ دائمةٌ بوزارة العدل تختصّ دون غيرها؛ التحقيق أمامها شرطُ قبول دعوى النسب (م8). موضوعان:
    ("دعاوى النسب — اللجنة والاختصاص والإجراء المسبق والتظلم والعقوبة (53/2026)",
     ["نسب", "اثبات النسب", "نفي النسب", "النسب المباشر", "النسب غير المباشر", "دعوى نسب", "دعوى النسب",
      "لجنه النسب", "لجنه دعاوى النسب", "الحاق نسب", "استلحاق", "اثبات البنوه", "نفي البنوه"],
     "legis-53-2026", [1, 3, 4, 8, 9, 10, 13, 14, 16, 17, 18, 19], "both"),
    ("تصحيح الأسماء وتغييرها — اللجنة والقيود والتظلم (53/2026)",
     ["تصحيح الاسم", "تغيير الاسم", "تصحيح الاسماء", "تغيير الاسماء", "تصحيح اسم", "تغيير اللقب",
      "تصحيح اللقب", "اضافه لقب", "حذف لقب", "الاسم الشخصي", "تصحيح الاسم في", "لجنه تصحيح الاسماء"],
     "legis-53-2026", [1, 3, 4, 11, 12, 13, 14, 15, 17, 18], "both"),
]

# حِزم مدنية (القانون المدني 67/1980) — (اسم، كلمات مفتاحية، أول مادة، آخر مادة)
# تُقصّ كل حزمة إلى 30 مادة كحدّ أقصى (المواد الحاكمة تأتي في صدر كل فصل).
_CIVIL_BUNDLES = [
    ("المسؤولية التقصيرية/الفعل الضار", ["ضرر", "ضرار", "تعويض", "فعل ضار", "مسؤول", "مسئول", "متبوع", "تابع", "اتلاف", "حادث", "تقصير", "عمل غير مشروع", "مسؤوليه تقصيريه"], 227, 261),
    ("الإثراء بلا سبب والفضالة ودفع غير المستحق", ["اثراء", "دفع غير مستحق", "دفع ما ليس مستحقا", "فضاله", "كسب دون سبب", "استرداد ما دفع"], 262, 278),
    ("تنفيذ الالتزام (العيني والتعويضي والغرامة التهديدية)", ["تنفيذ عيني", "تنفيذ جبري", "غرامه تهديديه", "امتناع عن التنفيذ", "اعذار", "تعويض عن التاخير", "فوائد تاخيريه"], 280, 306),
    ("الضمان العام (الدعوى غير المباشرة وعدم نفاذ التصرف والصورية)", ["ضمان عام", "دعوى غير مباشره", "عدم نفاذ التصرف", "دعوى بوليصيه", "صوريه", "اعسار", "حق الحبس", "حق حبس"], 307, 322),
    ("حوالة الحق والدين", ["حواله الحق", "حواله الدين", "حواله", "محال", "محيل", "محال عليه"], 364, 390),
    ("الوفاء والمقاصة والتجديد", ["وفاء", "مقاصه", "تجديد الالتزام", "انابه", "اتحاد الذمه", "عرض حقيقي", "وفاء بمقابل"], 391, 434),
    ("التقادم المسقط والإبراء واستحالة التنفيذ", ["تقادم", "سقوط بالتقادم", "مرور الزمن", "ابراء", "استحاله التنفيذ", "انقضاء الالتزام"], 435, 453),
    ("بطلان العقد وقابليته للإبطال وعيوب الرضا", ["بطلان", "باطل", "قابل للابطال", "ابطال", "عيب رضا", "غلط", "تدليس", "اكراه", "استغلال"], 179, 196),
    ("فسخ العقد والدفع بعدم التنفيذ والإقالة", ["فسخ", "اخلال", "عدم تنفيذ", "الدفع بعدم التنفيذ", "استحاله", "اقاله", "شرط فاسخ", "ملزم للجانبين"], 209, 219),
    ("البيع (التزامات البائع والمشتري والضمان)", ["عقد بيع", "المبيع", "مبيع", "بائع", "مشتري", "الثمن", "ضمان العيوب", "ضمان الاستحقاق", "تسليم المبيع"], 454, 518),
    ("الإيجار (التزامات المؤجر والمستأجر)", ["ايجار", "الاجره", "مؤجر", "مستاجر", "عين مؤجره", "ماجور", "اخلاء", "عقد ايجار"], 561, 648),
    ("المقاولة", ["مقاوله", "مقاول", "رب العمل", "مقايسه"], 661, 697),
    ("الوكالة", ["وكاله", "الوكيل", "عزل الوكيل", "توكيل", "عقد وكاله"], 698, 719),
    ("الكفالة", ["كفاله", "كفيل", "مكفول"], 745, 772),
    ("الرهن (الرسمي والحيازي)", ["رهن رسمي", "رهن حيازي", "رهن", "راهن", "مرتهن", "دين مضمون"], 971, 1026),
    ("الملكية والشيوع والقسمة والحيازة", ["ملكيه", "شيوع", "شائع", "قسمه", "شركاء", "حيازه", "تقادم مكسب", "التصاق"], 810, 943),
]

# حِزم قانون الإثبات (39/1980) — تُستحضر مع الصياغة المدنية عند ورود مسائل إثبات
_EVIDENCE_BUNDLES = [
    ("عبء الإثبات وقواعده العامة", ["عبء الاثبات", "على الدائن اثبات", "قواعد الاثبات", "ادله الاثبات", "طرق الاثبات"], 1, 7),
    ("المحررات الرسمية وحجيتها", ["محرر رسمي", "ورقه رسميه", "سند رسمي", "حجيه الورقه الرسميه", "المحرر الرسمي"], 8, 12),
    ("المحررات العرفية والتوقيع", ["محرر عرفي", "ورقه عرفيه", "سند عرفي", "توقيع", "بصمه", "المحرر العرفي"], 13, 21),
    ("إلزام الخصم بتقديم أوراق تحت يده", ["الزام الخصم بتقديم", "ورقه تحت يد الخصم", "تقديم مستند تحت يد"], 22, 25),
    ("إثبات صحة الأوراق (الإنكار والطعن بالتزوير)", ["تزوير", "انكار", "طعن بالتزوير", "صحه الاوراق", "مضاهاه", "ادعاء التزوير"], 26, 38),
    ("شهادة الشهود (البيّنة)", ["شهاده", "شهود", "البينه", "بالبينه", "سماع شاهد", "اثبات بالبينه"], 39, 51),
    ("القرائن وحجية الأمر المقضي", ["قرينه", "قرائن", "حجيه الامر المقضي", "قوه الامر المقضي", "الشيء المحكوم فيه"], 52, 54),
    ("الإقرار", ["اقرار", "حجيه الاقرار", "الاقرار القضائي"], 55, 57),
    ("استجواب الخصوم", ["استجواب", "استجواب الخصوم"], 58, 60),
    ("اليمين (الحاسمة والمتممة والنكول)", ["يمين", "يمين حاسمه", "يمين متممه", "نكول", "توجيه اليمين", "رد اليمين"], 61, 70),
    ("المعاينة ودعوى إثبات الحالة", ["معاينه", "اثبات الحاله", "دعوى اثبات حاله"], 71, 73),
]

# حِزم قانون المرافعات المدنية والتجارية (38/1980) — تُستحضر مع الصياغة المدنية
# عند ورود مسائل إجرائية (اختصاص، إعلان، دفوع، طعون، أوامر أداء، تحكيم، تنفيذ، حجز).
# النطاقات مضبوطة على التبويب الأصلي؛ تُقصّ كل حزمة إلى 30 مادة كحدّ أقصى.
# الكلمات مصمّمة لتجنّب الالتباس بألفاظ مدنية موضوعية شائعة
# (مثال: «الدفوع» لا «دفع» حتى لا تلتبس بوفاء الدين؛ «تنفيذ جبري» لا «تنفيذ» المجرّد).
_PROCEDURE_BUNDLES = [
    ("الاختصاص وتقدير قيمة الدعوى",
     ["اختصاص", "عدم الاختصاص", "الدفع بعدم الاختصاص", "تقدير قيمه الدعوى", "قيمه الدعوى",
      "الاختصاص النوعي", "الاختصاص القيمي", "الاختصاص المحلي", "الاختصاص الدولي",
      "احاله لعدم الاختصاص"], 23, 44),
    ("المواعيد وإعلان الأوراق القضائية",
     ["ميعاد", "المواعيد", "اعلان الصحيفه", "اعلان صحيفه", "بطلان الاعلان", "بطلان اعلان",
      "مندوب الاعلان", "التكليف بالحضور", "اعلان الاوراق", "ميعاد المسافه"], 5, 22),
    ("رفع الدعوى وقيدها والشطب",
     ["قيد الدعوى", "رفع الدعوى", "شطب الدعوى", "تجديد الدعوى", "ايداع الصحيفه",
      "قيد الصحيفه", "تجديد من الشطب"], 45, 53),
    ("حضور الخصوم والتوكيل والغياب",
     ["الحضور والتوكيل", "التوكيل بالخصومه", "توكيل بالخصومه", "غياب الخصم",
      "غياب المدعى عليه", "حضور الخصوم", "بمثابه الحضوري", "الحكم الغيابي", "غيابي"], 54, 61),
    ("الدفوع والطلبات العارضة والتدخل",
     ["الدفوع", "دفع شكلي", "دفع موضوعي", "الطلبات العارضه", "طلبات عارضه", "طلب عارض",
      "ادخال ضامن", "ادخال خصم", "التدخل في الدعوى"], 77, 89),
    ("وقف الخصومة وانقطاعها وسقوطها وتركها",
     ["وقف الخصومه", "وقف الدعوى", "انقطاع الخصومه", "انقطاع سير الخصومه", "سقوط الخصومه",
      "سقوط الدعوى", "ترك الخصومه", "اعتبار الدعوى كان لم تكن"], 90, 101),
    ("عدم صلاحية القضاة وردّهم وتنحيتهم",
     ["رد القاضي", "رد القضاه", "تنحي القاضي", "تنحيه القاضي", "عدم صلاحيه القاضي",
      "صلاحيه القاضي", "مخاصمه القضاه"], 102, 111),
    ("الأحكام ومصروفاتها وتصحيحها وتفسيرها",
     ["مصروفات الدعوى", "مصاريف الدعوى", "الرسوم القضائيه", "الزام بالمصروفات",
      "تصحيح الحكم", "تفسير الحكم", "طلب تفسير الحكم", "اغفال الفصل", "منطوق الحكم",
      "مسوده الحكم"], 112, 126),
    ("الاستئناف وطرق الطعن العامة",
     ["استئناف", "الطعن بالاستئناف", "صحيفه الاستئناف", "ميعاد الاستئناف", "استئناف الحكم",
      "مذكره استئناف", "طرق الطعن", "الطعن في الاحكام"], 127, 147),
    ("التماس إعادة النظر",
     ["التماس اعاده النظر", "اعاده النظر", "التماس"], 148, 151),
    ("الطعن بالتمييز",
     ["تمييز", "الطعن بالتمييز", "طعن بالتمييز", "محكمه التمييز", "صحيفه الطعن بالتمييز"], 152, 157),
    ("اعتراض الخارج عن الخصومة",
     ["اعتراض الخارج عن الخصومه", "الخارج عن الخصومه", "اعتراض الغير"], 158, 162),
    ("الأوامر على العرائض والتظلم منها",
     ["امر على عريضه", "امر على العريضه", "اوامر على العرائض", "التظلم من الامر",
      "تظلم من امر"], 163, 165),
    ("أوامر الأداء",
     ["امر اداء", "امر بالاداء", "اوامر الاداء", "طلب امر اداء", "استصدار امر اداء"], 166, 172),
    ("التحكيم",
     ["تحكيم", "المحكم", "اتفاق التحكيم", "شرط التحكيم", "حكم المحكمين", "هيئه التحكيم",
      "بطلان حكم التحكيم"], 173, 188),
    ("التنفيذ الجبري (أحكام عامة)",
     ["تنفيذ جبري", "التنفيذ الجبري", "السند التنفيذي", "الصيغه التنفيذيه", "قاضي التنفيذ",
      "اشكال في التنفيذ", "منازعه التنفيذ", "اعلان السند التنفيذي"], 189, 215),
    ("الحجوز (التحفظي والتنفيذي والبيع بالمزاد)",
     ["حجز", "الحجز التحفظي", "الحجز التنفيذي", "حجز ما للمدين لدى الغير", "توقيع الحجز",
      "بيع بالمزاد", "المزاد العلني", "حجز على منقول", "حجز على عقار"], 216, 288),
    ("التنفيذ المباشر (تسليم منقول أو عقار)",
     ["تسليم منقول", "تسليم عقار", "التنفيذ المباشر", "الطرد من العقار"], 289, 291),
    ("حبس المدين ومنعه من السفر",
     ["حبس المدين", "منع من السفر", "منع المدين من السفر", "الاكراه البدني"], 292, 298),
    ("العرض الحقيقي والإيداع",
     ["العرض الحقيقي", "عرض حقيقي", "عرض وايداع", "ايداع الدين"], 299, 304),
]

# حِزم قانون الرسوم القضائية (17/1973 — النافذ بعد تعديل المرسوم بقانون 78/2025)
# تُستحضَر مع الصياغة المدنية عند ورود مسائل الرسوم أو الإعفاء أو تقدير قيمة الدعوى.
# الكلمات مركّبة (رسوم/رسم + سياق) لتجنّب الالتباس بألفاظ مدنية عامة.
_FEES_BUNDLES = [
    ("تقدير قيمة الدعوى لأغراض الرسوم",
     ["تقدير قيمه الدعوى", "قيمه الدعوى", "غير مقدره القيمه", "دعوى غير مقدره القيمه",
      "تقدير الرسم"], 1, 5),
    ("الرسوم القضائية (النسبية والثابتة) وتحصيلها",
     ["رسم نسبي", "الرسم النسبي", "رسم ثابت", "الرسوم القضائيه", "الرسم القضائي", "قيمه الرسم",
      "تحصيل الرسوم", "رسوم الدعوى", "تجديد الدعوى من الشطب", "رسم التجديد"], 6, 10),
    ("الإعفاء من الرسوم القضائية وردّها",
     ["اعفاء من الرسوم", "الاعفاء من الرسوم", "طلب الاعفاء", "رد الرسوم", "لجنه الاعفاء",
      "العجز عن سداد الرسوم", "المعفى من الرسوم"], 12, 17),
    ("رسوم الإعلان وصور الأحكام",
     ["رسوم الاعلان", "رسم الاعلان", "رسم الانذار", "صوره الحكم", "رسوم الصور"], 18, 19),
    ("الوفاء بالرسم مسبقًا والتظلم من تقدير الرسوم",
     ["الوفاء بالرسم", "سداد الرسم", "عدم سداد الرسم", "تقدير الرسوم", "التظلم من الرسوم",
      "امر تقدير الرسوم", "قائمه الرسوم"], 20, 23),
]

# حِزم قانون الدعاوى قليلة القيمة (46/1989) — الإجراء المبسّط أمام المحكمة الجزئية
# للمنازعات التي لا تجاوز ألفي دينار. يُستحضَر كاملًا (10 مواد) عند إثارة هذا المسار.
_SMALLCLAIMS_BUNDLES = [
    ("الدعاوى قليلة القيمة (الإجراء المبسّط)",
     ["قليله القيمه", "دعوى قليله القيمه", "الدعاوى قليله القيمه", "لا تجاوز الفي دينار",
      "لا تجاوز الفين دينار", "الفي دينار", "التقاضي المبسط", "الاجراءات المبسطه",
      "المسار المبسط"], 1, 10),
]

# حِزمة قانون إعفاء الحكومة من الرسوم القضائية (7/1961) — تُستحضَر عند تمثيل
# إدارة الفتوى والتشريع للحكومة/المؤسسات العامة أو دعاوى دائرة الأيتام.
_GOVFEE_BUNDLES = [
    ("إعفاء الحكومة من الرسوم القضائية",
     ["اعفاء الحكومه من الرسوم", "الحكومه من الرسوم", "اداره الفتوى والتشريع",
      "دعاوى الحكومه", "بالنيابه عن دوائر الحكومه", "دائره الايتام", "اعفاء الدوله من الرسوم",
      "المؤسسات العامه من الرسوم"], 1, 4),
]

# حِزم قانون إيجار العقارات (35/1978) — قانون خاص موضوعي.
# بنية بلواحق معرّفات صريحة (لا نطاق رقمي) لأن فيه مواد مكرّرة بحروف
# (m26-mukarrar, -a..-d) لا يلتقطها النمط الرقمي. كل حزمة: (اسم، كلمات، [لواحق]).
_LEASE_BUNDLES = [
    ("انتهاء الإيجار والإخلاء",
     ["اخلاء", "انتهاء الايجار", "انهاء الايجار", "انهاء عقد الايجار", "طلب الاخلاء",
      "اخلاء العين", "اخلاء المستاجر", "فسخ عقد الايجار"],
     ["m19", "m20", "m21", "m22", "m23", "m26-mukarrar-b", "m26-mukarrar-c"]),
    ("الأجرة: تحديدها ووفاؤها",
     ["اجره العين", "الاجره المتفق", "وفاء الاجره", "المطالبه بالاجره", "الاجره المتاخره",
      "تحديد الاجره", "زياده الاجره", "اجره المثل", "قيمه الايجار", "الاجره الشهريه"],
     ["m4", "m10", "m11", "m11-mukarrar"]),
    ("أمر أداء الأجرة والتظلم والإشكال في التنفيذ",
     ["امر اداء بالاجره", "امر اداء الاجره", "امر بالاداء بالاجره", "التظلم من امر الاداء",
      "اشكال في التنفيذ", "اشكال التنفيذ", "اشكال في تنفيذ حكم الايجار"],
     ["m25", "m26-mukarrar", "m26-mukarrar-a"]),
    ("دوائر الإيجارات وإجراءات التقاضي",
     ["دائره الايجارات", "دوائر الايجارات", "دعوى ايجار", "دعاوى الايجار", "اختصاص الايجارات",
      "استئناف احكام الايجارات"],
     ["m24", "m25", "m26"]),
    ("التزامات المؤجر (التسليم والصيانة والضمان)",
     ["التزامات المؤجر", "تسليم العين", "صيانه العين", "ترميمات", "ضمان العيوب",
      "عيوب العين المؤجره", "صيانه الماجور"],
     ["m7", "m8", "m9"]),
    ("التزامات المستأجر والتأجير من الباطن",
     ["التزامات المستاجر", "استعمال العين", "التاجير من الباطن", "تاجير من الباطن",
      "العنايه بالعين", "رد العين المؤجره"],
     ["m12", "m13", "m14", "m15", "m23"]),
    ("انتقال ملكية العين المؤجرة وامتداد العقد ونطاقه",
     ["انتقال ملكيه العين", "بيع العين المؤجره", "امتداد عقد الايجار", "نفاذ الايجار في حق المشتري",
      "اثبات عقد الايجار", "تعدد المستاجرين", "نطاق تطبيق قانون الايجار"],
     ["m1", "m5", "m6", "m16", "m17", "m18"]),
    ("الإخلاء الإداري الحكومي للعقارات",
     ["الاخلاء الاداري", "اخلاء اداري", "اخلاء اداريا", "نزع الملكيه", "املاك الدوله الخاصه"],
     ["m2"]),
]

# حِزم قانون التسجيل العقاري (5/1959) — قانون خاص موضوعي/إجرائي للشهر العقاري.
# بنية بلواحق صريحة (فيه مواد مكرّرة بأرقام: m11-mukarrar-1..4، m12-mukarrar-1..2).
_REGISTRATION_BUNDLES = [
    ("المحررات الواجبة التسجيل والحقوق العينية العقارية",
     ["تسجيل المحررات", "المحررات الواجبه التسجيل", "واجب التسجيل", "تسجيل التصرف",
      "حق عيني عقاري", "الحقوق العينيه العقاريه", "تسجيل الارث", "الشهر العقاري",
      "تسجيل عقد البيع", "تسجيل عقد الايجار"],
     ["m7", "m8", "m9", "m10", "m11"]),
    ("تسجيل صحف الدعاوى العقارية والتأشير ومحوه",
     ["تسجيل صحيفه الدعوى", "تسجيل صحف الدعاوى", "صحيفه دعوى استحقاق", "دعوى صحه التعاقد",
      "التاشير على هامش السجل", "محو التاشير", "دعوى استحقاق عقار", "تسجيل الدعوى العقاريه"],
     ["m11-mukarrar-1", "m11-mukarrar-2", "m11-mukarrar-3", "m11-mukarrar-4"]),
    ("إجراءات التسجيل والتظلم من قرار المُسجِّل",
     ["اجراءات التسجيل", "طلب التسجيل", "التظلم من قرار المسجل", "رفض طلب التسجيل",
      "سقوط اسبقيه الطلب", "قيد طلب التسجيل", "استيفاء بيانات التسجيل", "اسبقيه التسجيل"],
     ["m12", "m12-mukarrar-1", "m12-mukarrar-2", "m15", "m16", "m19"]),
    ("بيانات المحررات وشروط قبولها للتسجيل",
     ["بيانات المحرر", "شروط المحرر", "محتويات المحرر", "وصف العقار", "اثبات اصل الملكيه"],
     ["m13", "m14", "m17", "m18"]),
    ("التصديق على التوقيعات والأهلية أمام المُسجِّل",
     ["التصديق على التوقيع", "التصديق على التوقيعات", "اهليه التعاقد", "التثبت من الاهليه",
      "اهليه المتعاقدين"],
     ["m29", "m30", "m31", "m32", "m33"]),
    ("رسوم التسجيل العقاري والإعفاء منها",
     ["رسوم التسجيل", "رسم التسجيل العقاري", "رسوم الشهر العقاري", "الاعفاء من رسوم التسجيل",
      "فئات رسوم التسجيل", "تحصيل الرسوم على العقود", "رسم التسجيل"],
     ["m57", "m58", "m58-mukarrar", "m59", "m61"]),
    ("آثار التسجيل وعقوبة التهرب من الرسوم",
     ["اثر التسجيل", "بطلان المحرر المسجل", "التهرب من رسوم التسجيل", "عقوبه التهرب من الرسوم",
      "اثر عدم التسجيل"],
     ["m60", "m60-mukarrar"]),
    ("دائرة التسجيل العقاري واختصاصها",
     ["دائره التسجيل العقاري", "اختصاص التسجيل العقاري", "اقسام دائره التسجيل"],
     ["m1", "m2", "m3"]),
]

# حِزم قانون التجارة (68/1980) — (اسم، كلمات، أول مادة، آخر مادة)، تُقصّ إلى 30 مادة.
# الكلمات مركّبة/نوعية لتجنّب الالتباس (مثل «الرهن التجاري» لا «الرهن»، «عقد النقل» لا «النقل»).
_COMMERCE_BUNDLES = [
    ("التاجر والأعمال التجارية والدفاتر التجارية",
     ["عمل تجاري", "اعمال تجاريه", "العمل التجاري", "صفه التاجر", "اكتساب صفه التاجر",
      "الاهليه التجاريه", "الدفاتر التجاريه", "حجيه الدفاتر"], 1, 33),
    ("المتجر والعنوان التجاري والمزاحمة غير المشروعة",
     ["المتجر", "العنوان التجاري", "بيع المتجر", "رهن المتجر", "المزاحمه غير المشروعه",
      "المنافسه غير المشروعه", "الاحتكار"], 34, 60),
    ("العلامات والبيانات التجارية",
     ["العلامه التجاريه", "علامه تجاريه", "البيانات التجاريه", "تقليد العلامه"], 86, 95),
    ("الالتزامات التجارية (التضامن والفوائد والإعذار والتقادم)",
     ["التضامن التجاري", "الفائده التجاريه", "الفوائد التجاريه", "الاعذار التجاري",
      "التقادم التجاري", "الالتزامات التجاريه"], 97, 118),
    ("البيع التجاري",
     ["بيع تجاري", "البيع التجاري", "تسليم البضاعه", "بيع البضائع", "البضاعه في الطريق"], 119, 160),
    ("النقل (البضائع والأشخاص) ومسؤولية الناقل",
     ["عقد النقل", "نقل البضائع", "نقل الاشخاص", "الناقل", "بوليصه الشحن", "سند الشحن",
      "مسؤوليه الناقل"], 161, 222),
    ("الرهن التجاري",
     ["الرهن التجاري", "رهن تجاري", "رهن البضائع", "رهن المنقول التجاري"], 223, 237),
    ("الإيداع في المخازن العامة (سند الإيداع وسند الرهن)",
     ["المخازن العامه", "سند الايداع", "سند الرهن", "ايداع البضائع في المخازن"], 238, 259),
    ("الوكالة التجارية والوكيل بالعمولة والممثلون التجاريون",
     ["الوكاله التجاريه", "وكاله تجاريه", "الوكيل بالعموله", "الوكاله بالعموله",
      "الممثل التجاري", "وكيل العقود"], 260, 305),
    ("السمسرة والبورصات التجارية",
     ["السمسره", "السمسار", "عموله السمسره", "البورصه", "عمليات البورصه"], 306, 328),
    ("عمليات البنوك (الحساب الجاري والاعتماد وخطاب الضمان والوديعة)",
     ["عمليات البنوك", "الحساب الجاري", "الاعتماد المستندي", "خطاب الضمان", "الوديعه المصرفيه",
      "فتح اعتماد", "القرض المصرفي"], 329, 404),
    ("الكمبيالة: إنشاؤها وتداولها وتظهيرها وقبولها وضمانها",
     ["كمبياله", "الكمبياله", "تظهير الكمبياله", "قبول الكمبياله", "ساحب الكمبياله",
      "الضمان الاحتياطي", "الاڤال"], 405, 452),
    ("الرجوع والاحتجاج (البروتستو) بالكمبيالة ومواعيدها",
     ["الرجوع بالكمبياله", "الاحتجاج", "البروتستو", "رجوع الحامل", "وفاء الكمبياله",
      "مواعيد البروتستو"], 453, 482),
    ("سقوط الحقوق الصرفية وانقضاء الكمبيالة وتقادمها",
     ["تقادم الكمبياله", "تقادم دعوى الكمبياله", "تقادم دعاوى الكمبياله", "سقوط حقوق الحامل",
      "سقوط الحق الصرفي", "سقوط الكمبياله", "تقادم صرفي", "الدفع بالتقادم الصرفي",
      "انقضاء الكمبياله"], 483, 505),
    ("السند لأمر (السند الإذني)",
     ["السند لامر", "السند الاذني", "سند لامر", "سند اذني"], 506, 509),
    ("الشيك: إنشاؤه وتداوله والوفاء به",
     ["الشيك", "تظهير الشيك", "الشيك المسطر", "شيك بدون رصيد", "الوفاء بالشيك",
      "مقابل الوفاء"], 511, 531),
    ("الرجوع بالشيك وانقضاؤه وتقادمه",
     ["الرجوع في الشيك", "تقادم الشيك", "رفض الوفاء بالشيك", "احتجاج الشيك",
      "الشيك المرفوض", "شيك بدون رصيد", "رفض الوفاء", "امتناع عن صرف الشيك"], 532, 554),
]

# حِزم قانون الشركات (1/2016) — (اسم، كلمات، أول مادة، آخر مادة)، تُقصّ إلى 30 مادة.
# منظّمة بحسب نوع الشركة + الموضوعات العرضية (رأس المال، الإدارة، التصفية، العقوبات).
_COMPANIES_BUNDLES = [
    ("أحكام عامة للشركات (التأسيس والشكل والشهر والبطلان)",
     ["تاسيس شركه", "تاسيس الشركه", "عقد الشركه", "بطلان الشركه", "شهر الشركه",
      "اشكال الشركات", "انواع الشركات", "الشخصيه الاعتباريه للشركه"], 1, 32),
    ("شركة التضامن",
     ["شركه التضامن", "الشريك المتضامن", "شركاء متضامنون", "مسؤوليه الشركاء المتضامنين"], 33, 55),
    ("شركة التوصية (البسيطة وبالأسهم)",
     ["شركه التوصيه", "التوصيه البسيطه", "التوصيه بالاسهم", "الشريك الموصي", "الشركاء الموصون"], 56, 75),
    ("شركات المحاصة والمهنية والشخص الواحد",
     ["شركه المحاصه", "الشركه المهنيه", "شركه الشخص الواحد", "شركه شخص واحد"], 76, 91),
    ("الشركة ذات المسؤولية المحدودة",
     ["ذات المسئوليه المحدوده", "ذات المسؤوليه المحدوده", "الشركه المحدوده", "حصص الشركاء"], 92, 118),
    ("تأسيس شركة المساهمة العامة ورأس مالها",
     ["شركه المساهمه", "المساهمه العامه", "تاسيس شركه المساهمه", "راس مال الشركه", "الاكتتاب",
      "نشره الاكتتاب", "حصه عينيه"], 119, 156),
    ("تعديل رأس المال والتصرف في الأسهم وحقوق المساهمين",
     ["تعديل راس المال", "زياده راس المال", "تخفيض راس المال", "تداول الاسهم", "التصرف في الاسهم",
      "حقوق المساهمين", "اسهم الشركه"], 157, 180),
    ("إدارة شركة المساهمة (مجلس الإدارة ومسؤوليته)",
     ["مجلس الاداره", "عضو مجلس الاداره", "رئيس مجلس الاداره", "مسؤوليه اعضاء مجلس الاداره",
      "اداره شركه المساهمه"], 181, 205),
    ("الجمعية العامة للمساهمين",
     ["الجمعيه العامه", "الجمعيه العاديه", "الجمعيه غير العاديه", "اجتماع الجمعيه", "قرارات الجمعيه"], 206, 220),
    ("حسابات الشركة ومراقب الحسابات وتوزيع الأرباح",
     ["مراقب الحسابات", "مراقب حسابات", "حسابات الشركه", "ميزانيه الشركه", "توزيع الارباح",
      "الاحتياطي القانوني"], 221, 233),
    ("شركة المساهمة المقفلة",
     ["المساهمه المقفله", "شركه المساهمه المقفله"], 234, 242),
    ("الشركة القابضة",
     ["الشركه القابضه", "شركه قابضه", "الشركه التابعه"], 243, 249),
    ("تحوّل الشركات واندماجها وانقسامها",
     ["تحول الشركه", "تحول الشركات", "اندماج", "الاندماج", "اندماج الشركات", "اندماج الشركه",
      "انقسام", "انقسام الشركه", "انقسام الشركات", "دمج الشركات"], 250, 265),
    ("انقضاء الشركة وتصفيتها",
     ["انقضاء الشركه", "تصفيه الشركه", "حل الشركه", "المصفي", "تصفيه شركه"], 266, 295),
    ("الرقابة والتفتيش والعقوبات في قانون الشركات",
     ["الرقابه والتفتيش", "التفتيش على الشركه", "عقوبات الشركات", "مخالفات قانون الشركات",
      "العقوبات في قانون الشركات"], 296, 306),
]

# حِزم قانون الإفلاس (71/2020) — (اسم، كلمات، أول مادة، آخر مادة)، تُقصّ إلى 30 مادة.
# ثلاثة مسارات: التسوية الوقائية، إعادة الهيكلة، شهر الإفلاس + الأحكام المشتركة والجرائم.
_BANKRUPTCY_BUNDLES = [
    ("أحكام عامة ونطاق تطبيق قانون الإفلاس (التوقف عن الدفع)",
     ["قانون الافلاس", "نطاق تطبيق الافلاس", "التوقف عن الدفع", "الكف عن الدفع",
      "المدين المتوقف عن الدفع", "التوقف عن دفع الديون"], 1, 12),
    ("افتتاح إجراءات الإفلاس وشروطها",
     ["افتتاح اجراءات الافلاس", "افتتاح الاجراءات", "طلب افتتاح الاجراءات", "قرار افتتاح الاجراءات",
      "شروط افتتاح الافلاس"], 13, 33),
    ("أمين الإفلاس والمراقب والمفتش",
     ["امين الافلاس", "تعيين الامين", "مراقب الافلاس", "مفتش الافلاس", "اجهزه الافلاس"], 34, 57),
    ("التسوية الوقائية: طلبها وأثر افتتاحها",
     ["التسويه الوقائيه", "تسويه وقائيه", "افتتاح التسويه الوقائيه", "طلب التسويه الوقائيه",
      "وقف المطالبات"], 58, 72),
    ("التسوية الوقائية: الموافقة والتصديق والتنفيذ وإنهاؤها",
     ["مقترح التسويه", "الموافقه على التسويه", "التصديق على التسويه", "تنفيذ التسويه الوقائيه",
      "انهاء التسويه الوقائيه"], 73, 96),
    ("إعادة الهيكلة",
     ["اعاده الهيكله", "اعاده هيكله", "خطه اعاده الهيكله", "اجراءات اعاده الهيكله",
      "افتتاح اعاده الهيكله"], 97, 130),
    ("شهر الإفلاس وآثاره (غلّ يد المدين وجماعة الدائنين)",
     ["شهر الافلاس", "حكم شهر الافلاس", "اشهار الافلاس", "المفلس", "غل يد المدين",
      "جماعه الدائنين", "التفليسه"], 131, 171),
    ("تحقيق الديون والتصفية والتوزيع في التفليسة",
     ["تحقيق الديون", "تصفيه التفليسه", "توزيع اموال التفليسه", "بيع اموال المفلس",
      "التوزيع على الدائنين", "قسمه اموال التفليسه"], 172, 195),
    ("إقفال التفليسة وانتهاؤها والصلح",
     ["اقفال التفليسه", "انتهاء التفليسه", "الصلح في التفليسه", "اتحاد الدائنين",
      "قفل التفليسه"], 196, 222),
    ("الأحكام المشتركة وفترة الريبة والطعن بتصرفات المدين",
     ["فتره الريبه", "الطعن بتصرفات المدين", "بطلان تصرفات المدين", "عدم نفاذ تصرفات المدين",
      "استرداد اموال التفليسه", "دعوى عدم النفاذ"], 224, 253),
    ("إفلاس الشركات والمشروعات الصغيرة والمتوسطة",
     ["افلاس الشركه", "افلاس شركه", "افلاس الشركات", "المشروعات الصغيره", "المشروعات المتوسطه"], 254, 266),
    ("التظلمات والاستئناف في الإفلاس",
     ["التظلم في الافلاس", "تظلم من قرار قاضي الافلاس", "استئناف احكام الافلاس",
      "الطعن في احكام الافلاس", "قاضي الافلاس"], 267, 274),
    ("جرائم الإفلاس (التدليس والتقصير) وردّ الاعتبار",
     ["الافلاس بالتدليس", "الافلاس بالتقصير", "جرائم الافلاس", "رد اعتبار المفلس",
      "رد الاعتبار", "المفلس بالتدليس"], 275, 308),
]

# حِزم قانون هيئة أسواق المال (7/2010) — (اسم، كلمات، أول مادة، آخر مادة)، تُقصّ إلى 30.
_CAPMARKETS_BUNDLES = [
    ("هيئة أسواق المال ومجلس المفوضين واختصاصاتها",
     ["هيئه اسواق المال", "هيئه سوق المال", "مجلس المفوضين", "مفوضي الهيئه",
      "اختصاص هيئه اسواق المال"], 2, 30),
    ("بورصة الأوراق المالية والإدراج",
     ["بورصه الاوراق الماليه", "البورصه", "ادراج الاوراق الماليه", "الادراج في البورصه",
      "اعضاء البورصه"], 31, 47),
    ("وكالة المقاصة والتقاص والإيداع المركزي",
     ["وكاله المقاصه", "المقاصه", "الايداع المركزي", "تسويه التداولات", "التقاص"], 48, 62),
    ("الترخيص لأنشطة الأوراق المالية ومراجعة حسابات المرخص لهم",
     ["مرخص له", "نشاط الاوراق الماليه", "ترخيص نشاط الاوراق", "الشخص المرخص",
      "مراجعه حسابات المرخص", "الاشخاص المرخص لهم"], 63, 70),
    ("الاستحواذ وحماية حقوق الأقلية",
     ["الاستحواذ", "عمليات الاستحواذ", "حمايه حقوق الاقليه", "عرض الاستحواذ",
      "الاستحواذ على الشركات المدرجه"], 71, 75),
    ("أنظمة الاستثمار الجماعي (الصناديق)",
     ["استثمار جماعي", "الاستثمار الجماعي", "صندوق استثمار", "صناديق استثمار",
      "صندوق الاستثمار", "وحدات الاستثمار"], 76, 91),
    ("نشرة الاكتتاب والطرح العام للأوراق المالية",
     ["نشره الاكتتاب", "الطرح العام", "الاكتتاب في الاوراق الماليه", "طرح الاوراق الماليه",
      "الاكتتاب العام"], 92, 99),
    ("الإفصاح عن المصالح والتعامل بالمعلومات الداخلية",
     ["الافصاح عن المصالح", "التعامل الداخلي", "المعلومات الداخليه", "استغلال المعلومات الداخليه",
      "المصلحه الجوهريه"], 100, 107),
    ("محكمة أسواق المال والطعن على أحكامها",
     ["محكمه اسواق المال", "محكمه سوق المال", "الطعن على احكام اسواق المال",
      "اختصاص محكمه اسواق المال"], 108, 117),
    ("جرائم الأوراق المالية وعقوباتها (التلاعب والإخلال بالسوق)",
     ["التلاعب في السوق", "التلاعب بالاسعار", "الاخلال بالسوق", "جرائم الاوراق الماليه",
      "عقوبات الاوراق الماليه", "استغلال المعلومات الداخليه"], 118, 135),
    ("التحقيق والدعوى الجزائية وتسوية المنازعات وسرّية المعلومات",
     ["التحقيق الاداري في المخالفات", "الدعوى الجزائيه في الاوراق الماليه", "تسويه المنازعات",
      "تسويه المخالفات", "سريه معلومات الهيئه", "تبادل المعلومات"], 136, 150),
    ("الأحكام الانتقالية لقانون أسواق المال",
     ["احكام انتقاليه لاسواق المال", "توفيق اوضاع الشركات المدرجه", "تحويل سوق الكويت للاوراق"], 151, 165),
]

# حِزم تعريفات اللائحة التنفيذية (كتاب التعريفات 7/2010) — بنية بلواحق معرّفات صريحة
# (أزواج دقيقة d1..d81). تُستحضَر مع مواضيع أسواق المال لتفسير المصطلحات.
_CAPMARKETS_DEF_BUNDLES = [
    ("تعريفات الصناديق والاستثمار الجماعي",
     ["صندوق", "صناديق", "الاستثمار الجماعي", "نظام استثمار جماعي", "وحدات الاستثمار"],
     ["k1-d5", "k1-d31", "k1-d32", "k1-d33", "k1-d34", "k1-d35", "k1-d36", "k1-d37",
      "k1-d38", "k1-d39", "k1-d40", "k1-d67", "k1-d68"]),
    ("تعريفات الاستحواذ والعروض والاندماج والانقسام",
     ["استحواذ", "عرض الشراء", "مستند العرض", "الاندماج", "الانقسام", "السيطره", "مسيطر"],
     ["k1-d7", "k1-d21", "k1-d22", "k1-d44", "k1-d56", "k1-d57", "k1-d58", "k1-d59",
      "k1-d60", "k1-d62", "k1-d64", "k1-d65"]),
    ("تعريفات الأشخاص المرخص لهم وذوي العلاقة",
     ["مرخص له", "الشخص المرخص", "شخص ذو علاقه", "مستشار استثمار", "مسوق", "المروج"],
     ["k1-d4", "k1-d24", "k1-d25", "k1-d26", "k1-d27", "k1-d28", "k1-d55", "k1-d61"]),
    ("تعريفات الأوراق المالية والاكتتاب والسندات",
     ["نشره الاكتتاب", "الاكتتاب", "ورقه ماليه", "سندات", "صكوك", "مشتقات ماليه"],
     ["k1-d17", "k1-d63", "k1-d66", "k1-d76", "k1-d80", "k1-d81"]),
    ("تعريفات الهيئة والبورصة والمقاصة والجهات المنظمة",
     ["الهيئه", "البورصه", "المقاصه", "الجهه المنظمه", "تسويه الاوراق الماليه"],
     ["k1-d1", "k1-d2", "k1-d3", "k1-d70", "k1-d72", "k1-d74", "k1-d79"]),
    ("تعريفات التحكيم وحماية البيانات الشخصية",
     ["التحكيم", "هيئه التحكيم", "نظام التحكيم", "البيانات الشخصيه", "حق التصحيح", "حق الشطب"],
     ["k1-d10", "k1-d11", "k1-d12", "k1-d13", "k1-d14", "k1-d43", "k1-d45", "k1-d69", "k1-d75"]),
]

# حِزم «كتاب هيئة أسواق المال» (الكتاب الثاني من اللائحة التنفيذية 7/2010) — تنظيم الهيئة
# ولجانها وماليتها وحماية البيانات؛ تُستحضَر مع الصياغة التجارية عند مساس المسألة بها.
# المعرّفات lreg-7-2010-k2-m{فصل-مادة}. لائحة تنفيذية دون القانون.
_CMAREG2_BUNDLES = [
    ("التظلم من قرارات الهيئة والبورصة — لجنة الشكاوى والتظلمات ومجلس التأديب",
     ["تظلم", "التظلمات", "لجنه الشكاوى", "الشكاوى والتظلمات", "الطعن على قرار الهيئه",
      "قرارات البورصه", "مجلس التاديب", "المساءله التاديبيه"],
     ["k2-m6-1-1", "k2-m6-1-2", "k2-m6-2-1", "k2-m6-2-2"]),
    ("حماية البيانات الشخصية — الاعتراض والشطب والتصحيح والشكوى",
     ["البيانات الشخصيه", "حمايه البيانات", "حق الاعتراض", "حق الشطب", "التصحيح",
      "تقييد المعالجه", "معالجه البيانات"],
     ["k2-m9-1", "k2-m9-2-1", "k2-m9-2-2", "k2-m9-2-3", "k2-m9-2-4",
      "k2-m9-3-1", "k2-m9-3-2", "k2-m9-3-3", "k2-m9-3-4", "k2-m9-4"]),
    ("اختصاصات الهيئة الرقابية والتنفيذية — الدعاوى والتفتيش والغرامات ووقف التداول",
     ["اختصاصات الهيئه", "صلاحيات الهيئه", "رفع الدعاوى", "التفتيش", "الغرامات",
      "وقف التداول", "الغاء الادراج", "اختصاصات مجلس المفوضين"],
     ["k2-m1-3", "k2-m1-11", "k2-m1-14"]),
    ("الرقابة الشرعية — المجلس الاستشاري والمعاملات المتوافقة مع الشريعة",
     ["الرقابه الشرعيه", "المجلس الاستشاري", "الشريعه الاسلاميه", "متوافق مع الشريعه",
      "المعاملات الاسلاميه"],
     ["k2-m6-3-1", "k2-m6-3-2", "k2-m6-3-3", "k2-m6-3-4", "k2-m6-3-5"]),
    ("تعارض المصالح وسرية المعلومات لمفوضي وموظفي الهيئة",
     ["تعارض المصالح", "سريه المعلومات", "سريه معلومات الهيئه", "الافصاح عن الاوراق الماليه",
      "ميثاق الشرف"],
     ["k2-m5-1", "k2-m5-2", "k2-m5-3", "k2-m5-4", "k2-m5-5", "k2-m5-6", "k2-m5-7", "k2-m5-8"]),
    ("مجلس مفوضي الهيئة — التشكيل والسلطة والتفويض",
     ["مجلس المفوضين", "مفوضي الهيئه", "تشكيل المجلس", "سلطه مجلس المفوضين",
      "صلاحيات الرئيس", "التفويض في الصلاحيات"],
     ["k2-m4-1", "k2-m4-2", "k2-m4-5", "k2-m4-19", "k2-m4-20"]),
    ("مالية الهيئة ومواردها ورسوم خدماتها",
     ["موارد الهيئه", "رسوم خدمات الهيئه", "ميزانيه الهيئه", "احتياطيات الهيئه",
      "راس مال الهيئه", "اموال الهيئه"],
     ["k2-m8-1", "k2-m8-10", "k2-m8-11", "k2-m8-25", "k2-m8-26"]),
    ("جدول رسوم خدمات الهيئة (الملحق 4) — التراخيص والإدراج والاندماج والموافقات والتظلمات",
     ["رسم الترخيص", "رسوم الترخيص", "رسم الاكتتاب", "رسم الادراج", "رسوم الادراج",
      "رسم الاندماج", "رسم الاستحواذ", "رسم عرض الشراء", "رسوم التظلم", "رسم التظلم",
      "رسم الشكوى", "رسوم الشكاوى", "رسم القيد", "رسم الصلح", "مقدار الرسم", "جدول الرسوم"],
     ["k2-fee1", "k2-fee2", "k2-fee3", "k2-fee4", "k2-fee5", "k2-fee7", "k2-fee11", "k2-fee12"]),
]

# حزم استرجاع الكتاب الثالث «إنفاذ القانون» من اللائحة التنفيذية 7/2010.
# المعرّفات lreg-7-2010-k3-m{فصل-مادة} للمواد، lreg-7-2010-k3-annex{n} للملاحق.
_CMAREG3_BUNDLES = [
    ("التحقيق والتفتيش والرقابة وطلب المعلومات — إنفاذ القانون",
     ["التحقيق", "الاستجواب", "التفتيش", "الرقابه والتفتيش", "طلب المعلومات",
      "اعلان المحال للتحقيق", "الحق في الدفاع", "سلطه الاداره القانونيه"],
     ["k3-m1-1", "k3-m1-2", "k3-m2-1", "k3-m2-2", "k3-m4-1", "k3-m4-3",
      "k3-m4-10", "k3-m4-11", "k3-m4-12", "k3-m4-13"]),
    ("المساءلة التأديبية ومجلس التأديب والجزاءات — إنفاذ القانون",
     ["المساءله التاديبيه", "مجلس التاديب", "المخالفه التاديبيه", "الجزاءات التاديبيه",
      "عزل عضو مجلس الاداره", "وقف الترخيص", "الغاء الترخيص", "جزاء مالي", "غرامه تاديبيه"],
     ["k3-m5-1", "k3-m5-2", "k3-m5-3", "k3-m5-11", "k3-m5-12", "k3-m5-13",
      "k3-m5-15", "k3-m5-16", "k3-m5-17"]),
    ("ضمانات المحال إلى مجلس التأديب والالتماس والتظلم من قراراته — إنفاذ القانون",
     ["ضمانات المحال", "جلسات مجلس التاديب", "التماس اعاده النظر", "التظلم من قرارات مجلس التاديب",
      "الاخطار بقرارات مجلس التاديب", "سماع الشهود"],
     ["k3-m5-6", "k3-m5-7", "k3-m5-8", "k3-m5-9", "k3-m5-10", "k3-m5-14",
      "k3-m5-18", "k3-m5-19", "k3-m5-20"]),
    ("البلاغ عن المخالفات والجرائم وحماية المبلّغ — إنفاذ القانون",
     ["البلاغ", "الابلاغ عن المخالفات", "حمايه المبلغ", "المبلغ عن الجرائم", "سجل البلاغات",
      "تقديم بلاغ"],
     ["k3-m3-1", "k3-m3-2", "k3-m3-3", "k3-m3-4", "k3-m3-5", "k3-m3-6",
      "k3-m3-7", "k3-annex5"]),
    ("تقديم بلاغ إلى نيابة أسواق المال والإجراءات التحفظية — إنفاذ القانون",
     ["نيابه اسواق المال", "الاجراءات التحفظيه", "المنع من السفر", "التحفظ على الاموال",
      "الوقف عن العمل", "بلاغ الى النيابه", "تعيين مدير لاداره الاموال"],
     ["k3-m6-1", "k3-m6-2", "k3-m6-3", "k3-m6-4", "k3-m6-5", "k3-m6-6", "k3-m6-7"]),
    ("الصلح مع الهيئة وانقضاء الدعوى الجزائية — إنفاذ القانون",
     ["الصلح", "التصالح", "عرض الصلح", "انقضاء الدعوى الجزائيه", "مبلغ الصلح", "طلب الصلح"],
     ["k3-m7-1", "k3-m7-2", "k3-m7-3", "k3-annex9"]),
    ("الشكاوى والتظلمات أمام لجنة الشكاوى والتظلمات — إنفاذ القانون",
     ["الشكاوى", "الشكوى", "لجنه الشكاوى", "التظلمات", "التظلم من قرار الهيئه",
      "فحص الشكوى", "نموذج الشكوى", "نموذج التظلم"],
     ["k3-m8-1", "k3-m8-2", "k3-m8-3", "k3-m8-6", "k3-m8-7", "k3-m9-1",
      "k3-m9-2", "k3-m9-5", "k3-m9-6", "k3-annex2", "k3-annex3"]),
    ("التحكيم في منازعات أسواق المال — الاتفاق والهيئة والإجراءات والحكم — إنفاذ القانون",
     ["التحكيم", "اتفاق التحكيم", "شرط التحكيم", "هيئه التحكيم", "المحكم", "حكم التحكيم",
      "تسويه المنازعات بالتحكيم", "طلب التحكيم", "نهائيه الحكم", "تصحيح الحكم"],
     ["k3-m12-1-1", "k3-m12-1-3", "k3-m12-1-5", "k3-m12-1-6", "k3-m12-2-1",
      "k3-m12-2-3", "k3-m12-2-4", "k3-m12-3-1", "k3-m12-3-9", "k3-m12-3-10",
      "k3-m12-4-3", "k3-m12-4-4", "k3-m12-4-5", "k3-m12-4-6"]),
    ("أتعاب المحكمين والخبراء والرسوم الإدارية للتحكيم (الملحق 6) — إنفاذ القانون",
     ["اتعاب المحكمين", "اتعاب الخبراء", "رسوم التحكيم", "الرسوم الاداريه", "جدول الاتعاب",
      "قيمه التحكيم", "تسجيل المحكمين", "تسجيل الخبراء"],
     ["k3-annex6", "k3-annex1", "k3-m12-2-2"]),
    ("إعلان الأوراق القضائية وإلغاء الرخصة أو التسجيل — إنفاذ القانون",
     ["اعلان الاوراق القضائيه", "تبليغ اوامر الحضور", "الغاء الرخصه", "الغاء التسجيل",
      "وقف الرخصه", "سحب الترخيص", "تقييد نشاط الشخص المرخص"],
     ["k3-m10-1", "k3-m10-2", "k3-m13-1", "k3-m13-2"]),
]

# حزم استرجاع الكتاب الرابع «بورصات الأوراق المالية ووكالات المقاصة» من اللائحة 7/2010.
# المعرّفات lreg-7-2010-k4-m{...} للمواد، lreg-7-2010-k4-annex{n} للملاحق.
_CMAREG4_BUNDLES = [
    ("ترخيص البورصة ووكالة المقاصة وتجديده وإلغاؤه",
     ["ترخيص البورصه", "ترخيص وكاله المقاصه", "طلب الترخيص", "تجديد الترخيص",
      "الغاء الترخيص", "شروط الترخيص", "مده الترخيص"],
     ["k4-m1-2", "k4-m1-3-1", "k4-m1-3-2", "k4-m1-3-3", "k4-m1-4",
      "k4-m1-7-1", "k4-m1-7-2", "k4-m1-7-3", "k4-annex1"]),
    ("التملك أو التصرف بنسبة 5% والسيطرة الفعلية على البورصة أو وكالة المقاصة",
     ["التملك بنسبه 5", "التصرف بنسبه 5", "السيطره الفعليه", "معيار النزاهه والامانه",
      "موافقه الهيئه المسبقه", "كبار المساهمين", "خمسه بالمائه من راس المال"],
     ["k4-m1-9-1", "k4-m1-9-2", "k4-m1-9-3", "k4-m1-9-4", "k4-m1-9-5",
      "k4-m1-10", "k4-m1-10-1", "k4-annex2"]),
    ("إدارة البورصة ومتطلباتها التنظيمية وقواعدها",
     ["اداره البورصه", "مجلس اداره البورصه", "نظام التداول", "المتطلبات التنظيميه للبورصه",
      "قواعد البورصه", "سريه المعلومات", "تعارض المصالح في البورصه"],
     ["k4-m2-1-1", "k4-m2-1-3", "k4-m2-1-4", "k4-m2-2-1", "k4-m2-2-7",
      "k4-m2-3-1", "k4-m2-3-2", "k4-m2-3-7"]),
    ("لجنة النظر في المخالفات بالبورصة والجزاءات والتظلم منها",
     ["لجنه النظر في المخالفات", "المخالفات في البورصه", "جزاءات البورصه", "التظلم من قرار البورصه",
      "مجلس التاديب", "وقف تداول ورقه ماليه"],
     ["k4-m2-4-1", "k4-m2-4-4", "k4-m2-4-5", "k4-m2-4-7", "k4-m2-4-10",
      "k4-m2-4-11", "k4-m2-4-12"]),
    ("تأسيس وكالة المقاصة وترخيصها وأنشطتها ومتطلبات إدارتها",
     ["وكاله المقاصه", "تاسيس وكاله مقاصه", "انشطه وكاله المقاصه", "اداره وكاله المقاصه",
      "خدمه التسويه والتقاص", "خدمه ايداع الاوراق الماليه", "الوسيط المركزي"],
     ["k4-m3-1-1", "k4-m3-1-2", "k4-m3-1-4", "k4-m3-1-5", "k4-m3-2-1",
      "k4-m3-3-1", "k4-m3-3-2", "k4-annex3"]),
    ("الاستعانة بجهة خارجية واستمرارية أعمال وكالة المقاصة",
     ["الاستعانه بجهه خارجيه", "اسناد الانشطه", "استمراريه الاعمال", "خطه استمراريه الاعمال",
      "تحليل تاثير الاعمال", "مقدم الخدمه"],
     ["k4-m3-3-3", "k4-m3-3-3-1", "k4-m3-3-3-2", "k4-m3-3-3-3", "k4-m3-3-4-1", "k4-m3-3-4-2"]),
    ("مركز التقاص — الضمانات وصندوق الضمان والهوامش وإدارة المخاطر",
     ["مركز التقاص", "صندوق الضمان", "الهوامش", "اداره المخاطر", "اعضاء التقاص",
      "الضمانات المقدمه", "اخفاق عضو التقاص", "اللجنه الاستشاريه للمخاطر"],
     ["k4-m3-5", "k4-m3-5-3", "k4-m3-5-4", "k4-m3-5-5", "k4-m3-5-6",
      "k4-m3-5-8", "k4-m3-5-9", "k4-m3-5-10", "k4-m3-5-11", "k4-m3-5-7-1"]),
    ("الكيان المركزي لإيداع الأوراق المالية — القيد ونقل الملكية والحسابات المجمعة",
     ["الكيان المركزي لايداع الاوراق الماليه", "الايداع المركزي", "قيد الاوراق الماليه",
      "نقل الملكيه", "سجل المصدر", "الحساب المجمع", "ايصالات الايداع", "خدمات الجمعيه العامه"],
     ["k4-m3-6", "k4-m3-6-1", "k4-m3-6-2", "k4-m3-6-3", "k4-m3-6-4",
      "k4-m3-6-5", "k4-m3-6-6", "k4-m3-6-10", "k4-m3-6-10-1", "k4-m3-6-11"]),
    ("أعضاء التقاص وأعضاء الإيداع — العضوية ومعايير القبول",
     ["اعضاء التقاص", "اعضاء الايداع", "معايير القبول", "عضويه وكاله المقاصه",
      "شروط العضويه"],
     ["k4-m3-7-1", "k4-m3-7-2", "k4-m3-7-3", "k4-m3-7-3-1", "k4-m3-7-4"]),
    ("تعافي مركز التقاص والكيان المركزي ونهائية التسوية والمقاصة",
     ["التعافي", "خطه التعافي", "نهائيه التسويه", "صافي التسويه", "امر التحويل",
      "اولويه المقاصه", "الافلاس", "التسويه الوقائيه", "اعاده الهيكله"],
     ["k4-m4-1", "k4-m4-2", "k4-m4-3", "k4-m4-4-1", "k4-m5-1-1", "k4-m5-1-2",
      "k4-m5-1-3", "k4-m5-2-1", "k4-m5-2-2", "k4-m5-3-1"]),
]

# حزم استرجاع فرع العمل — قانون العمالة المنزلية 68/2015 (اللاحقة تُلحق بـ legis-68-2015-).
_LABOR_BUNDLES = [
    ("عقد العمالة المنزلية وتعريفات القانون وحقوق الطرفين",
     ["العماله المنزليه", "العامل المنزلي", "عقد العمل", "عقد الاستقدام", "الخادم", "الخادمه",
      "تعريفات", "حقوق العامل"],
     ["m1", "m4", "m16", "m18", "m22"]),
    ("ترخيص مكاتب استقدام العمالة المنزلية وتجديده وإلغاؤه والتظلم",
     ["ترخيص المكتب", "مكتب الاستقدام", "استقدام العماله", "تجديد الترخيص", "الغاء الترخيص",
      "وقف الترخيص", "نقل الترخيص", "التظلم من قرار وزير الداخليه", "رسوم الترخيص"],
     ["m2", "m3", "m24", "m25", "m26", "m39", "m40", "m41", "m42", "m43"]),
    ("أجر العامل المنزلي ومواعيد الدفع والتعويض عن التأخير",
     ["الاجر", "اجر", "الراتب", "راتب", "رواتب", "دفع الاجر", "دفع الراتب", "تاخر",
      "التاخر في الاجر", "تاخير الراتب", "متاخرات", "الاجر الاساسي", "تعويض التاخير",
      "مواعيد الدفع", "خصم من الراتب"],
     ["m7", "m8", "m19", "m20", "m27"]),
    ("التزامات صاحب العمل — الإطعام والكسوة والعلاج والسكن وحفظ الوثائق",
     ["اطعام العامل", "كسوه", "علاج العامل", "سكن العامل", "سكن ملائم", "حجز الوثائق",
      "جواز السفر", "البطاقه المدنيه", "التزامات صاحب العمل"],
     ["m9", "m11", "m12", "m16"]),
    ("التزامات العامل المنزلي وواجباته",
     ["التزامات العامل المنزلي", "واجبات العامل", "المحافظه على اموال صاحب العمل", "اسرار العمل",
      "تعليمات صاحب العمل"],
     ["m13", "m14", "m15"]),
    ("الأعمال الخطرة وكرامة العامل وحظر تشغيل القاصرين",
     ["اعمال خطره", "كرامه العامل", "تشغيل القاصرين", "السن الادنى", "الاتجار بالبشر",
      "العمل خارج الكويت"],
     ["m10", "m21", "m29", "m46", "m47"]),
    ("مكافأة نهاية الخدمة للعامل المنزلي",
     ["مكافاه نهايه الخدمه", "نهايه الخدمه", "مكافاه العامل", "انتهاء العقد"],
     ["m23"]),
    ("منازعات العمالة المنزلية والاختصاص القضائي وإجراءات التقاضي",
     ["منازعات العماله المنزليه", "نزاع العامل وصاحب العمل", "اختصاص اداره العماله المنزليه",
      "الدائره العماليه", "تسويه النزاع", "الشكاوى", "اعفاء العامل من الرسوم",
      "رفع دعوى", "صحيفه دعوى", "المطالبه", "مطالبه بمستحقات", "المحكمه المختصه",
      "الرسوم القضائيه", "مستحقات العامل", "دعوى عماليه", "صياغه صحيفه"],
     ["m30", "m31", "m32", "m34", "m35", "m36", "m37", "m38"]),
    ("عقوبات وجزاءات قانون العمالة المنزلية",
     ["عقوبات", "جزاءات", "الحبس", "الغرامه", "مخالفه احكام القانون", "هروب العامل",
      "الابعاد"],
     ["m28", "m29", "m48", "m51"]),
    ("التفتيش واللوائح التنفيذية لقانون العمالة المنزلية",
     ["التفتيش", "موظفو الضبطيه", "اللائحه التنفيذيه", "قرارات وزير الداخليه", "تنظيم النشاط"],
     ["m44", "m45", "m49", "m50", "m52"]),
]

# حزم القانون 19/2000 بشأن دعم العمالة الوطنية وتشجيعها للعمل في الجهات غير الحكومية.
# مواضيع مستقلة عن العمالة المنزلية، لذا تُستحضَر بالكلمات المفتاحية فقط (لا نواة دائمة)
# حتى لا تُلوِّث استشارات العمالة المنزلية. اللاحقة تُلحَق بـ "legis-19-2000-".
_LABOR19_BUNDLES = [
    ("تعريفات ودعم العمالة الوطنية وسياسات التشغيل",
     ["دعم العماله الوطنيه", "العماله الوطنيه", "القوى العامله الوطنيه", "الجهات غير الحكوميه",
      "تشجيع التشغيل", "مجلس الخدمه المدنيه", "سياسات التشغيل"],
     ["m1", "m2"]),
    ("العلاوة الاجتماعية وعلاوة الأولاد",
     ["علاوه اجتماعيه", "علاوه الاولاد", "علاوه اولاد", "العلاوه الاجتماعيه", "استحقاق العلاوه"],
     ["m3"]),
    ("بدل البطالة للكويتي العاطل عن العمل",
     ["بدل البطاله", "عاطل عن العمل", "الكويتي العاطل", "بدل نقدي", "البطاله"],
     ["m4"]),
    ("مساهمة الدولة في تدريب العمالة الوطنية",
     ["تدريب العماله الوطنيه", "مساهمه في التدريب", "تنميه القوى العامله"],
     ["m5"]),
    ("نسب العمالة الوطنية والإحلال وحوافز التشغيل في القطاع غير الحكومي",
     ["نسبه العماله الوطنيه", "نسب العماله الوطنيه", "الاحلال", "احلال العماله",
      "تصريح عمل", "اذن عمل", "رسم اضافي", "العماله الوافده", "التزام بالنسبه",
      "الدعم العيني", "المناقصات", "الممارسات"],
     ["m6", "m7", "m8", "m9", "m11"]),
    ("التعيين بالإعلان في الجهات الحكومية والشركات المملوكة للدولة",
     ["التعيين بالاعلان", "الاعلان عن الوظائف", "صحيفتين يوميتين", "نتيجه القبول"],
     ["m10"]),
    ("تمويل دعم العمالة الوطنية والضريبة على أرباح الشركات",
     ["ضريبه", "الضريبه", "تمويل الدعم", "ارباح الشركات", "سوق الكويت للاوراق الماليه",
      "رسوم اضافيه", "الموارد الماليه"],
     ["m12", "m13"]),
    ("عقوبات تقديم بيانات غير صحيحة والتهرب من الضريبة",
     ["بيانات غير صحيحه", "عقوبه", "الحبس", "غرامه", "التهرب من الضريبه", "رد المبالغ"],
     ["m14", "m16"]),
    ("دفع مستحقات العاملين غير الكويتيين عبر البنوك المحلية",
     ["مستحقات العاملين", "الحسابات البنكيه", "البنوك المحليه", "دفع المستحقات",
      "العاملين غير الكويتيين", "الكشوف البنكيه"],
     ["m15", "m16"]),
]

# حزم القانون 6/2010 في شأن العمل في القطاع الأهلي — القانون العمّالي العام (الأصل).
# لا يسري على العمالة المنزلية (لها القانون الخاص 68/2015)، لذا تُستحضَر هذه الحزم
# لطلبات العمل العام فقط (غير المنزلية) بالكلمات المفتاحية. اللاحقة تُلحَق بـ "legis-6-2010-".
_LAB4_BUNDLES = [
    ("تعريفات القانون ونطاق سريانه على القطاع الأهلي",
     ["تعريفات", "نطاق السريان", "القطاع الاهلي", "يسري القانون", "العمل البحري",
      "استثناء من القانون", "لا يسري"],
     ["m1", "m2", "m3", "m4", "m5"]),
    ("الاستقدام وتصاريح العمالة الوافدة والهيئة العامة للقوى العاملة",
     ["استقدام", "تصريح عمل", "اذن عمل", "العماله الوافده", "عماله اجنبيه",
      "الهيئه العامه للقوى العامله", "احتياجات العماله", "نقل العامل", "اذن العمل"],
     ["m6", "m7", "m8", "m9", "m10"]),
    ("التلمذة والتدريب المهني",
     ["التلمذه", "التدريب المهني", "المتدرب", "عقد التلمذه", "تدريب العامل"],
     ["m11", "m12", "m13", "m14", "m15", "m16", "m17"]),
    ("تشغيل الأحداث والقاصرين",
     ["تشغيل الاحداث", "الحدث", "القاصر", "سن التشغيل", "الاعمال الخطره للاحداث",
      "تشغيل الصغار"],
     ["m18", "m19", "m20"]),
    ("تشغيل النساء وإجازة الوضع والأمومة",
     ["تشغيل النساء", "العامله", "المراه العامله", "اجازه الوضع", "اجازه الامومه",
      "العمل ليلا للنساء", "حظر تشغيل النساء", "اجر المراه"],
     ["m21", "m22", "m23", "m24", "m25"]),
    ("تكوين عقد العمل الفردي وفترة التجربة",
     ["عقد العمل", "تكوين العقد", "محدد المده", "غير محدد المده", "فتره التجربه",
      "بيانات العقد", "شروط العقد", "عقد العمل الفردي"],
     ["m26", "m27", "m28", "m29", "m30"]),
    ("التزامات العامل وصاحب العمل والجزاءات التأديبية",
     ["التزامات العامل", "التزامات صاحب العمل", "الجزاءات التاديبيه", "لائحه الجزاءات",
      "الخصم التاديبي", "المخالفات التاديبيه", "الانذار", "الفصل التاديبي", "لائحه الجزاء"],
     ["m31", "m32", "m33", "m34", "m35", "m36", "m37", "m38", "m39"]),
    ("انتهاء عقد العمل والفصل والاستقالة ومكافأة نهاية الخدمة",
     ["انتهاء عقد العمل", "انهاء العقد", "الفصل", "الاستقاله", "مكافاه نهايه الخدمه",
      "نهايه الخدمه", "الاخطار", "التعويض عن الفصل", "الفصل التعسفي", "مكافاه",
      "استحقاق المكافاه", "انهاء الخدمه", "فسخ عقد العمل", "ترك العمل"],
     ["m40", "m41", "m42", "m43", "m44", "m45", "m46", "m47", "m48", "m49", "m50",
      "m51", "m52", "m53"]),
    ("الأجر ومواعيد دفعه والاقتطاع منه",
     ["الاجر", "الراتب", "دفع الاجر", "مواعيد الدفع", "الخصم من الاجر", "الحجز على الاجر",
      "اجر اضافي", "اقتطاع من الاجر", "تاخر الاجر", "الاجر الاساسي"],
     ["m54", "m55", "m56", "m57", "m58", "m59", "m60", "m61", "m62"]),
    ("ساعات العمل والراحة الأسبوعية والعطلات الرسمية والعمل الإضافي",
     ["ساعات العمل", "الراحه الاسبوعيه", "العمل الاضافي", "ساعات اضافيه", "العطلات الرسميه",
      "الاعياد الرسميه", "فتره الراحه", "العمل الاضافي", "ايام الاعياد"],
     ["m63", "m64", "m65", "m66", "m67", "m68"]),
    ("الإجازات السنوية والمرضية والدراسية وإجازة الحج",
     ["الاجازه السنويه", "اجازه سنويه", "الاجازه المرضيه", "اجازه مرضيه", "اجازه دراسيه",
      "اجازه الحج", "اجازه بدون اجر", "بدل الاجازه", "رصيد الاجازه"],
     ["m69", "m70", "m71", "m72", "m73", "m74", "m75", "m76", "m77", "m78"]),
    ("السلامة والصحة المهنية وإصابات العمل والأمراض المهنية",
     ["السلامه المهنيه", "الصحه المهنيه", "اصابه العمل", "اصابات العمل", "المرض المهني",
      "التعويض عن الاصابه", "العجز", "الوفاه بسبب العمل", "التامين الصحي", "حادث العمل",
      "معدات الوقايه"],
     ["m79", "m80", "m81", "m82", "m83", "m84", "m85", "m86", "m87", "m88", "m89", "m90",
      "m91", "m92", "m93", "m94", "m95", "m96"]),
    ("المنظمات النقابية والحق النقابي",
     ["النقابه", "النقابات", "الحق النقابي", "منظمات العمال", "اتحاد العمال",
      "التنظيم النقابي", "منظمه اصحاب العمل"],
     ["m97", "m98", "m99", "m100", "m101", "m102", "m103", "m104", "m105", "m106",
      "m107", "m108", "m109"]),
    ("عقد العمل الجماعي",
     ["عقد العمل الجماعي", "الاتفاقيه الجماعيه", "العقد الجماعي", "المفاوضه الجماعيه"],
     ["m110", "m111", "m112", "m113", "m114", "m115", "m116", "m117", "m118", "m119",
      "m120", "m121"]),
    ("منازعات العمل الجماعية والتوفيق والتحكيم والإضراب",
     ["منازعات العمل الجماعيه", "النزاع الجماعي", "التوفيق", "التحكيم", "الاضراب",
      "الاغلاق", "لجنه التوفيق", "هيئه التحكيم"],
     ["m122", "m123", "m124", "m125", "m126", "m127", "m128", "m129", "m130", "m131"]),
    ("تفتيش العمل ومفتشو العمل والضبطية القضائية",
     ["تفتيش العمل", "مفتش العمل", "الضبطيه القضائيه", "التفتيش", "مفتشو العمل"],
     ["m132", "m133", "m134", "m135"]),
    ("العقوبات والجزاءات الجنائية لمخالفة قانون العمل",
     ["العقوبات", "الغرامه", "الحبس", "مخالفه احكام القانون", "الجزاءات الجنائيه",
      "عقوبه صاحب العمل", "العود"],
     ["m136", "m137", "m138", "m139", "m140", "m141"]),
    ("الأحكام الختامية وتقادم الدعوى العمالية والإعفاء من الرسوم وأولوية حقوق العمال",
     ["تقادم الدعوى العماليه", "سقوط الحق", "الاعفاء من الرسوم", "اولويه حقوق العمال",
      "الدعوى العماليه", "انقضاء الدعوى", "امتياز حقوق العمال", "الرسوم القضائيه",
      "مده التقادم"],
     ["m142", "m143", "m144", "m145", "m146", "m147", "m148", "m149", "m150"]),
]

# حزم القانون 28/1969 في شأن العمل في قطاع الأعمال النفطية — قانون قطاعي خاص يكمّله
# القانون العام 6/2010. يُستحضَر لطلبات العمل في القطاع النفطي فقط (بوابة «النفط»).
# اللاحقة تُلحَق بـ "legis-28-1969-".
_LAB5_BUNDLES = [
    ("تعريفات القطاع النفطي ونطاق السريان والمزايا الأفضل وعقد العمل الكتابي",
     ["تعريفات", "نطاق السريان", "الاعمال النفطيه", "عمال النفط", "المزايا الافضل",
      "عقد كتابي", "عقد العمل النفطي"],
     ["m1", "m2", "m3", "m4"]),
    ("ساعات العمل والمناوبة والعمل الإضافي والراحة الأسبوعية والعطلات في القطاع النفطي",
     ["ساعات العمل", "المناوبه", "دوره المناوبه", "العمل الاضافي", "ساعات اضافيه",
      "الراحه الاسبوعيه", "العطلات الرسميه", "الاجازه الرسميه", "المناطق البعيده"],
     ["m5", "m6", "m7", "m8", "m9", "m10"]),
    ("الإجازات المرضية والسنوية وتجميعها وإجازة التدريب لعمال النفط",
     ["الاجازه المرضيه", "اجازه مرضيه", "الاجازه السنويه", "اجازه سنويه", "تجميع الاجازه",
      "اجازه التدريب", "التدريب المهني", "رصيد الاجازه"],
     ["m11", "m12", "m13", "m14"]),
    ("التزامات أصحاب الأعمال النفطية الكبار (مائتا عامل فأكثر) من مرافق ووسائل",
     ["مائتي عامل", "200 عامل", "مرافق العمل", "وسائل الراحه", "الرعايه الطبيه",
      "التزامات صاحب العمل النفطي", "خدمات العمال"],
     ["m15", "m16", "m20"]),
    ("فسخ عقد العمل ومكافأة نهاية الخدمة وأنظمة التقاعد والادخار لعمال النفط",
     ["فسخ العقد", "انهاء العقد", "مكافاه نهايه الخدمه", "نهايه الخدمه", "الاخطار",
      "التقاعد", "الادخار", "التوفير", "انتهاء العقد"],
     ["m17", "m18", "m19"]),
    ("العقوبات والإخطار بالمخالفة والأحكام الختامية في قانون العمل النفطي",
     ["العقوبات", "الغرامه", "الحبس", "مخالفه احكام القانون", "الاخطار بالمخالفه",
      "الجزاءات", "احكام ختاميه"],
     ["m21", "m22", "m23", "m24"]),
]

# حزم القانون 8/2010 بشأن حقوق الأشخاص ذوي الإعاقة — الفرع «إداري». يُستحضَر لطلبات
# ذوي الإعاقة (بوابة محتوى «الإعاقة» أو الفرع «إداري»). اللاحقة تُلحَق بـ "legis-8-2010-".
_DISABILITY_BUNDLES = [
    ("تعريفات الإعاقة ونطاق التطبيق والخدمات وبطاقة الإعاقة",
     ["تعريفات", "نطاق التطبيق", "بطاقه اعاقه", "شهاده الاعاقه", "اللجنه الفنيه",
      "درجه الاعاقه", "نوع الاعاقه", "الشخص ذو الاعاقه", "الخدمات"],
     ["m1", "m2", "m3"]),
    ("حقوق الأشخاص ذوي الإعاقة: الصحة والتعليم والوصول والتنقل",
     ["حقوق ذوي الاعاقه", "الرعايه الصحيه", "التعليم", "الدمج التعليمي", "الوصول",
      "التنقل", "التصميم العام", "المباني", "بيئه خاليه من العوائق", "حق ذوي الاعاقه"],
     ["m4", "m5", "m6", "m7", "m8", "m9", "m10", "m11"]),
    ("التأهيل والتشغيل ونسبة توظيف ذوي الإعاقة",
     ["التاهيل", "اعاده التاهيل", "التشغيل", "توظيف ذوي الاعاقه", "نسبه التوظيف",
      "نسبه العماله", "العمل لذوي الاعاقه", "التدريب المهني", "تشغيل المعاق"],
     ["m12", "m13", "m14", "m15", "m16"]),
    ("الاندماج في المجتمع والترتيبات التيسيرية والرياضة والثقافة",
     ["الاندماج", "الدمج في المجتمع", "الترتيبات التيسيريه", "التيسيرات", "الرياضه",
      "الثقافه", "وسائل النقل", "المشاركه في المجتمع"],
     ["m17", "m18", "m19", "m20", "m21", "m22"]),
    ("الرعاية الاجتماعية والإيواء للأشخاص ذوي الإعاقة",
     ["الرعايه الاجتماعيه", "دور الايواء", "الرعايه الايوائيه", "الاسره البديله",
      "الرعايه المنزليه", "دور الرعايه"],
     ["m23", "m24", "m25", "m26", "m27"]),
    ("المزايا والإعفاءات والمخصص الشهري ومعاشات ذوي الإعاقة ومكافأة نهاية الخدمة",
     ["المزايا", "الاعفاءات", "المخصص الشهري", "معاش الاعاقه", "معاش", "اعفاء من الرسوم",
      "الاعفاء الجمركي", "مكافاه نهايه الخدمه", "علاوه", "السكن", "الاعفاء الضريبي",
      "المعاش التقاعدي", "بدل", "الاعانه الماليه"],
     ["m28", "m29", "m30", "m31", "m32", "m33", "m34", "m35", "m36", "m37", "m38",
      "m39", "m40", "m41", "m42", "m42mkr", "m43", "m44", "m45"]),
    ("الهيئة العامة لشؤون ذوي الإعاقة: التنظيم والاختصاصات والمجلس الأعلى",
     ["الهيئه العامه لشوون ذوي الاعاقه", "الهيئه", "المجلس الاعلى", "مجلس الاداره",
      "المدير العام", "اختصاصات الهيئه", "ميزانيه الهيئه", "تشكيل الهيئه"],
     ["m46", "m47", "m48", "m49", "m50", "m51", "m52", "m53", "m54", "m55", "m56", "m57"]),
    ("العقوبات والجزاءات في قانون ذوي الإعاقة",
     ["عقوبات", "الغرامه", "الحبس", "مخالفه احكام القانون", "التمييز ضد المعاق",
      "الجزاءات", "عقوبه"],
     ["m58", "m59", "m60", "m61", "m62", "m63"]),
    ("الأحكام العامة واللائحة التنفيذية لقانون ذوي الإعاقة",
     ["احكام عامه", "اللائحه التنفيذيه", "احكام ختاميه", "قرارات تنفيذيه"],
     ["m64", "m65", "m66", "m67", "m68", "m69", "m70", "m71", "m72"]),
]

# حزم المرسوم بالقانون 15/1979 في شأن الخدمة المدنية — الفرع «إداري». القانون العام للموظف
# الحكومي (يقابل 6/2010 للقطاع الخاص). يُستحضَر بوسم «إداري» أو بمحتوى خدمة مدنية.
# اللاحقة تُلحَق بـ "legis-15-1979-".
_CIVSERVICE_BUNDLES = [
    ("نطاق الخدمة المدنية والتعريفات ومجلس وديوان الخدمة المدنية",
     ["الخدمه المدنيه", "نظام الخدمه المدنيه", "مجلس الخدمه المدنيه", "ديوان الخدمه المدنيه",
      "نطاق التطبيق", "لجنه التخطيط", "الجهات الخاضعه"],
     ["m1", "m2", "m3", "m4", "m5", "m8"]),
    ("تصنيف الوظائف والدرجات والمجموعات النوعية والتدريب",
     ["تصنيف الوظائف", "الدرجات", "مجموعات الوظائف", "ترتيب الوظائف", "التدريب",
      "الوظائف الدائمه", "الوظائف المؤقته", "الوظيفه العامه خدمه وطنيه"],
     ["m9", "m10", "m11", "m12", "m13", "m14"]),
    ("التعيين والترقية والنقل والندب والوظائف القيادية والتعيين تحت التجربة",
     ["التعيين", "الترقيه", "النقل", "الندب", "الوظائف القياديه", "الوظيفه القياديه",
      "التعيين تحت التجربه", "شغل الوظائف", "درجه التعيين", "مده التعيين"],
     ["m15", "m15mkr", "m16", "m17"]),
    ("المرتب والعلاوات وحظر الحجز على المرتب واسترداد المبالغ وتقادمها",
     ["المرتب", "الراتب", "العلاوات", "حظر الحجز", "الخصم من المرتب", "الحجز على المرتب",
      "استرداد المبالغ", "التقادم", "المبالغ المدفوعه بدون وجه حق"],
     ["m18", "m19", "m20", "m21"]),
    ("الإجازات الدورية والدراسية والبعثات في الخدمة المدنية",
     ["الاجازه الدوريه", "الاجازه الدراسيه", "البعثات", "المنح الدراسيه", "الانقطاع عن العمل",
      "اجازه الموظف", "خمسه وثلاثين يوما"],
     ["m22", "m23", "m23mkr"]),
    ("واجبات الموظف العام والمحظورات عليه",
     ["واجبات الموظف", "محظورات الموظف", "يحظر على الموظف", "واجبات الوظيفه",
      "التزامات الموظف الحكومي"],
     ["m24", "m25", "m26"]),
    ("التأديب والعقوبات التأديبية والوقف عن العمل والمسؤولية",
     ["تاديب", "عقوبه تاديبيه", "عقوبات تاديبيه", "مخالفه تاديبيه", "وقف عن العمل",
      "محو العقوبه", "مجلس تاديبي", "مساءله تاديبيه", "فصل تاديبي", "مسئوليه الموظف"],
     ["m27", "m28", "m29", "m30", "m31"]),
    ("انتهاء خدمة الموظف والاستقالة والإحالة إلى التقاعد وسحب قرارات التعيين",
     ["انتهاء الخدمه", "انتهاء خدمه الموظف", "استقاله", "احاله للتقاعد", "احاله الى التقاعد",
      "سحب القرار", "سحب التعيين", "فصل من الخدمه", "بلوغ سن التقاعد"],
     ["m32", "m33", "m34", "m35"]),
    ("الأحكام الختامية وتعديل المرتبات والعلاوات في الخدمة المدنية",
     ["احكام ختاميه", "تعديل المرتبات", "اللوائح والقرارات", "نظم المرتبات", "الهيئات والمؤسسات العامه"],
     ["m36", "m37", "m38", "m39", "m40"]),
]

# حزم نظام الخدمة المدنية (المرسوم 1979) — اللائحة التنفيذية التفصيلية للمرسوم بالقانون
# 15/1979. تُستحضَر مع محتوى الخدمة المدنية لتكمّل القانون بالتفاصيل الإجرائية (لا سيما
# ضمانات التحقيق والتأديب). اللاحقة تُلحَق بـ "legis-nsm-1979-".
_NSM_BUNDLES = [
    ("شروط التعيين واللياقة الصحية والتعيين تحت الاختبار في الخدمة المدنية",
     ["شروط التعيين", "التعيين", "اللياقه الصحيه", "التعيين تحت الاختبار", "فتره الاختبار",
      "المؤهلات", "الكفايه للتعيين"],
     ["m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9", "m10", "m11", "m12", "m13"]),
    ("تقييم كفاءة الموظفين وتقارير الكفاية",
     ["تقييم الكفاءه", "تقرير الكفايه", "تقرير الكفاءه", "التقييم السنوي", "درجه الكفاءه",
      "تقارير الموظفين"],
     ["m14", "m15", "m16", "m17", "m18", "m19"]),
    ("العلاوات الدورية والتشجيعية",
     ["العلاوه الدوريه", "العلاوات", "العلاوه التشجيعيه", "علاوه دوريه"],
     ["m20", "m21"]),
    ("الترقية بالأقدمية وبالاختيار في الخدمة المدنية",
     ["الترقيه", "ترقيه الموظف", "الاقدميه", "الترقيه بالاختيار", "الترقيه بالاقدميه"],
     ["m22", "m23", "m24", "m25", "m26"]),
    ("لجنة شؤون الموظفين والترشيح للوظائف القيادية وشروطها",
     ["لجنه شئون الموظفين", "الوظائف القياديه", "الترشيح للوظيفه القياديه", "لجنه الموظفين",
      "شروط الوظيفه القياديه", "مده التعيين القيادي"],
     ["m27", "m28", "m29", "m30", "m30mkr", "m30mkr1", "m30mkrb", "m30mkrc"]),
    ("النقل والندب والإعارة في الخدمة المدنية",
     ["النقل", "الندب", "الاعاره", "نقل الموظف", "ندب الموظف", "اعاره الموظف"],
     ["m31", "m32", "m33", "m34"]),
    ("الإجازات: الدورية والمرضية والوضع والحج وبدون مرتب في الخدمة المدنية",
     ["الاجازه", "الاجازه الدوريه", "الاجازه المرضيه", "اجازه الوضع", "اجازه بدون مرتب",
      "الاجازه الخاصه", "اجازه الحج", "التصريح بالاجازه", "رصيد الاجازه"],
     ["m35", "m36", "m37", "m38", "m39", "m40", "m41", "m42", "m43", "m44", "m45",
      "m46", "m47", "m48", "m49", "m50", "m51", "m52", "m53"]),
    ("التأديب والتحقيق وضماناته والعقوبات التأديبية والسلطات المختصة",
     ["التاديب", "التحقيق", "التحقيق التاديبي", "الوقف عن العمل", "عقوبه تاديبيه",
      "ضمانات التحقيق", "حضور الموظف", "السلطه التاديبيه", "المجلس التاديبي", "سماع الدفاع",
      "قرار مسبب", "محو العقوبه", "الاحاله للتحقيق", "مساءله الموظف", "الجزاء التاديبي"],
     ["m54", "m55", "m56", "m57", "m58", "m59", "m60", "m61", "m62", "m63", "m64",
      "m65", "m66", "m67", "m68", "m69", "m70"]),
    ("انتهاء خدمة الموظف والاستقالة والغياب وبلوغ سن التقاعد",
     ["انتهاء الخدمه", "استقاله", "بلوغ سن التقاعد", "الغياب عن العمل", "احاله للتقاعد",
      "انهاء الخدمه", "ترك العمل"],
     ["m71", "m72", "m73", "m74", "m75", "m76", "m77", "m78", "m79", "m80", "m81"]),
    ("الأحكام العامة والتظلمات في نظام الخدمة المدنية",
     ["احكام عامه", "التظلم", "تظلم الموظف", "التسويه", "احكام ختاميه", "لجنه التظلمات"],
     ["m82", "m83", "m84", "m85", "m86", "m87", "m88", "m89", "m90", "m91", "m92", "m93", "m94"]),
]

# حزم قانون التأمينات الاجتماعية (61/1976) — قانون تأميني عابر للفروع (يسري على موظفي
# الدولة والقطاعين الأهلي والنفطي). منازعاته إدارية (المؤسسة العامة للتأمينات → القضاء
# الإداري). اللاحقة تُلحَق بـ "legis-61-1976-".
_SOCINS_BUNDLES = [
    ("تعريفات التأمينات الاجتماعية والمؤسسة العامة وإدارتها",
     ["التامينات الاجتماعيه", "المؤسسه العامه للتامينات", "تعريفات التامينات", "مجلس اداره المؤسسه",
      "المؤمن عليه", "صاحب المعاش"],
     ["m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9", "m10", "m10mkr", "m10mkra"]),
    ("تأمين الشيخوخة والعجز والمرض والوفاة والاشتراكات ومعاش التقاعد",
     ["معاش التقاعد", "معاش الشيخوخه", "معاش العجز", "معاش المرض", "معاش الوفاه", "الاشتراكات",
      "اشتراك التامين", "تامين الشيخوخه", "المعاش التقاعدي", "حساب المعاش", "مده الاشتراك",
      "معاش رئيس ونائب الرئيس", "معاش اعضاء مجلس الامه"],
     ["m11", "m12", "m13", "m14", "m15", "m16", "m17", "m17mkr", "m18", "m18mkr", "m19",
      "m19mkr", "m19mkra", "m20", "m21", "m22", "m23", "m24", "m24mkr", "m24mkr1", "m25",
      "m26", "m27", "m28", "m29", "m30", "m30mkr", "m31"]),
    ("تأمين إصابات العمل والأمراض المهنية والعلاج والتعويض والعجز",
     ["اصابه عمل", "اصابه العمل", "اصابات العمل", "المرض المهني", "الامراض المهنيه", "العلاج الطبي",
      "التعويض عن الاصابه", "العجز عن العمل", "التحكيم الطبي", "معاش الاصابه"],
     ["m32", "m33", "m34", "m35", "m36", "m37", "m38", "m39", "m40", "m41", "m42", "m43",
      "m44", "m45", "m46", "m47", "m48", "m49", "m50", "m51", "m52"]),
    ("تأمين الشيخوخة والمرض والوفاة لغير الخاضعين للباب الثالث",
     ["غير الخاضعين للباب الثالث", "التامين الاختياري", "معاش التقاعد للاصحاب", "اصحاب الاعمال",
      "المهن الحره", "التامين على اصحاب الاعمال"],
     ["m53", "m54", "m55", "m56", "m57", "m58", "m59", "m60", "m61", "m62"]),
    ("المستحقون عن المؤمن عليه أو صاحب المعاش والاستبدال والمعونة",
     ["المستحقون", "المستحقين عن المؤمن عليه", "الاستبدال", "استبدال المعاش", "المعونه",
      "الورثه", "توزيع المعاش", "الارمله", "الابناء المستحقون", "قسمه المعاش"],
     ["m63", "m64", "m65", "m66", "m67", "m68", "m69", "m70", "m71", "m72", "m73", "m74",
      "m75", "m76", "m77", "m77mkr", "m77mkra", "m78", "m78mkr", "m79"]),
    ("الأحكام العامة في التأمينات: الجمع بين المعاشات والتقادم والحقوق",
     ["الجمع بين المعاشين", "الجمع بين المعاش", "عدم جواز الجمع", "تقادم حقوق التامينات",
      "الحد الاقصى للمعاش", "زياده المعاش", "ايقاف المعاش", "استرداد المعاش", "احكام عامه للتامينات"],
     ["m80", "m81", "m82", "m83", "m84", "m85", "m86", "m87", "m88", "m89", "m90", "m91",
      "m92", "m93", "m94", "m95", "m96", "m97", "m98", "m99", "m100", "m101", "m102",
      "m103", "m104", "m105", "m106", "m107", "m108", "m109", "m110", "m111", "m112",
      "m112mkr", "m112mkra", "m113", "m114", "m115", "m116", "m117", "m118"]),
    ("العقوبات في قانون التأمينات الاجتماعية",
     ["عقوبات التامينات", "الغرامه", "مخالفه احكام التامينات", "عقوبه صاحب العمل التاميني"],
     ["m119", "m120", "m121", "m122", "m123", "m124"]),
    ("الأحكام الانتقالية في قانون التأمينات الاجتماعية",
     ["احكام انتقاليه", "تسويه المعاشات السابقه", "المعاشات القائمه", "احكام ختاميه للتامينات"],
     ["m125", "m126", "m126mkr", "m127", "m128", "m129", "m130", "m131", "m132"]),
]

# حزم المرسوم بقانون 128/1992 بشأن نظام التأمين التكميلي — مكمّل للتأمين الأساسي (61/1976)،
# تطبّقه المؤسسة العامة للتأمينات. اللاحقة تُلحَق بـ "legis-128-1992-".
_SUPINS_BUNDLES = [
    ("تعريفات التأمين التكميلي ونطاقه والصناديق",
     ["التامين التكميلي", "تامين تكميلي", "التكميلي", "نطاق التامين التكميلي", "صندوق التامين التكميلي",
      "التامين الاساسي"],
     ["m1", "m2", "m3", "m4"]),
    ("ضم المدد واستحقاق المعاش التكميلي وتسويته وتأجيل صرفه",
     ["المعاش التكميلي", "معاش تكميلي", "ضم المدد التكميليه", "تسويه المعاش التكميلي",
      "استحقاق المعاش التكميلي", "تاجيل المعاش التكميلي", "رصيد المؤمن عليه التكميلي"],
     ["m5", "m6", "m7", "m8", "m9"]),
    ("عدم الاستحقاق والاستبدال والعودة للاشتراك والحد الأدنى وأحكام التأمين التكميلي",
     ["عدم استحقاق المعاش التكميلي", "استبدال المعاش التكميلي", "العوده للاشتراك", "الحد الادنى للمعاش",
      "احكام التامين التكميلي", "المعاش التكميلي والاساسي"],
     ["m10", "m11", "m12", "m13", "m14", "m15", "m16", "m17"]),
]

# حزم عنقود تنظيم منظومة العدالة (القضاء/الفتوى/التحقيقات/المحاماة) — الفرع «إداري».
# كل قانون بمعرّفه الخاص. يبدأ بقانون الإدارة العامة للتحقيقات 53/2001 (بادئة legis-53-2001-).
_JUSTORG_BUNDLES = [
    ("اختصاص الإدارة العامة للتحقيقات بوزارة الداخلية وتشكيلها",
     ["الاداره العامه للتحقيقات", "التحقيقات بوزاره الداخليه", "تشكيل التحقيقات", "اختصاص التحقيقات",
      "مدير عام التحقيقات"],
     ["legis-53-2001-m1", "legis-53-2001-m2"]),
    ("تعيين المحققين والمدعين العامين وشروطهم واليمين والتجربة والترقية",
     ["تعيين محقق", "شروط المحقق", "المحقق", "مدعي عام", "رئيس تحقيق", "يمين المحقق",
      "ترقيه اعضاء التحقيقات", "الادعاء العام"],
     ["legis-53-2001-m3", "legis-53-2001-m4", "legis-53-2001-m5", "legis-53-2001-m6",
      "legis-53-2001-m7", "legis-53-2001-m8", "legis-53-2001-m9"]),
    ("مرتبات وبدلات وإجازات وواجبات ومحظورات وحصانة أعضاء الإدارة العامة للتحقيقات",
     ["مرتبات اعضاء التحقيقات", "بدل السكن للمحقق", "اجازات المحققين", "محظورات المحقق",
      "حصانه المحقق", "واجبات عضو التحقيقات", "عدم جواز التحقيق مع المحقق"],
     ["legis-53-2001-m10", "legis-53-2001-m11", "legis-53-2001-m12", "legis-53-2001-m13",
      "legis-53-2001-m14"]),
    ("تأديب أعضاء الإدارة العامة للتحقيقات ومجلس التأديب والتفتيش الفني والعقوبات",
     ["تاديب المحقق", "مجلس تاديب التحقيقات", "لفت النظر", "الدعوى التاديبيه للمحقق",
      "عقوبات المحققين", "التفتيش الفني", "حبس عضو التحقيقات"],
     ["legis-53-2001-m15", "legis-53-2001-m16", "legis-53-2001-m17", "legis-53-2001-m18",
      "legis-53-2001-m19", "legis-53-2001-m20", "legis-53-2001-m21", "legis-53-2001-m22",
      "legis-53-2001-m23"]),
    ("الأحكام العامة والانتقالية لقانون الإدارة العامة للتحقيقات",
     ["نقل اعضاء التحقيقات", "احكام عامه للتحقيقات", "اللائحه التنفيذيه للتحقيقات"],
     ["legis-53-2001-m24", "legis-53-2001-m25", "legis-53-2001-m26", "legis-53-2001-m27"]),
    # قانون تنظيم القضاء 23/1990
    ("المحاكم وأنواعها وولايتها ودرجاتها والجلسات ولغة المحاكم",
     ["تنظيم القضاء", "انواع المحاكم", "ولايه المحاكم", "درجات المحاكم", "محكمه التمييز",
      "محكمه الاستئناف", "المحكمه الكليه", "المحكمه الجزئيه", "اعمال السياده", "علنيه الجلسات",
      "لغه المحاكم"],
     ["legis-23-1990-m1", "legis-23-1990-m2", "legis-23-1990-m3", "legis-23-1990-m4",
      "legis-23-1990-m5", "legis-23-1990-m6", "legis-23-1990-m7", "legis-23-1990-m8",
      "legis-23-1990-m9", "legis-23-1990-m10", "legis-23-1990-m11", "legis-23-1990-m12",
      "legis-23-1990-m13", "legis-23-1990-m14", "legis-23-1990-m15"]),
    ("مجلس القضاء الأعلى وتشكيله واختصاصاته",
     ["مجلس القضاء الاعلى", "المجلس الاعلى للقضاء", "تشكيل مجلس القضاء", "اختصاص مجلس القضاء"],
     ["legis-23-1990-m16", "legis-23-1990-m17", "legis-23-1990-m18"]),
    ("تعيين القضاة وترقيتهم وأقدميتهم وعدم قابليتهم للعزل واستقلال القضاء",
     ["تعيين القضاه", "ترقيه القضاه", "اقدميه القضاه", "عدم قابليه القضاه للعزل", "استقلال القضاء",
      "شروط تعيين القاضي", "درجات القضاه", "نقل القاضي", "ندب القاضي", "عزل القاضي"],
     ["legis-23-1990-m19", "legis-23-1990-m20", "legis-23-1990-m21", "legis-23-1990-m22",
      "legis-23-1990-m23", "legis-23-1990-m24", "legis-23-1990-m25", "legis-23-1990-m26",
      "legis-23-1990-m27", "legis-23-1990-m28", "legis-23-1990-m29", "legis-23-1990-m30",
      "legis-23-1990-m31", "legis-23-1990-m32", "legis-23-1990-m32mkr", "legis-23-1990-m33"]),
    ("واجبات القضاة والجلسات والأحكام والتفتيش القضائي وتأديب القضاة والطعن في قراراتهم",
     ["واجبات القضاه", "التفتيش القضائي", "تاديب القضاه", "تاديب القاضي", "مجلس تاديب القضاه",
      "الطعن في القرارات الخاصه بشئون القضاه", "الجمعيات العامه للمحاكم", "اجازات القضاه"],
     ["legis-23-1990-m34", "legis-23-1990-m35", "legis-23-1990-m36", "legis-23-1990-m37",
      "legis-23-1990-m38", "legis-23-1990-m39", "legis-23-1990-m40", "legis-23-1990-m41",
      "legis-23-1990-m42", "legis-23-1990-m43", "legis-23-1990-m44", "legis-23-1990-m45",
      "legis-23-1990-m46", "legis-23-1990-m47", "legis-23-1990-m48", "legis-23-1990-m49",
      "legis-23-1990-m50", "legis-23-1990-m51", "legis-23-1990-m52"]),
    ("النيابة العامة: اختصاصاتها وتشكيلها وتعيين وترقية وتأديب أعضائها",
     ["النيابه العامه", "اختصاصات النيابه العامه", "تشكيل النيابه العامه", "اعضاء النيابه العامه",
      "تعيين اعضاء النيابه", "ترقيه اعضاء النيابه", "تاديب اعضاء النيابه", "المحامي العام",
      "رئيس النيابه"],
     ["legis-23-1990-m53", "legis-23-1990-m54", "legis-23-1990-m55", "legis-23-1990-m56",
      "legis-23-1990-m57", "legis-23-1990-m57mkr", "legis-23-1990-m58", "legis-23-1990-m59",
      "legis-23-1990-m60", "legis-23-1990-m61", "legis-23-1990-m62", "legis-23-1990-m63",
      "legis-23-1990-m64", "legis-23-1990-m65", "legis-23-1990-m66"]),
    ("العاملون بالمحاكم والنيابة والأحكام الختامية لتنظيم القضاء (المعهد والنادي)",
     ["العاملون بالمحاكم", "معهد الكويت القضائي", "المعهد القضائي", "نادي القضاه",
      "احكام ختاميه للقضاء"],
     ["legis-23-1990-m67", "legis-23-1990-m68", "legis-23-1990-m69", "legis-23-1990-m70",
      "legis-23-1990-m71", "legis-23-1990-m72", "legis-23-1990-m73", "legis-23-1990-m74"]),
    # المرسوم الأميري 12/1960 بشأن تنظيم إدارة الفتوى والتشريع
    ("إدارة الفتوى والتشريع: إلحاقها واختصاصها بالصياغة والفتوى وتمثيل الحكومة أمام القضاء",
     ["اداره الفتوى والتشريع", "الفتوى والتشريع", "صياغه مشروعات القوانين", "ابداء الراي",
      "تمثيل الحكومه امام القضاء", "تمثيل الحكومه امام المحاكم", "المستشار القانوني للحكومه",
      "الفتوى القانونيه"],
     ["legis-12-1960-m1", "legis-12-1960-m2", "legis-12-1960-m3", "legis-12-1960-m4",
      "legis-12-1960-m5", "legis-12-1960-m6", "legis-12-1960-m7", "legis-12-1960-m8",
      "legis-12-1960-m9", "legis-12-1960-m10", "legis-12-1960-m11"]),
    # المرسوم بقانون 10/2020 بشأن التوثيق
    ("التوثيق: التعريفات وإدارة التوثيق والموثق الحكومي والأهلي والسجلات وحجية المحررات",
     ["التوثيق", "الموثق", "الموثق الحكومي", "الموثق الاهلي", "اداره التوثيق", "المحرر الموثق",
      "حجيه المحرر", "سجل التوثيق", "توثيق المحررات", "اعمال التوثيق", "توثيق المحرر", "يوثق",
      "توثيق العقد", "التصديق على التوقيع", "التصديق على التوقيعات", "اثبات التاريخ في المحررات", "موثق حكومي", "موثق اهلي"],
     ["legis-10-2020-m1", "legis-10-2020-m2", "legis-10-2020-m3", "legis-10-2020-m4",
      "legis-10-2020-m5", "legis-10-2020-m5mkr", "legis-10-2020-m6", "legis-10-2020-m7",
      "legis-10-2020-m8", "legis-10-2020-m9", "legis-10-2020-m9mkr"]),
    ("توثيق الوكالات ومددها وترخيص الموثقين الأهليين والرقابة والتأديب والرسوم والعقوبات",
     ["توثيق الوكالات", "مده الوكاله", "ترخيص الموثق", "الموثق الاهلي", "الرقابه على الموثقين",
      "تاديب الموثق", "رسوم التوثيق", "عقوبات التوثيق", "الوكاله الموثقه",
      "الوكاله غير محدده المده", "غير محدده المده", "مده الوكاله خمس سنوات", "انتهاء الوكاله",
      "موثق اهلي", "ترخيص موثق", "تاديب موثق", "رقابه على الموثق"],
     ["legis-10-2020-m10", "legis-10-2020-m11", "legis-10-2020-m12", "legis-10-2020-m13",
      "legis-10-2020-m14", "legis-10-2020-m15", "legis-10-2020-m16", "legis-10-2020-m17",
      "legis-10-2020-m18", "legis-10-2020-m19", "legis-10-2020-m20", "legis-10-2020-m21",
      "legis-10-2020-m22", "legis-10-2020-m23", "legis-10-2020-m24", "legis-10-2020-m25",
      "legis-10-2020-m26", "legis-10-2020-t2025"]),
    # قانون تنظيم مهنة المحاماة 42/1964
    ("المحاماة: القيد بجدول المحامين وشروطه والجداول الملحقة",
     ["محام", "المحاماه", "مهنه المحاماه", "قيد المحامي", "جدول المحامين", "شروط القيد بجدول المحامين",
      "المحامي المشتغل", "جدول المحامين المشتغلين", "القيد بالجدول العام", "اجازه الحقوق",
      "شروط مزاوله المحاماه", "قانون المحاماه"],
     ["legis-42-1964-issawla", "legis-42-1964-issthania", "legis-42-1964-m1", "legis-42-1964-m2", "legis-42-1964-m3", "legis-42-1964-m4", "legis-42-1964-m5", "legis-42-1964-m5mkr", "legis-42-1964-m6"]),
    ("المحاماة: التمرين ولجنة قبول المحامين واليمين وحصانة المحامي",
     ["محام", "المحاماه", "المحامي تحت التمرين", "فتره التمرين", "لجنه قبول المحامين", "قبول المحامي",
      "يمين المحامي", "التحقيق مع محام", "المحامي المقبول امام المحكمه", "نقل اسم المحامي"],
     ["legis-42-1964-m6mkr", "legis-42-1964-m6mkra", "legis-42-1964-m7", "legis-42-1964-m8", "legis-42-1964-m9", "legis-42-1964-m10", "legis-42-1964-m11", "legis-42-1964-m11mkr"]),
    ("المحاماة: حظر الجمع والوكالة والمرافعة والرداء ولغة المحاكم",
     ["محام", "المحاماه", "حظر الجمع بين المحاماه", "الجمع بين الوظيفه والمحاماه", "الترافع ضد", "توكيل المحامي", "المرافعه امام المحاكم", "رداء المحاماه",
      "لغه المرافعه", "بطلان صحيفه الدعوى", "انابه المحامي", "مسئوليه المحامي", "مكتب المحامي"],
     ["legis-42-1964-m12", "legis-42-1964-m13", "legis-42-1964-m14", "legis-42-1964-m15", "legis-42-1964-m16", "legis-42-1964-m17", "legis-42-1964-m18", "legis-42-1964-m19", "legis-42-1964-m20", "legis-42-1964-m21", "legis-42-1964-m22", "legis-42-1964-m23", "legis-42-1964-m24", "legis-42-1964-m25"]),
    ("المحاماة: أتعاب المحاماة وتقديرها وامتيازها وتقادمها",
     ["محام", "المحاماه", "اتعاب المحامي", "اتعاب المحاماه", "تقدير الاتعاب", "امتياز اتعاب المحامي",
      "تقادم اتعاب المحامي", "سقوط حق المحامي في الاتعاب", "اتعاب المحاماه"],
     ["legis-42-1964-m32", "legis-42-1964-m33", "legis-42-1964-m34"]),
    ("المحاماة: التأديب والعقوبات والدعوى التأديبية ومجلس التأديب والطعن وانتحال المهنة",
     ["محام", "المحاماه", "تاديب المحامي", "اشتغل بالمحاماه", "مجلس تاديب المحامين", "العقوبات التاديبيه للمحامي", "محو اسم المحامي",
      "وقف المحامي", "الدعوى التاديبيه للمحامي", "استئناف قرار التاديب", "انتحال مهنه المحاماه",
      "الاشتغال بالمحاماه دون ترخيص", "اعاده قيد المحامي", "غلق مكتب المحامي"],
     ["legis-42-1964-m35", "legis-42-1964-m36", "legis-42-1964-m37", "legis-42-1964-m38", "legis-42-1964-m39", "legis-42-1964-m40", "legis-42-1964-m41", "legis-42-1964-m42", "legis-42-1964-m43", "legis-42-1964-m44", "legis-42-1964-m45", "legis-42-1964-m46"]),
    # قانون تنظيم الخبرة 40/1980 (الخبرة القضائية)
    ("الخبرة: أحكام عامة — ندب الخبير ومأموريته والأمانة والتقرير وحضوره وردّه",
     ["الخبره", "خبير", "الخبراء", "ندب خبير", "ندب الخبير", "ماموريه الخبير", "امانه الخبره",
      "تقرير الخبير", "رد الخبير", "اتعاب الخبير", "اتعاب الخبره", "مصروفات الخبره", "الخبره القضائيه"],
     ["legis-40-1980-iss1", "legis-40-1980-iss2", "legis-40-1980-iss3", "legis-40-1980-iss4", "legis-40-1980-m1", "legis-40-1980-m2", "legis-40-1980-m3", "legis-40-1980-m4", "legis-40-1980-m5", "legis-40-1980-m6", "legis-40-1980-m7", "legis-40-1980-m8", "legis-40-1980-m9", "legis-40-1980-m10", "legis-40-1980-m11", "legis-40-1980-m12", "legis-40-1980-m13", "legis-40-1980-m14", "legis-40-1980-m15", "legis-40-1980-m16", "legis-40-1980-m17", "legis-40-1980-m18", "legis-40-1980-m19", "legis-40-1980-m20", "legis-40-1980-m21", "legis-40-1980-m22", "legis-40-1980-m23",
      # إحالة م17/م18 (تقدير وتظلّم أتعاب الخبير) إلى تقدير وتظلّم مصروفات الدعوى بالمرافعات
      "legis-38-1980-m122", "legis-38-1980-m123", "legis-38-1980-m124"],
    ),
    ("الخبرة: الإدارة العامة للخبراء وتشكيلها وتعيين خبرائها وشروطهم واليمين وتأديبهم",
     ["الخبره", "خبير", "الخبراء", "الاداره العامه للخبراء", "خبراء الاداره", "تعيين خبير",
      "شروط تعيين الخبير", "يمين الخبير", "تاديب الخبير", "واجبات الخبير", "محظورات الخبير"],
     ["legis-40-1980-m24", "legis-40-1980-m25", "legis-40-1980-m26", "legis-40-1980-m27", "legis-40-1980-m28", "legis-40-1980-m29", "legis-40-1980-m30", "legis-40-1980-m31", "legis-40-1980-m32", "legis-40-1980-m33", "legis-40-1980-m34", "legis-40-1980-m35", "legis-40-1980-m36", "legis-40-1980-m37", "legis-40-1980-m38", "legis-40-1980-m39", "legis-40-1980-m40"],
    ),
    ("الخبرة: خبراء الجدول ولجنتهم وقيدهم وتأديبهم وحصانتهم ونظام الخبرة الإلكتروني",
     ["الخبره", "خبير", "الخبراء", "خبراء الجدول", "لجنه خبراء الجدول", "قيد خبراء الجدول",
      "تاديب خبراء الجدول", "حصانه الخبير", "نظام الخبره الالكتروني", "قيد الخبير"],
     ["legis-40-1980-m41", "legis-40-1980-m42", "legis-40-1980-m43", "legis-40-1980-m44", "legis-40-1980-m45", "legis-40-1980-m46", "legis-40-1980-m47", "legis-40-1980-m48", "legis-40-1980-m49", "legis-40-1980-m50", "legis-40-1980-m51", "legis-40-1980-m52", "legis-40-1980-m53", "legis-40-1980-m54"],
    ),
]

# النواة الإجرائية الدائمة — تُستحضَر مع كل استشارة أو دعوى مهما كان الفرع:
#   غير الجزائي ⇒ قانون المرافعات (38/1980): الإعلان/المواعيد + الاختصاص وتقدير القيمة + رفع الدعوى.
#   الجزائي     ⇒ قانون الإجراءات الجزائية (17/1960): يُفعَّل عند إدخال القانون (تُملأ النطاقات حينها).
_CIVIL_PROC_RANGES = ((5, 22), (23, 44), (45, 53))     # legis-38-1980
_PENAL_PROC_RANGES = ((1, 14), (36, 74), (220, 250))   # legis-17-1960 الإجراءات الجزائية:
# التنظيم القضائي والاختصاص (1-14)، التحريات والتحقيق والقبض والحبس الاحتياطي (36-74)،
# والأحكام وطرق الطعن (الاستئناف/الاستئناف العليا) والتنفيذ ورد الاعتبار (220-250).
# النواة المدنية العامة — «المظلّة الكبرى» للقانون الخاص: نظرية العقد والالتزام تُستحضَر
# مع كل مسألة مدنية/تجارية لسدّ الفراغ متى خلا القانون الخاص من نصّ حاكم (م2 تجاري).
_CIVIL_UMBRELLA_RANGES = ((179, 196), (209, 219), (280, 306))  # بطلان/عيوب الرضا + فسخ/الدفع بعدم التنفيذ + تنفيذ الالتزام

def _procedural_core(is_penal):
    out = []
    if is_penal:
        for a, b in _PENAL_PROC_RANGES:
            out.extend("legis-17-1960-m%d" % n for n in range(a, min(b, a + 29) + 1))
    else:
        for a, b in _CIVIL_PROC_RANGES:
            out.extend("legis-38-1980-m%d" % n for n in range(a, min(b, a + 29) + 1))
    return out

def _civil_umbrella():
    """المظلّة المدنية العامة (نظرية العقد والالتزام) — لكل فروع القانون الخاص."""
    out = []
    for a, b in _CIVIL_UMBRELLA_RANGES:
        out.extend("legis-67-1980-m%d" % n for n in range(a, min(b, a + 29) + 1))
    return out

def _admin_core():
    """نواة الاختصاص والإجراءات الإدارية (20/1981) — تُستحضَر لكل منازعة إدارية لمنع نفي
    وجود النص: إنشاء الدائرة الإدارية واختصاصها الوحيد (م1، م2)، ولاية الإلغاء (م5)، عدم وقف
    التنفيذ وجوازه (م6)، ميعاد دعوى الإلغاء ستون يومًا (م7)، التظلم الوجوبي السابق (م8)، رفع
    الدعوى بصحيفة (م9)، الرسم الثابت مائة دينار (م11)، الاستئناف (م12) وميعاده ثلاثون يومًا
    (م14) والحكم الباتّ (م12 مكرر)، والطعن بالتمييز فوق ثلاثين ألف دينار (م14 مكرر)،
    وتطبيق المرافعات تكميليًّا (م15)."""
    return ["legis-20-1981-" + s for s in
            ("m1", "m2", "m5", "m6", "m7", "m8", "m9", "m11",
             "m12", "m12mkr", "m14", "m14mkr", "m15")]

# خريطة الإحالات بين القوانين (تُولَّد server-side من نصوص القاعدة إلى /opt/LegalMind/admin/xref_map.json).
# غيابها = لا توسعة (سلوك آمن). صيغتها: {"معرّف المصدر": ["معرّف الهدف", ...]}
_XREF = {}
import os as _os_xr, json as _json_xr
# مسار مطلق ثابت أولًا (لأن __file__ قد يُحلّ خطأً حسب طريقة تشغيل الخدمة/الحزمة)، ثم بديل نسبيّ للوحدة
for _xrefp in (_os_xr.environ.get("LEGALMIND_XREF_MAP", ""),
               "/opt/LegalMind/admin/xref_map.json",
               _os_xr.path.join(_os_xr.path.dirname(_os_xr.path.abspath(__file__)), "xref_map.json")):
    try:
        if _xrefp and _os_xr.path.exists(_xrefp):
            with open(_xrefp, encoding="utf-8") as _f_xr:
                _XREF = _json_xr.load(_f_xr)
            if _XREF:
                break
    except Exception:
        _XREF = _XREF or {}


# مفاتيح الحماية من العنف الأسري (مرسوم بقانون 11/2026) — مشترَكة بين المسارين الجزائي والأسري،
# بمطابقة لغة الوقائع (لا المصطلح فقط): وصف الاعتداء داخل الأسرة، أمر الحماية، مراكز الإيواء…
_FAMVIOL_KEYS = ("العنف الأسري", "عنف اسري", "العنف الاسري", "الاعتداء الأسري", "أمر الحماية",
    "أوامر الحماية", "مخالفة أمر الحماية", "مراكز الإيواء", "الإيواء", "المعتدى عليه", "بلاغ عنف أسري",
    "الحماية من العنف", "اللجنة الوطنية للحماية", "تسوية النزاع الأسري", "ضرب الزوجة",
    "اعتداء على الزوجة", "إيذاء أحد أفراد الأسرة", "عنف داخل الأسرة", "ضرب الأبناء",
    "اعتداء على الأبناء", "تعنيف", "زوج يضرب زوجته", "اعتداء زوجي", "عنف منزلي", "إساءة أسرية",
    # محفّزات لغة الوقائع (وصف الاعتداء داخل الأسرة بمختلف صيغه):
    "اعتداء الأب", "اعتداء الأم", "اعتداء الزوج", "اعتداء على الأطفال", "ضرب الأطفال",
    "ضرب الأبناء", "إيذاء الأبناء", "إيذاء الأطفال", "إيذاء الطفل", "العنف ضد المرأة",
    "العنف ضد الأطفال", "العنف ضد الأبناء", "عنف ضد الزوجة", "إساءة معاملة الأبناء",
    "اعتداء داخل الأسرة", "تهديد داخل الأسرة", "ضرب داخل المنزل")


# المواد الحاكمة (العملية) في 11/2026 دون الإدارية/المؤسسية (اللجنة الوطنية م2-4/6، الإبلاغ الداخلي م12،
# نزاع الأغراض م17، حظر النشر م22، الإعلان م23، الاستعانة بالشرطة م24، الضبطية م27، اللائحة/الإلغاء/التنفيذ
# م29-31). تقليصها يُفسح مقعدًا في الميزانية لموادّ الضرب (16/1960) والتسوية الأسرية (12/2015) في الاستشارة نفسها.
_FAMVIOL_CORE = (1, 5, 7, 8, 9, 13, 14, 16, 18, 21, 25, 28)


def _famviol_ids(blob):
    """معرّفات المواد الحاكمة من قانون الحماية من العنف الأسري 11/2026 إن طابقت الوقائع
    (المواد العملية فقط لتنجو من قصّ الميزانية وتُفسح لغيرها من مجالات الجسر)."""
    if any(_draft_norm_ar(k) in blob for k in _FAMVIOL_KEYS):
        return ["legis-11-2026-m%d" % n for n in _FAMVIOL_CORE]
    return []


# حِزم استرجاع النواة الجزائية الموضوعية. لكل حزمة بادئةُ قانونها ونطاقُ موادّها، تُفعَّل بوسم
# الفرع «جزائي». جرائم أمن الدولة والرشوة تُشير إلى 31/1970 (المستبدِل) بدل 16/1960 (92-125 المعدّلة/الملغاة).
# الصيغة: (اسم, مفاتيح, بادئة القانون, من, إلى). المفاتيح تُطبَّع عند المطابقة (_draft_norm_ar).
_PENAL_BUNDLES = [
    # الحماية من العنف الأسري 11/2026 تُستحضَر عبر _famviol_ids (المواد الحاكمة فقط) في مساري الفرعين،
    # لا كنطاقٍ كامل هنا، حتى تنجو معها موادّ الجسر (الضرب/التسوية) من قصّ الميزانية.
    # الكشف عن العمولات في عقود الدولة (25/1996) — قانون خاصّ عقابيّ لمكافحة الفساد؛ 7 مواد كلها حاكمة
    # (م2 وجوب الكشف، م3 الإقرار لديوان المحاسبة، م4 عقوبة عدم الإقرار، م5 عقوبة البيان الكاذب/الإخفاء).
    # يُقدَّم في الترتيب لتنجو مواده — خاصّةً العقوبات م4/م5 — من قصّ الميزانية عند تزاحم حِزم 31/1970.
    # مفاتيح مطعّمة بالمصطلح المجرّد (عمولة/عمولات) + صور العقد الحكومي، لتُطابق لغة الوقائع الطبيعية
    # («عمولة نقدية لوسيط»، «عقد توريد مع وزارة») لا الصيغ المتلاصقة فقط؛ آمنة لأنها داخل الفرع الجزائي.
    ("الكشف عن العمولات في عقود الدولة", ("عمولة", "عمولات", "العمولة", "العمولات",
        "الكشف عن العمولات", "عمولة لوسيط", "عمولة نقدية", "عمولة عينية", "منفعة لوسيط",
        "وسيط", "الوسيط", "لوسيط", "عقد توريد", "عقد التوريد", "عقود التوريد", "صفقة أسلحة",
        "صفقات الأسلحة", "إرساء الصفقة", "إرساء المناقصة", "ترسية", "أشغال عامة", "الأشغال العامة",
        "الإقرار عن العمولة", "إخفاء العمولة", "لم يكشف عن العمولة", "عدم الكشف", "ديوان المحاسبة",
        "عقد مع جهة حكومية", "عقد حكومي", "المتعاقد مع الدولة"), "legis-25-1996", 1, 7),
    # مسؤولية الشخص الاعتباري (الشركات) عن جرائم الفساد — 31/1970 م59-61 (تُحيل إلى تعريف م22 من 2/2016).
    # جرائم الرشوة/العمولات كثيرًا ما تُرتكب باسم شركة، فتلزم استحضار عقوبة الشخص الاعتباري ولو لم يُذكر
    # «اختلاس». تُقدَّم في الترتيب (بعد العمولات مباشرةً) لتنجو موادّها الثلاث من قصّ الميزانية عند تزاحم الحِزم.
    ("مسؤولية الشخص الاعتباري (الشركات) عن جرائم الفساد", ("الشخص الاعتباري", "الشخص المعنوي",
        "مسؤولية الشخص الاعتباري", "مسؤولية الشركة", "مسؤولية الشركات", "المسؤولية الجزائية للشركة",
        "عقوبة الشركة", "عقوبة الشخص الاعتباري", "حرمان من التعاقد الحكومي", "استبعاد من التعاقد",
        "حرمان الشركة", "شركة متورطة في فساد", "شركة دفعت رشوة", "مسؤولية الشركة عن الفساد",
        "الشركة عن جريمة فساد", "للشركة", "وللشركة", "مسؤولية الموظف والشركة"), "legis-31-1970", 59, 61),
    # عقوبات إقرار الذمة المالية والكسب غير المشروع (2/2016 م46-48): م46 عقوبة التأخّر/عدم تقديم الإقرار
    # (غرامة + جواز العزل)، م47 الإقرار الناقص/غير الصحيح، م48 جريمة الكسب غير المشروع (حبس + مصادرة).
    # تُقدَّم في الترتيب لأنّ جزاء «عدم تقديم الإقرار» لغته بعيدة دلاليًّا فلا يجلبه المتجه (كما ظهر في الاختبار).
    ("عقوبات إقرار الذمة المالية والكسب غير المشروع (2/2016)", ("إقرار الذمة", "الذمة المالية",
        "لم يقدم إقرار", "لم يقدم إقراره", "عدم تقديم الإقرار", "عدم تقديم إقرار الذمة",
        "تأخر عن تقديم الإقرار", "التأخر في تقديم الإقرار", "التخلف عن تقديم الإقرار",
        "الكسب غير المشروع", "إقرار ناقص", "إقرار غير صحيح", "تضخم الذمة", "عقوبة الذمة المالية"),
        "legis-2-2016", 46, 48),
    # هيئة مكافحة الفساد والذمة المالية (2/2016) — قانون خاصّ عقابيّ/رقابيّ. خمس حزم موضوعية
    # (تعريف جرائم الفساد والتحقيق، الذمة المالية، حماية المبلّغين، العقوبات، الهيئة واختصاصها).
    # م22 تُغلق إحالة م59/م60 من 31/1970. يُقدَّم في الترتيب لتنجو مواده الحاكمة من قصّ الميزانية.
    ("تعريف جرائم الفساد والتحقيق فيها (2/2016)", ("جرائم الفساد", "جريمة فساد", "تعريف الفساد",
        "الفساد", "هيئة مكافحة الفساد", "نزاهة", "مكافحة الفساد", "الكسب غير المشروع",
        "إجراءات الضبط والتحقيق", "التحقيق في الفساد", "ضبط جرائم الفساد"), "legis-2-2016", 22, 29),
    ("إقرارات الذمة المالية (2/2016)", ("الذمة المالية", "إقرار الذمة", "الكشف عن الذمة المالية",
        "إقرارات الذمة", "الخاضعون لإقرار الذمة", "تضخم الذمة", "إقرار الذمة المالية",
        "عدم تقديم إقرار الذمة", "فحص إقرار الذمة", "سرية إقرار الذمة"), "legis-2-2016", 30, 36),
    ("حماية المبلّغين والإبلاغ عن الفساد (2/2016)", ("المبلّغ", "المبلغ", "المبلغ عن الفساد",
        "البلاغ عن الفساد", "حماية المبلغين", "حماية المبلّغين", "برنامج الحماية", "حماية الشهود",
        "الإبلاغ عن جريمة فساد", "الإبلاغ عن الفساد", "المخبر", "بلاغ عن فساد", "أبلغ عن",
        "بلّغ عن", "بلغ عن جريمة", "طلب الحماية", "يطلب الحماية", "حماية الشاهد", "حماية من الانتقام"),
        "legis-2-2016", 37, 43),
    ("عقوبات مكافحة الفساد والذمة المالية (2/2016)", ("عقوبة الفساد", "عقوبات جرائم الفساد",
        "عقوبة عدم تقديم إقرار الذمة", "مخالفة قانون الذمة المالية", "عقوبة إفشاء أسرار الهيئة",
        "عقوبة المبلغ الكاذب", "بلاغ كاذب عن الفساد", "إفشاء أسرار مكافحة الفساد"), "legis-2-2016", 44, 53),
    ("الهيئة العامة لمكافحة الفساد — الإنشاء والاختصاص (2/2016)", ("الهيئة العامة لمكافحة الفساد",
        "نزاهة", "مجلس الأمناء", "اختصاصات هيئة مكافحة الفساد", "الجهاز التنفيذي للهيئة",
        "أهداف هيئة مكافحة الفساد", "إنشاء هيئة مكافحة الفساد"), "legis-2-2016", 1, 21),
    # ── قانون حقوق الطفل 21/2015 (فرع جزائي؛ فصل عقوبات يجرّم الاعتداء على الطفل + إطار الحماية) ──
    # العقوبات أولًا لتنجو من قصّ الميزانية؛ ثمّ الحماية والحقوق والموضوعات (صحة/حضانة/تعليم/عمل/إعاقة).
    ("عقوبات جرائم الاعتداء على الطفل (21/2015)", ("الاعتداء على الطفل", "إيذاء الطفل", "الإساءة للطفل",
        "تعنيف الطفل", "ضرب الطفل", "استغلال الطفل", "إهمال الطفل", "تعريض الطفل للخطر", "جريمة ضد طفل",
        "جريمة على طفل", "عقوبة إيذاء الطفل", "التحرش بطفل", "تشغيل الطفل", "الاتجار بالطفل",
        "تضاعف العقوبة إذا وقعت على طفل", "التسول بالطفل", "حرمان الطفل من التعليم",
        # صيغ نكرة/أفعال تطابق لغة الوقائع:
        "اعتدى على طفل", "اعتداء على طفل", "ضرب طفل", "إيذاء طفل", "أصاب طفلا", "إساءة لطفل",
        "استغلال طفل", "التحرش بالطفل", "تحرش بطفل", "اعتدى على الطفل", "جناية على طفل",
        "على طفل", "ضرب طفلا", "اعتدى بالضرب", "عنف ضد طفل", "أذى طفلا"),
        "legis-21-2015", 80, 94),
    ("الطفل المعرّض للخطر ومراكز حماية الطفولة (21/2015)", ("الطفل المعرض للخطر", "حماية الطفل",
        "مراكز حماية الطفولة", "تدابير حماية الطفل", "الطفل في خطر", "الطفل المعرض للأذى",
        "إجراءات حماية الطفل", "انتزاع الطفل من الخطر", "طفل معرض للخطر", "معرض للخطر",
        "تعريض الطفل للخطر", "طفل في خطر", "طفل مهمل", "إهمال والديه", "الطفل المهمل"),
        "legis-21-2015", 76, 79),
    ("الإبلاغ عن إيذاء الطفل والحماية الطبية (21/2015)", ("الإبلاغ عن إيذاء الطفل", "الإشعار عن الطفل",
        "التبليغ عن إساءة معاملة الطفل", "إشعار مركز حماية الطفل", "التقرير الطبي للطفل المعتدى عليه"),
        "legis-21-2015", 26, 29),
    ("حقوق الطفل الأساسية والنسب والاسم (21/2015)", ("حقوق الطفل", "حقوق الطفل الأساسية", "حق الطفل في النسب",
        "نسب الطفل", "اسم الطفل", "تعريف الطفل", "تصنيف الأطفال", "حق الطفل في الحياة"), "legis-21-2015", 1, 6),
    ("صحة الطفل والميلاد والتطعيم (21/2015)", ("صحة الطفل", "تطعيم الطفل", "تحصين الطفل", "شهادة الميلاد",
        "التبليغ عن المواليد", "قيد المواليد", "البطاقة الصحية للطفل", "الطفل حديث الولادة", "الطفل اللقيط",
        "غذاء الطفل", "رعاية الحامل"), "legis-21-2015", 7, 25),
    ("حضانة الطفل ورعايته البديلة (21/2015)", ("دور الحضانة", "الحضانة العائلية", "الأسر البديلة",
        "رعاية الطفل", "مؤسسات رعاية الأطفال", "الطفل المحروم من الرعاية الأسرية", "نادي الطفل",
        "الطفل مجهول الوالدين"), "legis-21-2015", 30, 37),
    ("تعليم الطفل (21/2015)", ("تعليم الطفل", "التعليم الإلزامي", "رياض الأطفال", "حق الطفل في التعليم",
        "مراحل التعليم", "حرمان الطفل من التعليم"), "legis-21-2015", 38, 45),
    ("عمل الطفل والأم العاملة (21/2015)", ("عمل الطفل", "تشغيل الطفل", "عمالة الأطفال", "حظر تشغيل الطفل",
        "سن تشغيل الطفل", "ساعات عمل الطفل", "الأم العاملة", "إجازة رعاية الطفل", "رضاعة الطفل",
        "دار حضانة في مكان العمل", "شغل طفل", "تشغيل طفل", "عمل طفل", "شغّل طفلا", "شغل طفلا",
        "عمالة طفل", "تشغيل الأطفال", "تشغيل حدث"), "legis-21-2015", 46, 56),
    ("الطفل ذو الإعاقة (21/2015)", ("الطفل ذو الإعاقة", "الطفل ذي الإعاقة", "ذي الإعاقة", "ذو الإعاقة",
        "الطفل المعاق", "تأهيل الطفل", "التأهيل", "إعاقة الطفل", "رعاية الطفل المعاق",
        "وقاية الطفل من الإعاقة", "الأطفال ذوي الإعاقة"), "legis-21-2015", 57, 64),
    ("الطفل في نزاع مع القانون وسلامته وحمايته الإعلامية (21/2015)", ("الطفل في نزاع مع القانون",
        "الحدث الجانح", "الأحداث", "قيادة الطفل مركبة", "سفر الطفل", "سلامة الطفل في المركبات",
        "المطبوعات الضارة بالطفل", "حماية الطفل في الإعلام", "المحتوى الضار للأطفال", "الطفل والسينما",
        "تعريف الإهمال", "مطبوعات ضارة", "الضارة بالأطفال", "محتوى ضار للأطفال", "مصنفات للأطفال",
        "نشر ضار للأطفال", "ثقافة الطفل"), "legis-21-2015", 65, 75),
    # ── قانون الأحداث 111/2015 (فرع جزائي؛ الحدث في نزاع مع القانون: تدابير/عقوبات/محكمة/إفراج) ──
    ("تعريف الحدث وسنّ المسؤولية ولجنة الرعاية (111/2015)", ("الحدث", "الأحداث", "قانون الأحداث",
        "سن المسؤولية الجزائية", "الحدث المنحرف", "الحدث المعرض للانحراف", "حدث ارتكب", "حدث عمره",
        "لجنة رعاية الأحداث", "الطفل الجانح", "المسؤولية الجزائية للحدث"), "legis-111-2015", 1, 4),
    ("تدابير الأحداث غير العقابية (111/2015)", ("تدابير الحدث", "التدبير على الحدث", "الاختبار القضائي",
        "تسليم الحدث", "إيداع الحدث", "التدريب المهني للحدث", "الإلزام بواجبات", "مراقب السلوك",
        "تدبير للحدث", "الحدث من سبع إلى خمس عشرة"), "legis-111-2015", 5, 14),
    ("عقوبات الأحداث والحبس والحبس الاحتياطي (111/2015)", ("عقوبة الحدث", "عقوبة الأحداث", "حبس الحدث",
        "الحبس الاحتياطي للحدث", "لا إعدام على الحدث", "لا حبس مؤبد على الحدث", "معاقبة الحدث",
        "الحدث الذي أكمل الخامسة عشرة", "تنفيذ العقوبة على الحدث", "الحدث في المؤسسة العقابية"),
        "legis-111-2015", 15, 32),
    ("محكمة ونيابة الأحداث والمحاكمة والاستئناف (111/2015)", ("محكمة الأحداث", "نيابة الأحداث",
        "شرطة حماية الأحداث", "محاكمة الحدث", "محاكمة الأحداث", "اختصاص محكمة الأحداث",
        "استئناف أحكام الأحداث", "الطعن في أحكام الأحداث", "إجراءات محاكمة الحدث", "الصلح مع الحدث",
        "الادعاء المدني أمام محكمة الأحداث"), "legis-111-2015", 33, 60),
    ("الإفراج تحت شرط عن الحدث وأحكام ختامية (111/2015)", ("الإفراج تحت شرط عن الحدث", "الإفراج الشرطي للحدث",
        "حظر نشر أسماء الأحداث", "نشر أسماء الأحداث", "نشر صور الأحداث", "إعفاء الحدث من الرسوم",
        "إساءة سلوك الحدث المفرج عنه", "الإفراج تحت شرط عن حدث", "إفراج تحت شرط عن حدث",
        "الإفراج عن الحدث", "الإفراج تحت شرط عن الأحداث"), "legis-111-2015", 61, 69),
    ("مبادئ ومشروعية وتقادم", ("لا جريمة إلا بنص", "مبدأ الشرعية", "الشرعية الجزائية",
        "تقادم الدعوى الجزائية", "سقوط الدعوى الجزائية", "سقوط العقوبة", "تقادم العقوبة",
        "انقطاع التقادم", "سريان قانون الجزاء", "الجنايات والجنح", "تعريف الجناية", "تعريف الجنحة"),
        "legis-16-1960", 1, 17),
    ("المسؤولية الجنائية والسن والجنون", ("المسؤولية الجنائية", "سن المسؤولية", "الحدث الجانح",
        "الصغير", "الجنون", "العته", "السكر", "فقد الوعي", "الإكراه", "حالة الضرورة", "موانع المسؤولية"),
        "legis-16-1960", 18, 26),
    ("أسباب الإباحة والدفاع الشرعي", ("أسباب الإباحة", "الدفاع الشرعي", "استعمال الحق",
        "أداء الواجب", "رضاء المجني عليه", "تنفيذ أمر تجب طاعته"), "legis-16-1960", 27, 44),
    ("الشروع والمساهمة الجنائية", ("الشروع", "الشروع في الجريمة", "المساهمة الجنائية",
        "الفاعل الأصلي", "الشريك", "التحريض", "الاتفاق الجنائي", "المساعدة على الجريمة"), "legis-16-1960", 45, 56),
    ("العقوبات الأصلية والتبعية", ("العقوبات الأصلية", "الإعدام", "الحبس المؤبد", "الحبس المؤقت",
        "الغرامة", "العقوبات التبعية", "العقوبات التكميلية", "المصادرة", "تعدد العقوبات", "تعدد الجرائم"),
        "legis-16-1960", 57, 79),
    ("تفريد العقوبة والإفراج الشرطي", ("تشديد العقوبة", "تخفيف العقوبة", "الظروف المشددة",
        "الظروف المخففة", "العذر القانوني", "العود", "وقف تنفيذ العقوبة", "الإفراج تحت شرط",
        "الإفراج الشرطي", "رد الاعتبار"), "legis-16-1960", 80, 91),
    # أمن الدولة — المستبدَل بالقانون 31/1970: الخارجي (م1-22) والداخلي (م23-34)، مقسومًا لتفادي حدّ الـ30
    ("جرائم أمن الدولة الخارجي", ("أمن الدولة", "الجرائم الماسة بأمن الدولة", "الخيانة", "التجسس",
        "أمن الدولة الخارجي", "التعامل مع دولة أجنبية", "إفشاء أسرار الدفاع"), "legis-31-1970", 1, 22),
    ("جرائم أمن الدولة الداخلي", ("أمن الدولة", "الجرائم الماسة بأمن الدولة", "قلب نظام الحكم",
        "الانقلاب", "الإرهاب", "التجمهر", "أمن الدولة الداخلي", "المتفجرات",
        "الجمعيات غير المشروعة", "قلب نظام الحكم بالقوة"), "legis-31-1970", 23, 34),
    ("حرمة الأديان والجرائم الماسة بالدين", ("حرمة الأديان", "ازدراء الأديان", "إهانة الدين",
        "الشعائر الدينية", "سب الذات الإلهية"), "legis-16-1960", 109, 125),
    # الرشوة واستغلال النفوذ — الفصل الأول من الباب الثاني (م35-43): م35 عقوبة المرتشي الأصلية،
    # م36-38 صور القبول والتعريف، م39 الراشي والوسيط، م40 التشديد، م41 العرض، م42 المصادرة، م43 من في حكم الموظف.
    # مفاتيح مصطلحية + بلا «ال» + محفّزات لغة الوقائع (تُطابق وصف الواقعة بلا مصطلح «رشوة»)؛
    # آمنة لأنها تُفعَّل داخل الفرع الجزائي فقط.
    ("الرشوة واستغلال النفوذ", ("رشوة", "الرشوة", "مرتشي", "راشي", "الوسيط في الرشوة", "عرض رشوة",
        "استغلال النفوذ", "طلب عطية", "وعد أو عطية", "مقابل عمل من أعمال الوظيفة", "أدى له بغير حق",
        "مبلغ مقابل", "مبلغا مقابل", "مقابل إنجاز", "مقابل أداء عمل", "مقابل أداء", "طلب مبلغ",
        "قبض مبلغ", "قبض المبلغ", "دفع مبلغ للموظف", "هدية للموظف", "عطية للموظف",
        "مقابل ترسية", "مقابل الترسية", "مبالغ مقابل", "تلقى مبالغ", "مبالغ مقابل ترسية",
        "مقابل ترسية عقد", "لترسية العقد", "مقابل ترسية العقد", "دفعت للموظف مقابل"),
        "legis-31-1970", 35, 43),
    # الاختلاس والغدر وسوء معاملة الأفراد — الفصول 2-4 (م44-61)
    ("الاختلاس والغدر وسوء معاملة الأفراد", ("الاختلاس", "اختلاس المال العام", "الأموال الأميرية",
        "الغدر", "إساءة استعمال السلطة", "سوء معاملة الموظفين", "التعذيب", "القبض بدون وجه حق",
        "استغلال الوظيفة", "الإضرار بالمال العام"), "legis-31-1970", 44, 61),
    ("جرائم الوظيفة (قانون الجزاء)", ("الرشوة", "المرتشي", "الاختلاس", "استغلال الوظيفة",
        "الموظف العام", "التعذيب", "القبض بدون وجه حق"), "legis-16-1960", 126, 135),
    ("شهادة الزور والبلاغ الكاذب وانتحال الصفة", ("شهادة الزور", "اليمين الكاذبة", "البلاغ الكاذب",
        "الوشاية الكاذبة", "انتحال صفة", "انتحال وظيفة", "فض الأختام"), "legis-16-1960", 136, 148),
    ("القتل والإيذاء والإجهاض والخطف", ("القتل", "القتل العمد", "سبق الإصرار", "القتل الخطأ",
        "الضرب", "الجرح", "الإيذاء", "الإصابة", "التعرض للخطر", "ترك الأطفال", "الإجهاض",
        "الخطف", "الحجز", "الاتجار بالرقيق", "الإهمال المفضي"), "legis-16-1960", 149, 178),
    ("الجرائم الجنسية والعرض والقذف والسب", ("الزنا", "اللواط", "هتك العرض", "الاغتصاب",
        "الفعل الفاضح", "خدش الحياء", "التحريض على الفجور", "الدعارة", "القمار", "القذف",
        "السب", "إفشاء الأسرار"), "legis-16-1960", 186, 215),
    ("السرقة والنصب وخيانة الأمانة", ("السرقة", "السرقة بالإكراه", "النصب", "الاحتيال",
        "خيانة الأمانة", "التبديد", "إساءة الائتمان", "انتزاع المال"), "legis-16-1960", 217, 241),
    ("الحريق والإتلاف والتزوير وتقليد المسكوكات", ("الحريق", "الإتلاف", "التخريب", "التزوير",
        "تزوير المحررات", "المحررات الرسمية", "المحررات العرفية", "استعمال محرر مزور",
        "تقليد الأختام", "تزييف العملة", "المسكوكات", "تزوير الطوابع"), "legis-16-1960", 242, 271),
    ("جرائم الإفلاس والإضرار بالدائنين", ("الإفلاس", "التفليس بالتدليس", "التفليس بالتقصير",
        "الإضرار بالدائنين", "التصرف في الأموال إضرارًا", "المدين المفلس"), "legis-16-1960", 274, 286),
    # ── قانون الأسلحة والذخائر 13/1991 (فرع جزائي؛ ترخيص الحيازة/الاستيراد وحظرها والعقوبات) ──
    # ملاحظة: مواد م21/م22/م24 لها «مكرر» لا يبلغها نطاقُ الأرقام؛ تُجلب المكرّرات صراحةً عبر _weapons_ids.
    ("الأسلحة والذخائر — التعريفات والترخيص وشروطه وإلغاؤه", ("سلاح", "أسلحة", "ذخيرة", "ذخائر",
        "مسدس", "بندقية", "ترخيص سلاح", "ترخيص حمل السلاح", "حيازة سلاح", "إحراز سلاح", "شروط الترخيص",
        "الأسلحة البيضاء", "سلاح أبيض", "الأسلحة الهوائية", "كاتم صوت", "كاتمات الصوت"), "legis-13-1991", 1, 5),
    ("الأسلحة — التزامات الحيازة والأماكن المحظورة والإعفاءات", ("فقد السلاح", "سرقة السلاح",
        "وفاة حائز السلاح", "نقل حيازة السلاح", "الأماكن المحظورة", "حمل السلاح في", "استعمال السلاح في",
        "إعفاء من الترخيص", "أفراد الشرطة", "الحرس الوطني", "الرماية"), "legis-13-1991", 6, 15),
    ("الأسلحة — الاستيراد والاتجار والإصلاح والنقل", ("استيراد الأسلحة", "الاتجار في الأسلحة",
        "إصلاح الأسلحة", "مصنع أسلحة", "نقل الأسلحة", "تصنيع السلاح", "دفتر الأسلحة"), "legis-13-1991", 16, 20),
    ("الأسلحة — العقوبات والمصادرة وإيقاع الروع", ("عقوبة حيازة السلاح", "عقوبة السلاح", "مصادرة السلاح",
        "إيقاع الروع", "التلويح بالسلاح", "حمل سلاح في مكان عام", "عقوبة الأسلحة البيضاء",
        "عقوبة كاتم الصوت", "عقوبة المدفع"), "legis-13-1991", 21, 25),
    # ── قانون حماية الأموال العامة 1/1993 (فرع جزائي؛ جرائم المال العام وتشديدها) ──
    # ملاحظة: م21 مكرر (عدم سقوط الدعوى بالتقادم) لا يبلغه نطاقُ الأرقام؛ يُجلب صراحةً عبر _publicfunds_ids.
    ("حماية المال العام — أحكام عامة والاختصاص", ("حماية الأموال العامة", "حماية المال العام",
        "المال العام", "الأموال العامة", "في حكم الموظف العام", "الاختصاص خارج الكويت",
        "النيابة العامة بالمال العام", "حفظ التحقيق"), "legis-1-1993", 1, 5),
    ("حماية المال العام — رقابة ديوان المحاسبة والإخطار", ("ديوان المحاسبة", "الإخطار عن الأموال",
        "لجنة حماية الأموال العامة", "الاستثمارات الحكومية", "الرقابة على المال العام",
        "موافاة ديوان المحاسبة"), "legis-1-1993", 6, 8),
    ("حماية المال العام — الاختلاس والاستيلاء والربح غير المشروع", ("اختلاس المال العام", "اختلاس أموال عامة",
        "الاستيلاء على المال العام", "الاستيلاء بغير حق", "الإضرار بمصلحة الجهة", "الربح غير المشروع",
        "المقاولات والتوريدات", "عمولة غير مشروعة", "منفعة من عمل حكومي"), "legis-1-1993", 9, 12),
    ("حماية المال العام — الإفشاء والإضرار الجسيم والوثائق والعزل والرد", ("إفشاء أسرار الوظيفة",
        "الإضرار الجسيم بالمال العام", "الإهمال الوظيفي", "التفريط في أداء الوظيفة", "الاحتفاظ بوثائق رسمية",
        "العزل والرد", "غرامة تعادل ضعف", "الإضرار بالخطأ الجسيم"), "legis-1-1993", 13, 16),
    ("حماية المال العام — الإبلاغ والإعفاء ورد المال وعدم التقادم", ("تأخير الإخطار", "عدم الإبلاغ عن الجريمة",
        "البيانات الكاذبة", "الإعفاء من العقاب", "رد الأموال العامة", "عدم سقوط الدعوى بالتقادم",
        "عدم انقضاء الدعوى بالتقادم", "لا تنقضي الدعوى"), "legis-1-1993", 17, 22),
    ("حماية المال العام — الإجراءات التحفظية ومنع السفر والتصرف", ("منع السفر", "منع التصرف في الأموال",
        "التحفظ على الأموال", "الإجراءات التحفظية", "تهريب الأموال", "بطلان تصرفات المحكوم عليه",
        "التحفظ على أموال المتهم", "منع التصرف والإدارة"), "legis-1-1993", 23, 28),
    # ── قانون مكافحة المخدرات 159/2025 (فرع جزائي؛ الجرائم والعقوبات والعلاج) ──
    # ملاحظة: الحزم بنطاق الأرقام؛ ومحفّز _drugs_ids يضمن نجاة مواد العقوبات المحورية وعدم التقادم مبكّرًا.
    ("المخدرات — التعريفات والكيانات والمراكز", ("تعريف المخدرات", "المؤثرات العقلية", "السلائف الكيميائية",
        "المجلس الأعلى لمكافحة المخدرات", "مركز التأهيل", "مركز علاج الإدمان", "المدمن", "المتعاطي"),
        "legis-159-2025", 1, 4),
    ("المخدرات — تراخيص الاستيراد والتصدير والنقل", ("استيراد المخدرات", "تصدير المخدرات", "نقل المخدرات",
        "ترخيص المخدرات", "الإفراج الجمركي عن المخدرات", "استيراد المؤثرات العقلية"), "legis-159-2025", 5, 15),
    ("المخدرات — تراخيص الاتجار والحيازة الطبية والوصفات", ("الاتجار في المخدرات", "الوصفة الطبية للمخدر",
        "صرف المخدر", "حيازة الطبيب للمخدر", "الصيدلي والمخدر", "وصفة مؤثر عقلي", "حيازة طبية"),
        "legis-159-2025", 16, 31),
    ("المخدرات — الإنتاج والزراعة والسجلات", ("إنتاج المخدرات", "صنع المخدرات", "زراعة النباتات المخدرة",
        "مصنع أدوية مخدر", "سجلات المخدرات", "تعديل الجداول"), "legis-159-2025", 32, 41),
    ("المخدرات — العقوبات: الاتجار والجلب والتصنيع والتنظيم العصابي (الإعدام/المؤبد)", ("الاتجار بالمخدرات",
        "جلب المخدرات", "تهريب المخدرات", "زراعة بقصد الاتجار", "الترويج", "المقايضة بالمخدر",
        "الإعدام في المخدرات", "المؤبد في المخدرات", "تنظيم عصابي للمخدرات", "الظروف المشددة"),
        "legis-159-2025", 42, 47),
    ("المخدرات — العقوبات: الحيازة والتعاطي وإدارة مكان التعاطي", ("حيازة المخدرات", "تعاطي المخدرات",
        "الاستعمال الشخصي", "إدارة مكان التعاطي", "الحيازة المجردة", "التعاطي في السجون",
        "جدول 3 مخدر", "المجموعة الرابعة"), "legis-159-2025", 48, 52),
    ("المخدرات — العقوبات: الطبيب والشخص الاعتباري والترويج والتحريض", ("وصفة بقصد التعاطي", "الطبيب المخالف",
        "الشخص الاعتباري في المخدرات", "الترغيب والإغراء على التعاطي", "الدعاية للمخدرات",
        "جريمة العنف تحت تأثير المخدر"), "legis-159-2025", 53, 60),
    ("المخدرات — العلاج والإيداع (بدائل العقوبة)", ("المدمن المتقدم للعلاج", "الإبلاغ عن المدمن",
        "إيداع المتعاطي", "مركز التأهيل", "بديل العقوبة بالعلاج", "الإفراج عن المودع",
        "فحص الكشف عن التعاطي"), "legis-159-2025", 61, 67),
    ("المخدرات — صدور الأحكام والمصادرة وعدم التقادم والاختصاص", ("مصادرة المخدرات", "إتلاف المخدرات",
        "عدم سقوط الدعوى بالتقادم في المخدرات", "عدم التقادم", "اختصاص محكمة الجنايات بالمخدرات",
        "المكافأة عن ضبط المخدرات", "وقف تنفيذ السجين الأجنبي", "الإبعاد"), "legis-159-2025", 68, 78),
    # ── قانون مكافحة غسل الأموال وتمويل الإرهاب 106/2013 (فرع جزائي) ──
    ("غسل الأموال — التعريفات والجرائم", ("غسل الأموال", "غسيل الأموال", "تمويل الإرهاب", "متحصلات الجريمة",
        "الجريمة الأصلية", "العمل الإرهابي", "الأموال محل الجريمة"), "legis-106-2013", 1, 3),
    ("غسل الأموال — تدابير العناية الواجبة والإخطار والسجلات", ("العناية الواجبة", "المستفيد الحقيقي",
        "الإخطار عن المعاملات المشبوهة", "المعاملات المشبوهة", "حفظ السجلات", "المؤسسات المالية",
        "الأعمال والمهن غير المالية", "التحقق من هوية العميل"), "legis-106-2013", 4, 13),
    ("غسل الأموال — الجهات المختصة ووحدة التحريات ونقل العملة", ("وحدة التحريات المالية", "جهات الرقابة",
        "نقل العملة عبر الحدود", "الإفصاح عن العملة", "الأدوات القابلة للتداول"), "legis-106-2013", 14, 20),
    ("غسل الأموال — أحكام عامة والتجميد والمصادرة والبطلان", ("تجميد الأموال", "قرارات مجلس الأمن",
        "مصادرة متحصلات الجريمة", "بطلان التصرف", "التعاون الدولي", "أسلحة الدمار الشامل",
        "الأصول المجمدة"), "legis-106-2013", 21, 26),
    ("غسل الأموال — العقوبات", ("عقوبة غسل الأموال", "عقوبة تمويل الإرهاب", "الشخص الاعتباري في غسل الأموال",
        "البنك الصوري", "الإفصاح الكاذب عن العملة", "عقوبة المؤسسات المالية", "تشديد عقوبة غسل الأموال",
        "الإعفاء من عقوبة غسل الأموال", "المصادرة في غسل الأموال"), "legis-106-2013", 27, 41),
    ("غسل الأموال — أحكام ختامية", ("أيلولة الأموال المصادرة", "الخزانة العامة",
        "التعاون القضائي الدولي"), "legis-106-2013", 42, 45),
    # ── اللائحة التنفيذية لغسل الأموال (قرار وزاري 37/2013) — لاحقة لـ 106/2013 ──
    ("غسل الأموال — اللائحة التنفيذية: العناية الواجبة وتحديد الهوية والحد المعتمد", ("العناية الواجبة",
        "تحديد هوية العميل", "المستفيد الفعلي", "المستفيد الحقيقي", "الحد المعتمد", "الشخص المعرض سياسياً",
        "العناية الواجبة المشددة", "قبول العملاء", "تقييم المخاطر"), "regl-106-2013", 1, 11),
    ("غسل الأموال — اللائحة التنفيذية: الضوابط الداخلية والإخطار والرقابة واللجنة الوطنية", ("الضوابط الداخلية",
        "الاستعانة بأطراف", "الإخطار عن العمليات المشبوهة", "الفحص الميداني", "اللجنة الوطنية لمكافحة غسل الأموال",
        "أمانة سر اللجنة", "الفريق الفني", "تدريب الموظفين"), "regl-106-2013", 12, 26),
    # ── المرسوم بقانون بمكافحة جرائم الإرهاب 47/2026 (فرع جزائي) ──
    ("الإرهاب — التعريفات والنطاق والشروع والإبلاغ والإعفاء", ("العمل الإرهابي", "التنظيم الإرهابي",
        "الخطورة الإرهابية", "تعريف الإرهاب", "الشروع في جريمة إرهابية", "عدم الإبلاغ عن جريمة إرهابية",
        "إيواء إرهابي", "الإعفاء من عقوبة الإرهاب", "التسليم المراقب"), "legis-47-2026", 1, 6),
    ("الإرهاب — جرائم الأعمال الإرهابية وعقوباتها", ("جريمة إرهابية", "عقوبة الإرهاب", "الأعمال الإرهابية",
        "الاعتداء على وسائل النقل", "الاعتداء على البعثات الدبلوماسية", "التدريب على السلاح لعمل إرهابي",
        "إنشاء تنظيم إرهابي", "إدارة تنظيم إرهابي", "الانضمام إلى تنظيم إرهابي", "الدعوة للانضمام",
        "التخابر مع تنظيم إرهابي", "الإكراه على الانضمام", "دخول الدولة لارتكاب عمل إرهابي",
        "تشديد عقوبة الجريمة الإرهابية"), "legis-47-2026", 7, 16),
    ("الإرهاب — الأحكام الوقائية وحالة الخطورة الإرهابية وإعادة التأهيل", ("الخطورة الإرهابية",
        "مركز إعادة التأهيل", "التدابير الوقائية", "مراقبة الشرطة", "حظر ارتياد الأماكن", "منع الاتصال",
        "برنامج إعادة التأهيل", "التطرف", "الأحداث في جرائم الإرهاب"), "legis-47-2026", 17, 23),
    ("الإرهاب — اللجنة الوطنية لمكافحة الإرهاب واختصاصاتها", ("اللجنة الوطنية لمكافحة الإرهاب",
        "استراتيجية مكافحة الإرهاب", "التوعية بمخاطر الإرهاب"), "legis-47-2026", 24, 25),
    ("الإرهاب — الأحكام الإجرائية الخاصة والشخص الاعتباري وعدم التقادم والاختصاص", ("الشخص الاعتباري في الإرهاب",
        "التسليم المراقب", "عدم تقادم جرائم الإرهاب", "عدم انقضاء الدعوى في الإرهاب",
        "اختصاص محكمة الجنايات بالإرهاب", "النيابة العامة في جرائم الإرهاب"), "legis-47-2026", 26, 31),
    # ── النظام الموحد الخليجي لمكافحة الغش التجاري 20/2019 (فرع جزائي) ──
    ("الغش التجاري — التعريفات والحظر والتزامات المزوّد والضبط والتفتيش", ("الغش التجاري", "بضائع مغشوشة",
        "بضاعة مغشوشة", "بضاعة فاسدة", "سلعة مغشوشة", "الغش في البضاعة", "سحب البضائع المغشوشة",
        "الضبطية القضائية", "التفتيش على المحال التجارية", "التحفظ على البضائع", "النظام الموحد لمكافحة الغش",
        "غش تجاري", "إغلاق المحل التجاري"), "legis-20-2019", 1, 9),
    ("الغش التجاري — العقوبات والمصادرة والإتلاف والعَود والشخص الاعتباري", ("عقوبة الغش التجاري",
        "مصادرة البضائع المغشوشة", "إتلاف البضائع", "العود في الغش التجاري", "غرامة الغش التجاري",
        "الشخص الاعتباري في الغش", "موازين مزيفة", "مكاييل مزيفة", "أختام مزيفة", "نشر الحكم في الغش"),
        "legis-20-2019", 10, 18),
    # ── قانون مكافحة الاتجار بالأشخاص وتهريب المهاجرين 91/2013 (فرع جزائي) ──
    ("الاتجار بالأشخاص وتهريب المهاجرين — التعريفات والجرائم والعقوبات والمصادرة", ("الاتجار بالأشخاص",
        "الاتجار بالبشر", "اتجار بالاشخاص", "تهريب المهاجرين", "تهريب مهاجرين", "الهجرة غير المشروعة",
        "استغلال جنسي", "السخرة", "الاسترقاق", "نزع الأعضاء", "الاتجار بالنساء", "الاتجار بالأطفال",
        "الدخول غير المشروع", "جماعة إجرامية منظمة", "الجريمة المنظمة عبر الوطنية"),
        "legis-91-2013", 1, 9),
    ("الاتجار بالأشخاص — الإعفاء والاختصاص وحماية المجني عليهم وعدم النزول عن العقوبة", ("الإعفاء من عقوبة الاتجار",
        "حماية المجني عليه", "المجني عليه في الاتجار", "دور الرعاية", "مراكز الإيواء", "الاتجار بالأشخاص",
        "تهريب المهاجرين", "إعادة المهاجر", "عدم النزول عن العقوبة"), "legis-91-2013", 10, 14),
    # ── المرسوم بقانون بحماية الوحدة الوطنية 19/2012 (فرع جزائي — خطاب الكراهية) ──
    ("حماية الوحدة الوطنية — تجريم الكراهية وإثارة الفتن والتحريض والعقوبات", ("حماية الوحدة الوطنية",
        "الوحدة الوطنية", "خطاب الكراهية", "ازدراء فئة", "ازدراء أي فئة", "إثارة الفتن الطائفية",
        "الفتنة الطائفية", "الفتنة القبلية", "الفتن الطائفية", "التحريض على الكراهية", "الكراهية والازدراء",
        "التمييز العنصري", "تفوق العرق", "نشر أفكار عنصرية", "الحض على الكراهية", "ازدراء المجتمع"),
        "legis-19-2012", 1, 5),
    # ── تأمين وحماية المصالح العليا للجهات العسكرية 13/2026 (فرع جزائي) — بندلان لتجاوز حدّ الـ30 مادة ──
    ("تأمين المصالح العليا للجهات العسكرية — التعاريف والتأمين والتنقلات والإجراءات",
        ("المصالح العليا للجهات العسكرية", "الجهات العسكرية", "تأمين المنشآت العسكرية", "المناطق المحمية",
         "المنطقة المحمية العسكرية", "التنقلات العسكرية", "المواكب العسكرية", "الأرتال العسكرية",
         "التحركات العسكرية", "النشاط المعادي", "الأمن العسكري", "الحرس الوطني", "الأسرار العسكرية",
         "الوثائق العسكرية السرية", "المناطق العسكرية"), "legis-13-2026", 1, 24),
    ("تأمين المصالح العليا للجهات العسكرية — العقوبات والأحكام الختامية", ("المصالح العليا للجهات العسكرية",
        "الجهات العسكرية", "عقوبة الاعتداء على الجهات العسكرية", "إفشاء الأسرار العسكرية", "التخابر العسكري",
        "تصوير المنشآت العسكرية", "النشاط المعادي", "جريمة عسكرية", "أسرار عسكرية", "الاعتداء العسكري",
        "عقوبة إفشاء الأسرار"), "legis-13-2026", 25, 34),
    # ── جرائم المفرقعات 35/1985 (فرع جزائي) — 11 مادة، حزمةٌ واحدة (دون سقف الـ30) ──
    ("جرائم المفرقعات — الاستعمال والإحراز والتدريب والعقوبات والاختصاص", ("المفرقعات", "مفرقعات",
        "المتفجرات", "جرائم المفرقعات", "استعمال المفرقعات", "إحراز مفرقعات", "الاتجار بالمفرقعات",
        "صنع المفرقعات", "قنابل", "ديناميت", "بارود", "عبوة ناسفة", "تفجير", "التدريب على المفرقعات",
        "مصادرة المفرقعات"), "legis-35-1985", 1, 11),
    # ── تخصيص دوائر جزائية لجرائم أمن الدولة والإرهاب 51/2026 (فرع جزائي) — 7 مواد، حزمةٌ واحدة ──
    ("تخصيص دوائر جزائية متخصصة — جرائم أمن الدولة والأعمال الإرهابية", ("دوائر جزائية متخصصة",
        "الدائرة الجزائية المتخصصة", "تخصيص دوائر جزائية", "محكمة أمن الدولة", "اختصاص جرائم أمن الدولة",
        "المحكمة المختصة بجرائم الإرهاب", "محاكمة جرائم الإرهاب", "استئناف جرائم الإرهاب",
        "الحبس الاحتياطي في جرائم الإرهاب", "جرائم أمن الدولة الخارجي والداخلي"), "legis-51-2026", 1, 7),
]


def _childrights_ids(blob):
    """معرّفات حزم قانون حقوق الطفل 21/2015 (المعرّفة ضمن _PENAL_BUNDLES) لاستعمالها أيضًا في فرع
    الأحوال الشخصية — فالقانون مزدوج الطبيعة (جزائي + أسري) مثل قانون العنف الأسري 11/2026.
    يُرشِّح الحزم ذات البادئة legis-21-2015 ويُعيد موادّها الحاكمة إن طابقت الوقائع."""
    ids = []
    for _name, keys, pref, a, b in _PENAL_BUNDLES:
        if pref == "legis-21-2015" and any(_draft_norm_ar(k) in blob for k in keys):
            ids.extend("%s-m%d" % (pref, n) for n in range(a, min(b, a + 29) + 1))
    return ids


# ── الجسر الأسريّ–الجزائيّ ──────────────────────────────────────────────────────
# قضايا العنف الأسريّ وإساءة معاملة الطفل تلتقي فيها أربعة مجالات: الجزاء (جريمة الاعتداء)،
# والعنف الأسري 11/2026 (أمر الحماية والإيواء)، وحقوق الطفل 21/2015، والأحوال (التفريق للضرر
# والحضانة والنفقة). عند وجود محتوى النِّزاع نصل الطرف الناقص في كلا الفرعين: نجلب في فرع الأحوال
# جرائمَ الاعتداء الجزائية، وفي الفرع الجزائي الآثارَ الأسرية — مقيَّدًا بالمحتوى حتى لا يُثقِل غيرها.
_NEXUS_KEYS = ("العنف الأسري", "عنف اسري", "العنف الاسري", "اعتداء أسري", "عنف منزلي", "أمر الحماية",
    "ضرب الزوجة", "اعتداء على الزوجة", "إيذاء الزوجة", "تعنيف الزوجة", "ضرب الزوج", "زوج يضرب زوجته",
    "إيذاء أحد أفراد الأسرة", "اعتداء داخل الأسرة", "ضرب داخل المنزل", "تعنيف",
    "الاعتداء على الطفل", "اعتداء على طفل", "اعتدى على طفل", "إيذاء الطفل", "إيذاء طفل", "ضرب الطفل",
    "ضرب طفل", "ضرب الأبناء", "اعتداء على الأبناء", "إساءة معاملة الطفل", "تعنيف الطفل", "إهمال الطفل",
    "على طفل", "التطليق للضرر", "التفريق للضرر", "تطليق للضرر", "طلاق للضرر")

# جرائم الاعتداء على النفس (قانون الجزاء 16/1960): الضرب والجرح والأذى والعاهة والتعدّي الخفيف
# + م167 (إهمال رب الأسرة رعاية الصغير). النواة الجزائية للعنف الأسريّ وإساءة الطفل.
_NEXUS_PENAL = ["legis-16-1960-m%d" % n for n in range(160, 168)] + ["legis-16-1960-m152", "legis-16-1960-m173"]
# مسمّيات حِزم الأحوال (من _DRAFT_BUNDLES) التي تمثّل الآثار الأسرية للعنف: التفريق/الفرقة، الحضانة، الخلع.
_NEXUS_FAMILY_NAMES = ("التفريق", "الفرقة", "الحضانة", "الخلع")


def _nexus_bridge(blob, madhab, is_penal):
    """عند محتوى عنفٍ أسريّ/إساءةٍ للطفل يصل الطرفَ الناقص في كل فرع (بلا تكرار مُثقِل):
    - الفرع الجزائيّ: يضيف الآثار الأسرية (التفريق للضرر/الحضانة/الخلع بحسب المذهب) — فالجرائم موجودة أصلًا.
    - فرع الأحوال: يضيف جرائم الاعتداء على النفس (16/1960) — فالآثار الأسرية موجودة أصلًا.
    مقيَّد بالمحتوى؛ يعيد [] لغيره. يُستدعى في صدر كلّ مسار لتنجو موادّه من قصّ الميزانية."""
    if not any(_draft_norm_ar(k) in blob for k in _NEXUS_KEYS):
        return []
    # الإجراء المسبق لمحكمة الأسرة (12/2015 م8-11: التسوية الأسرية الوجوبية) — مشترك يُستحضَر في الفرعين
    common = ["legis-12-2015-m%d" % n for n in (8, 9, 10, 11)]
    if not is_penal:
        return list(_NEXUS_PENAL) + common     # فرع الأحوال ⇐ جرائم الاعتداء كاملةً + إجراء التسوية
    is_jaafari = bool(madhab and "جعفر" in madhab)
    madhab_set = bool((madhab or "").strip())  # المذهب غير المحدَّد ⇒ الطرفان معًا
    # الفرع الجزائيّ ⇐ نواة جريمة الاعتداء المصغّرة (الضرب/التعدّي/التهديد) لتنجو مبكّرًا + الآثار الأسرية
    ids = ["legis-16-1960-m160", "legis-16-1960-m163", "legis-16-1960-m173"]
    for _name, keys, pref, nums, scope in _DRAFT_BUNDLES:
        if scope == "sunni" and madhab_set and is_jaafari:
            continue
        if scope == "jaafari" and madhab_set and not is_jaafari:
            continue
        if any(w in _name for w in _NEXUS_FAMILY_NAMES):
            ids.extend("%s-m%d" % (pref, n) for n in nums)
    return ids + common


# ── مُصنّف الفرع المحتوائيّ ──────────────────────────────────────────────────────
# إشارات كل فرع (مطبَّعة). المصنّف يعدّ الإشارات لكل فرع ويختار الأعلى. يملأ الفرع عند غيابه،
# ويصحّح الوسم الصريح فقط عند تعارضٍ قاطع (إشارات قوية للفرع المكتشَف + صفر دعم للفرع الموسوم).
_BRANCH_SIGNALS = [
    ("أحوال شخصية", ("طلاق", "تطليق", "خلع", "حضانه", "نفقه", "نسب", "مهر", "عده", "رضاع", "ميراث",
        "وصيه", "ولايه", "نشوز", "زواج", "خطبه", "حاضنه", "محضون", "التفريق للضرر", "بائن", "رجعي",
        "مؤخر الصداق", "الصداق", "المطلقه", "الزوجه", "زوجها", "عصمه",
        "اثبات النسب", "نفي النسب", "دعوى نسب", "تصحيح الاسم", "تغيير الاسم", "تصحيح الاسماء",
        "الاسم الشخصي", "لجنه دعاوى النسب", "استلحاق")),
    ("جزائي", ("جريمه", "عقوبه", "يعاقب", "رشوه", "اختلاس", "سرقه", "قتل", "ضرب", "تهديد", "اعتداء",
        "مخدرات", "تزوير", "نصب", "احتيال", "عنف اسري", "فساد", "حبس", "جنحه", "جنايه",
        "النيابه العامه", "المتهم", "المجني عليه", "تحرش", "اغتصاب", "هتك عرض", "بلاغ كاذب",
        "شهاده زور", "مسؤوليه جزائيه", "ابتزاز", "عصابه", "جانٍ", "الجاني", "ارتكب",
        "الاحداث", "محكمه الاحداث", "نيابه الاحداث", "قانون الاحداث", "الحدث المنحرف", "حدث ارتكب",
        "حيازه سلاح", "احراز سلاح", "سلاح غير مرخص", "اسلحه بيضاء", "سلاح ابيض", "كاتم صوت",
        "اسلحه هوائيه", "ذخيره", "ذخائر", "ايقاع الروع", "ترخيص سلاح", "مدفع رشاش",
        "المال العام", "الاموال العامه", "حمايه الاموال العامه", "اختلاس المال العام",
        "الاستيلاء على المال العام", "الاضرار بالمال العام", "الربح غير المشروع",
        "مخدرات", "مخدر", "مؤثرات عقليه", "مؤثر عقلي", "الاتجار بالمخدرات", "تعاطي المخدرات",
        "حيازه مخدرات", "جلب مخدرات", "تهريب مخدرات", "ترويج مخدرات", "سلائف كيميائيه",
        "ادمان", "مدمن", "متعاطي", "هيروين", "حشيش", "كوكايين", "شبو",
        "غسل الاموال", "غسيل الاموال", "تمويل الارهاب", "متحصلات الجريمه", "وحده التحريات الماليه",
        "المعاملات المشبوهه", "العنايه الواجبه", "المستفيد الحقيقي", "تجميد الاموال",
        "ارهاب", "عمل ارهابي", "جريمه ارهابيه", "تنظيم ارهابي", "خليه ارهابيه", "ارهابي",
        "الخطوره الارهابيه", "التطرف", "الاعمال الارهابيه", "اللجنه الوطنيه لمكافحه الارهاب",
        "غش تجاري", "الغش التجاري", "بضائع مغشوشه", "بضاعه مغشوشه", "بضاعه فاسده", "سلعه مغشوشه",
        "البضائع الفاسده", "الغش في البضاعه",
        "الاتجار بالاشخاص", "اتجار بالاشخاص", "الاتجار بالبشر", "تهريب المهاجرين", "تهريب مهاجرين",
        "الهجره غير المشروعه", "استغلال جنسي", "السخره", "نزع الاعضاء",
        "دعاره", "البغاء", "الفجور", "القواده", "محل للدعاره", "هتك العرض", "الفعل الفاضح",
        "محاكمه الوزراء", "محاكمه وزير", "مساءله الوزير", "جرائم الوزراء", "اتهام وزير",
        "حمايه الوحده الوطنيه", "الوحده الوطنيه", "خطاب الكراهيه", "اثاره الفتن الطائفيه", "الفتنه الطائفيه",
        "الفتنه القبليه", "التحريض على الكراهيه", "ازدراء فئه",
        "المصالح العليا للجهات العسكريه", "الجهات العسكريه", "المناطق المحميه العسكريه", "النشاط المعادي",
        "افشاء الاسرار العسكريه", "الاسرار العسكريه", "تامين المنشات العسكريه", "التنقلات العسكريه",
        "مفرقعات", "المفرقعات", "متفجرات", "المتفجرات", "جرائم المفرقعات", "قنابل", "ديناميت", "عبوه ناسفه",
        "تفجير", "الاتجار بالمفرقعات", "صنع المفرقعات",
        "دوائر جزائيه متخصصه", "محكمه امن الدوله", "جرائم امن الدوله", "محاكمه جرائم الارهاب",
        "الدائره الجزائيه المتخصصه", "اختصاص جرائم الارهاب",
        "الاعلام الالكتروني", "تنظيم الاعلام الالكتروني", "موقع الكتروني", "صحيفه الكترونيه", "حجب موقع",
        "ترخيص موقع الكتروني", "المدير المسؤول", "وسيله اعلاميه الكترونيه",
        "قانون المرور", "مخالفه مروريه", "المخالفات المروريه", "حادث مروري", "رخصه سوق", "رخصه القياده",
        "اجازه تسيير", "الاداره العامه للمرور", "محكمه المرور", "القياده تحت تاثير", "تجاوز الاشاره الضوئيه",
        "السحب الاداري لرخصه السوق", "نقاط المخالفات المروريه", "حجز المركبه", "ترخيص المركبه")),
    ("عمل", ("عامل", "عامله", "صاحب العمل", "فصل تعسفي", "الاجر", "راتب", "مكافاه نهايه الخدمه",
        "اجازه", "عماله منزليه", "استقدام", "عقد عمل", "نقابه", "اصابه عمل", "خادمه", "الكفيل",
        "رب العمل", "منشاه", "العمال")),
    ("تجاري", ("شركه", "تاجر", "افلاس", "اوراق تجاريه", "شيك", "كمبياله", "سجل تجاري",
        "وكاله تجاريه", "علامه تجاريه", "مساهم", "حصص", "الاسهم", "تصفيه شركه", "شركاء", "الشركاء")),
    ("إداري", ("موظف عام", "الخدمه المدنيه", "قرار اداري", "ترقيه", "تاديب", "مناقصه", "عقد اداري",
        "ذوي الاعاقه", "تامينات اجتماعيه", "معاش", "تقاعد", "ديوان الخدمه", "الغاء قرار",
        "الجهه الاداريه", "الوزاره", "الهيئه العامه",
        "حمايه البيئه", "قانون البيئه", "التلوث", "الهيئه العامه للبيئه", "المجلس الاعلى للبيئه",
        "نفايات خطره", "تقييم المردود البيئي", "محميات طبيعيه", "شرطه البيئه", "الاضرار البيئيه", "جون الكويت",
        "بلديه الكويت", "المجلس البلدي", "الجهاز التنفيذي للبلديه", "مخالفه بلديه", "المخالفات البلديه",
        "اشتراطات البناء", "ترخيص بناء", "التخطيط العمراني", "ازاله المخالفه البلديه", "رخصه محل")),
    ("مدني", ("عقد بيع", "الايجار", "تعويض", "مسؤوليه تقصيريه", "ملكيه", "رهن", "كفاله", "وديعه",
        "مقاوله", "المبيع", "فسخ العقد", "بطلان العقد", "التقادم", "الالتزام", "الدائن", "المدين",
        "فعل ضار", "المؤجر", "المستاجر", "عقد ايجار")),
]
_BRANCH_KEYSETS = [(br, tuple(_draft_norm_ar(k) for k in kws)) for br, kws in _BRANCH_SIGNALS]

# مطابقة بحدود الكلمة مع بادئات عربية (ال/و/ف/ب/ل/ك…) لتفادي المطابقة داخل جذرٍ آخر
# (مثال: «معاملة» كانت تُطابق «عامل»، و«منصب» تُطابق «نصب»). تُستعمل في المصنّف فقط.
_BR_PFX = r'(?:وال|فال|بال|كال|لل|ال|و|ف|ب|ل|ك)?'
_BR_MCACHE = {}


def _kmatch(key, blob):
    rx = _BR_MCACHE.get(key)
    if rx is None:
        rx = re.compile(r'(?:^|\s)' + _BR_PFX + re.escape(key))
        _BR_MCACHE[key] = rx
    return rx.search(blob) is not None


def _detect_branch(blob):
    """يُعيد (الفرع الأعلى إشارةً, درجته, خريطة الدرجات) من محتوى الوقائع (بحدود الكلمة)."""
    scores = {br: sum(1 for k in kws if _kmatch(k, blob)) for br, kws in _BRANCH_KEYSETS}
    best = max(scores, key=lambda b: scores[b])
    return best, scores[best], scores


def _branch_to_domain(bn):
    """يحوّل وسم الفرع القادم من الواجهة إلى أحد فروع المصنّف الستة (أو None)."""
    n = _draft_norm_ar(bn or "")
    if not n.strip():
        return None
    if "احوال" in n:
        return "أحوال شخصية"
    if any(k in n for k in ("جزاي", "جناي", "عقوبات", "جزاء")):
        return "جزائي"
    if "عمل" in n or "عمال" in n:
        return "عمل"
    if "تجار" in n:
        return "تجاري"
    if "اداري" in n or "اداره" in n:
        return "إداري"
    if "مدني" in n:
        return "مدني"
    return None


def _resolve_branch(branch, blob):
    """يحسم الفرع الفعليّ: يملؤه عند غيابه من الوقائع، ويصحّح الوسم الصريح فقط عند تعارضٍ قاطع."""
    det, ds, scores = _detect_branch(blob)
    tagged = _branch_to_domain(branch)
    if tagged is None:                                 # لا وسم صريح ⇒ استعمل المكتشَف إن وُجد
        return (det if ds >= 1 else branch)
    if det != tagged and ds >= 3 and scores.get(tagged, 0) == 0:
        return det                                     # تعارض قاطع: محتوى فرعٍ آخر بلا أيّ دعمٍ للموسوم
    return branch                                      # عدا ذلك: احترام اختيار المستخدم


# ربط ذكر الجريمة + سياق الحدث ⇒ استحضار مواد عقوبات الأحداث (111/2015 م15-32). المفاتيح الاسمية
# للحزمة لا تلتقط «حدثٌ سرق» (تعريفٌ فقط)، فنجلب مواد العقوبة عند اجتماع «حدث» + جريمة (بحدود الكلمة).
_JUV_PRESENCE = ("حدث", "الحدث", "الأحداث", "حدثا", "الحدث المنحرف", "قاصر", "صغير")
_JUV_CRIME = ("سرقه", "سرق", "اعتداء", "اعتدى", "ضرب", "قتل", "جريمه", "جنايه", "جنحه", "مخدرات",
    "تزوير", "نصب", "احتيال", "هتك عرض", "اغتصاب", "حريق", "اتلاف", "ارتكب", "خطف", "رشوه", "تحرش")


def _juvenile_penalty_ids(blob):
    """متى اجتمع «حدث/قاصر» وجريمةٌ صريحة: قائمة التدابير (م5) وأساس التسليم (م6) — إذ تُحيل إليها
    م16 صراحةً — إلى جانب مواد العقوبات (م15-32). تُقدَّم لتنجو من قصّ الميزانية."""
    if any(_kmatch(_draft_norm_ar(j), blob) for j in _JUV_PRESENCE) and \
       any(_kmatch(_draft_norm_ar(c), blob) for c in _JUV_CRIME):
        return ["legis-111-2015-m5", "legis-111-2015-m6"] + \
               ["legis-111-2015-m%d" % n for n in range(15, 33)]
    return []


# محفّز الصلح/التنازل/العفو: القاعدة العامة لانقضاء الدعوى الجزائية (17/1960 م238-243) — إذ تحصر
# التصالح في جرائم الشكوى والإيذاء/التعدي البسيط، فيُحسم أنّ الجنايات لا تقبله إلا بنصّ خاص —
# مع م45 (صلح الأحداث). لولاها يرى النموذج نصف الصورة فيتحفّظ. مطابقة بحدود الكلمة.
_SETTLE_KEYS = ("صلح", "التصالح", "تصالح", "تنازل", "التنازل", "عفو المجني عليه", "عفا المجني عليه",
    "انقضاء الدعوى الجزائيه", "سحب الشكوى", "التنازل عن الشكوى", "الصلح مع المتهم", "العفو الفردي")


def _settlement_ids(blob):
    """أحكام الصلح/العفو/التنازل العامة (17/1960 م238-243) + صلح الأحداث (21/2015... 111/2015 م45)
    متى ذُكر الصلح/التنازل — ليكتمل الحسم في أنّ الجنايات لا تقبل التصالح إلا بنصّ."""
    if any(_kmatch(_draft_norm_ar(k), blob) for k in _SETTLE_KEYS):
        return ["legis-17-1960-m%d" % n for n in range(238, 244)] + ["legis-111-2015-m45"]
    return []


# محفّز حظر نشر أسماء/صور الأحداث: م67 من 111/2015 تحمل الحظر والجزاء معًا (غرامة 1000-5000 د)
# — وقد كانت تُقصّ من الميزانية فيظنّ النموذجُ أنّ نصّ المادة والعقوبة «غير مرفق». مطابقة بحدود الكلمة.
_JUV_PUB_KEYS = ("نشر", "ينشر", "تنشر", "النشر", "صوره", "صور", "الصحف", "المطبوعات",
    "الاعلام", "وسائل الاعلام", "الاذاعه", "البث", "نشر الاسم", "نشر اسم", "نشر صوره")


def _juv_publication_ids(blob):
    """متى اجتمع «حدث/قاصر» ومسألةُ النشر/الاسم/الصورة/الإعلام: م67 (حظر النشر وعقوبته) + م40 (سرّية
    المحاكمة) + م43 (خلوّ صحيفة الحالة) — لتنجو مبكّرًا فلا يُظنّ نصّ الحظر والجزاء غيرَ مرفق."""
    if any(_kmatch(_draft_norm_ar(j), blob) for j in _JUV_PRESENCE) and \
       any(_kmatch(_draft_norm_ar(k), blob) for k in _JUV_PUB_KEYS):
        return ["legis-111-2015-m67", "legis-111-2015-m40", "legis-111-2015-m43"]
    return []


# محفّز الأسلحة: مواد م21/م22/م24 لها «مكرر» (مضافة بتعديلٍ لاحق: عقوبة الأسلحة البيضاء/الهوائية بلا
# ترخيص، وجريمة إيقاع الروع) لا يبلغها نطاقُ الأرقام في _PENAL_BUNDLES؛ فنجلبها صراحةً مع المواد
# الحاكمة (التعريفات، حظر الحيازة بلا ترخيص، الأماكن المحظورة، الاستيراد) مبكّرًا لتنجو من القصّ.
_WEAPONS_KEYS = ("سلاح", "اسلحه", "ذخيره", "ذخائر", "مسدس", "بندقيه", "مدفع", "رشاش", "سلاح ابيض",
    "اسلحه بيضاء", "سلاح هوائي", "اسلحه هوائيه", "كاتم صوت", "كاتمات الصوت", "حيازه سلاح",
    "احراز سلاح", "ترخيص سلاح", "ايقاع الروع", "التلويح بالسلاح", "رماية")


def _weapons_ids(blob):
    """متى ذُكرت الأسلحة/الذخائر: المواد الحاكمة لقانون 13/1991 شاملةً مواد «المكرر» العقابية
    (م21/م22/م24 مكرر) التي لا يجلبها نطاقُ الأرقام — لتنجو مبكّرًا من قصّ الميزانية."""
    if any(_kmatch(_draft_norm_ar(k), blob) for k in _WEAPONS_KEYS):
        return ["legis-13-1991-m%d" % n for n in (1, 2, 3, 12, 13, 14, 16)] + \
               ["legis-13-1991-m21", "legis-13-1991-m21-mukarrar",
                "legis-13-1991-m22", "legis-13-1991-m22-mukarrar",
                "legis-13-1991-m23", "legis-13-1991-m24", "legis-13-1991-m24-mukarrar",
                "legis-13-1991-m25"]
    return []


# محفّز جرائم المال العام (1/1993): م21 مكرر (عدم سقوط الدعوى بالتقادم) لا يبلغه نطاقُ الأرقام؛
# فنجلبه صراحةً مع مواد الجرائم الحاكمة (الاختلاس/الاستيلاء/الإضرار) والعزل والرد ورد المال — مبكّرًا
# لتنجو من القصّ. مطابقة بحدود الكلمة. آمنة لأنها داخل الفرع الجزائيّ.
# مفاتيح جرائم المال العام — بصياغةٍ واقعيةٍ لا اصطلاحيةٍ فقط: السؤال الحيّ يقول «أضرّ بأموال الهيئة»
# و«عمولة» و«صفقة توريد» و«التحفّظ على أمواله وأموال زوجته»، لا «المال العام» حرفيًّا. فنوسّع الكواشف
# لمؤشّرات الجريمة المالية الوظيفية (اختلاس/استيلاء/إضرار مالي/عمولة/تربّح/توريد/مقاولة/تحفّظ). مطابقة
# بحدود الكلمة داخل الفرع الجزائيّ. (المرشّح آمن لأنّ 1/1993 هو القانون الحاكم لجرائم المال العام.)
_PUBFUNDS_KEYS = ("المال العام", "الاموال العامه", "حمايه الاموال العامه", "اختلاس المال العام",
    "اختلاس اموال عامه", "الاستيلاء على المال العام", "الاضرار بالمال العام", "ديوان المحاسبه",
    "الربح غير المشروع", "عموله للموظف", "منفعه من المقاولات", "موظف عام اختلس", "اختلس اموالا",
    # صياغات واقعية:
    "اختلاس", "اختلس", "الاستيلاء", "استولى", "تبديد", "بدد", "اموال الهيئه", "اموال الجهه",
    "اضر باموال", "الاضرار باموال", "اضرار باموال", "اضر بمصلحه", "الاضرار بمصلحه الجهه",
    "عموله", "عقد توريد", "صفقه توريد", "التوريدات", "المقاولات", "تربح", "التربح", "منفعه غير مشروعه",
    "التحفظ على الاموال", "التحفظ على اموال", "منع من التصرف", "تهريب الاموال", "رد المال العام",
    "استرداد المال العام", "منع من السفر لجريمه ماليه")


def _publicfunds_ids(blob):
    """متى مسّ الطلبُ جرائمَ المال العام (1/1993): المواد الحاكمة للجرائم (م9-م16) + رد المال والرأفة
    المشروطة (م20) + عدم سقوط الدعوى بالتقادم (م21 مكرر) + الرد رغم الانقضاء (م22) + الإجراءات التحفظية
    شاملةً أموال الزوجة والأولاد (م24) — لتنجو مبكّرًا من قصّ الميزانية."""
    if any(_kmatch(_draft_norm_ar(k), blob) for k in _PUBFUNDS_KEYS):
        return ["legis-1-1993-m%d" % n for n in (9, 10, 11, 12, 14, 16, 20)] + \
               ["legis-1-1993-m21-mukarrar", "legis-1-1993-m22", "legis-1-1993-m24"]
    return []


# محفّز جرائم المخدرات (159/2025): يلتقط الصياغة الواقعية (حشيش/هيروين/كبتاجون/تعاطي/اتجار/ترويج/
# إدمان) فيستحضر مبكّرًا مواد العقوبات المحورية (الاتجار م42/م43، التشديد م44، الحيازة المجردة م48،
# التعاطي م49، التدرّج بالجدول م52) وبدائل العلاج (م63/م64) والمصادرة (م69) وعدم التقادم (م74)
# والاختصاص (م75) — لتنجو من القصّ. مطابقة بحدود الكلمة داخل الفرع الجزائيّ.
_DRUGS_KEYS = ("مخدر", "مخدرات", "مؤثر عقلي", "مؤثرات عقليه", "حشيش", "هيروين", "كوكايين", "شبو",
    "كبتاجون", "قنب", "ماريجوانا", "حبوب مخدره", "حبوب مؤثره", "سلائف كيميائيه", "ادمان", "مدمن",
    "متعاطي", "تعاطي", "الاتجار بالمخدرات", "ترويج مخدر", "جلب مخدرات", "تهريب مخدرات",
    "حيازه مخدر", "زراعه القنب", "مواد مخدره", "مستحضرات مخدره")


def _drugs_ids(blob):
    """متى مسّ الطلبُ جرائمَ المخدرات (159/2025): مواد العقوبات المحورية + التدرّج بالجدول + بدائل العلاج
    والإيداع + المصادرة + عدم التقادم + الاختصاص — تُقدَّم لتنجو من قصّ الميزانية."""
    if any(_kmatch(_draft_norm_ar(k), blob) for k in _DRUGS_KEYS):
        # م46/م47 (الحمل على التعاطي بالعنف، والدسّ) تُجلب لأنّ م74 تُحيل إليهما في استثناء عدم التقادم
        return ["legis-159-2025-m%d" % n for n in (42, 43, 44, 45, 46, 47, 48, 49, 52)] + \
               ["legis-159-2025-m59", "legis-159-2025-m63", "legis-159-2025-m64",
                "legis-159-2025-m69", "legis-159-2025-m74", "legis-159-2025-m75"]
    return []


# محفّز التقادم العامّ: مدد سقوط الدعوى الجزائية والعقوبة مقرّرة في قانون الجزاء 16/1960 م3-م10
# (لا في الإجراءات 17/1960 كما قد يُظنّ): الجنايات 10 سنوات للدعوى/20 للعقوبة/30 للإعدام (م4)،
# الجنح 5/10 (م6)، عدم الوقف (م7)، الانقطاع بالاتهام/التحقيق ولا تطول بأكثر من نصفها (م8)، التعدّد
# (م9)، وقف سقوط العقوبة (م10). تُستحضَر متى مسّ الطلبُ التقادم/سقوط الدعوى بأيّ صياغة — لكلّ الفروع
# الجزائية (فالنموذج كان يتحفّظ «المدد غير مرفقة» وهي مُدرَجة). مطابقة بحدود الكلمة داخل الفرع الجزائيّ.
_PRESC_KEYS = ("تقادم", "التقادم", "سقوط الدعوى", "تسقط الدعوى", "انقضاء الدعوى", "مضي المده",
    "بمضي المده", "مرور الزمن", "سقوط العقوبه", "تسقط العقوبه", "مده السقوط", "تقادم الجريمه")


def _prescription_ids(blob):
    """مواد التقادم العامّة (16/1960 م3-م10): مدد سقوط الدعوى والعقوبة والوقف والانقطاع — لتكتمل إجابة
    التقادم بالمدد لا بالمبدأ فقط، في أيّ سؤالٍ جزائيّ. تُقدَّم لتنجو من قصّ الميزانية."""
    if any(_kmatch(_draft_norm_ar(k), blob) for k in _PRESC_KEYS):
        return ["legis-16-1960-m%d" % n for n in range(3, 11)]
    return []


# محفّز غسل الأموال/تمويل الإرهاب (106/2013): يستحضر مبكّرًا الجرائمَ (م2/م3) والعقوبات المحورية
# (م28 غسل ≤10 سنوات، م29 تمويل ≤15 سنة، م30 التشديد ≤20، م31 الإعفاء، م32 الشخص الاعتباري)
# والمصادرة (م40) والتجميد (م25) — لتنجو من القصّ. مطابقة بحدود الكلمة داخل الفرع الجزائيّ.
_AML_KEYS = ("غسل الاموال", "غسيل الاموال", "تمويل الارهاب", "متحصلات الجريمه", "متحصلات جريمه",
    "غسل اموال", "الاموال المتحصله", "وحده التحريات الماليه", "معامله مشبوهه", "معاملات مشبوهه",
    "تجميد اموال", "العنايه الواجبه", "المستفيد الحقيقي", "الابلاغ عن معامله", "الاخطار عن معامله",
    "بنك صوري", "افصاح كاذب عن العمله", "العنايه الواجبه", "الشخص المعرض سياسيا", "المستفيد الفعلي",
    "تحديد هويه العميل", "الحد المعتمد", "اللجنه الوطنيه لمكافحه غسل الاموال")


def _aml_ids(blob):
    """جرائم غسل الأموال وتمويل الإرهاب (106/2013): الجرائم (م2/م3) + العقوبات (م28-م32) + المصادرة
    (م40) + التجميد (م25) — تُقدَّم لتنجو من قصّ الميزانية."""
    if any(_kmatch(_draft_norm_ar(k), blob) for k in _AML_KEYS):
        return ["legis-106-2013-m%d" % n for n in (2, 3, 28, 29, 30, 31, 32)] + \
               ["legis-106-2013-m25", "legis-106-2013-m40"] + \
               ["regl-106-2013-m5", "regl-106-2013-m6", "regl-106-2013-m7", "regl-106-2013-m16"]
    return []


# محفّز التزامات المؤسسات المالية وحظر إفصاح التنبيه (106/2013): أسئلة الامتثال/التبليغ لا تذكر «غسل
# الأموال» بالضرورة، بل «تحذير العميل/الإفصاح له» أو «الاحتفاظ بالسجلّات» أو «الإخطار عن معاملة» — فنستحضر
# عنقود الالتزامات: العناية الواجبة (م5)، الضوابط الداخلية (م10)، السجلّات (م11)، الإخطار (م12)،
# حظر التنبيه + حصانة حسن النية (م13)، الرقابة (م14)، الجزاءات الإدارية (م15)، وعقوبات المخالفة:
# البنك الصوري (م34)، التنبيه/الإخطار الكاذب (م35)، خرق السرّية (م36) — تُقدَّم لتنجو من القصّ.
_AML_BANK_KEYS = ("تحذير العميل", "اخبار العميل", "تنبيه العميل", "الافصاح للعميل", "افشاء للعميل",
    "حظر الافصاح", "عدم اخبار العميل", "الاخطار عن معامله مشبوهه", "الابلاغ عن الاشتباه",
    "الاحتفاظ بالسجلات", "حفظ السجلات", "مراقب الالتزام", "الضوابط الداخليه", "برنامج الامتثال",
    "التزامات المؤسسات الماليه", "التزامات البنك", "العنايه الواجبه", "حسن النيه", "الاعفاء من المسؤوليه",
    "بنك صوري", "الجزاءات الاداريه", "مخالفه التزامات مكافحه غسل الاموال")


def _aml_bank_ids(blob):
    """التزامات المؤسسات المالية وحظر إفصاح التنبيه (tipping-off) في 106/2013: العناية الواجبة/السجلّات/
    الإخطار/حظر التنبيه + حصانة حسن النية + الرقابة والجزاءات الإدارية والجزائية — لأسئلة الامتثال والتبليغ."""
    if any(_kmatch(_draft_norm_ar(k), blob) for k in _AML_BANK_KEYS):
        return ["legis-106-2013-m%d" % n for n in (5, 10, 11, 12, 13, 14, 15, 34, 35, 36)]
    return []


# محفّز جرائم الإرهاب (47/2026): يستحضر مبكّرًا نواةَ المرسوم — التعريفات (م1)، النطاق (م2)، الشروع (م4)،
# عدم الإبلاغ/الإيواء (م5)، الإعفاء (م6)، تشديد العقوبة (م7)، إنشاء/إدارة التنظيم (م12) والانضمام (م13)،
# الخطورة الإرهابية وإجراءاتها (م18/م19)، الشخص الاعتباري (م26)، عدم التقادم (م28)، الاختصاص (م29) —
# لتنجو من القصّ. وجسرُ تمويل الإرهاب: يقرن الجريمةَ الأصلية (47/2026) بجريمة التمويل وعقوبتها في 106/2013.
_TERROR_KEYS = ("ارهاب", "الارهاب", "عمل ارهابي", "عملا ارهابيا", "جريمه ارهابيه", "جرائم الارهاب",
    "تنظيم ارهابي", "منظمه ارهابيه", "خليه ارهابيه", "ارهابي", "الخطوره الارهابيه", "تمويل الارهاب",
    "الانضمام لتنظيم ارهابي", "التطرف", "اعادة تاهيل المتطرفين", "تدابير وقائيه", "تخابر مع تنظيم ارهابي",
    "اللجنه الوطنيه لمكافحه الارهاب", "دخول الدوله لارتكاب عمل ارهابي", "التنظيمات الارهابيه")


def _terrorism_ids(blob):
    """جرائم الإرهاب (47/2026): نواةُ التعريفات/النطاق/الشروع/الإبلاغ/الإعفاء/تشديد العقوبة/التنظيم/الخطورة
    الإرهابية/الشخص الاعتباري/عدم التقادم/الاختصاص — تُقدَّم لتنجو. وجسرُ التمويل يصل 106/2013 (م3 التجريم،
    م29 العقوبة، م2 غسل العائدات) بجريمة الإرهاب الأصلية عند ذكر تمويل الإرهاب."""
    if not any(_kmatch(_draft_norm_ar(k), blob) for k in _TERROR_KEYS):
        return []
    ids = ["legis-47-2026-m%d" % n for n in (1, 2, 4, 5, 6, 7, 12, 13, 18, 19, 26, 28, 29)]
    if _kmatch(_draft_norm_ar("تمويل الارهاب"), blob):
        ids += ["legis-106-2013-m3", "legis-106-2013-m29", "legis-106-2013-m2"]
    return ids


# محفّز جرائم المفرقعات (35/1985): قانونٌ جزائيٌّ صغير (11 مادة) متلازمُ المواد — الاستعمال والإعدام (م1)،
# تعريض الأرواح والأموال (م2)، الإحراز/الصنع/الاتّجار بغير ترخيص وتعريف المفرقعات والمصادرة (م3)، التدريب
# (م4)، عدم الإبلاغ والإخفاء (م5)، مخالفة الترخيص (م6)، الإعفاء (م7)، منع النزول عن الإعدام/المؤبّد (م8)،
# واختصاص محكمة أمن الدولة (م9). نستحضره كاملًا مبكّرًا لتنجو العقوباتُ من القصّ. وجسرُ الإرهاب: المفرقعات
# بقصد إشاعة الذعر/تخريب المرافق عملٌ إرهابيّ (م1)، فنقرن نواةَ 47/2026 عند الطابع الإرهابيّ.
_EXPLOSIVES_KEYS = ("مفرقعات", "المفرقعات", "متفجرات", "المتفجرات", "مواد متفجره", "جرائم المفرقعات",
    "استعمال مفرقعات", "احراز مفرقعات", "حيازه مفرقعات", "صنع المفرقعات", "الاتجار بالمفرقعات", "تفجير",
    "قنبله", "قنابل", "ديناميت", "بارود", "عبوه ناسفه", "عبوات ناسفه", "تصنيع متفجرات", "التدريب على المفرقعات")


def _explosives_ids(blob):
    """جرائم المفرقعات (35/1985) كاملًا (م1-م11): الاستعمال (م1)، التعريض (م2)، الإحراز/الاتّجار/التعريف
    والمصادرة (م3)، التدريب (م4)، عدم الإبلاغ (م5)، الترخيص (م6)، الإعفاء (م7)، منع تخفيف الإعدام/المؤبّد
    (م8)، اختصاص محكمة أمن الدولة (م9) — لتنجو مجتمعةً. وعند الطابع الإرهابيّ (إشاعة الذعر) نضمّ نواةَ 47/2026."""
    if not any(_kmatch(_draft_norm_ar(k), blob) for k in _EXPLOSIVES_KEYS):
        return []
    ids = ["legis-35-1985-m%d" % n for n in range(1, 12)]
    if any(_kmatch(_draft_norm_ar(k), blob) for k in ("اشاعه الذعر", "ارهاب", "ارهابي", "عمل ارهابي", "تخريب المرافق")):
        ids += ["legis-47-2026-m%d" % n for n in (1, 2, 4, 7)]   # جسرُ الإرهاب: المفرقعات وسيلةٌ إرهابيّة
    return ids


# محفّز تخصيص الدوائر الجزائية (51/2026): مرسومٌ صغير (7 مواد) ينشئ دوائرَ جزائيةً متخصّصةً في المحكمة
# الكلية والاستئناف تختصّ دون غيرها بجرائم أمن الدولة (31/1970) والأعمال الإرهابية (47/2026) — يُجيب سؤالَ
# «أيّ محكمةٍ تنظر جرائم الإرهاب/أمن الدولة». نستحضره كاملًا على مفاتيح الاختصاص القضائيّ لهذه الجرائم؛
# ونقرن نواةَ 47/2026 عند الطابع الإرهابيّ ليكتمل المشهدُ الموضوعيّ + الاختصاصيّ.
_STATESEC_COURT_KEYS = ("دوائر جزائيه", "دائره جزائيه", "الدوائر الجزائيه المتخصصه", "تخصيص دوائر جزائيه",
    "الدائره الجزائيه المتخصصه", "محكمه امن الدوله", "اي محكمه تنظر جرائم الارهاب", "اي محكمه تنظر جرائم امن الدوله",
    "المحكمه المختصه بجرائم الارهاب", "المحكمه المختصه بجرائم امن الدوله", "اختصاص نظر جرائم امن الدوله",
    "اختصاص نظر جرائم الارهاب", "استئناف احكام الارهاب", "استئناف جرائم امن الدوله", "الطعن في جرائم امن الدوله",
    "الحبس الاحتياطي في جرائم الارهاب", "محاكمه جرائم الارهاب", "محاكمه جرائم امن الدوله", "قاضي جرائم الارهاب",
    "الدائره المختصه بالارهاب", "المحكمه المختصه بالارهاب",
    # مواضيعُ مجرّدة: أيّ سؤالٍ عن هذه الجرائم يستحقّ استحضارَ محكمتها المتخصّصة (قانونٌ صغيرٌ 7 مواد، ضجيجُه ضئيل):
    "جرائم امن الدوله", "امن الدوله الخارجي", "امن الدوله الداخلي", "الاعمال الارهابيه", "جرائم الاعمال الارهابيه",
    "جريمه امن الدوله", "امن الدوله", "عمل ارهابي", "عملا ارهابيا")


def _statesec_court_ids(blob):
    """تخصيص الدوائر الجزائية (51/2026) كاملًا (م1-م7): الدائرة المتخصصة في الكلية وسلطة الحبس الاحتياطي
    (م1)، دائرة الاستئناف ونهائية حكمها (م2)، وجه السرعة ومنع الادّعاء المدني (م3)، إحالة الدعاوى (م4)،
    نطاق السريان الزمنيّ (م5) — لتنجو مجتمعةً. وعند الطابع الإرهابيّ نضمّ نواةَ 47/2026 (م1/م2/م7)."""
    if not any(_kmatch(_draft_norm_ar(k), blob) for k in _STATESEC_COURT_KEYS):
        return []
    ids = ["legis-51-2026-m%d" % n for n in range(1, 8)]
    if any(_kmatch(_draft_norm_ar(k), blob) for k in ("ارهاب", "ارهابي", "جرائم الارهاب", "عمل ارهابي")):
        ids += ["legis-47-2026-m%d" % n for n in (1, 2, 7)]      # الجسر الموضوعيّ: تعريف/نطاق/تشديد الإرهاب
    return ids


# محفّز قانون المرور (67/1976): قانونٌ كبير (59 مادة، 6 أبواب) يتجاوز سقفَ الحزمة الواحدة، فنُوجّهه بالموضوع:
# نستحضر نواةً خفيفةً دائمة (التعاريف م2 + مسؤولية المالك م30) ثم موادَّ البابِ الموافقِ لكلمات السؤال —
# الترخيص/رخص القيادة/قواعد المرور/العقوبات — وللعقوبات نستحضر النواةَ العقابيةَ كاملةً (م33-م44) لتنجو.
_TRAFFIC_KEYS = ("مرور", "قانون المرور", "مركبه", "مركبات", "سياره", "سيارات", "دراجه اليه",
    "شاحنه", "قياده", "رخصه قياده", "رخصه القياده", "رخصه سوق", "رخصه السوق", "اجازه تسيير", "تسيير المركبه",
    "ترخيص المركبه", "ترخيص سياره", "لوحات المركبه", "لوحه المركبه", "حادث مروري", "حادث سير", "حادث سياره",
    "مخالفه مروريه", "المخالفات المروريه", "الاداره العامه للمرور", "اشاره المرور", "الاشاره الضوئيه",
    "قواعد المرور", "السحب الاداري", "نقاط المخالفات", "محكمه المرور", "حزام الامان", "تجاوز الاشاره",
    "القياده تحت تاثير", "حجز المركبه", "تعليم القياده", "المجلس الاعلى للمرور", "تجاوز السرعه",
    "الوقوف والانتظار", "التامين على المركبه",
    # صيغُ ملكيةٍ وتأمينٍ وحوادثَ طبيعيةٌ شائعةٌ في أسئلة المواطنين (اللاحقةُ الملكيةُ تُفلِت من مطابقة «سياره»):
    "سيارتي", "سيارته", "سيارتك", "مركبتي", "مركبته", "التامين الالزامي", "تامين المركبه", "تامين السياره",
    "التامين ضد الغير", "حادث بالسياره", "حادث سيارتي", "تصادم", "تصادم سيارتين")


# محفّز قانون حماية البيئة (42/2014): قانونٌ إطاريٌّ ضخم (182 مادة، 9 أبواب) محايدُ الفرع (إداري: الهيئة
# والتراخيص؛ جزائي: العقوبات الباب السابع م128-م157؛ مدني: المسؤولية والتعويض الباب الثامن م158-م167).
# نُوجّهه بالباب: نواةٌ خفيفة (التعاريف م1 + الهيئة م6) ثم موادُّ البابِ الموافقِ لكلمات السؤال، مع استحضار
# العقوبات كاملةً لأيّ سؤالِ مخالفةٍ/غرامةٍ بيئية — لتنجو من القصّ (الاسترجاع الدلاليّ يكمّل التفاصيل).
_ENV_KEYS = ("بيئه", "حمايه البيئه", "قانون البيئه", "تلوث", "التلوث", "الهيئه العامه للبيئه", "المجلس الاعلى للبيئه",
    "صندوق حمايه البيئه", "نفايات", "النفايات الخطره", "نفايات طبيه", "مواد كيميائيه", "مواد خطره",
    "تقييم المردود البيئي", "المردود البيئي", "تلوث الهواء", "انبعاثات", "البيئه البحريه", "البيئه الساحليه",
    "التلوث البحري", "مياه الشرب", "المياه الجوفيه", "التنوع البيولوجي", "محميات طبيعيه", "المحميات الطبيعيه",
    "الكائنات الفطريه", "جون الكويت", "شرطه البيئه", "الاضرار البيئيه", "الضرر البيئي", "التعويض البيئي",
    "كوارث بيئيه", "ازمات بيئيه", "المخلفات", "الصيد الجائر", "الاحتباس الحراري", "طبقه الاوزون")


def _environment_ids(blob):
    """قانون حماية البيئة (42/2014) — استحضارٌ مُوجَّهٌ بالباب (182 مادة): نواةٌ (تعاريف م1 + الهيئة م6)،
    ثم الإدارة/التنمية/الأرضية-النفايات/الهواء/المائية-البحرية/التنوع-المحميات/الإدارة-شرطة البيئة/العقوبات
    (الباب السابع)/المسؤولية المدنية (الثامن) بحسب كلمات السؤال. محايدُ الفرع (يُستحضَر في الغلاف)."""
    if not any(_kmatch(_draft_norm_ar(k), blob) for k in _ENV_KEYS):
        return []
    P = "legis-42-2014-m%d"

    def K(*keys):
        return any(_kmatch(_draft_norm_ar(k), blob) for k in keys)

    # ترتيبٌ بالأولوية: المواد المحدّدة (جسورُ المخالفة⇄العقوبة + النواة) تُقدَّم أوّلًا لتنجو من قصّ الميزانية،
    # ثم النطاقاتُ العريضةُ للباب كسياقٍ داعمٍ بأسقفٍ مضبوطة. نصُّ العقوبة يُحيل على المخالفة برقمها
    # («كل من خالف المادة (25)») فيبعُد دلاليًّا؛ فالجسرُ يقرنُهما ويُقدّمهما.
    head = [P % 1, P % 6]                                     # النواة: التعاريف + الهيئة
    if K("نفايات", "النفايات الخطره", "نفايات طبيه", "مواد كيميائيه", "مواد خطره", "المخلفات الخطره",
         "التخلص من النفايات"):
        head += [P % 28, P % 29, P % 130, P % 131]           # حظرُ التخلّص (م28/م29) + عقوبتُه (م130 حتى الإعدام/م131)
    if K("البيئه البحريه", "التلوث البحري", "جون الكويت", "تلوث بحري", "المناطق البحريه", "التلوث من السفن"):
        head += [P % 68, P % 73, P % 141, P % 142, P % 146]  # المناطق المحظورة (م68) + تصريف المنشآت الصناعية (م73) + عقوباتها
    if K("جون الكويت", "محميات طبيعيه", "المحميات الطبيعيه", "التنوع البيولوجي", "الكائنات الفطريه", "الصيد الجائر"):
        head += [P % 108, P % 149, P % 150]                  # حظرُ جون الكويت (م108) وعقوبتُه (م149)
    if K("مسؤوليه", "مسؤوليه مدنيه", "المسئوليه المدنيه", "التعويض", "الضرر البيئي", "الاضرار البيئيه", "اصلاح الضرر"):
        head += [P % 159, P % 160, P % 161]                  # نواةُ المسؤولية المدنية الخاصة (42/2014)
        # جسرُ الشريعة العامة: م160 تقوم «مع عدم الإخلال بأي قانون آخر»، وما سكتت عنه (الخطأ/السببية/تقدير
        # التعويض) يُرَدّ إلى المسؤولية التقصيرية في القانون المدني 67/1980 (م227 فما بعد) تطبيقًا تكميليًّا:
        head += ["legis-67-1980-m%d" % n for n in range(227, 235)]

    tail = []

    def rng(a, b, cap=12):                                    # سقفٌ افتراضيٌّ أضيق (سياقٌ داعم لا يزاحم الجسور)
        tail.extend(P % n for n in range(a, min(b, a + cap - 1) + 1))
    if K("تعريف", "تعاريف", "نطاق", "اهداف القانون", "المكان العام"):
        rng(1, 3)
    if K("الهيئه العامه للبيئه", "المجلس الاعلى للبيئه", "صندوق حمايه البيئه", "اداره شئون البيئه",
         "مجلس الاداره", "المدير العام", "اختصاصات الهيئه"):
        rng(4, 15)
    if K("تقييم المردود البيئي", "المردود البيئي", "التنميه والبيئه", "المحيط المهني", "دراسه بيئيه"):
        rng(16, 20)
    if K("نفايات", "النفايات الخطره", "نفايات طبيه", "مواد كيميائيه", "مواد خطره", "المخلفات", "الحمأه",
         "البيئه الارضيه", "البيئه الزراعيه", "تلوث التربه"):
        rng(21, 47, 12)
    if K("تلوث الهواء", "الهواء الخارجي", "انبعاثات", "طبقه الاوزون", "الاحتباس الحراري", "الضوضاء", "الروائح"):
        rng(48, 64, 12)
    if K("البيئه البحريه", "البيئه الساحليه", "التلوث البحري", "مياه الشرب", "المياه الجوفيه", "التلوث من السفن",
         "البيئه المائيه", "جون الكويت"):
        rng(65, 99, 14)
    if K("التنوع البيولوجي", "محميات طبيعيه", "المحميات الطبيعيه", "الكائنات الفطريه", "الانقراض",
         "الصيد الجائر", "جون الكويت"):
        rng(100, 110)
    if K("شرطه البيئه", "الاستراتيجيات البيئيه", "كوارث بيئيه", "ازمات بيئيه", "الاعلام البيئي", "التوعيه البيئيه",
         "الاداره البيئيه"):
        rng(111, 127, 12)
    if K("عقوبه", "عقوبات", "غرامه", "مخالفه", "يعاقب", "جريمه بيئيه", "الحبس", "مصادره", "المخالفات البيئيه"):
        rng(128, 157, 16)                                    # الباب السابع: العقوبات
    if K("مسؤوليه مدنيه", "المسئوليه المدنيه", "التعويض", "الضرر البيئي", "الاضرار البيئيه", "اصلاح الضرر"):
        rng(158, 167)
    if K("احكام ختاميه", "اللائحه التنفيذيه", "التقادم البيئي"):
        rng(168, 181, 12)
    return list(dict.fromkeys(head + tail))                   # الجسورُ أوّلًا ثم السياق (dedup يحفظ ترتيب الأولوية)


# محفّز قانون بلدية الكويت (33/2016): قانونٌ إداريٌّ (53 مادة، 4 أبواب) — نُوجّهه بالباب: النواة (التعاريف
# م1 + البلدية وشخصيّتها م2) ثم المجلس البلدي وانتخاباته واختصاصاته (م4-م30) أو الجهاز التنفيذي والمدير
# العام والتراخيص (م31-م37) أو المخالفات والعقوبات والإزالة والتظلّم (م38-م44) أو الأحكام الختامية (م45-م53).
_MUNI_KEYS = ("بلديه", "البلديه", "بلديه الكويت", "المجلس البلدي", "الجهاز التنفيذي للبلديه", "المدير العام للبلديه",
    "عضويه المجلس البلدي", "انتخابات البلديه", "اشتراطات البناء", "تراخيص البناء", "ترخيص بناء", "التخطيط العمراني",
    "تقسيم المناطق", "القسائم", "الاعلانات البلديه", "المحال التجاريه", "مخالفه بلديه", "المخالفات البلديه",
    "ازاله المخالفه", "التعديات على املاك الدوله", "الاملاك العامه البلديه", "رخصه محل", "اشغال الطريق")


def _municipality_ids(blob):
    """قانون بلدية الكويت (33/2016) — استحضارٌ مُوجَّهٌ بالباب (53 مادة): النواة (م1/م2) ثم المجلس البلدي
    واختصاصاته (م4-م30) أو الجهاز التنفيذي والتراخيص (م31-م37) أو المخالفات والعقوبات والإزالة (م38-م44)
    أو الأحكام الختامية (م45-م53) بحسب كلمات السؤال. محايدُ الفرع (يُستحضَر في الغلاف)."""
    if not any(_kmatch(_draft_norm_ar(k), blob) for k in _MUNI_KEYS):
        return []
    P = "legis-33-2016-m%d"
    ids = [P % 1, P % 2]

    def K(*keys):
        return any(_kmatch(_draft_norm_ar(k), blob) for k in keys)

    def rng(a, b, cap=14):
        ids.extend(P % n for n in range(a, min(b, a + cap - 1) + 1))
    if K("المخالفات البلديه", "مخالفه بلديه", "عقوبه", "غرامه", "يعاقب", "ازاله المخالفه", "التنفيذ الاداري",
         "التظلم", "الازاله على نفقه المخالف", "مصادره"):
        rng(38, 44)                                          # الباب الثالث: المخالفات والعقوبات — النواة العقابية
    if K("المجلس البلدي", "عضويه المجلس البلدي", "انتخابات البلديه", "اسقاط العضويه", "اختصاصات المجلس",
         "التخطيط العمراني", "اشتراطات البناء", "تقسيم المناطق", "القسائم", "الاعلانات", "المحال"):
        rng(4, 30, 16)                                       # الباب الأول: المجلس البلدي واختصاصاته
    if K("الجهاز التنفيذي للبلديه", "المدير العام للبلديه", "المدير العام", "اصدار التراخيص", "تراخيص البناء",
         "ترخيص بناء", "رخصه محل", "الترخيص البلدي"):
        rng(31, 37)                                          # الباب الثاني: الجهاز التنفيذي والتراخيص
    if K("املاك الدوله", "الاملاك العامه", "التعديات", "اشغال الطريق", "اللائحه التنفيذيه", "احكام ختاميه"):
        rng(45, 53)                                          # الباب الرابع: أحكام ختامية
    if not (ids[2:]):                                        # سؤالٌ عامّ عن البلدية ⇒ النواة + المجلس + العقوبات
        rng(2, 5); rng(38, 44)
    return list(dict.fromkeys(ids))


# محفّز قانون تنظيم الإعلام الإلكتروني (8/2016): قانونٌ صغير (27 مادة) — نُوجّهه بالموضوع محايدَ الفرع (جزائي:
# الحجب/العقوبات/الاختصاص م18-م23؛ إداري: الترخيص م6-م16). النواةُ التعريفات (م1) والنطاق (م5). وجسرُ الإحالة:
# م18 يُحيل محظوراتِه وعقوباتِه إلى المطبوعات 3/2006 والإعلام المرئي 61/2007 — يُفعَّل حين يُدخَلان. ورفيقتُه اللائحةُ
# التنفيذية 100/2016 (regl-8-2016، 19 مادة) تُفصّل الإجراء: القيد والمستندات والدراسة وقرار الوزير والتظلم والكفالة
# (500 دينار) والترخيص والبيع والتجديد والنقل والإلغاء (رم7-رم18)، ومحتوًى تنفرد به: الاستطلاعات (رم6) والدعم والجائزة
# والبطاقات المهنية (رم4) والسجل العام (رم5) — نُلحقها بعناقيد القانون المقابلة.
_EMEDIA_KEYS = ("الاعلام الالكتروني", "اعلام الكتروني", "موقع الكتروني", "المواقع الالكترونيه", "وسيله اعلاميه الكترونيه",
    "الوسائل الاعلاميه الالكترونيه", "صحيفه الكترونيه", "الصحافه الالكترونيه", "النشر الالكتروني", "المحتوى الالكتروني",
    "وكاله انباء الكترونيه", "ترخيص موقع", "ترخيص الموقع", "حجب موقع", "حجب الموقع", "الحجب", "المدير المسؤول",
    "خدمات اخباريه الكترونيه", "النطاق الالكتروني", "الحساب الالكتروني", "تنظيم الاعلام الالكتروني",
    "الوسيله الاعلاميه", "وسيله اعلاميه", "البطاقات المهنيه", "بطاقه مهنيه", "استطلاع الراي", "استطلاعات الراي",
    "موقعي الالكتروني", "موقعي الاخباري", "موقعي الاعلامي", "وسيلتي الاعلاميه", "صحيفتي الالكترونيه",
    "موقعه الالكتروني", "موقع اخباري", "الموقع الاخباري", "الموقع الالكتروني",
    "الوسيله الاعلاميه الالكترونيه", "المواقع الاخباريه")


def _emedia_ids(blob):
    """تنظيم الإعلام الإلكتروني (8/2016، 27 مادة) + رفيقتُه اللائحة التنفيذية (100/2016، regl-8-2016، 19 مادة)
    — استحضارٌ مُوجَّهٌ بالموضوع: النواة (تعريفات م1، النطاق م5)، ثم الترخيص والمدير المسؤول والكفالة والإلغاء
    (قانون م6-م16 + لائحة رم7-رم18: القيد/المستندات/الدراسة/قرار الوزير والتظلم/الكفالة 500 دينار/البيع/التجديد
    /النقل/الإلغاء)، أو واجبات المحتوى والرد (م17)، أو المحظورات والحجب والعقوبات (م18/م19)، أو الاختصاص الجزائي
    وسقوط الدعوى (م20-م23)، أو محتوًى تنفرد به اللائحة: الاستطلاعات (رم6) والدعم والجائزة (رم4) والسجل (رم5). محايدُ الفرع."""
    if not any(_kmatch(_draft_norm_ar(k), blob) for k in _EMEDIA_KEYS):
        return []
    P = "legis-8-2016-m%d"
    R = "regl-8-2016-m%d"
    ids = [P % 1, P % 5]

    def K(*keys):
        return any(_kmatch(_draft_norm_ar(k), blob) for k in keys)

    def rng(a, b):
        ids.extend(P % n for n in range(a, b + 1))
    # المحظورات والحجب والعقوبات (الجزائي) — تُقدَّم أوّلًا لتنجو:
    if K("حجب", "عقوبه", "عقوبات", "غرامه", "مخالفه", "يعاقب", "محظورات", "جريمه", "بدون ترخيص", "بلا ترخيص"):
        rng(18, 19)
    if K("النيابه العامه", "دائره الجنايات", "المحكمه المختصه", "سقوط الدعوى", "التقادم", "ضبط المخالفات",
         "الطعن بالتمييز", "الاختصاص", "اختصاص", "تختص", "محكمه", "اي محكمه"):
        rng(20, 23)
    if K("ترخيص", "الترخيص", "كفاله", "الكفاله الماليه", "الغاء الترخيص", "المدير المسؤول", "تجديد الترخيص",
         "نقل الترخيص", "شروط الترخيص", "الاخطار"):
        rng(6, 16)
        # اللائحة التنفيذية 100/2016 — التفصيل الإجرائيّ للترخيص (القيد/المستندات/الدراسة/القرار/الكفالة/التجديد/النقل/الإلغاء):
        ids += [R % 7, R % 8, R % 10, R % 11, R % 12, R % 13, R % 14, R % 15, R % 16, R % 17, R % 18]
    if K("الرد", "التصحيح", "التكذيب", "مسؤوليه المدير", "تحري الدقه", "المحتوى المنشور"):
        ids.append(P % 17)
        ids.append("legis-3-2006-m17")               # نظيرتُها في المطبوعات: الردّ والتصحيح دون مقابل
    # جسرُ م18 مُفعَّلًا: م18 لا تحمل عقوبةً ذاتية بل تُحيل المحظوراتِ وعقوباتِها إلى المطبوعات والنشر
    # 3/2006 (م19/م20/م21 محظورات، م26/م27 عقوباتها) — فلا يُكتفى بها وحدها وإلّا وصلت إحالةٌ بلا مُحال إليه.
    if K("محظورات", "محظور", "يحظر", "ممنوع نشره", "ما لا يجوز نشره", "المساس", "ازدراء", "تحقير",
         "الذات الالهيه", "امير البلاد", "الفتن الطائفيه", "خدش الاداب", "عقوبه", "عقوبات", "يعاقب"):
        ids.append(P % 18)
        ids += ["legis-3-2006-m%d" % n for n in (19, 20, 21, 26, 27)]
        ids += ["legis-61-2007-m%d" % n for n in (11, 12, 13)]   # الطرفُ الثاني للإحالة
        ids += _unity_ids(blob)          # م21/11 (فتنٌ طائفية أو قبلية) ⇒ العقوبةُ الأشدّ في 19/2012
    if K("تعريف", "تعاريف", "نطاق", "يسري", "الحساب الشخصي", "دور النشر", "استطلاعات الراي", "السجل"):
        rng(1, 5)
    # محتوًى تنفرد به اللائحة التنفيذية 100/2016:
    if K("استطلاعات الراي", "استطلاع الراي", "استطلاع", "مجلس الامه", "الشان العام"):
        ids.append(R % 6)
    if K("دعم", "الدعم", "جائزه", "بطاقه مهنيه", "البطاقات المهنيه", "تدريب", "دورات", "رعايه الدوله",
         "الاعلانات", "المميزات"):
        ids.append(R % 4)
    if K("سجل", "السجل", "قيد الطلب", "قيد الطلبات"):
        ids += [R % 5, R % 7]
    if K("تعريف", "تعاريف", "نطاق", "يسري"):
        ids += [R % 1, R % 2]
    if K("كفاله", "الكفاله الماليه", "خمسمائه دينار", "ضمان بنكي", "الضمان المالي", "مده الترخيص", "عشر سنوات"):
        ids += [R % 12, R % 15]
    # جسرُ القضاء الإداري (20/1981): رفضُ الترخيص أو إلغاؤه قرارٌ إداريّ، والتظلّمُ إلى الوزير مرحلةٌ سابقة لا
    # نهاية الطريق — فيُستحضَر مسارُ الطعن (م7 ميعاد الستين يومًا، م8 التظلّم الوجوبيّ، م5 ولاية الإلغاء، م6 وقف
    # التنفيذ، م12/م14 الاستئناف). يُعبَر ولو صُنّف السؤالُ جزائيًّا — إذ عقوبةُ التشغيل بلا ترخيص وطعنُ الرفض
    # يردان في سؤالٍ واحد. يُلحَق أخيرًا فلا يزاحم نصوصَ التشريع الخاصّ في أولوية الاقتطاع.
    adm = _admin_core() if K(
        "رفض", "الرفض", "رفضت", "مرفوض", "تظلم", "التظلم", "طعن", "الطعن", "قرار الوزير", "قرار اداري",
        "القضاء الاداري", "الدائره الاداريه", "وقف التنفيذ", "سحب", "سحبت", "الغاء", "الغت", "ملغى") else []
    if not [x for x in ids[2:] if x.startswith("legis-8-2016")]:  # سؤالٌ عامّ ⇒ النواة + العقوبات + الاختصاص
        rng(1, 5); rng(18, 23)
    # نواةُ القانون (م1/م5) ثم جسرُ القضاء الإداري إن نطق، ثم بقيّةُ العناقيد — ليصدّر الجسرُ لا يُذيَّل.
    return list(dict.fromkeys(ids[:2] + adm + ids[2:]))


# محفّز جرائم قانون الجزاء 16/1960 — بُني بعد قياسٍ لأربعٍ وعشرين عائلة كشف أنّ إحدى عشرة منها تُعطي
# صفرَ موادّ. وللعطب سببان لا يُعالَجان بتوسيع مفاتيح الحزم القائمة: (1) الحزمُ تطابق بالاحتواء النصّيّ
# ومفاتيحُها معرَّفةٌ بأل («الخطف»، «الاختلاس»، «الحريق»)، والسؤالُ الطبيعيّ ينطقها نكرةً؛ (2) الأسئلةُ
# النظرية («أسباب الإباحة»، «الإفراج الشرطي») لا تُصنَّف جزائيةً فلا تُشغَّل حزمُ الفرع أصلًا. وهذا المحفّز
# يعمل في الغلاف فيتجاوز السببين معًا. والنطاقاتُ أدناه مأخوذةٌ من الحزم القائمة نفسها — لا أرقامَ مُخترَعة.
#
# ملاحظةٌ على المطابقة: _kmatch تُطابق بدايةَ الكلمة بلا حدٍّ في آخرها، فمفتاحٌ من حرفين مثل «سب» يلتقط
# محفّز قانون المعاملات الإلكترونية (20/2014، 46 مادة) — محايدُ الفرع (مدنيّ: الحجّية والإثبات؛ جزائيّ: م37-م42؛
# إداريّ: التراخيص وطلبُ البيانات والتظلّم). وم2 وم3 مستبدَلتان بالمرسوم بقانون 148/2025 فأُلغيت الاستثناءاتُ
# القديمة (الأحوال الشخصية والعقار والكمبيالات والمحرَّر الرسميّ) — فتُصدَّران كي لا يُفتى باستثناءٍ ملغى.
_ETRX_KEYS = ("المعاملات الالكترونيه", "معامله الكترونيه", "التوقيع الالكتروني", "توقيع الكتروني",
    "المستند الالكتروني", "السجل الالكتروني", "سجل الكتروني", "الرساله الالكترونيه", "شهاده التصديق",
    "التصديق الالكتروني", "مزود خدمات التصديق", "ختم الوقت", "الدفع الالكتروني", "وسيله الدفع",
    "القيد غير المشروع", "الكتابه الالكترونيه", "الدعامه الالكترونيه", "اداه التوقيع", "التشفير",
    "العقد الالكتروني", "التعاقد الالكتروني", "نظام المعالجه", "نظام معالجه", "معالجه الكترونيه",
    "البيانات الشخصيه", "بياناتي الشخصيه", "بيانات شخصيه", "معلومات شخصيه", "اختراق", "الاختراق",
    "حمايه البيانات", "خصوصيه البيانات", "نظام الكتروني")


def _etrx_ids(blob):
    """المعاملات الإلكترونية (20/2014) — النواة: م2 النطاق وم3 الحجّية (النصّ النافذ بعد 148/2025)، ثم الحجّية
    والإثبات (م6/م7/م14/م18) أو التوقيع المحميّ والتصديق (م19-م25) أو الدفع الإلكتروني (م28-م31) أو الخصوصية
    وطلبُ البيانات (م32-م36) أو العقوبات والصلح (م37-م42)."""
    if not any(_kmatch(_draft_norm_ar(k), blob) for k in _ETRX_KEYS):
        return []
    P = "legis-20-2014-m%d"
    ids = [P % 2, P % 3]

    def K(*keys):
        return any(_kmatch(_draft_norm_ar(k), blob) for k in keys)

    def rng(a, b):
        ids.extend(P % n for n in range(a, b + 1))
    if K("عقوبه", "عقوبات", "غرامه", "جريمه", "يعاقب", "حبس", "تزوير", "اختراق", "صلح", "الصلح",
         "مصادره", "النيابه العامه"):
        rng(37, 42)
    if K("حجيه", "اثبات", "الاثبات", "دليل", "صوره", "نسخه", "محرر", "المحرر", "انعقاد", "التصرف"):
        ids += [P % 6, P % 7, P % 14, P % 18]      # وم7/م18 يُحيلان إلى الإثبات المدنيّ 39/1980
    if K("توقيع", "التوقيع", "تصديق", "شهاده"):
        rng(18, 21)                                     # حجّيةُ التوقيع وشروطُ حمايته وعبءُ إثباته
    if K("مزود", "مزودي", "جهه التصديق", "خدمات التصديق", "ترخيص", "الجهه المختصه", "اعتماد"):
        rng(22, 25)                                     # مزوّدو خدمات التصديق وترخيصُهم — لا يُقحَمون بلا سؤال
    if K("دفع", "الدفع", "تحويل", "حساب مصرفي", "بنك", "المؤسسه الماليه", "بطاقه", "البنك المركزي"):
        rng(28, 31)
    if K("خصوصيه", "بيانات شخصيه", "حمايه البيانات", "افشاء", "الاطلاع", "محو", "تظلم", "طلب بيانات"):
        rng(32, 36)
    if K("تعريف", "تعاريف", "نطاق", "يسري", "جهه حكوميه", "عطاءات"):
        ids += [P % 1, P % 4, P % 26, P % 27]
    if not ids[2:]:
        ids += [P % 1, P % 6, P % 7, P % 18, P % 19]
    return list(dict.fromkeys(ids))


# محفّز التسجيل العقاري (5/1959) — القانون مُدخَلٌ كاملًا (72 كائنًا) وله حِزمٌ في `_REGISTRATION_BUNDLES`،
# لكنّها محبوسةٌ بقيدين: الكتلةُ كلُّها مشروطةٌ بفرعٍ «مدني/تجاري»، ومفاتيحُها مركّبةٌ تُطابَق بالاحتواء
# الحرفيّ («اثبات اصل الملكيه»، «تسجيل عقد البيع») فلا ينطقها السؤالُ الطبيعيّ. فيُستحضَر هنا في الغلاف
# محايدَ الفرع — إذ سؤالُ العقار يرد مدنيًّا وتجاريًّا وجزائيًّا (تزوير محرَّر) وأحوالًا شخصية (إرث ووقف).
#
# والبوّابةُ اقترانيّة: لفظُ العقار وحده لا يكفي (فيزاحم بلا موجب)، بل يُشترط معه فعلٌ تصرّفيّ — إلّا في
# ألفاظٍ قاطعةٍ لا تحتمل غيرَ هذا القانون («التسجيل العقاري»، «الشهر العقاري»، «الحقوق العينية»).
_REALTY_STRONG = ("التسجيل العقاري", "تسجيل عقاري", "الشهر العقاري", "شهر عقاري", "دائره التسجيل",
                  "صحه ونفاذ", "شهاده عقاريه", "وثيقه الملكيه", "سند الملكيه", "حق عيني",
                  "الحقوق العينيه", "حقوق عينيه")
_REALTY_SUBJ = ("عقار", "اراضي", "ارض", "قسيمه", "قسائم", "شاليه")
_REALTY_ACT = ("تسجيل", "شهر", "ملكيه", "تملك", "يملك", "بيع", "باع", "شراء", "اشتري", "مشتري", "بائع",
               "نقل", "انتقال", "تصرف", "هبه", "مقايضه", "رهن", "ارتفاق", "انتفاع", "قسمه", "وقف",
               "وصيه", "ميراث", "ارث", "تركه", "حصه", "شيوع", "استحقاق", "عقد", "محرر")

# جسرُ المعاملة الإلكترونية ⇄ العقار: 20/2014 (م2/م3 بنصّهما بعد المرسوم 148/2025) تُنشئ الالتزامَ،
# وم7 من 5/1959 تحبسه عند حدّه — «لا تنشأ ولا تنتقل… ولا يكون للتصرّفات غير المسجَّلة من الآثار سوى
# الالتزامات الشخصية بين ذوي الشأن». وم17 (التحريرُ بمعرفة موظّفي الدائرة) وم29/م30 (التصديقُ الحضوريّ
# بشاهدين واستيثاقٌ شفويّ) تُفسّران لماذا لا يقوم البريدُ الموقَّعُ إلكترونيًّا مقامَ محرَّر التسجيل.
# وفي هذه الحال تُختصَر القائمةُ إلى النواة الحاسمة وحدها كي لا تُزاحِم موادَّ 20/2014 في نافذة الصدارة.
_REALTY_ETRX_CORE = ("m7", "m17", "m29", "m30")


def _realty_ids(blob):
    """التسجيل العقاري 5/1959 — الصدارةُ دائمًا لم7 (أثرُ عدم التسجيل)، ثمّ العنقودُ بحسب موضوع السؤال."""
    def K(*keys):
        return any(_kmatch(_draft_norm_ar(k), blob) for k in keys)

    def KW(*keys):
        """للمفاتيح القصيرة الملتبسة: «قيم» تلتقط «قيمته»، و«ولي» تلتقط «وليس» ما لم يُحَدَّ آخرُها."""
        return any(_kmatch_w(_draft_norm_ar(k), blob) for k in keys)

    if not (K(*_REALTY_STRONG) or (K(*_REALTY_SUBJ) and K(*_REALTY_ACT))):
        return []
    P = "legis-5-1959-%s"
    if any(_kmatch(_draft_norm_ar(k), blob) for k in _ETRX_KEYS):
        core = [P % s for s in _REALTY_ETRX_CORE]
        # ولو نطق السؤالُ بالخصومة وجب أن يُلحَق عنقودُ صحف الدعاوى: فالجوابُ الصحيح هنا ليس البطلانَ بل
        # دعوى صحّةٍ ونفاذٍ يقوم حكمُها مقام التنفيذ (م289 مدنيّ) ويُسجَّل بم7 نفسها، ويُحفَظ أثرُها في
        # مواجهة الغير بتسجيل صحيفتها والتأشير بمنطوق الحكم (م11 مكرر 1-4). رُصد سقوطُه فعلًا: أعلن
        # النموذجُ أنّ «سندَ التأشير غيرُ مرفق» وهو مُدخَلٌ في القاعدة — فكان الاختصارُ حاجبًا لا موفّرًا.
        if K("دعوى", "دعوي", "دعواي", "اقاضي", "قضاء", "محكمه", "صحيفه", "تاشير", "انكر", "ينكر",
             "يرفض", "امتنع", "الغير", "حجه على الغير"):
            core += [P % ("m11-mukarrar-%d" % n) for n in range(1, 4)]
        return core
    ids = [P % "m7"]
    if K("بيع", "باع", "شراء", "اشتري", "نقل", "انتقال", "تصرف", "هبه", "مقايضه", "ملكيه", "تملك"):
        ids += [P % s for s in ("m8", "m13", "m14", "m17", "m12")]
    if K("توقيع", "تصديق", "وكاله", "وكيل", "توكيل", "حضور", "شاهد", "شهود", "اهليه", "نيابه"):
        ids += [P % s for s in ("m29", "m30", "m31", "m32", "m45", "m46", "m49", "m50", "m51")]
    if K("ارث", "ميراث", "تركه", "وارث", "ورثه", "وصيه", "وقف", "قسمه"):
        ids += [P % s for s in ("m10", "m20", "m21", "m8")]
    if K("ايجار", "منفعه", "مستاجر", "مؤجر"):
        ids.append(P % "m11")
    if K("دعوى", "دعوي", "صحيفه", "استحقاق", "تاشير", "محو", "شطب", "حجه على الغير", "حكم نهائي"):
        ids += [P % ("m11-mukarrar-%d" % n) for n in range(1, 5)]
    if K("رسم", "رسوم", "اعفاء", "تهرب"):
        ids += [P % s for s in ("m57", "m58", "m58-mukarrar", "m59", "m60", "m60-mukarrar", "m61")]
    if KW("قاصر", "قاصرا", "القصر", "ولايه", "ولي", "وصايه", "وصي", "محجور", "قيم", "سفه",
          "عته", "جنون", "قوامه"):
        ids += [P % ("m%d" % n) for n in range(33, 44)]
    if K("غير كويتي", "اجنبي", "الاجانب", "جنسيه"):
        ids += [P % s for s in ("m5", "m6")]
    if K("رهن", "ارتفاق", "انتفاع", "حق تبعي"):
        ids.append(P % "m9")
    if K("اجراءات", "طلب", "مستندات", "شهاده", "اسبقيه", "قيد", "بيانات"):
        ids += [P % s for s in ("m12", "m12-mukarrar-1", "m12-mukarrar-2", "m15", "m16", "m18", "m19")]
    if len(ids) == 1:                                   # سؤالٌ عامّ ⇒ النواةُ الموضوعية
        ids += [P % s for s in ("m8", "m13", "m14", "m12", "m29", "m3")]
    return list(dict.fromkeys(ids))


# محفّز الاختصاص وتقدير قيمة الدعوى (المرافعات 38/1980) — رُصد أنّ النموذج بلغ الاختصاصَ في دعوى
# عقاريةٍ **قياسًا** على م833 مدنيّ (وهي في دعوى القسمة)، وقواعدُ الاختصاص من النظام العام لا تثبت
# بقياس. ومعاينةُ القانون كشفت أنّه لا بابَ اختصاصٍ محلّيًّا فيه أصلًا — فالكويت وحدةٌ قضائية —
# وإنّما ثلاثة أبواب: الدوليّ (م23-م28)، والنوعيّ والقيميّ (م29-م36)، وتقديرُ القيمة (م37-م44).
# والمسارُ الصحيح ترتيبًا هو مسارُ الاستدلال نفسُه: م40 (تقديرُ دعوى صحّة العقد بقيمة المتعاقد عليه)
# ⇐ م39 (الدعوى العقارية بقيمة العقار) ⇐ م29 (نصابُ الجزئية خمسةُ آلاف) ⇐ م34 (فما جاوزه فللكلية).
_VENUE_ASK = ("اي محكمه", "أي محكمه", "المحكمه المختصه", "محكمه مختصه", "الاختصاص", "اختصاص",
              "تختص", "يختص", "نصاب", "النصاب", "قيمه الدعوى", "قيمه الدعوي", "تقدير الدعوى",
              "امام اي", "ارفع الدعوى", "ارفع دعوى", "اين ارفع")
_VENUE_CIV = ("دعوى", "دعوي", "دعواي", "عقد", "العقد", "بيع", "عقار", "تعويض", "الزام", "فسخ",
              "ابطال", "صحه ونفاذ", "صحه العقد", "صحه التوقيع", "ثمن", "دين", "شركه", "ميراث",
              "تركه", "قسمه", "حراسه", "مستعجل")
# الجزائيُّ اختصاصُه في الإجراءات الجزائية 17/1960 لا في المرافعات — فيُمنع التسرّب صراحةً.
_VENUE_NOT = ("جنايه", "جنايات", "جنحه", "جنح", "جزائي", "جزائيه", "عقوبه", "عقوبات", "متهم",
              "النيابه العامه", "يعاقب", "حبس", "جريمه", "مخالفه مروريه")
# ومنازعةُ العقد الإداريّ ليست من هذا الباب أصلًا: م2 من 20/1981 تُسند إلى الدائرة الإدارية
# «**وحدها** بنظر المنازعات التي تنشأ بين الجهات الإدارية والمتعاقد الآخر في عقود الالتزام والأشغال
# العامة والتوريد أو أيّ عقد إداريّ». فتوجيهُ صاحبها إلى المحكمة الكلية بم29/م34 خطأٌ يُبطل الإجراء،
# ولذا تُحوَّل إلى نواة القضاء الإداريّ بدل أن تُترك للقواعد العامّة. رُصد فعلًا في أربعة أسئلةٍ من أربعة.
# والبوّابةُ هنا مضبوطةٌ عمدًا: ألفاظٌ لا تحتمل غيرَ العقد الإداريّ تُشعلها وحدَها؛ أمّا ذكرُ الجهة
# (وزارة، بلدية، الدولة) فلا يكفي إلّا مقترنًا بلفظ تعاقد — وإلّا حُوّلت دعوى التعويض عن خطأٍ طبّيّ
# ضدّ وزارة الصحة إلى القضاء الإداريّ، وهي مسؤوليةٌ تقصيريةٌ من اختصاص المحاكم العادية.
_VENUE_ADM_ONLY = ("عقد اداري", "عقدا اداريا", "عقود اداريه", "عقد التزام", "عقود الالتزام",
                   "اشغال عامه", "توريد", "التوريد", "مناقصه", "مناقصات", "امتياز مرفق",
                   "التزام مرفق", "مرفق عام")
_VENUE_ADM_ENT = ("جهه اداريه", "جهات اداريه", "وزاره", "الوزاره", "وزارات", "هيئه عامه",
                  "مؤسسه عامه", "بلديه", "جهه حكوميه", "جهات حكوميه", "الدوله", "الحكومه")
_VENUE_ADM_CTR = ("عقد", "العقد", "عقود", "تعاقد", "تعاقدت", "متعاقد", "مقاول", "مقاوله",
                  "مورد", "توريد", "التزام", "مستحقات العقد")
# الشريعةُ العامة للعقد تُستحضَر مع نواة القضاء الإداريّ في منازعة العقد: قوّةُ العقد (م196)،
# وحسنُ النية في تنفيذه (م197)، ومدّةُ عدم سماع الدعوى العامّة خمسَ عشرةَ سنة (م438) وانقطاعُها
# بالمطالبة القضائية ولو أمام محكمةٍ غير مختصّة (م448)، وتقديرُ التعويض عند خلوّ العقد منه (م300).
_ADM_CIVIL_CORE = ["legis-67-1980-m" + n for n in ("196", "197", "438", "448", "300")]


def _venue_ids(blob):
    """اختصاصُ المرافعات 38/1980 — مرتَّبٌ ترتيبَ الاستدلال: تقديرُ القيمة أوّلًا ثمّ درجةُ المحكمة."""
    def K(*keys):
        return any(_kmatch(_draft_norm_ar(k), blob) for k in keys)

    if not (K(*_VENUE_ASK) and K(*_VENUE_CIV)) or K(*_VENUE_NOT):
        return []
    if K(*_VENUE_ADM_ONLY) or (K(*_VENUE_ADM_ENT) and K(*_VENUE_ADM_CTR)):
        # عقدٌ إداريّ ⇒ الدائرةُ الإدارية وحدها، لا قواعدُ الاختصاص في المرافعات. ومعها الشريعةُ العامة
        # للعقد: م15 من 20/1981 تُحيل صراحةً إلى ما لم يرد فيه نصّ، وولايةُ «القضاء الكامل» في م2 دعوى
        # موضوعٍ لا إلغاء — فتحكمها مدّةُ عدم سماع الدعوى العامّة (م438: خمس عشرة سنة) وانقطاعُها
        # (م448) لا ميعادُ الستّين يومًا. رُصد فعلًا: استُحضرت م448 وحدَها فأعلن الجوابُ أنّ نصَّ
        # المدّة «غيرُ مرفق» وهو مُدخَل — حلقةُ الانقطاع بلا حلقة المدّة. وتُسقَط م12 مكرر (خاصّةٌ
        # بالتأديب) كي لا تزاحم، فيبقى المجموعُ سبعةَ عشرَ داخل نافذة الدرجة العالية.
        return ([x for x in _admin_core() if not x.endswith("-m12mkr")] + _ADM_CIVIL_CORE)
    P = "legis-38-1980-m%s"
    ids = []
    if K("صحه ونفاذ", "صحه العقد", "صحه عقد", "ابطال", "فسخ", "عقد", "العقد", "بيع"):
        ids.append(P % "40")
    if K("عقار", "ارض", "قسيمه", "ملكيه", "ارتفاق", "انتفاع", "رقبه", "حيازه"):
        ids.append(P % "39")
    if K("توقيع", "تزوير", "محرر", "ورقه عرفيه"):
        ids.append(P % "42")
    ids += [P % "29", P % "34", P % "37"]                # النصاب ⇐ الكلية ⇐ وقتُ التقدير
    if K("استئناف", "تمييز", "طعن"):
        ids.append(P % "36")
    if K("اجنبي", "الاجانب", "خارج الكويت", "دوله اجنبيه", "موطن في الخارج"):
        ids += [P % "23", P % "24"]
    if K("ميراث", "تركه", "ارث", "وارث", "ورثه"):
        ids.append(P % "25")
    if K("مستعجل", "حراسه", "وقتي", "تحفظي"):
        ids += [P % "31", P % "32"]
    if K("رهن", "حجز", "حق عيني تبعي"):
        ids.append(P % "41")
    return list(dict.fromkeys(ids))


# محفّزُ المناقصات العامة 49/2016 — القانونُ الخاصُّ بالشراء العامّ، الحالُّ محلَّ 37/1964 (م94).
# وموقعُه من الترتيب قبل «الاختصاص العامّ» (_venue_ids): فذاك يُحوّل منازعةَ العقد الإداريّ إلى نواة
# 20/1981 — وهو صحيح لكنّه ناقص. فم79 من 49/2016 تُخصّص الولايةَ أكثر: **غرفةٌ** من غرف الدائرة
# الإدارية بالمحكمة الكلية، و**دائرةٌ متخصّصةٌ** بمحكمة الاستئناف حكمُها **باتّ لا يجوز الطعن فيه
# بأيّ طريق** — فلا تمييزَ هنا خلافًا للقاعدة العامّة في م14 مكرر من 20/1981. ومن أجاب بالتمييز
# اعتمادًا على النواة العامّة وحدَها أضاع على صاحبه ميعادًا لا يُستدرَك. ولذا يتصدّر هذا المحفّزُ.
_TENDER_STRONG = ("مناقصه", "مناقصات", "المناقصات العامه", "الجهاز المركزي للمناقصات", "الجهاز المركزي",
                  "عطاء", "عطاءات", "مناقص", "المناقصين", "متعهد", "المتعهدين",
                  "ممارسه عامه", "الممارسه", "امر مباشر", "التعاقد المباشر", "الشراء العام",
                  "مشتريات عامه", "ترسيه", "الترسيه", "كراسه الشروط", "دفتر الشروط",
                  "التامين الاولي", "التامين النهائي", "تصنيف المقاولين", "سجل الموردين",
                  "لجنه التصنيف", "لجنه التظلمات", "اوامر تغييريه", "امر تغييري", "شراء جماعي",
                  "تاهيل مسبق", "التاهيل المسبق")
# ولا تكفي «جهةٌ عامة» وحدَها؛ لا بدّ من اقترانها بلفظِ شراءٍ أو تعاقدٍ — وإلّا انجرّت إلى هنا
# دعوى تعويضٍ تقصيريّةٌ ضدّ وزارة، وليست من الشراء العامّ في شيء.
_TENDER_ENT = ("جهه عامه", "جهات عامه", "الجهه صاحبه الشان", "وزاره", "الوزاره", "هيئه عامه",
               "مؤسسه عامه", "بلديه", "جهه حكوميه", "جهات حكوميه", "الجهاز", "مؤسسه البترول")
_TENDER_ACT = ("توريد", "مقاوله", "مقاولات", "اشغال عامه", "شراء", "مشتريات", "تعاقد", "عقد توريد",
               "خدمات", "طرح", "اعلان مناقصه")
# وبوّابةٌ ثالثة اقترانية: ألفاظٌ اصطلاحيةٌ في هذا القانون لكنّها مشتركةٌ مع غيره — «تأمين» يعني
# التأمينَ التجاريّ في بابه، و«سجل» و«فئة» و«حرمان» ألفاظٌ عامة. فلا تنطق إلّا مقترنةً بسياق شراءٍ
# صريح. وهذا يلتقط صيغةَ الإضافة التي تفلت من المفاتيح المركّبة («تأميننا النهائي»، «سجلّ المقاولين»).
_TENDER_TERM = ("تامين", "التامين", "تامينات", "ضمان", "خطاب ضمان", "سجل", "قوائم", "تصنيف",
                "فئه", "الفئه", "جزاء", "جزاءات", "انذار", "حرمان", "حذف", "شطب", "غرامه", "غرامات")
_TENDER_CTX = ("مناقصه", "مناقصات", "عطاء", "عطاءات", "مناقص", "الجهاز", "الجهه صاحبه الشان",
               "مقاول", "مقاولين", "مورد", "موردين", "متعهد", "متعهدين", "توريد", "مقاوله",
               "ترسيه", "الشراء العام", "اشغال عامه")
# ونطاقُ السريان (م2/م3) يُستحضَر دائمًا: فأوّلُ سؤالٍ في كلّ نزاعِ شراءٍ هو «هل يسري القانونُ أصلًا؟»
# — وم3 تستثني النفطَ ومشتقّاتِه والغازَ والبتروكيماوياتِ وتُسندها لوحدة الشراء بمؤسسة البترول.
_TENDER_CORE = ("m2", "m3")
_TENDER_P = "legis-49-2016-%s"


def _tender_ids(blob):
    """المناقصات العامة 49/2016 — عناقيدُ بحسب موضع السؤال من دورة الشراء، والنواةُ نطاقُ السريان."""
    def K(*keys):
        return any(_kmatch(_draft_norm_ar(k), blob) for k in keys)

    if not (K(*_TENDER_STRONG) or (K(*_TENDER_ENT) and K(*_TENDER_ACT))
            or (K(*_TENDER_TERM) and K(*_TENDER_CTX))):
        return []
    P = _TENDER_P
    ids = [P % s for s in _TENDER_CORE]
    # (1) الخصومة: شكوى ⇐ تظلّم ⇐ دعوى. وهذا أخطرُ العناقيد لأنّ ميعادَه سبعةُ أيام عملٍ لا ستّون
    # يومًا، ودرجتَه درجتان لا ثلاث. ويُجسَر إلى م2 من 20/1981 (الولايةُ الكاملةُ في العقد الإداريّ)
    # وم15 منه (تطبيقُ المرافعات تكميليًّا) — أساسًا عامًّا يقوم عليه التخصيصُ في م79.
    # وتُذكَر صيغُ الفعل صراحةً («نتظلّم»، «أتظلّم») لأنّ سوابقَ المطابقة تشمل «ال/و/ف/ب/ل/ك» ولا
    # تشمل حروفَ المضارعة — ولولا ذلك لسقط عنقودُ الخصومة من سؤالٍ صريحٍ فيها.
    if K("تظلم", "التظلم", "نتظلم", "اتظلم", "يتظلم", "تتظلم", "تظلمنا", "شكوى", "شكوي", "نشكو",
         "طعن", "نطعن", "دعوى", "دعوي", "محكمه", "اختصاص", "تختص", "قضاء",
         "استئناف", "تمييز", "نزاع", "منازعه", "خصومه", "الغاء القرار", "قرار الترسيه"):
        ids += [P % s for s in ("m77", "m78", "m79", "m80", "m81")]
        ids += ["legis-20-1981-m2", "legis-20-1981-m15"]
    # (2) الجزاءات الإدارية على المتعاقد ومساءلةُ الموظّف ومنعُ تضارب المصالح (وجزاؤه إبطالُ العقد).
    if K("جزاء", "جزاءات", "عقوبه اداريه", "انذار", "تخفيض الفئه", "حذف من السجل", "حرمان",
         "شطب", "ايقاف", "تضارب المصالح", "مساءله", "تحقيق", "مخالفه", "تعثر", "متعثره"):
        ids += [P % s for s in ("m85", "m82", "m83", "m84")]
    # (3) التأمينان: الأوّليّ (م45) والنهائيّ (م65) ومصادرتُهما (م66، م70) وردُّهما (م69).
    if K("تامين", "التامين", "ضمان", "خطاب ضمان", "مصادره", "صادر", "رد التامين"):
        ids += [P % s for s in ("m45", "m65", "m66", "m69", "m70")]
    # (4) العقد: توقيعُه (م68)، والباطن (م71)، والانسحاب (م72)، والأوامر التغييرية وسقفُها 5% (م74)،
    # وتعديلُ الأسعار (م75)، والاعتماد المالي (م76)، والعقدُ النموذجيّ وكرّاستاه (م86).
    if K("العقد", "عقد", "توقيع العقد", "تنفيذ", "الباطن", "مقاول بالباطن", "انسحاب", "انسحب",
         "امر تغييري", "اوامر تغييريه", "تعديل الاسعار", "زياده", "نقص", "اعتماد مالي", "فسخ",
         "غرامه", "غرامات", "تسليم", "استلام"):
        ids += [P % s for s in ("m68", "m71", "m72", "m74", "m75", "m76", "m86")]
    # (5) التسجيل والتصنيف والتأهيل، وشروطُ المتعاقد بصيغة 1/2024 (لا جنسيةَ ولا وكيلَ محلّيّ).
    if K("تسجيل", "قوائم", "تصنيف", "فئه", "الفئه", "تاهيل", "شروط المتعاقد", "سجل تجاري",
         "اجنبي", "الاجانب", "جنسيه", "وكيل محلي", "شركه اجنبيه"):
        ids += [P % s for s in ("m24", "m26", "m27", "m31", "m32")]
    # (6) أساليبُ التعاقد وحدودُها المالية — بابُ «هل كان يجوز أصلًا أن يُتعاقَد بهذا الطريق؟».
    if K("اسلوب", "طريقه التعاقد", "مناقصه محدوده", "ممارسه", "امر مباشر", "حد مالي", "نصاب",
         "خمسه وسبعين", "75000", "اذن الجهاز", "بدون اذن", "استثناء"):
        ids += [P % s for s in ("m13", "m14", "m17", "m18", "m19", "m22", "m23")]
    # (7) الطرحُ والإعلانُ والعطاءُ وفتحُ المظاريف والتقييمُ والترسيةُ والعدولُ عنها.
    if K("طرح", "اعلان", "الاعلان", "وثائق", "مظروف", "المظاريف", "فتح المظاريف", "تقييم",
         "مقارنه", "اقل الاسعار", "ترسيه", "الترسيه", "عدول", "العدول", "الغاء المناقصه",
         "اعاده الطرح", "سريان العطاء"):
        ids += [P % s for s in ("m38", "m39", "m46", "m48", "m53", "m56", "m63", "m64", "m73")]
    # (8) الأفضليةُ للمنتج المحلّيّ والمشروعات الصغيرة والمتوسطة — نسبٌ صريحةٌ بعد 74/2019.
    if K("منتج محلي", "المنتج المحلي", "منتج وطني", "المنتج الوطني", "افضليه", "اولويه",
         "مشروع صغير", "المشروعات الصغيره", "متوسطه", "نسبه", "20%", "10%", "30%"):
        ids += [P % s for s in ("m61", "m62", "m62-mukarrar", "m87")]
    # (9) الإعلانُ الإلكترونيّ وبطلانُه (م80) — ويُجسَر إلى 20/2014 (حجّيةُ السجلّ والتوقيع والإرسال).
    if K("الكتروني", "الكترونيا", "بريد الكتروني", "فاكس", "الموقع الالكتروني", "بوابه", "نظام الي"):
        ids += [P % "m80", "legis-20-2014-m10", "legis-20-2014-m22"]
    # (10) اللائحةُ والرسومُ والشفافيةُ والاتفاقُ بين الجهات العامة والأحكامُ الختامية.
    if K("لائحه", "اللائحه التنفيذيه", "رسم", "رسوم", "شفافيه", "نشر", "بوابه المشتريات",
         "بدء العمل", "الغاء القانون", "37 لسنه 1964"):
        ids += [P % s for s in ("m89", "m90", "m91", "m93", "m94", "m96")]
    if len(ids) == len(_TENDER_CORE):                    # سؤالٌ عامّ ⇒ عمودُ الدورة الفقريّ
        ids += [P % s for s in ("m13", "m48", "m63", "m64", "m77", "m79")]
    return list(dict.fromkeys(ids))


# «سبيل» و«سبق»، و«تعدي» تلتقط «تعديل». ولذا يُطابَق هنا بحدَّي الكلمة.
_PEN_BND = {}


def _kmatch_w(key, blob):
    """مطابقةٌ بحدَّي الكلمة (بادئةً ونهايةً) — تمنع «سبيل/سبق/تعديل/سمعة» من إشعال مفاتيحَ قصيرة."""
    rx = _PEN_BND.get(key)
    if rx is None:
        rx = re.compile(r'(?:^|\s)' + _BR_PFX + re.escape(key) + r'(?=\s|$|[.,؛:؟!)\]])')
        _PEN_BND[key] = rx
    return rx.search(blob) is not None


_PENAL_KEYS = (
    "اهانه", "اهان", "تعدى", "التعدي", "مقاومه", "شيك", "الشيك", "شيكات", "رصيد",
    "خمر", "الخمر", "مسكر", "مسكرات", "بلاغ", "بلاغا", "وشايه", "شهاده", "زور",
    "قذف", "القذف", "السب", "سبا", "تشهير", "تسميم", "بالسم", "ازعاج", "تصالح", "التصالح",
    "امن الدوله", "تخابر", "خيانه عظمى", "تجسس", "شعائر", "تدنيس",
    "اختلاس", "رشوه", "رشوة", "مرتشي", "راشي", "استغلال الوظيفه", "تعذيب",
    "قتل", "قتله", "ضرب", "جرح", "ايذاء", "عاهه", "خطف", "حجز", "اجهاض", "اجهض",
    "عرض", "هتك", "اغتصاب", "فاضح", "الحياء", "دعاره", "فجور", "قمار", "ميسر",
    "سرقه", "سرق", "نصب", "احتيال", "خيانه الامانه", "تبديد", "اختلاسا",
    "تزوير", "زور محررا", "محرر رسمي", "محرر عرفي", "تزييف", "مسكوكات", "حريق", "اتلاف", "تخريب",
    "افلاس", "تفليس", "شروع", "الشروع", "فاعل اصلي", "شريك", "تحريض", "مساهمه",
    "اباحه", "الاباحه", "دفاع شرعي", "اداء الواجب", "عود", "العود", "افراج شرطي", "رد الاعتبار")


def _penal_ids(blob):
    """عناقيدُ جرائم 16/1960 — كلُّ عنقودٍ يجمع الأصلَ وفروعَه «مكرر» وقيدَه الإجرائيّ. مقيسٌ لا مفترَض."""
    if not any(_kmatch_w(_draft_norm_ar(k), blob) for k in _PENAL_KEYS):
        return []
    P = "legis-16-1960-m%s"
    ids = []

    def K(*keys):
        return any(_kmatch_w(_draft_norm_ar(k), blob) for k in keys)

    def rng(a, b, cap=26):
        ids.extend(P % n for n in range(a, min(b, a + cap - 1) + 1))
    # ── جرائمُ قِيست غيابًا ثمّ عوقبت بعناقيدَ دقيقة (الأصل + فروعُه المفكوكة) ──
    if K("اهانه", "اهان", "تعدى", "التعدي", "مقاومه", "تصالح", "التصالح", "التنازل عن الشكوى"):
        ids += [P % n for n in ("133", "134", "135", "135-mukarrar", "135-mukarrar-a")]
    if K("شيك", "الشيك", "شيكات", "رصيد", "بدون رصيد", "المسحوب عليه", "الساحب"):
        ids += [P % n for n in ("237", "237-mukarrar", "237-mukarrar-a", "237-mukarrar-b", "238")]
    if K("خمر", "الخمر", "مسكر", "مسكرات", "شراب مسكر"):
        ids += [P % n for n in ("206", "206-mukarrar-a", "206-mukarrar-b", "206-mukarrar-c")]
    if K("تسميم", "بالسم", "بجواهر", "جواهر سامه"):
        ids += [P % n for n in ("149", "149-mukarrar", "150")]
    if K("بلاغ", "بلاغا", "وشايه", "ازعاج", "بلاغ كاذب"):
        ids += [P % n for n in ("145", "145-mukarrar")]
    if K("شهاده", "زور", "شاهد زور", "اليمين الكاذبه"):
        ids += [P % "136"]
    if K("قذف", "القذف", "السب", "سبا", "تشهير", "نقد مباح", "حسن النيه"):
        ids += [P % n for n in ("209", "210", "211", "214", "215")]
    # ── العائلاتُ التي أعطت صفرًا: نطاقاتٌ مأخوذةٌ من الحزم القائمة ──
    if K("امن الدوله", "تخابر", "تجسس", "خيانه عظمى", "شعائر", "تدنيس", "سب الاديان"):
        rng(109, 125)
    if K("اختلاس", "اختلاسا", "رشوه", "رشوة", "مرتشي", "راشي", "استغلال الوظيفه", "تعذيب"):
        rng(126, 135)
    if K("قتل", "قتله", "ضرب", "جرح", "ايذاء", "عاهه", "خطف", "حجز", "اجهاض", "اجهض"):
        rng(149, 178)
    if K("عرض", "هتك", "اغتصاب", "فاضح", "الحياء", "دعاره", "فجور", "قمار", "ميسر"):
        rng(186, 215)
    if K("سرقه", "سرق", "نصب", "احتيال", "خيانه الامانه", "تبديد"):
        rng(217, 241)
    if K("تزوير", "زور محررا", "محرر رسمي", "محرر عرفي", "تزييف", "مسكوكات", "حريق", "اتلاف", "تخريب"):
        rng(242, 271)
    if K("افلاس", "تفليس"):
        rng(274, 286)
    if K("شروع", "الشروع", "فاعل اصلي", "شريك", "تحريض", "مساهمه"):
        rng(45, 56)
    if K("اباحه", "الاباحه", "دفاع شرعي", "اداء الواجب", "رضاء المجني عليه"):
        rng(27, 44)
    if K("عود", "العود", "افراج شرطي", "رد الاعتبار", "وقف التنفيذ"):
        rng(80, 91)
    return list(dict.fromkeys(ids))


# محفّز قانون المطبوعات والنشر (3/2006، 33 مادة) — محايدُ الفرع (جزائي: المحظورات والعقوبات م19-م28؛ إداري:
# التراخيص والطعن م3-م18). ونواتُه م1 (حرية الصحافة) وم2 (التعاريف — وفيها النصُّ الجامع: «ويدخل في حكم
# المطبوع ما ينشر من خلال المواقع أو الوسائل الإعلامية الإلكترونية»، فهو جسرٌ نصّيٌّ إلى 8/2016). وم11 تُجيز
# صراحةً الطعنَ بإلغاء رفض الترخيص أمام الدائرة الإدارية وفق 20/1981 — وهو نصٌّ خاصٌّ لاحق يواجه استثناءَ
# «تراخيص إصدار الصحف والمجلات» في م1/خامسا من 20/1981، فيلزم استحضارُهما معًا لا أحدُهما.
_PRESS_KEYS = ("المطبوعات والنشر", "المطبوعات", "مطبوع", "المطبوع", "الصحيفه", "صحيفه", "الصحف", "صحف",
    "مجله", "المجلات", "رئيس التحرير", "نائب رئيس التحرير", "المحرر", "الناشر", "الطابع", "مطبعه",
    "المطبعه", "دار نشر", "دور النشر", "وكاله انباء", "الصحافه", "صحفي", "الصحفيين", "النشر",
    "حريه الصحافه", "ترخيص صحيفه", "ترخيص الصحيفه", "تعطيل الصحيفه", "ايقاف الصحيفه", "مصادره المطبوع",
    "صحيفتي", "صحيفته", "مجلتي", "مطبعتي", "جريده", "الجريده", "مقال", "المقال", "كاتب المقال")


# جسرُ الوحدة الوطنية (19/2012، خمسُ مواد): م21/11 من المطبوعات تحظر «إثارة الفتن الطائفية أو القبلية»
# بغرامةٍ 3000-10000 (م27/3)، بينما يجرّم المرسومُ بقانون 19/2012 الفعلَ ذاتَه بعقوبةٍ أشدّ — وم27 نفسُها
# تُصرّح بـ«عدم الإخلال بأيّ عقوبة أشدّ ينصّ عليها قانون آخر». فلا يستقيم عرضُ الأخفّ دون الأشدّ. مفاتيحُه
# في حزم الفرع تشترط عباراتٍ مركّبة («الفتنة القبلية») فتفوتها الصيغُ الطبيعية («خلافٌ قبليّ»)، ومن ثمّ هذا
# الجسرُ المباشر بمفاتيحَ مجرّدة.
_UNITY_KEYS = ("فتنه", "فتن", "قبلي", "قبليه", "القبائل", "قبيله", "طائفي", "طائفيه", "الطوائف", "مذهبي",
    "كراهيه", "ازدراء", "عنصري", "عنصريه", "التمييز العنصري", "تفوق", "عرق", "الاعراق", "نسب", "جنس",
    "الوحده الوطنيه", "خطاب الكراهيه", "الحض على الكراهيه")


def _unity_ids(blob):
    """المرسوم بقانون 19/2012 (حماية الوحدة الوطنية) — م1 الحظر، م2 العقوبات، م3 الشخص الاعتباري،
    م4 الإعفاء للمبادر بالإبلاغ. يُستحضَر متى لامس السؤالُ الفتنةَ أو الكراهيةَ أو ازدراءَ فئة."""
    if not any(_kmatch(_draft_norm_ar(k), blob) for k in _UNITY_KEYS):
        return []
    return ["legis-19-2012-m%d" % n for n in (1, 2, 3, 4)]


# محفّز قانون الإعلام المرئي والمسموع (61/2007، 21 مادة) — محايدُ الفرع. نواتُه م1 (التعاريف). وم11 فيه
# هي الطرفُ الثاني لإحالة م18 من 8/2016 (أربعةَ عشرَ محظورًا)، وعقوباتُها في م12/م13. وم5 تمنح — كنظيرتها
# م11 من المطبوعات — الطعنَ بالإلغاء أمام الدائرة الإدارية وفق 20/1981 صراحةً.
_BCAST_KEYS = ("الاعلام المرئي", "المرئي والمسموع", "الاعلام المسموع", "بث تلفزيوني", "بث اذاعي", "البث",
    "اعاده البث", "قناه فضائيه", "القنوات الفضائيه", "قناه تلفزيونيه", "محطه اذاعيه", "الاذاعه",
    "التلفزيون", "ترخيص البث", "مدير عام القناه", "المصنفات المرئيه", "التردد", "الاقمار الصناعيه",
    "قناتي", "قناته", "محطه بث", "بث فضائي", "القناه", "بثت", "تبث", "يبث", "المذيع", "البرنامج")


def _bcast_ids(blob):
    """الإعلام المرئي والمسموع (61/2007) — النواة (تعاريف م1)، ثم المحظورات والعقوبات (م11-م14) أو
    الترخيص والمدير العام والكفالة والإلغاء (م2-م10) أو الاختصاص (م17/م18). ومتى دار السؤال على رفض
    الترخيص ضُمّت م5 (الطعن) إلى نواة 20/1981، ومتى لامس الكراهيةَ ضُمّ 19/2012. محايدُ الفرع."""
    if not any(_kmatch(_draft_norm_ar(k), blob) for k in _BCAST_KEYS):
        return []
    P = "legis-61-2007-m%d"
    ids = [P % 1]

    def K(*keys):
        return any(_kmatch(_draft_norm_ar(k), blob) for k in keys)

    def rng(a, b):
        ids.extend(P % n for n in range(a, b + 1))
    adm = []
    if K("محظور", "محظورات", "يحظر", "عقوبه", "عقوبات", "غرامه", "جريمه", "يعاقب", "مصادره", "حبس",
         "الذات الالهيه", "امير البلاد", "ازدراء", "تحقير", "خدش الاداب", "بدون ترخيص", "بلا ترخيص"):
        rng(11, 14); ids += [P % 17, P % 18]
        adm += _unity_ids(blob)
    if K("النيابه العامه", "دائره الجنايات", "المحكمه المختصه", "الاختصاص", "اختصاص", "تختص", "محكمه",
         "الطعن بالتمييز"):
        ids += [P % 17, P % 18]
    if K("ترخيص", "الترخيص", "كفاله", "مدير عام", "الغاء الترخيص", "تجديد", "راس مال", "مباشره البث",
         "شروط", "التزامات"):
        rng(2, 10)
    if not ids[1:]:                                    # سؤالٌ عامّ ⇒ النواة + المحظورات + العقوبات
        rng(11, 13)
    if K("رفض", "الرفض", "رفضت", "مرفوض", "تظلم", "طعن", "الطعن", "الغاء", "الغت", "سحب", "قرار الوزير",
         "الدائره الاداريه", "القضاء الاداري"):
        adm = [P % 5] + _admin_core() + adm
    return list(dict.fromkeys(ids[:1] + adm + ids[1:]))


def _press_ids(blob):
    """المطبوعات والنشر (3/2006) — استحضارٌ مُوجَّهٌ بالموضوع: النواة (م1 الحرية، م2 التعاريف الجامعة
    للإلكتروني)، ثم المحظورات والعقوبات (م19-م28) أو تراخيص الصحيفة والطعن (م9-م18) أو تراخيص المطابع
    والمحال (م3-م7) أو الاختصاص والسقوط (م23-م25). ومتى دار السؤال على رفض/إلغاء الترخيص ضُمّت م11
    (الطعن أمام الدائرة الإدارية) إلى نواة 20/1981 — وتُصدَّر لتنجو. محايدُ الفرع."""
    if not any(_kmatch(_draft_norm_ar(k), blob) for k in _PRESS_KEYS):
        return []
    P = "legis-3-2006-m%d"
    ids = [P % 1, P % 2]

    def K(*keys):
        return any(_kmatch(_draft_norm_ar(k), blob) for k in keys)

    def rng(a, b):
        ids.extend(P % n for n in range(a, b + 1))
    adm = []
    # المحظورات والعقوبات أوّلًا (الأثقل وزنًا):
    if K("محظور", "محظورات", "يحظر", "عقوبه", "عقوبات", "غرامه", "جريمه", "يعاقب", "مصادره", "حبس",
         "الذات الالهيه", "امير البلاد", "الفتن الطائفيه", "ازدراء", "تحقير", "خدش الاداب"):
        rng(19, 22); rng(26, 28); ids += [P % 23, P % 24]   # من يحقّق ومن يحاكم — لازمُ سؤال العقوبة
        adm += _unity_ids(blob)          # العقوبةُ الأشدّ (19/2012) تُقدَّم مع المحظور لا بعده
    if K("النيابه العامه", "دائره الجنايات", "المحكمه المختصه", "الاختصاص", "اختصاص", "تختص", "محكمه",
         "سقوط الدعوى", "التقادم", "الطعن بالتمييز"):
        rng(23, 25)
    if K("ترخيص", "الترخيص", "كفاله", "رئيس التحرير", "الغاء الترخيص", "تجديد", "نقل الترخيص",
         "راس مال", "تعطيل", "ايقاف", "مراسل", "الصحف الاجنبيه"):
        rng(9, 18)
    if K("مطبعه", "المطبعه", "محل بيع", "دار نشر", "دور النشر", "ترجمه", "دعايه", "اعلان", "استيراد",
         "المطبوعات الوارده", "الطابع", "ايداع نسخه"):
        rng(3, 7)
    if K("رقابه مسبقه", "حريه الصحافه", "حريه النشر", "تعريف", "تعاريف"):
        ids += [P % 1, P % 2, P % 8]
    if not ids[2:]:                                    # سؤالٌ عامّ ⇒ النواة + المحظورات + العقوبات
        rng(19, 21); rng(26, 27)
    # جسرُ الطعن: م11 صريحةٌ في إجازته أمام الدائرة الإدارية وفق 20/1981 — تُضَمّ مع نواة القضاء الإداري.
    if K("رفض", "الرفض", "رفضت", "مرفوض", "تظلم", "طعن", "الطعن", "الغاء", "الغت", "سحب", "قرار الوزير",
         "الدائره الاداريه", "القضاء الاداري"):
        adm = [P % 11] + _admin_core()
    return list(dict.fromkeys(ids[:2] + adm + ids[2:]))


def _traffic_ids(blob):
    """قانون المرور (67/1976) — استحضارٌ مُوجَّهٌ بالموضوع (59 مادة): نواةٌ خفيفة (التعاريف م2 + مسؤولية
    المالك م30)، ثم بابُ الترخيص (م4-م14) أو رخص القيادة (م15-م24) أو قواعد المرور (م25-م32) أو العقوبات
    كاملةً (م33-م44 + الصلح م41 والسحب الإداري ونظام النقاط م42/م42مكرر) بحسب كلمات السؤال — لتنجو مجتمعةً."""
    if not any(_kmatch(_draft_norm_ar(k), blob) for k in _TRAFFIC_KEYS):
        return []
    P = "legis-67-1976-m%s"
    ids = [P % "2", P % "30"]

    def K(*keys):
        return any(_kmatch(_draft_norm_ar(k), blob) for k in keys)

    def add(*ms):
        ids.extend(P % m for m in ms)
    if K("تعريف", "تعاريف", "انواع المركبات", "الدراجه", "المقطوره", "الطريق", "المشاه", "الوزن الاقصى"):
        add("1", "2", "3")
    if K("ترخيص", "تسيير", "اجازه تسيير", "تامين", "التامين", "مؤمن", "مؤمنه", "مؤمن عليها", "سياره مؤمنه",
         "لوحات", "لوحه", "نقل الملكيه", "دفتر الترخيص", "تجديد الترخيص", "ترخيص المركبه", "ورش الاصلاح"):
        add("4", "5", "5-mukarrar", "6", "7", "8", "9", "10", "10-mukarrar", "11", "12", "13", "14")
    if K("رخصه سوق", "رخصه قياده", "رخصه القياده", "قياده", "رخصه السوق", "اختبار القياده", "تعليم القياده",
         "مدارس القياده", "تصريح تعلم", "المعلم", "رخصه دوليه"):
        add("15", "16", "17", "18", "20", "21", "22", "23", "24")
    if K("قواعد المرور", "اشاره", "الوقوف", "الانتظار", "السرعه", "اداب المرور", "حفريات", "عرقله المرور",
         "مسؤوليه المالك", "الاداب العامه في المركبه", "سباق"):
        add("25", "26", "27", "28", "29", "30", "31", "32")
    if K("عقوبه", "عقوبات", "غرامه", "مخالفه", "يعاقب", "حبس", "جريمه", "المخالفات", "الصلح", "العود",
         "القبض", "مصادره المركبه", "العقوبات البديله"):
        add("33", "33-mukarrar", "34", "35", "36", "36-mukarrar", "37", "37-mukarrar", "38", "39",
            "39-mukarrar", "40", "41", "41-mukarrar", "42", "42-mukarrar", "44")
    if K("القياده تحت تاثير", "مسكر", "مسكرات", "خمر", "سكران", "مخدرات", "مؤثرات عقليه", "ثمل", "تحت تاثير"):
        add("38", "44")
    if K("سحب الرخصه", "سحب رخصه السوق", "السحب الاداري", "نقاط المخالفات", "محكمه المرور", "الصلح",
         "العقوبات البديله", "خدمه المجتمع"):
        add("39", "39-mukarrar", "41", "42", "42-mukarrar")
    if K("حجز المركبه", "حجز المركبات", "الحجز المنزلي"):
        add("43")
    if K("المجلس الاعلى للمرور", "الاشراف على المرور", "حجيه المحاضر", "الاجهزه المختصه"):
        add("45", "45-mukarrar", "46")
    # جسرُ الشريعة العامة: التعويضُ عن حوادث المركبات يرتكز على المسؤولية التقصيرية (الفعل الضار) في
    # القانون المدني 67/1980 (م227 فما بعد) — نصٌّ عامٌّ يكمّل قانونَ المرور (تأمينُ م6 لا يحكم قدرَ التعويض):
    if K("تعويض", "المسؤوليه المدنيه", "مسؤوليه مدنيه", "مسؤوليه", "الضرر", "تعويض الحادث", "التعويض عن الحادث",
         "المتضرر من الحادث", "اصابات الحادث", "خساره الحادث", "اصابه", "عجز", "دية", "الديه"):
        # الفعل الضار العام (م227-234) + نواةُ تعويض الإصابة الجسدية في الحوادث (م247 عناصر الضرر، م248 الدية
        # الشرعية للإصابة) + التزام المؤمِّن وحلوله (م800/م801) — الشريعةُ العامة المكمّلة لتأمين المرور (م6):
        ids += ["legis-67-1980-m%d" % n for n in range(227, 235)] + \
               ["legis-67-1980-m247", "legis-67-1980-m248", "legis-67-1980-m800", "legis-67-1980-m801"]
    return list(dict.fromkeys(ids))


# محفّز الغش التجاري (20/2019): قانونٌ صغيرٌ (18 مادة) عقوباتُه (م10-م18) وتعريفاتُه/حظرُه/ضبطُه (م1-م9)
# متلازمةٌ في أيّ سؤالٍ عنه؛ فنستحضره كاملًا مبكّرًا على أيّ مصطلحٍ محوريٍّ للغش — لتنجو العقوبات والمصادرة
# والعَود من القصّ (حزمُ النطاق وحدها فوّتت العقوبات لأنّ مفاتيحها كانت عباراتٍ حرفيّةً طويلة).
_FRAUD_KEYS = ("غش تجاري", "الغش التجاري", "بضائع مغشوشه", "بضاعه مغشوشه", "بضاعه فاسده", "بضائع فاسده",
    "سلعه مغشوشه", "البضائع المغشوشه", "البضائع الفاسده", "الغش في البضاعه", "مكافحه الغش التجاري",
    "البضاعه المغشوشه", "البضاعه الفاسده")


_TRAFFICK_KEYS = ("الاتجار بالاشخاص", "اتجار بالاشخاص", "الاتجار بالبشر", "تهريب المهاجرين", "تهريب مهاجرين",
    "المجني عليه في الاتجار", "ضحايا الاتجار", "ضحيه الاتجار", "استغلال جنسي", "السخره", "الاسترقاق",
    "نزع الاعضاء", "الهجره غير المشروعه", "استغلال البشر", "الاتجار بالنساء", "الاتجار بالاطفال",
    "اتجار بالنساء", "اتجار بالبشر", "الاتجار بنساء", "الاتجار باطفال")


def _trafficking_ids(blob):
    """قانون مكافحة الاتجار بالأشخاص وتهريب المهاجرين (91/2013) كاملًا (م1-م14): التعريفات والعقوبات
    والظروف المشددة (م2/م3) والإخفاء (م4) والمصادرة (م5) والشخص الاعتباري (م6) والإعفاء (م10) والاختصاص
    (م11) وحمايةُ المجني عليهم وإيواؤهم (م12) وعدمُ النزول عن العقوبة (م13) — لتنجو مجتمعةً من القصّ."""
    if any(_kmatch(_draft_norm_ar(k), blob) for k in _TRAFFICK_KEYS):
        return ["legis-91-2013-m%d" % n for n in range(1, 15)]
    return []


# جسر جرائم الآداب/الدعارة في قانون الجزاء 16/1960 — يخدم أسئلة الآداب المستقلّة وأسئلةَ الاتجار
# بالأشخاص للاستغلال الجنسيّ معًا (فوقائع الاتجار الجنسيّ تُشكّل كذلك جرائمَ دعارةٍ في الجزاء). مواد
# مُتحقَّقة من القاعدة: الخطف للبغاء م180، هتك العرض م191/م192، الفعل الفاضح م199، والدعارة م200-م204.
_MORALITY_KEYS = ("دعاره", "الدعاره", "البغاء", "بغاء", "الفجور", "فجور", "استغلال جنسي", "الاستغلال الجنسي",
    "الحمل على الدعاره", "الاكراه على الدعاره", "الاكراه على البغاء", "القواده", "محل للدعاره",
    "استغلال البغاء", "هتك العرض", "هتك عرض", "التحريض على الدعاره", "الفعل الفاضح", "استغلال جنسي للاطفال",
    "ممارسه الفجور", "اداره محل للدعاره")


def _morality_ids(blob):
    """جرائم الآداب والدعارة في قانون الجزاء 16/1960: الخطف بقصد البغاء (م180)، هتك العرض بالإكراه ودون
    الحادية والعشرين (م191/م192)، الفعل الفاضح (م199)، والتحريض على الدعارة والحمل عليها والقوادة وإدارة
    محلّ الدعارة (م200-م204) — تُقدَّم مبكّرًا؛ وهي كذلك الوجهُ العقابيّ في الجزاء للاتجار الجنسيّ."""
    if any(_kmatch(_draft_norm_ar(k), blob) for k in _MORALITY_KEYS):
        return ["legis-16-1960-m%d" % n for n in (180, 191, 192, 199, 200, 201, 202, 203, 204)]
    return []


# محاكمة الوزراء (88/1995): قانونٌ إجرائيٌّ صغير (16 مادة + م6مكرر) متلازمُ المواد — نستحضره كاملًا مبكّرًا
# على أيّ مصطلحٍ محوريّ؛ ويشمل «م6 مكرر» (التظلّم من الحفظ) التي لا تُدرِكها حزمُ النطاق (تعجز عن «مكرر»).
_MINISTER_KEYS = ("محاكمه الوزراء", "محاكمه وزير", "محاكمه الوزير", "جرائم الوزراء", "جريمه الوزير",
    "مساءله الوزير", "مساءله الوزراء", "اتهام وزير", "لجنه تحقيق الوزراء", "المحكمه الخاصه بالوزراء",
    "جريمه ارتكبها وزير", "احاله وزير للمحاكمه", "الوزير في تاديه وظيفته")


def _minister_ids(blob):
    """قانون محاكمة الوزراء (88/1995) كاملًا: الجرائم (م2) ولجنة التحقيق (م3/م4) والتظلّم من الحفظ (م6مكرر)
    والمحكمة الخاصة والطعن بالتمييز (م8-م12) وعدم النزول/الإحالة — لتنجو مجتمعةً (م6مكرر تفوتها حزمُ النطاق)."""
    if any(_kmatch(_draft_norm_ar(k), blob) for k in _MINISTER_KEYS):
        return ["legis-88-1995-m%d" % n for n in range(1, 17)] + ["legis-88-1995-m6-mukarrar"]
    return []


# تأمين المصالح العليا للجهات العسكرية (13/2026): قانونٌ جزائيٌّ صغير (34 مادة) — حظرٌ موضوعيٌّ (السرية
# م5، دخول التنظيمات م4، المناطق المحمية م8/م11/م12) وعقوباتٌ في الفصل الخامس (م25-م32). عقوبةُ إفشاء
# الأسرار (مخالفة م5) مدفونةٌ في ذيل م25 التي تصدّرها «يخالف المواد (8)،(11)،(12)» فتبعُد دلاليًّا عن
# «إفشاء سرّ عسكريّ» وتفوتها حزمُ النطاق؛ فنستحضر الحظرَ وعقوباتِه مقترنَين مبكّرًا لتنجو م25 قطعًا.
_MILSEC_KEYS = ("المصالح العليا للجهات العسكريه", "الجهات العسكريه", "افشاء سر عسكري", "افشاء الاسرار العسكريه",
    "الاسرار العسكريه", "سر عسكري", "اسرار الدفاع", "سر من اسرار الدفاع", "الوثائق العسكريه السريه",
    "وثيقه عسكريه سريه", "منطقه عسكريه محظوره", "منطقه محميه عسكريه", "المناطق المحميه", "دخول منطقه عسكريه",
    "دخول المنشات العسكريه", "المنشات العسكريه", "تامين المنشات العسكريه", "المناطق العسكريه", "التخابر العسكري",
    "اخبار كاذبه عن الجهات العسكريه", "عقوبه افشاء الاسرار العسكريه", "اقتحام منطقه محميه")


def _milsec_ids(blob):
    """تأمين المصالح العليا للجهات العسكرية (13/2026): الحظرُ الموضوعيّ (السرية م5، دخول التنظيمات م4،
    المناطق المحمية والمناورات م8/م11/م12) مقترنًا بالفصل الخامس كاملًا (م25-م32): عقوبةُ مخالفة م5
    (حبسٌ حتى 5 سنوات + غرامة 5-10 آلاف — ذيلُ م25) وعقوبةُ المناطق المحمية (م25 صدرها)، الإشاعات الكاذبة
    (م26)، إضرار المكلّف بالمصالح (م27)، مضاعفة زمن الحرب (م28)، واختصاص النيابة العامة (م30) — لتنجو مجتمعةً."""
    if any(_kmatch(_draft_norm_ar(k), blob) for k in _MILSEC_KEYS):
        return ["legis-13-2026-m%d" % n for n in (1, 4, 5, 8, 11, 12) + tuple(range(25, 33))]
    return []


def _fraud_ids(blob):
    """النظام الموحد لمكافحة الغش التجاري (20/2019) كاملًا (م1-م18): الحظر والالتزامات والضبط + العقوبات
    (م11/م12) والمصادرة والإتلاف والنشر (م13) والشخص الاعتباري (م14) والعَود (م15)؛ مع لائحته التنفيذية
    (106/2021 — regl-20-2019): إجراءات السحب والإعلان والإتلاف وردّ القيمة والضبط والعينات — لتنجو مجتمعةً."""
    if any(_kmatch(_draft_norm_ar(k), blob) for k in _FRAUD_KEYS):
        return ["legis-20-2019-m%d" % n for n in range(1, 19)] + \
               ["regl-20-2019-m%d" % n for n in (2, 3, 4, 5, 6, 7, 10, 11, 14, 15, 16, 17, 18)]
    return []


# جسر «الجريمة الأصلية» لغسل الأموال — مستنبَطٌ من ديباجة 106/2013 التي تُعدّد قوانين الجرائم الأصلية.
# غسل الأموال يفترض جريمةً أصليةً تولّدت منها المتحصّلات؛ فمتى ذُكر الغسلُ/المتحصّلات مع نوعٍ من هذه
# الجرائم، نستحضر قانونَ تلك الجريمة الأصلية مع 106/2013 — مقيَّدًا بالمحتوى فلا ضجيج.
# (ملاحظة: ديباجة 106/2013 تسمّي قانون الأسلحة «13/1990»، والصواب المُدخَل 13/1991 — غالبًا خطأ مطبعيّ.)
_PROCEEDS_KEYS = ("غسل الاموال", "غسيل الاموال", "غسل اموال", "تبييض الاموال", "متحصلات", "المتحصلات",
    "عائدات", "الاموال المتحصله", "متحصله من جريمه", "غسل عائدات", "غسل متحصلات")
_PREDICATE_MAP = (
    (("مخدرات", "مخدر", "اتجار بالمخدرات", "تهريب مخدرات", "عائدات المخدرات", "حشيش", "هيروين", "كوكايين"),
     ["legis-159-2025-m42", "legis-159-2025-m43", "legis-159-2025-m48"]),
    (("رشوه", "فساد", "اختلاس", "المال العام", "استغلال نفوذ", "عموله للموظف", "الاستيلاء على المال العام"),
     ["legis-1-1993-m9", "legis-1-1993-m11", "legis-31-1970-m35", "legis-31-1970-m47", "legis-31-1970-m48"]),
    (("سلاح", "اسلحه", "اتجار بالسلاح", "تهريب اسلحه", "الاتجار غير المشروع بالسلاح"),
     ["legis-13-1991-m2", "legis-13-1991-m21", "legis-13-1991-m24"]),
    # جرائم الأموال الأصلية في قانون الجزاء 16/1960 (مواد مُتحقَّقة): السرقة م217/م222، النصب م231/م236،
    # خيانة الأمانة م240 — عائداتها من أكثر ما يُغسَل. تُقدَّم مواد بعينها لتنجو من قصّ حزمة 217-241 الواسعة.
    (("سرقه", "مسروقات", "سرقه بالاكراه", "نصب", "احتيال", "خيانه الامانه", "تبديد", "اساءه الائتمان",
      "استيلاء على مال", "انتزاع المال"),
     ["legis-16-1960-m217", "legis-16-1960-m222", "legis-16-1960-m231", "legis-16-1960-m236",
      "legis-16-1960-m240"]),
    # التزوير وتقليد المحرّرات (16/1960): تعريف م257، عقوبة م258، المحرّر الرسميّ/أوراق البنوك م259،
    # استعمال المحرّر المزوّر م260 — عائدات التزوير الماليّ من الجرائم الأصلية الشائعة لغسل الأموال.
    (("تزوير", "محرر مزور", "تزوير محررات", "تزييف", "تقليد اختام", "استعمال محرر مزور", "اوراق مزوره"),
     ["legis-16-1960-m257", "legis-16-1960-m258", "legis-16-1960-m259", "legis-16-1960-m260"]),
    # الاتجار بالأشخاص/تهريب المهاجرين (91/2013): عائداتها من الجرائم الأصلية لغسل الأموال (م5 مصادرة العائدات).
    (("اتجار بالاشخاص", "الاتجار بالاشخاص", "الاتجار بالبشر", "تهريب المهاجرين", "تهريب مهاجرين",
      "استغلال جنسي", "السخره", "الاسترقاق"),
     ["legis-91-2013-m2", "legis-91-2013-m3", "legis-91-2013-m5"]),
)


def _predicate_offense_ids(blob):
    """متى ذُكر غسلُ الأموال/المتحصّلات مع نوعٍ من الجرائم الأصلية (مخدرات/فساد ومال عام/أسلحة)، نستحضر
    قانونَ تلك الجريمة الأصلية — إعمالًا لشبكة ديباجة 106/2013. مقيَّدٌ بذكر الغسل فلا يُفعَّل لغيره."""
    if not any(_kmatch(_draft_norm_ar(k), blob) for k in _PROCEEDS_KEYS):
        return []
    ids = []
    for keys, arts in _PREDICATE_MAP:
        if any(_kmatch(_draft_norm_ar(k), blob) for k in keys):
            ids += arts
    return ids


# جسرٌ عكسيّ: متى نُوقشت جريمةٌ مُولِّدةٌ للمتحصّلات (مخدرات/فساد/سرقة/تزوير) مع قرينةٍ ماليّة (أرباح/
# عائدات/إخفاء أموال) دون ذكرٍ صريحٍ للغسل، نُنبّه إلى أنّ غسل تلك العائدات جريمةٌ مستقلّةٌ تحت 106/2013
# (م2 التجريم، م28 العقوبة). مُقيَّدٌ بقرينةٍ ماليّةٍ صريحةٍ فلا يُفعَّل لكلّ ذكرٍ لجريمةٍ أصلية.
_MONEY_CUE_KEYS = ("عائدات", "متحصلات", "ارباح الجريمه", "ارباح غير مشروعه", "حصيله الجريمه",
    "اخفاء الاموال", "اخفاء اموال", "تحويل الاموال", "اموال متحصله", "اموال ناتجه عن الجريمه",
    "اموال غير مشروعه", "توظيف الاموال", "تهريب الاموال")
_PREDICATE_ALL_KEYS = tuple(k for keys, _ in _PREDICATE_MAP for k in keys)


def _reverse_predicate_ids(blob):
    """الجسر العكسيّ: جريمةٌ أصليةٌ + قرينةٌ ماليّةٌ (عائدات/إخفاء أموال) ⇒ التنبيهُ إلى جريمة غسل تلك
    العائدات تحت 106/2013 (م2/م28). مُقيَّدٌ بقرينةٍ ماليّة، فلا يُفعَّل لمجرّد ذكر الجريمة الأصلية."""
    if not any(_kmatch(_draft_norm_ar(k), blob) for k in _MONEY_CUE_KEYS):
        return []
    if not any(_kmatch(_draft_norm_ar(k), blob) for k in _PREDICATE_ALL_KEYS):
        return []
    return ["legis-106-2013-m2", "legis-106-2013-m28"]


# إعمال «رسم علاقات الديباجات» في الاسترجاع: متى سمّى السؤالُ قانونًا بعينه، نستحضر ديباجاتِ القوانين
# المتّصلة به موضوعيًّا في ديباجته (وما يُستنَد إليه فيها ومَن استند إليه) — تحقيقًا لملاحظة المستخدم بأنّ
# الديباجة تكشف القوانين المتّصلة. القوانين المُدخَلة فقط، وبحدٍّ أقصى؛ والملفّ يُحمَّل مرّةً بأمانٍ تامّ.
_PREAMBLE_XREF_PATH = "/opt/LegalMind/admin/preamble_xref.json"
_INGESTED_LAWS = frozenset({
    "1/1993", "1/2016", "10/2020", "106/2013", "11/2026", "111/2015", "12/1960", "12/2015",
    "124/2019", "128/1992", "13/1991", "15/1979", "159/2025", "16/1960", "17/1960", "17/1973",
    "19/2000", "2/2016", "20/1981", "21/2015", "23/1990", "25/1996", "28/1969", "31/1970",
    "35/1978", "38/1980", "39/1980", "40/1980", "42/1964", "46/1987", "46/1989", "5/1959",
    "51/1984", "53/2001", "6/2010", "61/1976", "67/1980", "68/1980", "68/2015", "7/1961",
    "7/2010", "71/2020", "8/2010", "47/2026", "53/2026", "20/2019", "91/2013", "88/1995", "19/2012",
    "13/2026", "35/1985", "51/2026", "67/1976", "42/2014", "33/2016", "8/2016", "3/2006", "61/2007",
    "20/2014"})
_LAWREF_RE = re.compile(
    r"(?:قانون|مرسوم(?:\s+بقانون)?)\s+(?:رقم\s*)?\(?\s*([0-9٠-٩]{1,4})\s*\)?\s*لسنه\s*([0-9٠-٩]{4})"
    r"|(?<![0-9٠-٩])([0-9٠-٩]{1,4})\s*/\s*([0-9٠-٩]{4})(?![0-9٠-٩])"
    # النمط المجرّد «N لسنه YYYY» (اسمُ القانون قد يفصل «قانون» عن رقمه: «قانون المفرقعات 35 لسنة 1985»)؛
    # آمنٌ لأنّ لاحقة «لسنه YYYY» خاصّةٌ بأرقام القوانين/المراسيم لا بأرقام المواد.
    r"|(?<![0-9٠-٩])([0-9٠-٩]{1,4})\s*لسنه\s*([0-9٠-٩]{4})")
_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _load_preamble_xref():
    try:
        with open(_PREAMBLE_XREF_PATH, encoding="utf-8") as f:
            return json.load(f).get("laws", {}) or {}
    except Exception:
        return {}


_PREAMBLE_XREF = _load_preamble_xref()


def _preamble_related_ids(blob):
    """متى سمّى السؤالُ قانونًا بعينه (رقم/سنة أو N/Y)، نستحضر ديباجته وديباجاتِ القوانين المتّصلة به في
    رسم الديباجات (subject_links + cited_by) — المُدخَلة فقط، بحدٍّ أقصى 8 — لكشف الشبكة التشريعية للسؤال."""
    if not _PREAMBLE_XREF:
        return []
    ids, seen = [], set()
    for a, b, c, d, e, f in _LAWREF_RE.findall(blob):
        n, y = (a, b) if a else (c, d) if c else (e, f)
        law = "%s/%s" % (n.translate(_DIG), y.translate(_DIG))
        node = _PREAMBLE_XREF.get(law)
        if not node:
            continue
        for rel in [law] + node.get("subject_links", []) + node.get("cited_by", []):
            if rel in _INGESTED_LAWS and rel not in seen:
                seen.add(rel)
                nn, yy = rel.split("/")
                ids.append("legis-%s-%s-preamble" % (nn, yy))
            if len(ids) >= 8:
                return ids
    return ids


def _draft_bundles(request_type, facts, subqueries, madhab, branch=None):
    """غلافٌ: حِزم الفرع (النواة الحاكمة) ثم طبقةُ «رسم الديباجات» — ديباجاتُ القوانين المتّصلة بأيّ
    قانونٍ سمّاه السؤالُ صراحةً — تُلحَق أخيرًا (سياقٌ داعمٌ لا يزاحم النواة). قراءةٌ فقط، غير مُخلٍّ بالترتيب."""
    ids = _draft_bundles_inner(request_type, facts, subqueries, madhab, branch)
    _blob = _draft_norm_ar(
        (request_type or "") + " " + (facts or "") + " " + " ".join(subqueries or []))
    # قوانينُ محايدةُ الفرع (أسئلتها تتوزّع فروعًا) تُستحضَر هنا في الغلاف بصرف النظر عن فرع المصنّف:
    # المرور 67/1976 (جزائي/مدني/إداري)، وحماية البيئة 42/2014، والبلدية 33/2016، والإعلام الإلكتروني 8/2016.
    tr = (_traffic_ids(_blob) + _environment_ids(_blob) + _municipality_ids(_blob)
          + _emedia_ids(_blob) + _press_ids(_blob) + _bcast_ids(_blob) + _penal_ids(_blob)
          + _realty_ids(_blob) + _etrx_ids(_blob) + _tender_ids(_blob) + _venue_ids(_blob))
    rel = _preamble_related_ids(_blob)
    # «الخاصُّ يقيّد العامّ» — ترتيبًا لا حكمًا فحسب: متى نطق محفّزٌ متخصّص (وبواباتُه ضيّقة، فنطقُه يعني أنّ
    # السؤال منعقدٌ على قانونه) تصدّرت موادُّه النواةَ العامّة للفرع. وإلّا ابتلعت النواةُ العامّة (الإجراءات
    # الجزائية 17/1960 مثلًا) نافذةَ الدرجة العالية كاملةً، فتهبط موادُّ القانون الخاصّ ولوائحه وجسورُه إلى
    # درجة الصفر وتُقتطع عند امتلاء ميزانية السياق — وهو ما رصدناه فعلًا: 18 معرّفًا عامًّا في الصدارة و20/1981
    # في الترتيب 104. الديباجاتُ المتّصلة تبقى في الذيل (سياقٌ داعمٌ لا يزاحم).
    if tr:
        return list(dict.fromkeys(tr + list(ids) + rel))
    return list(dict.fromkeys(list(ids) + rel)) if rel else ids


def _draft_bundles_inner(request_type, facts, subqueries, madhab, branch=None):
    """معرّفات المواد الحاكمة حسب كلمات الطلب والمذهب/الفرع + نواة إجرائية دائمة.
    الأحوال الشخصية: حزم أسرية (سنّي 51/1984، جعفري 124/2019، إجرائي 12/2015).
    المدني/التجاري: حزم القانون المدني والتجاري والشركات وغيرها.
    كل الفروع (عدا الجزائي): تُضاف نواة المرافعات. الجزائي: نواة الإجراءات الجزائية.
    الفرع يُحسم أولًا بالمصنّف المحتوائيّ (يملؤه عند غيابه، ويصحّح الوسم عند تعارضٍ قاطع)."""
    _blob0 = _draft_norm_ar(
        (request_type or "") + " " + (facts or "") + " " + " ".join(subqueries or []))
    branch = _resolve_branch(branch, _blob0)           # ← التصنيف المحتوائيّ التلقائيّ لكل الفروع
    _nb = _draft_norm_ar(branch or "")               # جزائي⇒جزايي، جنائي⇒جنايي بعد التطبيع
    is_penal = any(k in _nb for k in ("جزاي", "جزاء", "جناي", "عقوبات"))
    # كشف فرع العمل: «عمل/عمال/منزلي» بعد التطبيع (لأن «العمالة المنزلية» لا تحوي «عمل» متّصلة)،
    # أو استدلالًا من محتوى الطلب عند غياب الفرع أو عدم تحديده — لمنع تفويت نواة الاختصاص.
    # الفرع الجزائي يُحسم أولًا وله الأولوية المطلقة: جرائم الرشوة/الاختلاس/جرائم الموظفين تذكر
    # «الموظف العام» فتخدع كواشفَ الخدمة المدنية/الإداري فتختطف الطلب. متى وُسم الفرع «جزائي»
    # نُرجع حِزم النواة الجزائية الموضوعية (16/1960 + المعدِّل 31/1970) + النواة الإجرائية (17/1960).
    if is_penal:
        blob = _blob0
        ids = []
        ids += _famviol_ids(blob)                        # 11/2026 الحاكمة (12 مادة) — أولًا لتنجو
        ids += _nexus_bridge(blob, madhab, is_penal)     # الجسر: نواة الضرب + آثار أسرية للعنف/الطفل
        ids += _juvenile_penalty_ids(blob)               # عقوبات الأحداث عند «حدث + جريمة» — لتنجو مبكّرًا
        ids += _settlement_ids(blob)                      # قاعدة الصلح/التنازل العامة (17/1960 م238-243) — لتنجو
        ids += _juv_publication_ids(blob)                 # حظر نشر اسم/صورة الحدث وعقوبته (111/2015 م67) — لتنجو
        ids += _weapons_ids(blob)                          # الأسلحة 13/1991 شاملةً مواد المكرر العقابية — لتنجو
        ids += _publicfunds_ids(blob)                      # جرائم المال العام 1/1993 + عدم التقادم (م21 مكرر) — لتنجو
        ids += _drugs_ids(blob)                             # جرائم المخدرات 159/2025 (عقوبات/علاج/مصادرة/عدم تقادم) — لتنجو
        ids += _prescription_ids(blob)                      # مدد التقادم العامة (16/1960 م3-م10) — لكل الفروع الجزائية
        ids += _aml_ids(blob)                                # غسل الأموال/تمويل الإرهاب 106/2013 (جرائم/عقوبات/مصادرة) — لتنجو
        ids += _aml_bank_ids(blob)                           # التزامات المؤسسات المالية + حظر إفصاح التنبيه (م5-م15/م34-م36) — للامتثال
        ids += _terrorism_ids(blob)                          # جرائم الإرهاب 47/2026 (نواة + جسر تمويل الإرهاب ⇄ 106/2013) — لتنجو
        ids += _explosives_ids(blob)                          # جرائم المفرقعات 35/1985 كاملًا (م1-م11) + جسر الإرهاب عند إشاعة الذعر — لتنجو
        ids += _statesec_court_ids(blob)                      # تخصيص الدوائر الجزائية 51/2026 (م1-م7) لجرائم أمن الدولة/الإرهاب + جسر 47/2026 — لتنجو
        # (قانون المرور 67/1976 يُستحضَر في الغلاف _draft_bundles محايدَ الفرع — لا هنا — لأنّ أسئلته تتوزّع فروعًا)
        ids += _fraud_ids(blob)                               # الغش التجاري 20/2019 كاملًا + لائحته 106/2021 (العقوبات/الإجراءات) — لتنجو
        ids += _trafficking_ids(blob)                         # الاتجار بالأشخاص 91/2013 كاملًا (م1-م14 بحماية المجني عليهم م12) — لتنجو
        ids += _morality_ids(blob)                            # جرائم الآداب/الدعارة 16/1960 (م180/م191-م204) — للآداب واستغلال الاتجار الجنسيّ
        ids += _minister_ids(blob)                            # محاكمة الوزراء 88/1995 كاملًا (م1-م16 + م6مكرر التظلّم) — لتنجو
        ids += _milsec_ids(blob)                              # المصالح العليا للجهات العسكرية 13/2026: الحظر (م4/م5/م8/م11/م12) + العقوبات (م25-م32) — لتنجو م25 (عقوبة إفشاء م5)
        ids += _predicate_offense_ids(blob)                  # جسر الجريمة الأصلية (ديباجة 106/2013): غسل ⇄ مخدرات/فساد/سلاح/سرقة/نصب/تزوير
        ids += _reverse_predicate_ids(blob)                  # جسرٌ عكسيّ: جريمة أصلية + قرينة ماليّة ⇒ التنبيه لجريمة غسل عائداتها (106 م2/م28)
        for _name, keys, pref, a, b in _PENAL_BUNDLES:
            if any(_draft_norm_ar(k) in blob for k in keys):
                nums = range(a, min(b, a + 29) + 1)      # حدّ أقصى 30 مادة لكل حزمة
                ids.extend("%s-m%d" % (pref, n) for n in nums)
        ids += _procedural_core(is_penal)                # نواة الإجراءات الجزائية
        return list(dict.fromkeys(ids))
    _is_labor = any(k in _nb for k in ("عمل", "عمال", "منزلي")) and "احوال" not in _nb
    # تجاوز تصنيف الفرع عند محتوى عمالة منزلية لا لبس فيه («منزلي» + سياق عمالي):
    # قد يصل الطلب موسومًا بفرع خاطئ (مثلًا «أحوال شخصية» افتراضيًّا) رغم أن الوقائع
    # منازعة عمالة منزلية — فيَجُبّ المحتوى الصريح الوسمَ الخاطئ لئلا تُفوَّت نصوص القانون.
    _dom_labor = ("منزلي" in _blob0) and any(
        k in _blob0 for k in ("عامل", "عامله", "استقدام", "صاحب العمل", "خادم"))
    if _dom_labor:
        _is_labor = True
    # تجاوز محتوى العمل العام (غير المنزلي): كثيرًا ما يصل الطلب موسومًا بفرع افتراضي خاطئ
    # («أحوال شخصية») رغم أنّ الوقائع منازعة عمل في القطاع الأهلي — فتُفوَّت نواة الاختصاص
    # والنصوص الإجرائية. نكتفي بمصطلحات عمّالية صريحة نادرة في غير سياق العمل، ولا نُفعّله
    # متى وُسم الطلب صراحةً «مدني/تجاري» (لهما مسارهما) أو كان محتواه منزليًّا.
    _gen_labor = (
        ("منزلي" not in _blob0)
        and not (branch and ("مدني" in branch or "تجاري" in branch))
        and any(k in _blob0 for k in (
            "صاحب العمل", "عقد العمل", "مكافاه نهايه الخدمه", "نهايه الخدمه",
            "القطاع الاهلي", "قطاع الاهلي", "قانون العمل", "الفصل التعسفي",
            "فصل تعسفي", "اصابه عمل", "اصابه العمل", "المرض المهني",
            "تصريح عمل", "اذن عمل", "اجازه مرضيه", "العماله الوافده",
            "عمال النفط", "الاعمال النفطيه", "عامل نفط")))
    if _gen_labor:
        _is_labor = True
    # الفرع الإداري — قانون حقوق الأشخاص ذوي الإعاقة 8/2010 (النص الخاص لمسائل الإعاقة).
    # يُفعَّل بوسم الفرع «إداري» أو بمحتوى إعاقة صريح يَجُبّ الوسم الخاطئ (كما في العمل)،
    # ويُقدَّم على مسار العمل متى كان المحتوى عن الإعاقة (لأنه النص الخاص).
    _disab = any(k in _blob0 for k in (
        "ذوي الاعاقه", "ذو الاعاقه", "الاشخاص ذوي الاعاقه", "الاعاقه", "المعاق",
        "بطاقه اعاقه", "معاش اعاقه", "الهيئه العامه لشوون ذوي الاعاقه"))
    if _disab:
        _is_labor = False                              # الإعاقة نصّها الخاص 8/2010
        blob = _blob0
        ids = []
        for _name, keys, sfx in _DISABILITY_BUNDLES:
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-8-2010-" + s for s in sfx)
        if not ids:                                    # محتوى إعاقة دون كلمة مفتاحية دقيقة
            ids.extend("legis-8-2010-" + s for s in ("m1", "m2", "m28", "m37"))
        # التأمينات الاجتماعية 61/1976 — معاش الإعاقة يحيل إليها (م41/42 من 8/2010)
        for _name, keys, sfx in _SOCINS_BUNDLES:
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-61-1976-" + s for s in sfx)
        for _name, keys, sfx in _SUPINS_BUNDLES:      # التأمين التكميلي 128/1992
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-128-1992-" + s for s in sfx)
        ids += _admin_core()                           # منازعات الإعاقة أمام الدائرة الإدارية
        ids += _procedural_core(is_penal)              # نواة المرافعات تسري تكميليًّا
        return list(dict.fromkeys(ids))
    # الفرع الإداري العام — القضاء الإداري (20/1981) + الخدمة المدنية (15/1979). يُفعَّل بوسم
    # الفرع «إداري» أو بمحتوى إداري/خدمة مدنية صريح يَجُبّ الوسم الخاطئ. النواة الإدارية دائمة،
    # وتُضاف حِزم الخدمة المدنية بحسب الكلمات المفتاحية.
    _admin_content = any(k in _blob0 for k in (
        "قرار اداري", "الغاء القرار", "دعوى الالغاء", "المنازعات الاداريه",
        "الطعن بالالغاء", "الدائره الاداريه", "القضاء الاداري", "قرار الجهه الاداريه",
        "تظلم اداري", "دعوى التعويض الاداري"))
    _civserv = any(k in _blob0 for k in (
        "خدمه المدنيه", "ديوان الخدمه", "مجلس الخدمه", "موظف حكومي", "الموظف الحكومي",
        "موظف عام", "الموظف العام", "وظيفه عامه", "وظيفه حكوميه", "قانون الخدمه المدنيه",
        "وظائف قياديه", "احاله للتقاعد", "احاله الى التقاعد", "عقوبه تاديبيه",
        "مجلس تاديبي", "وقف عن العمل", "اجازه دوريه", "ترقيه"))
    # التأمينات الاجتماعية 61/1976 — عابر للفروع؛ منازعاته إدارية (المؤسسة العامة للتأمينات)
    _socins = any(k in _blob0 for k in (
        "التامينات الاجتماعيه", "المؤسسه العامه للتامينات", "معاش تقاعدي", "المعاش التقاعدي",
        "معاش الشيخوخه", "معاش العجز", "معاش الوفاه", "معاش الاصابه", "الاستبدال",
        "مكافاه التقاعد", "المؤمن عليه", "اشتراكات التامين", "معاش",
        "التامين التكميلي", "المعاش التكميلي", "معاش تكميلي", "تكميلي"))
    # عنقود تنظيم منظومة العدالة (تحقيقات/قضاء/فتوى/محاماة) — إداري تنظيمي
    _justorg = any(_draft_norm_ar(k) in _blob0 for k in (
        "الادارة العامة للتحقيقات", "التحقيقات بوزارة الداخلية", "محقق", "المحقق",
        "مدعي عام", "رئيس تحقيق", "الادعاء العام", "عضو الادعاء", "مجلس تأديب التحقيقات",
        # قانون تنظيم القضاء 23/1990 — مصطلحات تنظيمية خاصّة (لا «المحكمة/القاضي» المجرّدة)
        "تنظيم القضاء", "مجلس القضاء الأعلى", "تعيين القضاة", "ترقية القضاة", "تأديب القضاة",
        "تأديب القاضي", "عدم قابلية القضاة للعزل", "استقلال القضاء", "التفتيش القضائي",
        "أعضاء النيابة العامة", "تشكيل النيابة العامة", "درجات القضاة", "شؤون القضاة",
        "المعهد القضائي", "نادي القضاة",
        # إدارة الفتوى والتشريع 12/1960
        "إدارة الفتوى والتشريع", "الفتوى والتشريع", "تمثيل الحكومة أمام القضاء",
        "المستشار القانوني للحكومة",
        # قانون التوثيق 10/2020 — مصطلحات تنظيمية خاصّة بأعمال التوثيق
        "التوثيق", "الموثق", "إدارة التوثيق", "الموثق الحكومي", "الموثق الأهلي",
        "توثيق الوكالات", "توثيق الوكاله", "تصديق التوقيعات", "الصيغة التنفيذية", "المحرر الموثق",
        "موثق حكومي", "موثق اهلي", "وكاله غير محدده المده",
        # قانون تنظيم مهنة المحاماة 42/1964 — جذور خاصّة بالمهنة (نتجنّب «المحامي» المجرّدة)
        "المحاماه", "مهنه المحاماه", "جدول المحامين", "تاديب المحامي", "اتعاب المحامي",
        "المحامي تحت التمرين", "لجنه قبول المحامين", "المحامي المشتغل", "قيد المحامي"))
    # «محام» + سياق مهني/تأديبي/أتعاب = قانون المحاماة 42/1964 (نتجنّب «محام» المجرّدة وحدها)
    _justorg = _justorg or ("محام" in _blob0 and any(
        k in _blob0 for k in ("تاديب", "اتعاب", "قيد", "جدول", "تمرين", "مزاوله",
                              "انتحال", "المهنه", "جمعيه المحامين", "نقابه", "التحقيق مع محام")))
    # قانون تنظيم الخبرة 40/1980 — جذور خاصّة + مُطلِق مركّب («خبير» + سياق خبرة قضائية)
    _justorg = _justorg or any(_draft_norm_ar(k) in _blob0 for k in (
        "خبراء الجدول", "الاداره العامه للخبراء", "ندب خبير", "ندب الخبير", "تاديب الخبير",
        "اتعاب الخبير", "خبير قضائي", "قيد الخبير", "ماموريه الخبير", "قانون تنظيم الخبره",
        "رد الخبير", "الخبير المنتدب", "تقرير الخبير"))
    _justorg = _justorg or ("خبير" in _blob0 and any(
        k in _blob0 for k in ("ندب", "تاديب", "جدول", "اتعاب", "قضائي", "يمين", "قيد",
                              "مامور", "الاداره العامه للخبراء", "امانه", "تقرير")))
    # وكالة (بأي وصف بينها) + «غير محددة المدة» = مفهوم القاعدة الخمسية في قانون التوثيق 10/2020
    _justorg = _justorg or ("وكاله" in _blob0 and "غير محدده المده" in _blob0)
    # تجاوز الوسم العمّالي عند محتوى خدمة مدنية صريح: الموظف الحكومي يخضع لـ15/1979 لا 6/2010.
    # نستعمل جذورًا بلا «ال» لتطابق الصيغتين (بـ«ال» وبدونها) بعد التطبيع.
    if _is_labor and any(k in _blob0 for k in (
            "خدمه المدنيه", "ديوان الخدمه", "مجلس الخدمه", "موظف حكومي",
            "الموظف الحكومي", "احاله للتقاعد", "احاله الى التقاعد", "القضاء الاداري")):
        _is_labor = False
    # لا يُختطَف الطلب الجزائي إلى المسار الإداري: جرائم الرشوة/الاختلاس تذكر «الموظف العام» فيتوهّم
    # كاشفُ الخدمة المدنية أنه طلبٌ إداريّ فيرجع مبكّرًا قبل حزم الجزاء. وسمُ الفرع «جزائي» يَجُبّ ذلك.
    if (not _is_labor) and (not is_penal) and (("اداري" in _nb) or _admin_content or _civserv or _socins or _justorg):
        blob = _blob0
        ids = _admin_core()
        for _name, keys, sfx in _CIVSERVICE_BUNDLES:
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-15-1979-" + s for s in sfx)
        # اللائحة التنفيذية التفصيلية (نظام الخدمة المدنية 1979) — تكمّل القانون 15/1979
        for _name, keys, sfx in _NSM_BUNDLES:
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-nsm-1979-" + s for s in sfx)
        # قانون التأمينات الاجتماعية 61/1976 — المعاشات وإصابات العمل والاستبدال
        for _name, keys, sfx in _SOCINS_BUNDLES:
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-61-1976-" + s for s in sfx)
        for _name, keys, sfx in _SUPINS_BUNDLES:      # التأمين التكميلي 128/1992
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-128-1992-" + s for s in sfx)
        # عنقود تنظيم منظومة العدالة (المعرّفات كاملة داخل الحزمة)
        for _name, keys, sfx in _JUSTORG_BUNDLES:
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend(sfx)
        if _civserv and not any(x.startswith("legis-15-1979-") for x in ids):
            ids += ["legis-15-1979-" + s for s in ("m1", "m2", "m15", "m28", "m32")]
            ids += ["legis-nsm-1979-" + s for s in ("m1", "m55", "m60", "m71")]
        ids += _procedural_core(is_penal)
        return list(dict.fromkeys(ids))
    if (not _is_labor) and branch and ("مدني" in branch or "تجاري" in branch) and "أحوال" not in branch:
        blob = _draft_norm_ar(
            (request_type or "") + " " + (facts or "") + " " + " ".join(subqueries or []))
        ids = []
        for _name, keys, a, b in _CIVIL_BUNDLES:
            if any(_draft_norm_ar(k) in blob for k in keys):
                nums = range(a, min(b, a + 29) + 1)          # حدّ أقصى 30 مادة لكل حزمة
                ids.extend("legis-67-1980-m%d" % n for n in nums)
        for _name, keys, a, b in _EVIDENCE_BUNDLES:          # الإثبات 39/1980
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-39-1980-m%d" % n for n in range(a, b + 1))
        for _name, keys, a, b in _PROCEDURE_BUNDLES:         # المرافعات 38/1980
            if any(_draft_norm_ar(k) in blob for k in keys):
                nums = range(a, min(b, a + 29) + 1)          # حدّ أقصى 30 مادة لكل حزمة
                ids.extend("legis-38-1980-m%d" % n for n in nums)
        for _name, keys, a, b in _FEES_BUNDLES:              # الرسوم القضائية 17/1973
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-17-1973-m%d" % n for n in range(a, b + 1))
        for _name, keys, a, b in _SMALLCLAIMS_BUNDLES:       # الدعاوى قليلة القيمة 46/1989
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-46-1989-m%d" % n for n in range(a, b + 1))
        for _name, keys, a, b in _GOVFEE_BUNDLES:            # إعفاء الحكومة من الرسوم 7/1961
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-7-1961-m%d" % n for n in range(a, b + 1))
        for _name, keys, sfx in _LEASE_BUNDLES:              # إيجار العقارات 35/1978
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-35-1978-" + s for s in sfx)
        for _name, keys, sfx in _REGISTRATION_BUNDLES:       # التسجيل العقاري 5/1959
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-5-1959-" + s for s in sfx)
        for _name, keys, a, b in _COMMERCE_BUNDLES:          # التجارة 68/1980
            if any(_draft_norm_ar(k) in blob for k in keys):
                nums = range(a, min(b, a + 29) + 1)          # حدّ أقصى 30 مادة لكل حزمة
                ids.extend("legis-68-1980-m%d" % n for n in nums)
        for _name, keys, a, b in _COMPANIES_BUNDLES:         # الشركات 1/2016
            if any(_draft_norm_ar(k) in blob for k in keys):
                nums = range(a, min(b, a + 29) + 1)          # حدّ أقصى 30 مادة لكل حزمة
                ids.extend("legis-1-2016-m%d" % n for n in nums)
        for _name, keys, a, b in _BANKRUPTCY_BUNDLES:        # الإفلاس 71/2020
            if any(_draft_norm_ar(k) in blob for k in keys):
                nums = range(a, min(b, a + 29) + 1)          # حدّ أقصى 30 مادة لكل حزمة
                ids.extend("legis-71-2020-m%d" % n for n in nums)
        for _name, keys, a, b in _CAPMARKETS_BUNDLES:        # هيئة أسواق المال 7/2010
            if any(_draft_norm_ar(k) in blob for k in keys):
                nums = range(a, min(b, a + 29) + 1)          # حدّ أقصى 30 مادة لكل حزمة
                ids.extend("legis-7-2010-m%d" % n for n in nums)
        for _name, keys, sfx in _CAPMARKETS_DEF_BUNDLES:     # تعريفات لائحة أسواق المال (ك1)
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("lreg-7-2010-" + s for s in sfx)
        for _name, keys, sfx in _CMAREG2_BUNDLES:            # كتاب هيئة أسواق المال (ك2)
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("lreg-7-2010-" + s for s in sfx)
        for _name, keys, sfx in _CMAREG3_BUNDLES:            # كتاب إنفاذ القانون (ك3)
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("lreg-7-2010-" + s for s in sfx)
        for _name, keys, sfx in _CMAREG4_BUNDLES:            # كتاب البورصات ووكالات المقاصة (ك4)
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("lreg-7-2010-" + s for s in sfx)
        ids += _civil_umbrella()                     # المظلّة المدنية (نظرية العقد والالتزام)
        ids += _procedural_core(is_penal)            # نواة المرافعات (أو الجزائية) دائمًا
        return ids
    if _is_labor:
        # فرع العمل — نُوى الاختصاص الدائمة أولًا، ثم الحِزم الموضوعية، ثم نواة المرافعات.
        # ترتيب المقدّمة مقصود: المستهلك يُدرج معرّفات الحِزم بدرجة تطابق صفرية بعد نتائج
        # المتجه، ثم يقصّ الذيل حسب ميزانية السياق (CTX_BUDGET). فالنصوص الموضوعية
        # (كمكافأة نهاية الخدمة) تُستحضَر أصلًا عبر بحث المتجه بدرجات عالية فتتصدّر، أمّا
        # النُوى الإجرائية/الاختصاصية فبعيدة دلاليًّا ولا يجلبها المتجه — لذا تُوضَع في
        # مقدّمة قائمة الحِزم لتضمن نجاتها من القصّ ولا تُنفى نصوصها.
        blob = _blob0
        _general_labor = ("منزلي" not in blob) and (not _dom_labor)
        ids = []
        # (1) النواة الإجرائية العمّالية العامة (6/2010) لطلبات العمل غير المنزلية:
        # م144 تقادم الدعوى بسنة والإعفاء من الرسوم القضائية ونظرها على وجه الاستعجال،
        # م145 امتياز حقوق العمال على أموال صاحب العمل، م146 وجوب سبق الطلب لإدارة العمل
        # ثم الإحالة للمحكمة الكلية خلال شهر وتعويض التأخير 1% شهريًّا، م147 تحديد الجلسة.
        if _general_labor:
            ids += ["legis-6-2010-m144", "legis-6-2010-m145",
                    "legis-6-2010-m146", "legis-6-2010-m147"]
        # (2) نواة الاختصاص العمالية الدائمة: اختصاص الإدارة ثم المحكمة (م31) والدائرة
        # العمالية (م35) والإعفاء من الرسوم (م36) ومواعيد الجلسة (م37) من 68/2015، مع
        # المرسوم 46/1987 المُنشئ للدائرة العمالية بالمحكمة الكلية والمختص دون غيره
        # بالمنازعات العمالية «أياً كانت قيمتها» (م1) واستئنافها (م2) والإحالة بلا رسوم (م3).
        ids += ["legis-68-2015-m%s" % n for n in ("31", "35", "36", "37")]
        ids += ["legis-46-1987-m1", "legis-46-1987-m2", "legis-46-1987-m3"]
        # (3) الحِزم الموضوعية بحسب الكلمات المفتاحية
        for _name, keys, sfx in _LABOR_BUNDLES:
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-68-2015-" + s for s in sfx)
        for _name, keys, sfx in _LABOR19_BUNDLES:      # 19/2000 دعم العمالة الوطنية
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-19-2000-" + s for s in sfx)
        if _general_labor:                             # 6/2010 القانون العام (غير المنزلي)
            for _name, keys, sfx in _LAB4_BUNDLES:
                if any(_draft_norm_ar(k) in blob for k in keys):
                    ids.extend("legis-6-2010-" + s for s in sfx)
            # القطاع النفطي — 28/1969 (قانون قطاعي خاص يكمّله العام 6/2010): بوابة «النفط»
            if any(_draft_norm_ar(k) in blob for k in (
                    "النفط", "نفطيه", "نفطي", "الغاز الطبيعي", "بترول")):
                for _name, keys, sfx in _LAB5_BUNDLES:
                    if any(_draft_norm_ar(k) in blob for k in keys):
                        ids.extend("legis-28-1969-" + s for s in sfx)
        # التأمينات الاجتماعية 61/1976 — تكميليًّا للعامل عند مساس الإصابة/المعاش/التقاعد
        for _name, keys, sfx in _SOCINS_BUNDLES:
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-61-1976-" + s for s in sfx)
        for _name, keys, sfx in _SUPINS_BUNDLES:      # التأمين التكميلي 128/1992
            if any(_draft_norm_ar(k) in blob for k in keys):
                ids.extend("legis-128-1992-" + s for s in sfx)
        ids += _procedural_core(is_penal)              # نواة المرافعات تسري تكميليًّا
        return list(dict.fromkeys(ids))                # إزالة التكرار مع حفظ الترتيب
    if branch and "أحوال" not in branch:
        # مجالات أخرى (إداري…) بلا حِزم موضوعية بعد — تبقى النواة الإجرائية
        return _procedural_core(is_penal)
    is_jaafari = bool(madhab and "جعفر" in madhab)
    madhab_set = bool((madhab or "").strip())     # هل حُدِّد المذهب؟ إن لم يُحدَّد نستحضر المذهبين معًا
    blob = _draft_norm_ar(
        (request_type or "") + " " + (facts or "") + " " + " ".join(subqueries or []))
    ids = []
    ids += _nexus_bridge(blob, madhab, is_penal)  # الجسر: جرائم الاعتداء الجزائية (16/1960) عند العنف/الطفل — أولًا لتنجو
    ids += _famviol_ids(blob)     # الحماية من العنف الأسري 11/2026
    ids += _childrights_ids(blob)  # حقوق الطفل 21/2015 (مزدوج: يُستحضَر في الأحوال أيضًا)
    for _name, keys, prefix, nums, scope in _DRAFT_BUNDLES:
        if scope == "sunni" and madhab_set and is_jaafari:
            continue                              # 51/1984 تُستبعَد فقط متى حُدِّد المذهب الجعفري صراحةً
        if scope == "jaafari" and madhab_set and not is_jaafari:
            continue                              # 124/2019 تُستبعَد فقط متى حُدِّد مذهبٌ غير الجعفري
        if any(_draft_norm_ar(k) in blob for k in keys):
            ids.extend("%s-m%d" % (prefix, n) for n in nums)
    ids += _civil_umbrella()                          # الأحوال الشخصية من القانون الخاص: المظلّة المدنية
    ids += _procedural_core(is_penal)                # والمرافعات تسري تكميليًّا
    return ids

_DRAFT_SYSTEM = """أنت المساعد القانوني لنظام LegalMind — نظام تشغيل قانوني للمحامي الكويتي.

مهمتك تنفيذ طلبات المحامي: صياغة (صحيفة دعوى، مذكرة دفاع أول درجة/استئناف/تمييز، أمر أداء، تظلم من أمر على عريضة، أي طلب قضائي) أو استشارة قانونية.

قواعد ملزمة:
1. اعتمد حصريًا على المصادر المرفقة داخل <السياق> — تشريعات ومبادئ قضائية وأحكام ونماذج من قاعدة معرفة النظام. لا تستشهد بمادة أو طعن غير موجود في السياق، ولا تختلق أرقام مواد أو طعون أو نصوصًا.
2. إن لم تكفِ المصادر للإجابة الموثقة قل صراحة: «لا توجد في المصادر المرفوعة أدلة كافية لإجابة موثقة عن هذه المسألة» وحدد ما ينقص، ثم قدّم ما يمكن تقديمه بحذر مع وسمه بوضوح أنه خارج المصادر.
3. ميّز بين المذهبين: السنّي يحكمه قانون الأحوال الشخصية 51/1984، والجعفري قانون 124/2019. الإجراءات يحكمها قانون محكمة الأسرة 12/2015 (المعدل) ومرسوم بقانون 53/2026 لدعاوى النسب وتصحيح الأسماء.
4. انتبه للإجراءات السابقة الوجوبية متى ظهرت في السياق — مثل المرور بمركز تسوية المنازعات الأسرية قبل دعاوى الطلاق والتطليق (م9 ق12/2015)، ولجنة دعاوى النسب قبل دعوى النسب، وقواعد التحكيم في التفريق للضرر (م127-132 ق51/1984)، والمواعيد.
5. النماذج المرفقة مرجع صياغة وهيكل فقط (غير قابلة للاستشهاد كسلطة). اتبع شكلها الكويتي في الصياغة.
6. القانون المدني (67/1980) هو الشريعة العامة والمظلّة الكبرى للقانون الخاص بكل فروعه (تجاري، شركات، إيجار، والأحوال الشخصية في جوانبها المالية والالتزامية): متى خلا القانون الخاص الحاكم للمسألة من نصٍّ يغطّيها، فارجع إلى القواعد العامة في القانون المدني — نظرية الالتزام والعقد (التكوين، الآثار، البطلان، الفسخ، التنفيذ، الانقضاء) — لسدّ الفراغ، واذكر صراحةً أنّ الأساس مدنيّ تطبيقًا تكميليًّا (م2 من قانون التجارة تقضي بسريان القواعد المدنية على المسائل التجارية عند غياب نصٍّ تجاري). أما في الأحوال الشخصية فيُقدَّم النصّ الخاص (51/1984 سنّي، 124/2019 جعفري) ثم المذهب، وتبقى القواعد المدنية العامة سندًا تكميليًّا في المسائل المالية دون العبادات والأحكام الأسرية الصرفة. ولا يسري ذلك على الجزائي.
7. الترتيب في الاستدلال: النصّ الخاص أولًا، فإن سكت فالقواعد العامة في القانون المدني، مع الإشارة لكلٍّ منهما بوضوح.

بنية الإجابة (التزم بها بعناوين ماركداون):
# أولًا: الفحص الإجرائي المسبق
(الإجراءات الوجوبية قبل الرفع/التقديم، الاختصاص، المواعيد — بالاستناد للمواد)
# ثانيًا: سيناريو النجاح والفشل
(سيناريو النجاح، سيناريوهات الفشل/التعثر، ثم مواطن القوة ومواطن الضعف)
# ثالثًا: التنفيذ
(الصياغة الكاملة بالشكل الكويتي مع عناصر نائبة [ … ] للبيانات الشخصية، أو الاستشارة الكاملة — مع الاستشهاد بالمواد والمبادئ من السياق)

اكتب بعربية قانونية فصيحة. البيانات الشخصية في الصياغة تكون عناصر نائبة بين معقوفات."""

class _DraftAttach(_DraftBase):
    kind: str            # image | pdf | text
    media_type: _DraftOpt[str] = None   # image/jpeg, image/png, application/pdf
    data: _DraftOpt[str] = None         # base64 (للصورة/PDF)
    text: _DraftOpt[str] = None         # نص مستخرج (للنص)
    name: _DraftOpt[str] = None

class _DraftIn(_DraftBase):
    request_type: str
    facts: str
    madhab: _DraftOpt[str] = None
    branch: _DraftOpt[str] = None
    attachment: _DraftOpt[_DraftAttach] = None

@app.post("/api/draft")
def draft_endpoint(inp: _DraftIn, _: str = Depends(require_auth)) -> dict:
    facts = (inp.facts or "").strip()
    if not facts:
        raise HTTPException(400, "الوقائع مطلوبة")
    key = _draft_env("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(500, "ANTHROPIC_API_KEY غير مضبوط في /opt/LegalMind/deploy/.env")
    import anthropic
    client = anthropic.Anthropic(api_key=key)

    query = inp.request_type + " - " + facts[:1500]
    if inp.madhab:
        query += " (مذهب " + inp.madhab + ")"
    subqueries = _draft_subqueries(client, inp.request_type, facts, inp.madhab)
    vectors = _draft_embed_multi([query] + subqueries)

    # الاستعلام الكامل: كل الأنواع؛ كل محور فرعي: تشريعات ومبادئ
    plans = [(vectors[0], [
        (["legislation_article", "legislation_issuing_article"], 8, "تشريع"),
        (["judicial_principle"], 8, "مبدأ قضائي"),
        (["full_judgment"], 2, "حكم كامل"),
        (["judicial_template"], 2, "نموذج صياغة"),
    ])]
    for v in vectors[1:]:
        plans.append((v, [
            (["legislation_article", "legislation_issuing_article"], 6, "تشريع"),
            (["judicial_principle"], 6, "مبدأ قضائي"),
        ]))
    best = {}
    for vec, buckets in plans:
        for types, lim, label in buckets:
            try:
                for h in _draft_search(vec, types, lim):
                    p = h.get("payload") or {}
                    oid = p.get("object_id")
                    if not oid:
                        continue
                    sc = h.get("score", 0)
                    if oid not in best or sc > best[oid][1]:
                        best[oid] = (label, sc, p)
            except Exception:
                continue
    # قصّ لكل نوع بعد الدمج
    caps_n = {"تشريع": 12, "مبدأ قضائي": 12, "حكم كامل": 2, "نموذج صياغة": 2}
    grouped = {}
    for oid, (label, sc, p) in best.items():
        grouped.setdefault(label, []).append((sc, label, p))
    hits = []
    for label, items in grouped.items():
        items.sort(reverse=True, key=lambda x: x[0])
        for sc, lb, p in items[:caps_n[label]]:
            hits.append((lb, sc, p))
    # ضمانة تشريعية: (1) حزم الفصول الحاكمة حسب نوع المطالبة، (2) بحث معجمي عام
    picked = {p.get("object_id") for _l, _s, p in hits}
    bundle_added, lex_added = [], []
    for _bi, oid in enumerate(_draft_bundles(inp.request_type, facts, subqueries, inp.madhab, inp.branch)):
        if oid in picked:
            continue
        picked.add(oid)
        # المواد الحاكمة الأولى في الحزمة (المرتّبة أولًا) تُعطى درجة عالية لتنجو من قصّ الميزانية:
        # المادة الأساس للجريمة قد تكون بعيدة دلاليًّا فلا يجلبها المتجه (كم35 رشوة «يعاقب… كل موظف عام…»)،
        # فلو بقيت بدرجة صفر لَقُصّت خلف نتائج المتجه وتوسعة الإحالات. الذيل (كالنواة الإجرائية) يبقى منخفضًا.
        _bscore = 0.85 if _bi < 18 else 0.0
        hits.append(("تشريع", _bscore, {"object_id": oid}))
        bundle_added.append(oid)
    for oid in _draft_lexical(subqueries, facts):
        if oid in picked or len(lex_added) >= 8:
            continue
        picked.add(oid)
        hits.append(("تشريع", 0.0, {"object_id": oid}))
        lex_added.append(oid)
    # توسعة الإحالات بين القوانين: كل مادة مُستحضَرة تجرّ المواد المُحال إليها صراحةً في قانون آخر
    # (مستوى واحد فقط، بسقف 24 هدفًا، لمنع الإجابات السلبية الكاذبة عن مصادر مرفوعة أصلًا).
    xref_added = []
    for oid in list(picked):
        for tgt in _XREF.get(oid, ()):
            if tgt in picked or len(xref_added) >= 24:
                continue
            picked.add(tgt)
            # درجة موجبة صغيرة: ترفع المادة المُحال إليها فوق حشو الحزم الجامعة (درجة 0) لتنجو من قصّ الميزانية
            hits.append(("تشريع", 0.05, {"object_id": tgt}))
            xref_added.append(tgt)
    ids = {p.get("object_id") for _l, _s, p in hits if p.get("object_id")}
    texts = _draft_fetch_texts(ids)
    caps = {"تشريع": 2200, "مبدأ قضائي": 1400, "حكم كامل": 3500, "نموذج صياغة": 3500}
    prio = {"تشريع": 0, "مبدأ قضائي": 1, "حكم كامل": 2, "نموذج صياغة": 3}
    # الأولوية: التشريع الحاكم أولًا ثم المبادئ ثم الأحكام ثم النماذج؛ ميزانية سياق قصوى
    ordered = sorted(hits, key=lambda h: (prio.get(h[0], 9), -(h[1] or 0.0)))
    CTX_BUDGET = 55000
    parts, seen, used = [], set(), 0
    for label, _score, p in ordered:
        oid = p.get("object_id")
        if not oid or oid in seen or oid not in texts:
            continue
        t = texts[oid]
        block = (
            '<مصدر نوع="' + label + '" معرف="' + oid + '" فرع="' + (t["branch"] or "")
            + '" موضوع="' + (t.get("topic") or "") + '" عنوان="' + (t.get("title") or "") + '">\n'
            + (t["text"] or "")[:caps.get(label, 2000)] + "\n</مصدر>")
        if parts and used + len(block) > CTX_BUDGET:
            continue                     # تجاوز الميزانية: تخطَّ المصدر الأدنى أولوية
        seen.add(oid)
        used += len(block)
        parts.append(block)
    context = "\n\n".join(parts)

    att = inp.attachment
    att_note = ""
    if att and att.kind == "text" and (att.text or "").strip():
        att_note = ("\n\n<مرفق نصّي اسم=\"" + (att.name or "مرفق") + "\">\n"
                    + (att.text or "")[:20000] + "\n</مرفق>")
    elif att and att.kind in ("image", "pdf"):
        att_note = ("\n\nملاحظة: أرفق المستخدم " + ("صورة" if att.kind == "image" else "ملف PDF")
                    + " (" + (att.name or "مرفق") + ") — اقرأه واستعمله في تحليلك وصياغتك.")
    user_msg = ("المجال القانوني: " + (inp.branch or "غير محدد")
                + "\nنوع الطلب: " + inp.request_type
                + "\nالمذهب: " + (inp.madhab or "غير محدد")
                + "\n\nالوقائع والمطلوب:\n" + facts + att_note
                + "\n\n<السياق>\n" + context + "\n</السياق>")

    # بناء محتوى الرسالة: نص + مرفق بصري (صورة/PDF) عند وجوده
    if att and att.kind in ("image", "pdf") and att.data:
        _blk = ({"type": "image",
                 "source": {"type": "base64", "media_type": att.media_type or "image/jpeg",
                            "data": att.data}}
                if att.kind == "image" else
                {"type": "document",
                 "source": {"type": "base64", "media_type": "application/pdf",
                            "data": att.data}})
        _content = [{"type": "text", "text": user_msg}, _blk]
    else:
        _content = user_msg
    try:
        if _DRAFT_MODEL.startswith("claude-fable"):
            # Fable 5: التفكير مفعل دائمًا؛ تراجع تلقائي إلى Opus 4.8 عند رفض الأمان
            resp = client.beta.messages.create(
                model=_DRAFT_MODEL,
                max_tokens=12000,
                betas=["server-side-fallback-2026-06-01"],
                fallbacks=[{"model": "claude-opus-4-8"}],
                system=_DRAFT_SYSTEM,
                messages=[{"role": "user", "content": _content}],
            )
        else:
            resp = client.messages.create(
                model=_DRAFT_MODEL,
                max_tokens=12000,
                thinking={"type": "adaptive"},
                system=_DRAFT_SYSTEM,
                messages=[{"role": "user", "content": _content}],
            )
    except anthropic.AuthenticationError:
        raise HTTPException(500, "مفتاح ANTHROPIC_API_KEY غير صالح")
    except anthropic.RateLimitError:
        raise HTTPException(503, "تجاوز حد الاستخدام — أعد المحاولة بعد قليل")
    except anthropic.APIStatusError as e:
        detail = ""
        try:
            body = getattr(e, "body", None)
            if isinstance(body, dict):
                detail = str(((body.get("error") or {}).get("message")) or "")[:300]
            if not detail:
                detail = str(getattr(e, "message", "") or "")[:300]
        except Exception:
            pass
        raise HTTPException(
            502, "خطأ من واجهة Claude: " + str(e.status_code)
            + (" — " + detail if detail else ""))
    except anthropic.APIConnectionError:
        raise HTTPException(502, "تعذر الاتصال بواجهة Claude")

    if resp.stop_reason == "refusal":
        return {"answer": "تعذر إتمام هذا الطلب (رفض أمان). أعد صياغة الطلب بشكل مختلف.",
                "sources_used": len(parts), "model": resp.model}
    answer = "".join(b.text for b in resp.content if b.type == "text")
    return {"answer": answer, "sources_used": len(parts), "model": resp.model,
            "subqueries": subqueries, "bundle_extra": bundle_added, "lexical_extra": lex_added,
            "usage": {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens}}
# ==================== نهاية استوديو الصياغة ====================


# ==================== عرض كائن مفرد — /api/object ====================
@app.get("/api/object/{object_id}")
def get_object_full(object_id: str, _: str = Depends(require_auth)) -> dict:
    import psycopg
    dsn = _draft_env("DATABASE_URL") or \
        "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    with psycopg.connect(dsn) as _c, _c.cursor() as _cur:
        _cur.execute(
            "SELECT id, object_type, branch, topic, subtopic, micro_issue, title, "
            "original_text, verification_status FROM knowledge_objects WHERE id = %s",
            (object_id,))
        r = _cur.fetchone()
    if not r:
        raise HTTPException(404, "المصدر غير موجود")
    return {"id": r[0], "object_type": r[1], "branch": r[2], "topic": r[3],
            "subtopic": r[4], "micro_issue": r[5], "title": r[6], "text": r[7],
            "verification_status": r[8]}
# ==================== نهاية عرض كائن مفرد ====================

# ==================== تصفّح قاعدة المعرفة الهرمي — /api/browse ====================
_BROWSE_TYPES = {
    "laws": ("legislation_article", "legislation_issuing_article", "legislation_preamble"),
    "principles": ("judicial_principle", "full_judgment"),
    "judgments": ("full_judgment",),
    "templates": ("judicial_template",),
}
@app.get("/api/browse")
def browse_kb(kind: str, b: str = "", t: str = "", group: str = "",
              _: str = Depends(require_auth)) -> dict:
    import psycopg
    types = _BROWSE_TYPES.get(kind)
    if not types:
        raise HTTPException(400, "نوع تصفّح غير معروف")
    dsn = _draft_env("DATABASE_URL") or \
        "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    tph = ",".join(["%s"] * len(types))
    BR = "CASE WHEN branch LIKE 'أحوال شخصية%%' THEN 'أحوال شخصية' ELSE COALESCE(NULLIF(branch,''),'غير مصنّف') END"
    TP = "COALESCE(NULLIF(topic,''),'عام')"
    # مفتاح التجميع: قانون (legis-N-Y) أو كتاب لائحة تنفيذية (lreg-N-Y-kM) — كلٌّ عقدةٌ مستقلّة
    GEXPR = ("COALESCE(substring(id from '^(legis-[0-9]+-[0-9]+)'), "
             "substring(id from '^(lreg-[0-9]+-[0-9]+-k[0-9]+)'))")
    with psycopg.connect(dsn) as _c, _c.cursor() as _cur:
        if kind == "laws":
            # فرع (مجلد) ← قانون/كتاب لائحة ← مواد
            if not b:
                _cur.execute(
                    "SELECT " + BR + " AS g, count(*) FROM knowledge_objects "
                    "WHERE object_type IN (" + tph + ") GROUP BY g ORDER BY count(*) DESC",
                    tuple(types))
                return {"mode": "groups", "level": "branch",
                        "groups": [{"key": r[0], "count": r[1]} for r in _cur.fetchall()]}
            if not group:
                _cur.execute(
                    "SELECT " + GEXPR + " AS g, count(*), "
                    "CASE WHEN " + GEXPR + " LIKE 'lreg-%%' "
                    "THEN split_part(min(title), ' — ', 2) || "
                    "COALESCE(' — كتاب ' || min(metadata->>'book_title'), '') "
                    "ELSE split_part(min(title), ' — ', 2) END AS name "
                    "FROM knowledge_objects WHERE object_type IN (" + tph + ") AND " + BR + " = %s "
                    "GROUP BY g ORDER BY g", tuple(types) + (b,))
                return {"mode": "groups", "level": "law",
                        "groups": [{"key": r[0], "count": r[1], "name": (r[2] or None)}
                                   for r in _cur.fetchall() if r[0]]}
            _cur.execute(
                "SELECT id, title, branch, subtopic, micro_issue FROM knowledge_objects "
                "WHERE object_type IN (" + tph + ") "
                "AND " + GEXPR + " = %s ORDER BY id LIMIT 3000",
                tuple(types) + (group,))
            return {"mode": "items", "items": [
                {"id": r[0], "title": r[1], "branch": r[2], "subtopic": r[3], "micro_issue": r[4]}
                for r in _cur.fetchall()]}
        # غير التشريعات: فرع ← موضوع ← عناصر
        if not b:
            _cur.execute(
                "SELECT " + BR + " AS g, count(*) FROM knowledge_objects "
                "WHERE object_type IN (" + tph + ") GROUP BY g ORDER BY count(*) DESC",
                tuple(types))
            return {"mode": "groups", "level": "branch",
                    "groups": [{"key": r[0], "count": r[1]} for r in _cur.fetchall()]}
        if not t:
            _cur.execute(
                "SELECT " + TP + " AS g, count(*) FROM knowledge_objects "
                "WHERE object_type IN (" + tph + ") AND " + BR + " = %s "
                "GROUP BY g ORDER BY count(*) DESC", tuple(types) + (b,))
            return {"mode": "groups", "level": "topic",
                    "groups": [{"key": r[0], "count": r[1]} for r in _cur.fetchall()]}
        _cur.execute(
            "SELECT id, title, branch, subtopic, micro_issue FROM knowledge_objects "
            "WHERE object_type IN (" + tph + ") AND " + BR + " = %s AND " + TP + " = %s "
            "ORDER BY id LIMIT 3000", tuple(types) + (b, t))
        return {"mode": "items", "items": [
            {"id": r[0], "title": r[1], "branch": r[2], "subtopic": r[3], "micro_issue": r[4]}
            for r in _cur.fetchall()]}
# ==================== نهاية تصفّح قاعدة المعرفة الهرمي ====================


# ==================== محرّر المواد والمبادئ داخل النظام — /edit ====================
from fastapi import Request as _EditRequest

_EDIT_FIELDS = ("branch", "topic", "subtopic", "micro_issue", "title")

def _edit_normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").replace("ـ", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


@app.put("/api/object/{object_id}")
async def update_object(object_id: str, request: _EditRequest,
                        _: str = Depends(require_auth)) -> dict:
    """تعديل نصّ مادة/مبدأ (وحقول التصنيف اختياريًا). لا يعيد الفهرسة تلقائيًّا."""
    body = await request.json()
    text = (body.get("text") or "").strip()
    if len(text) < 2:
        raise HTTPException(400, "النص فارغ أو قصير جدًّا")
    dsn = _draft_env("DATABASE_URL") or DATABASE_URL
    sets = ["original_text=%s", "normalized_text=%s",
            "verification_status=%s", "updated_at=now()"]
    vstatus = body.get("verification_status") or "source_verified"
    if vstatus not in VERIFICATION_STATUSES:
        vstatus = "source_verified"
    vals = [text, _edit_normalize(text), vstatus]
    for f in _EDIT_FIELDS:
        if f in body:
            v = body.get(f)
            v = (str(v).strip() or None) if v is not None else None
            sets.append(f + "=%s"); vals.append(v)
    vals.append(object_id)
    with psycopg.connect(dsn) as _c, _c.cursor() as _cur:
        _cur.execute("SELECT 1 FROM knowledge_objects WHERE id=%s", (object_id,))
        if not _cur.fetchone():
            raise HTTPException(404, "المصدر غير موجود")
        _cur.execute("UPDATE knowledge_objects SET " + ",".join(sets) + " WHERE id=%s",
                     tuple(vals))
        _c.commit()
    return {"ok": True, "id": object_id,
            "note": "حُفِظ في قاعدة البيانات. اضغط «إعادة الفهرسة» ليظهر التعديل في البحث."}


@app.post("/api/reindex")
def reindex_now(_: str = Depends(require_auth)) -> dict:
    """إعادة فهرسة كاملة عند الطلب (بضع ثوانٍ) لتحديث متجهات البحث بعد التعديل."""
    env = dict(os.environ)
    envf = Path("/opt/LegalMind/deploy/.env")
    if envf.exists():
        for line in envf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env["HF_HUB_OFFLINE"] = "1"; env["TRANSFORMERS_OFFLINE"] = "1"
    try:
        proc = subprocess.run([ENGINE_PY, "-m", "engine.legalmind_engine", "reindex"],
                              cwd="/opt/LegalMind", env=env,
                              capture_output=True, text=True, timeout=600)
    except Exception as exc:
        raise HTTPException(500, f"تعذّرت إعادة الفهرسة: {exc}")
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        raise HTTPException(500, f"فشلت إعادة الفهرسة: {out[-400:]}")
    m = re.search(r'\{[^{}]*"consistent"[^{}]*\}', out, re.S)
    return {"ok": True, "reindex": (json.loads(m.group(0)) if m else {"raw": out[-400:]})}


def _engine_env() -> dict:
    """بيئة تشغيل المحرّك: متغيّرات deploy/.env + وضع HF دون اتصال."""
    env = dict(os.environ)
    envf = Path("/opt/LegalMind/deploy/.env")
    if envf.exists():
        for line in envf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env["HF_HUB_OFFLINE"] = "1"; env["TRANSFORMERS_OFFLINE"] = "1"
    return env


@app.post("/api/reindex-one/{object_id:path}")
def reindex_one(object_id: str, _: str = Depends(require_auth)) -> dict:
    """إعادة فهرسة كائن واحد فقط (سريعة، غير هدّامة). تُستدعى تلقائيًّا بعد حفظ التعديل
    فيظهر التعديل في البحث فورًا دون إعادة بناء المجموعة كاملةً (التي تتجاوز مهلة nginx)."""
    object_id = (object_id or "").strip()
    if not object_id:
        raise HTTPException(400, "معرّف فارغ")
    cli = "/opt/LegalMind/engine/reindex_one_cli.py"
    try:
        proc = subprocess.run([ENGINE_PY, cli, object_id],
                              cwd="/opt/LegalMind", env=_engine_env(),
                              capture_output=True, text=True, timeout=180)
    except Exception as exc:
        raise HTTPException(500, f"تعذّرت إعادة الفهرسة الجزئية: {exc}")
    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        raise HTTPException(500, f"فشلت إعادة الفهرسة الجزئية: {((proc.stderr or '') + out)[-400:]}")
    try:
        res = json.loads(out.splitlines()[-1]) if out else {}
    except Exception:
        raise HTTPException(500, f"مخرجات غير متوقّعة من المحرّك: {out[-300:]}")
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "تعذّرت إعادة الفهرسة الجزئية"))
    return {"ok": True, "id": object_id, "point_id": res.get("point_id")}


_EDIT_INJECT = r"""<script id="legalmind-edit-inject">
(function(){
  var RE=/((?:legis|lreg|nsm|jud|prin)-[0-9A-Za-z؀-ۿ_]+(?:-[0-9A-Za-z؀-ۿ_]+)*)/;
  function add(){
    try{
      var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,null,false);
      var hits=[],n;
      while(n=w.nextNode()){ if(RE.test(n.nodeValue)) hits.push(n); }
      for(var i=0;i<hits.length;i++){
        var node=hits[i], el=node.parentElement;
        if(!el||el.getAttribute('data-lm-edit'))continue;
        var m=node.nodeValue.match(RE); if(!m)continue;
        if(el.tagName==='A'||el.tagName==='SCRIPT'||el.tagName==='STYLE')continue;
        el.setAttribute('data-lm-edit','1');
        var a=document.createElement('a');
        a.textContent='✏️ تعديل';
        a.href='/edit?id='+encodeURIComponent(m[1]);a.target='_blank';a.title='تعديل هذه المادة';
        a.style.cssText='margin-inline-start:10px;font-size:12px;font-weight:700;padding:2px 10px;border:1px solid #2f81f7;border-radius:6px;color:#2f81f7;text-decoration:none;white-space:nowrap;display:inline-block';
        el.appendChild(a);
      }
    }catch(e){}
  }
  var t; function sched(){clearTimeout(t);t=setTimeout(add,120);}
  try{new MutationObserver(sched).observe(document.documentElement,{childList:true,subtree:true,characterData:true});}catch(e){}
  if(document.readyState!=='loading')add(); else document.addEventListener('DOMContentLoaded',add);
  setTimeout(add,400);setTimeout(add,1200);
})();
</script>"""

@app.get("/edit", response_class=HTMLResponse)
def edit_page(_: str = Depends(require_auth)) -> HTMLResponse:
    return HTMLResponse(_EDIT_HTML)


_EDIT_HTML = r"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>محرّر المواد والمبادئ — LegalMind</title>
<style>
:root{--bg:#0f1720;--card:#16212e;--line:#26374a;--tx:#e6edf3;--mut:#8aa0b4;--acc:#2f81f7;--ok:#2ea043;--warn:#d29922}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.7 "Segoe UI",Tahoma,sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:18px}
h1{font-size:20px;margin:6px 0 14px}.mut{color:var(--mut)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:14px}
.row{display:flex;gap:8px;flex-wrap:wrap}.row>*{flex:1;min-width:120px}
input,select,textarea,button{font:inherit;color:var(--tx);background:#0d1520;border:1px solid var(--line);border-radius:8px;padding:9px 11px}
input:focus,textarea:focus,select:focus{outline:none;border-color:var(--acc)}
textarea{width:100%;min-height:340px;line-height:1.9;resize:vertical}
label{display:block;font-size:13px;color:var(--mut);margin:8px 0 4px}
button{cursor:pointer;background:#1b2b3d;border-color:var(--line)}button:hover{border-color:var(--acc)}
button.pri{background:var(--acc);border-color:var(--acc);color:#fff}button.ok{background:var(--ok);border-color:var(--ok);color:#fff}
.res{border:1px solid var(--line);border-radius:8px;max-height:230px;overflow:auto;margin-top:8px}
.res div{padding:8px 10px;border-bottom:1px solid var(--line);cursor:pointer}.res div:hover{background:#0d1520}
.res b{color:var(--acc)}.msg{padding:9px 12px;border-radius:8px;margin-top:10px;display:none}
.msg.s{display:block;background:#12331d;border:1px solid var(--ok)}.msg.e{display:block;background:#3a1d1d;border:1px solid #b62324}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}@media(max-width:640px){.grid{grid-template-columns:1fr}}
small{color:var(--mut)}.tag{font-size:12px;color:var(--mut)}
</style></head><body><div class="wrap">
<h1>محرّر المواد والمبادئ <span class="mut" style="font-size:13px">— تعديل نصّ أي مصدر في قاعدة المعرفة</span></h1>

<div class="card">
  <label>ابحث بالمعرّف (مثل <span class="tag">legis-67-1980-m202</span>) أو بالنصّ:</label>
  <div class="row">
    <input id="q" placeholder="معرّف المادة أو كلمات للبحث الدلالي" style="flex:3">
    <button onclick="byId()">تحميل بالمعرّف</button>
    <button onclick="byText()">بحث دلالي</button>
  </div>
  <div id="res" class="res" style="display:none"></div>
</div>

<div id="editor" class="card" style="display:none">
  <div class="row"><div><label>المعرّف</label><input id="oid" readonly></div>
    <div><label>النوع</label><input id="otype" readonly></div></div>
  <div class="grid">
    <div><label>العنوان</label><input id="title"></div>
    <div><label>الفرع</label><input id="branch"></div>
    <div><label>الموضوع</label><input id="topic"></div>
    <div><label>الموضوع الفرعي</label><input id="subtopic"></div>
  </div>
  <label>حالة التوثيق</label>
  <select id="vstatus">
    <option value="source_verified">مُوثَّق من المصدر (source_verified)</option>
    <option value="operationally_accepted">مقبول تشغيليًّا</option>
    <option value="machine_pending_human">بانتظار مراجعة بشرية</option>
    <option value="historical_only">تاريخي فقط</option>
    <option value="requires_post_2026_reassessment">يحتاج إعادة تقييم</option>
  </select>
  <label>النصّ الكامل للمادة/المبدأ</label>
  <textarea id="text" spellcheck="false"></textarea>
  <small id="len"></small>
  <div class="row" style="margin-top:12px">
    <button class="pri" onclick="save()">💾 حفظ</button>
    <button class="ok" onclick="reindex()">🔄 إعادة الفهرسة (لتحديث البحث)</button>
    <button onclick="reload()">استرجاع الأصل</button>
  </div>
  <div id="msg" class="msg"></div>
</div>

<script>
var cur=null;
function j(u,o){return fetch(u,o).then(function(r){return r.json().then(function(d){if(!r.ok)throw new Error(d.detail||JSON.stringify(d));return d})})}
function esc(s){return (s||'').replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c]})}
function show(m,ok){var e=document.getElementById('msg');e.className='msg '+(ok?'s':'e');e.textContent=m}
function fill(o){cur=o;document.getElementById('editor').style.display='block';
 document.getElementById('oid').value=o.id;document.getElementById('otype').value=o.object_type||'';
 document.getElementById('title').value=o.title||'';document.getElementById('branch').value=o.branch||'';
 document.getElementById('topic').value=o.topic||'';document.getElementById('subtopic').value=o.subtopic||'';
 document.getElementById('vstatus').value=o.verification_status||'source_verified';
 document.getElementById('text').value=o.text||o.original_text||'';upd();
 document.getElementById('res').style.display='none';window.scrollTo(0,document.getElementById('editor').offsetTop-10)}
function upd(){var t=document.getElementById('text').value;document.getElementById('len').textContent=t.length+' حرف'}
document.addEventListener('input',function(e){if(e.target.id==='text')upd()});
function byId(){var id=document.getElementById('q').value.trim();if(!id)return;
 j('/api/object/'+encodeURIComponent(id)).then(fill).catch(function(e){show('لم يُعثر على المعرّف: '+e.message,false)})}
function byText(){var q=document.getElementById('q').value.trim();if(q.length<2)return;
 j('/api/search?limit=15&q='+encodeURIComponent(q)).then(function(d){var r=document.getElementById('res');
  if(!d.results||!d.results.length){r.style.display='block';r.innerHTML='<div>لا نتائج</div>';return}
  r.style.display='block';r.innerHTML=d.results.map(function(x){return '<div onclick="load(\''+x.object_id+'\')"><b>'+x.object_id+'</b> — '+esc(x.title||'')+'<br><small>'+esc((x.text||'').slice(0,90))+'…</small></div>'}).join('')})
  .catch(function(e){show(e.message,false)})}
function load(id){j('/api/object/'+encodeURIComponent(id)).then(fill).catch(function(e){show(e.message,false)})}
function reload(){if(cur)load(cur.id)}
function save(){if(!cur)return;var b={text:document.getElementById('text').value,
  title:document.getElementById('title').value,branch:document.getElementById('branch').value,
  topic:document.getElementById('topic').value,subtopic:document.getElementById('subtopic').value,
  verification_status:document.getElementById('vstatus').value};
 j('/api/object/'+encodeURIComponent(cur.id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})
  .then(function(d){show(d.note||'حُفِظ.',true)}).catch(function(e){show('تعذّر الحفظ: '+e.message,false)})}
function reindex(){show('جارٍ إعادة الفهرسة…',true);
 j('/api/reindex',{method:'POST'}).then(function(d){var x=d.reindex||{};
  show('تمّت الفهرسة: '+(x.postgres_objects||'?')+' كائن، متّسق='+(x.consistent),true)})
  .catch(function(e){show('فشلت الفهرسة: '+e.message,false)})}
(function(){var pid=new URLSearchParams(location.search).get('id');if(pid){document.getElementById('q').value=pid;load(pid)}})();
</script></div></body></html>"""
# ==================== نهاية المحرّر ====================
