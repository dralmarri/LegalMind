from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://legalmind:legalmind@127.0.0.1:55432/legalmind")
router = APIRouter(prefix="/api/cases", tags=["cases"])


def db_fetch(query: str, params: tuple = ()) -> list[dict]:
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=5, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return list(cur.fetchall())
    except Exception as exc:
        raise HTTPException(503, f"تعذر الاتصال بقاعدة البيانات: {exc}") from exc


def db_execute(query: str, params: tuple = ()) -> dict | None:
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=5, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone() if cur.description else None
            conn.commit()
            return row
    except Exception as exc:
        raise HTTPException(503, f"تعذر حفظ البيانات: {exc}") from exc


class CaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    branch: str = Field(min_length=2, max_length=100)
    topic: str = ""
    subtopic: str = ""
    client_name: str = ""
    client_capacity: str = ""
    opponent_name: str = ""
    court_name: str = ""
    court_level: str = ""
    facts: str = ""
    requests: str = ""
    notes: str = ""


class CaseUpdate(BaseModel):
    title: str | None = None
    topic: str | None = None
    subtopic: str | None = None
    client_name: str | None = None
    client_capacity: str | None = None
    opponent_name: str | None = None
    court_name: str | None = None
    court_level: str | None = None
    status: str | None = None
    facts: str | None = None
    requests: str | None = None
    notes: str | None = None


def _case_key() -> str:
    return f"CASE-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"


@router.get("")
def list_cases():
    return db_fetch(
        """SELECT id,case_key,title,branch,topic,subtopic,client_name,client_capacity,
                  opponent_name,court_name,court_level,status,created_at,updated_at
           FROM legal_cases ORDER BY updated_at DESC LIMIT 300"""
    )


@router.post("")
def create_case(payload: CaseCreate):
    return db_execute(
        """INSERT INTO legal_cases(case_key,title,branch,topic,subtopic,client_name,client_capacity,
                  opponent_name,court_name,court_level,facts,requests,notes)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           RETURNING *""",
        (_case_key(), payload.title.strip(), payload.branch.strip(), payload.topic.strip(),
         payload.subtopic.strip(), payload.client_name.strip(), payload.client_capacity.strip(),
         payload.opponent_name.strip(), payload.court_name.strip(), payload.court_level.strip(),
         payload.facts.strip(), payload.requests.strip(), payload.notes.strip()),
    )


@router.get("/{case_id}")
def get_case(case_id: str):
    rows = db_fetch("SELECT * FROM legal_cases WHERE id=%s", (case_id,))
    if not rows:
        raise HTTPException(404, "القضية غير موجودة")
    case = rows[0]
    case["authorities"] = db_fetch(
        """SELECT ca.id,ca.authority_role,ca.relevance_note,ca.verification_status,
                  ko.id AS object_id,ko.object_type,ko.title,ko.branch,ko.topic,ko.subtopic,ko.micro_issue
           FROM case_authorities ca JOIN knowledge_objects ko ON ko.id=ca.object_id
           WHERE ca.case_id=%s ORDER BY ca.created_at""", (case_id,)
    )
    case["drafts"] = db_fetch(
        "SELECT id,draft_type,version,title,drafting_status,authority_report,created_at,updated_at FROM case_drafts WHERE case_id=%s ORDER BY updated_at DESC",
        (case_id,),
    )
    return case


@router.patch("/{case_id}")
def update_case(case_id: str, payload: CaseUpdate):
    data = payload.model_dump(exclude_none=True)
    if not data:
        return get_case(case_id)
    allowed = {"title","topic","subtopic","client_name","client_capacity","opponent_name","court_name","court_level","status","facts","requests","notes"}
    data = {k: v for k, v in data.items() if k in allowed}
    assignments = ",".join(f"{key}=%s" for key in data)
    row = db_execute(f"UPDATE legal_cases SET {assignments},updated_at=now() WHERE id=%s RETURNING *", tuple(data.values()) + (case_id,))
    if not row:
        raise HTTPException(404, "القضية غير موجودة")
    return row


@router.get("/{case_id}/coverage")
def case_coverage(case_id: str):
    rows = db_fetch("SELECT branch,topic,subtopic FROM legal_cases WHERE id=%s", (case_id,))
    if not rows:
        raise HTTPException(404, "القضية غير موجودة")
    case = rows[0]
    topic = case.get("topic") or ""
    subtopic = case.get("subtopic") or ""
    counts = db_fetch(
        """SELECT object_type,COUNT(*)::int AS count FROM knowledge_objects
           WHERE branch=%s AND (%s='' OR topic=%s) AND (%s='' OR subtopic=%s)
           GROUP BY object_type""",
        (case["branch"], topic, topic, subtopic, subtopic),
    )
    by_type = {r["object_type"]: r["count"] for r in counts}
    legislation = by_type.get("legislation", 0)
    principles = by_type.get("judicial_principle", 0)
    templates = by_type.get("judicial_template", 0) + by_type.get("legal_memorandum", 0)
    ready = legislation > 0 and principles > 0 and templates > 0
    return {
        "counts": by_type,
        "drafting_ready": ready,
        "drafting_status": "ready_for_grounded_draft" if ready else "blocked_missing_authorities",
        "missing": [name for name, ok in {
            "تشريع": legislation > 0,
            "مبدأ قضائي": principles > 0,
            "نموذج أو مذكرة": templates > 0,
        }.items() if not ok],
        "note": "وجود حكم كامل يعزز جودة التطبيق، بينما فتح المسودة المسندة يتطلب تشريعًا ومبدأً ونموذجًا مطابقًا."
    }
