"""
apply_chat.py
-------------
   POST /apply/chat  { message, resume_id } -> { reply, email_draft_id?, autofill_run_id? }

One paste, both actions. A person drops the job description into a chat box,
optionally with a form link and a recipient email in the same message, and
this figures out what to do: draft the application email, start filling the
form, or both. It never sends or submits anything — it produces a draft and
a pre-filled link for the person to review, exactly like the two dedicated
tabs, just reached from one message instead of two forms.

It is a plain intent router, not an agent framework: pull any supported
form link and any recipient email out of the text with a regex, then reuse
the same drafting and autofill paths the rest of the app already uses.
"""
import logging
import re
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.http import parse_uuid
from app.models import AutofillRun, EmailSend, Profile, Resume, User
from app.routers.auth import get_current_user
from app.routers.autofill import _run as run_autofill_task
from app.services import ai_service, autofill_service

router = APIRouter(prefix="/apply", tags=["apply"])
log = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s<>\"']+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


class ApplyChatIn(BaseModel):
    message: str
    resume_id: str


def _extract(message: str):
    """Pull the first supported form link and the first email address out of
    the message. Emails that are part of a URL are ignored so a link never
    reads as a recipient."""
    urls = _URL_RE.findall(message)
    form_url = next((u.rstrip(".,)") for u in urls if autofill_service.is_supported_form_url(u.rstrip(".,)"))), None)
    joined_urls = " ".join(urls)
    recipient = next((e for e in _EMAIL_RE.findall(message) if e not in joined_urls), None)
    return form_url, recipient


@router.post("/chat")
async def apply_chat(
    body: ApplyChatIn,
    bg: BackgroundTasks,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(422, "Paste a job description, a form link, or a recipient email to apply.")

    resume = await db.get(Resume, parse_uuid(body.resume_id, "Resume"))
    if not resume or resume.user_id != u.id:
        raise HTTPException(404, "Resume not found")
    if resume.status != "ready":
        raise HTTPException(409, "Resume is still processing. Wait for it to finish.")

    form_url, recipient = _extract(message)

    res = await db.execute(select(Profile).where(Profile.user_id == u.id))
    profile = res.scalar_one_or_none()

    email_draft_id: Optional[str] = None
    autofill_run_id: Optional[str] = None
    did = []

    if recipient:
        job_parsed = await ai_service.parse_job(message)
        fit = await ai_service.analyze_fit(resume.parsed_data or {}, job_parsed)
        name = (resume.parsed_data or {}).get("name") or u.full_name or ""
        drafted = await ai_service.generate_email(
            name=name,
            job_parsed=job_parsed,
            fit=fit,
            knowledge_graph=(profile.knowledge_graph if profile else None) or None,
            resume_parsed=resume.parsed_data or {},
            custom_instructions=(profile.custom_instructions if profile else None) or "",
            linkedin_url=(profile.linkedin_url if profile else None) or "",
            github_url=(profile.github_url if profile else None) or "",
        )
        e = EmailSend(
            user_id=u.id,
            resume_id=resume.id,
            recipient_email=recipient,
            subject=drafted.get("subject", ""),
            body=drafted.get("body", ""),
            status="draft",
        )
        db.add(e)
        await db.commit()
        await db.refresh(e)
        email_draft_id = str(e.id)
        did.append(f"drafted an application email to {recipient}")

    if form_url:
        run = AutofillRun(user_id=u.id, resume_id=resume.id, form_url=form_url, status="running")
        db.add(run)
        await db.commit()
        await db.refresh(run)
        autofill_run_id = str(run.id)
        # The job description text rides along as extra context for the
        # form answers, same as the dedicated form tab.
        bg.add_task(run_autofill_task, str(run.id), form_url, message)
        did.append("started filling the form")

    if not did:
        reply = (
            "I could not find a Google or Microsoft Form link, or a recipient email, in that. "
            "Paste the job description together with a form link, a recipient email address, or "
            "both, and I will fill the form and draft the email for you to review."
        )
    else:
        reply = "Done. I " + " and ".join(did) + ". Review each below, nothing is sent or submitted until you do."

    return {
        "reply": reply,
        "email_draft_id": email_draft_id,
        "autofill_run_id": autofill_run_id,
    }
