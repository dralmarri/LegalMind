from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText


import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from admin.app import require_auth

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://legalmind:legalmind@127.0.0.1:55432/legalmind")
router = APIRouter(prefix="/api/support", tags=["support"])

def _env(name):
    """بيئة العملية أولاً ثم قراءة .env مباشرة — نفس نمط llm.py، بيئة systemd لا تحمّل .env تلقائيًا."""
    val = os.environ.get(name)
    if val:
        return val
    try:
        with open("/opt/LegalMind/deploy/.env", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None


def _send_notification_email(name, contact, message):
    """يرسل بريدًا عند وصول رسالة جديدة — لا أثر إن لم تُضبط متغيرات SMTP في .env."""
    def _clean(v):
        return "".join(ch for ch in (v or "") if not ch.isspace())
    host = _clean(_env("SMTP_HOST"))
    port = _clean(_env("SMTP_PORT"))
    user = _clean(_env("SMTP_USER"))
    pw = _clean(_env("SMTP_PASS"))
    to = _clean(_env("SMTP_TO")) or user
    if not (host and port and user and pw and to):
        return
    try:
        body = (
            "رسالة جديدة من نموذج تواصل معنا — صوت العدالة\n\n"
            "الاسم: %s\n"
            "وسيلة التواصل: %s\n\n"
            "الرسالة:\n%s"
        ) % (name or "(غير مذكور)", contact, message)
        msg = MIMEText(body, _charset="utf-8")
        msg["Subject"] = "رسالة جديدة — تواصل معنا (صوت العدالة)"
        msg["From"] = user
        msg["To"] = to
        with smtplib.SMTP(host, int(port), timeout=10) as s:
            s.starttls()
            s.login(user, pw)
            s.send_message(msg)
    except Exception as exc:
        print("[support] email-error:", exc)



def db_execute(query: str, params: tuple = ()) -> dict | None:
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=5, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone() if cur.description else None
            conn.commit()
            return row
    except Exception as exc:
        raise HTTPException(503, f"تعذر حفظ الرسالة: {exc}") from exc


def db_fetch(query: str, params: tuple = ()) -> list[dict]:
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=5, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return list(cur.fetchall())
    except Exception as exc:
        raise HTTPException(503, f"تعذر القراءة: {exc}") from exc


class SupportMessageIn(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    contact: str = Field(min_length=3, max_length=300)
    message: str = Field(min_length=3, max_length=5000)


@router.post("/message")
def support_message_create(inp: SupportMessageIn, request: Request) -> dict:
    ip = request.client.host if request.client else None
    db_execute(
        "INSERT INTO support_messages (name, contact, message, ip) VALUES (%s,%s,%s,%s)",
        (inp.name, inp.contact, inp.message, ip),
    )
    _send_notification_email(inp.name, inp.contact, inp.message)
    return {"ok": True}


@router.get("/messages")
def support_messages_list(limit: int = 100, _: str = Depends(require_auth)) -> list[dict]:
    return db_fetch(
        "SELECT id, name, contact, message, ip, created_at FROM support_messages "
        "ORDER BY id DESC LIMIT %s",
        (limit,),
    )
