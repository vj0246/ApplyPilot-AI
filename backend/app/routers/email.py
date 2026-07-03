"""
email.py
--------
   POST /email/draft         { job_id, resume_id, recipient_email, extra_context? } -> 201, draft
   GET  /email/{id}          -> draft or sent record
   PATCH /email/{id}         { subject?, body? } -> edit before sending
   POST /email/{id}/send     -> actually sends, from the user's own address

Drafting and sending are two separate calls on purpose. The AI reads the
job description and writes the email, a person can read it and change the
subject or body, and only the explicit send call puts it on the wire. This
mirrors the autofill router's rule of never submitting anything on the
user's behalf without them looking at it first.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.database import get_db
from app.models import EmailSend, Job, Profile, Resume, User
from app.routers.auth import get_current_user
from app.services import ai_service, email_service

router = APIRouter(prefix="/email", tags=["email"])


class EmailDraftIn(BaseModel):
    job_id: str
    resume_id: str
    recipient_email: str
    extra_context: str = ""


class EmailEditIn(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None


def _out(e: EmailSend) -> dict:
    return {
        "id": str(e.id),
        "status": e.status,
        "recipient_email": e.recipient_email,
        "subject": e.subject,
        "body": e.body,
        "error": e.error_msg,
        "sent_at": e.sent_at.isoformat() if e.sent_at else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@router.post("/draft", status_code=201)
async def create_draft(
    body: EmailDraftIn,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(Job, uuid.UUID(body.job_id))
    if not job or job.user_id != u.id:
        raise HTTPException(404, "Job not found")

    resume = await db.get(Resume, uuid.UUID(body.resume_id))
    if not resume or resume.user_id != u.id:
        raise HTTPException(404, "Resume not found")

    res = await db.execute(select(Profile).where(Profile.user_id == u.id))
    profile = res.scalar_one_or_none()
    knowledge_graph = (profile.knowledge_graph if profile else None) or None

    fit = await ai_service.analyze_fit(resume.parsed_data or {}, job.parsed_data or {})
    name = (resume.parsed_data or {}).get("name") or u.full_name or ""
    drafted = await ai_service.generate_email(
        name=name,
        job_parsed=job.parsed_data or {},
        fit=fit,
        extra_context=body.extra_context,
        knowledge_graph=knowledge_graph,
    )

    e = EmailSend(
        user_id=u.id,
        job_id=job.id,
        resume_id=resume.id,
        recipient_email=body.recipient_email,
        subject=drafted.get("subject", ""),
        body=drafted.get("body", ""),
        status="draft",
    )
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return _out(e)


@router.get("/{email_id}")
async def get_email(
    email_id: uuid.UUID,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    e = await db.get(EmailSend, email_id)
    if not e or e.user_id != u.id:
        raise HTTPException(404, "Email not found")
    return _out(e)


@router.patch("/{email_id}")
async def edit_email(
    email_id: uuid.UUID,
    body: EmailEditIn,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    e = await db.get(EmailSend, email_id)
    if not e or e.user_id != u.id:
        raise HTTPException(404, "Email not found")
    if e.status == "sent":
        raise HTTPException(409, "This email was already sent and cannot be edited.")

    if body.subject is not None:
        e.subject = body.subject
    if body.body is not None:
        e.body = body.body

    await db.commit()
    await db.refresh(e)
    return _out(e)


@router.post("/{email_id}/send")
async def send_email_now(
    email_id: uuid.UUID,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    e = await db.get(EmailSend, email_id)
    if not e or e.user_id != u.id:
        raise HTTPException(404, "Email not found")
    if e.status == "sent":
        raise HTTPException(409, "This email was already sent.")

    res = await db.execute(select(Profile).where(Profile.user_id == u.id))
    profile = res.scalar_one_or_none()
    if not profile or not profile.smtp_password_encrypted:
        raise HTTPException(
            422,
            "No sending account is configured yet. Add your email address and app password in "
            "settings before sending.",
        )

    try:
        password = crypto.decrypt(profile.smtp_password_encrypted)
        await email_service.send_email(
            smtp_host=profile.smtp_host,
            smtp_port=profile.smtp_port or 587,
            smtp_username=profile.smtp_username,
            smtp_password=password,
            sender_email=profile.sender_email,
            recipient_email=e.recipient_email,
            subject=e.subject,
            body=e.body,
        )
        e.status = "sent"
        e.sent_at = datetime.now(timezone.utc)
        e.error_msg = None
        await db.commit()
    except Exception as ex:
        e.status = "failed"
        e.error_msg = str(ex)[:400]
        await db.commit()
        raise HTTPException(502, f"Could not send the email. {e.error_msg}")

    await db.refresh(e)
    return _out(e)
