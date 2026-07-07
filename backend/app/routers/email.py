"""
email.py
--------
   POST /email/draft         { job_id? or job_description?, resume_id, recipient_email, extra_context? } -> 201, draft
   GET  /email/{id}          -> draft or sent record
   PATCH /email/{id}         { subject?, body? } -> edit before sending
   POST /email/{id}/send     -> actually sends, from the user's own address

Drafting and sending are two separate calls on purpose. The AI reads the
job description and writes the email, a person can read it and change the
subject or body, and only the explicit send call puts it on the wire. This
mirrors the autofill router's rule of never submitting anything on the
user's behalf without them looking at it first.

A draft can point at a job already saved on the Jobs page (job_id), or at
a job description pasted straight into this flow (job_description). The
pasted case is parsed on the fly and never written to the jobs table —
mailing one job description about a role you are not tracking should not
force it into your saved job list.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.config import settings
from app.core.database import get_db
from app.core.auth import decode_token
from app.models import EmailSend, Job, Profile, Resume, User
from app.routers.auth import get_current_user
from app.services import ai_service, email_service, gmail_service, sendgrid_service

router = APIRouter(prefix="/email", tags=["email"])
log = logging.getLogger(__name__)


class EmailDraftIn(BaseModel):
    resume_id: str
    recipient_email: str
    job_id: Optional[str] = None
    job_description: Optional[str] = None
    extra_context: str = ""

    @model_validator(mode="after")
    def _one_job_source(self):
        if not self.job_id and not (self.job_description or "").strip():
            raise ValueError("Provide either job_id or job_description.")
        return self


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


@router.get("/oauth/status")
async def oauth_status():
    return {
        "available": gmail_service.is_configured(),
        "default_sending_available": sendgrid_service.is_configured(),
    }


@router.get("/oauth/start")
async def oauth_start(
    request: Request,
    return_to: str = Query("settings"),
    u: User = Depends(get_current_user),
):
    """Returns the Google consent URL for the frontend to redirect the
    browser to. The state parameter carries the caller's own access
    token rather than a separate server side session, because the
    redirect back in oauth_callback below arrives as a plain browser
    navigation from Google with no Authorization header at all — the
    token, which Google only ever sees as an opaque string it echoes
    back unchanged, is what lets the callback know whose profile to
    attach the connection to. return_to rides alongside it so someone
    connecting Gmail from the onboarding wizard lands back inside the
    wizard instead of getting bounced out to settings mid flow."""
    if not gmail_service.is_configured():
        raise HTTPException(
            503,
            "Gmail sending is not set up on this server yet. Ask the administrator to add "
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )
    raw_token = request.headers["Authorization"][7:]
    safe_return_to = return_to if return_to in ("settings", "onboarding") else "settings"
    return {"url": gmail_service.build_auth_url(state=f"{raw_token}::{safe_return_to}")}


@router.get("/oauth/callback")
async def oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Google redirects the user's browser here after the consent
    screen. No Authorization header exists on this request — the state
    parameter carries the token that came back from oauth_start, and
    the whole exchange either lands on the settings page with a plain
    success or failure flag for the frontend to show, since there is no
    JSON caller waiting on the other end of a browser redirect."""
    raw_state = state or ""
    token_part, _, return_to = raw_state.partition("::")
    base = settings.FRONTEND_URL.rstrip("/")
    settings_url = (
        f"{base}/onboarding?gmailstep=1" if return_to == "onboarding"
        else f"{base}/settings?tab=email"
    )
    if error:
        return RedirectResponse(f"{settings_url}&gmail=denied")
    if not code or not token_part:
        return RedirectResponse(f"{settings_url}&gmail=error")

    payload = decode_token(token_part)
    if not payload:
        return RedirectResponse(f"{settings_url}&gmail=error")

    try:
        tokens = await gmail_service.exchange_code(code)
        refresh_token = tokens.get("refresh_token")
        gmail_address = gmail_service.email_from_id_token(tokens.get("id_token", ""))
        if not refresh_token or not gmail_address:
            # Google omits refresh_token on a repeat consent for an
            # account that never revoked the last one — the fix is
            # revoking access at myaccount.google.com/permissions once,
            # which forces prompt=consent to actually issue a new one.
            return RedirectResponse(f"{settings_url}&gmail=noconsent")

        res = await db.execute(select(Profile).where(Profile.user_id == uuid.UUID(payload["sub"])))
        profile = res.scalar_one_or_none()
        if not profile:
            return RedirectResponse(f"{settings_url}&gmail=error")

        profile.gmail_address = gmail_address
        profile.gmail_refresh_token_encrypted = crypto.encrypt(refresh_token)
        profile.gmail_connected_at = datetime.now(timezone.utc)
        await db.commit()
        return RedirectResponse(f"{settings_url}&gmail=connected")
    except Exception as ex:
        log.error(f"Gmail OAuth callback failed: {ex}")
        return RedirectResponse(f"{settings_url}&gmail=error")


@router.delete("/oauth/disconnect")
async def oauth_disconnect(
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Profile).where(Profile.user_id == u.id))
    profile = res.scalar_one_or_none()
    if profile:
        profile.gmail_address = None
        profile.gmail_refresh_token_encrypted = None
        profile.gmail_connected_at = None
        await db.commit()
    return {"gmail_connected": False}


@router.post("/draft", status_code=201)
async def create_draft(
    body: EmailDraftIn,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    saved_job_id = None
    if body.job_id:
        job = await db.get(Job, uuid.UUID(body.job_id))
        if not job or job.user_id != u.id:
            raise HTTPException(404, "Job not found")
        job_parsed = job.parsed_data or {}
        saved_job_id = job.id
    else:
        # pasted directly into this flow, parsed for this one email only,
        # never written to the jobs table
        job_parsed = await ai_service.parse_job(body.job_description or "")

    resume = await db.get(Resume, uuid.UUID(body.resume_id))
    if not resume or resume.user_id != u.id:
        raise HTTPException(404, "Resume not found")

    res = await db.execute(select(Profile).where(Profile.user_id == u.id))
    profile = res.scalar_one_or_none()
    knowledge_graph = (profile.knowledge_graph if profile else None) or None
    custom_instructions = (profile.custom_instructions if profile else None) or ""

    fit = await ai_service.analyze_fit(resume.parsed_data or {}, job_parsed)
    name = (resume.parsed_data or {}).get("name") or u.full_name or ""
    drafted = await ai_service.generate_email(
        name=name,
        job_parsed=job_parsed,
        fit=fit,
        extra_context=body.extra_context,
        knowledge_graph=knowledge_graph,
        resume_parsed=resume.parsed_data or {},
        custom_instructions=custom_instructions,
        linkedin_url=(profile.linkedin_url if profile else None) or "",
        github_url=(profile.github_url if profile else None) or "",
    )

    e = EmailSend(
        user_id=u.id,
        job_id=saved_job_id,
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
    use_gmail = bool(profile and profile.gmail_refresh_token_encrypted)
    use_smtp = bool(profile and profile.smtp_password_encrypted)
    # A user's own address always wins over the shared SendGrid sender:
    # both Gmail OAuth and the app password path send from the applicant's
    # literal mailbox, which lands in the inbox and reads as genuinely
    # from them. SendGrid is only the zero setup fallback for someone who
    # has connected nothing of their own yet.
    use_sendgrid = bool(not use_gmail and not use_smtp and sendgrid_service.is_configured())
    if not (use_gmail or use_smtp or use_sendgrid):
        raise HTTPException(
            422,
            "No sending account is configured yet. Add your own email address and app password in "
            "settings so applications send from your mailbox.",
        )

    # The resume goes out attached to every application email, no
    # exceptions — an application email without the resume document is a
    # worse first impression than no email at all. If the stored file is
    # gone (the upload disk on the host is wiped on every redeploy), the
    # send is refused with a clear ask to upload the resume again rather
    # than quietly sending without it.
    attachment_bytes = None
    attachment_filename = None
    if e.resume_id:
        resume = await db.get(Resume, e.resume_id)
        if resume:
            # Postgres copy first — it survives redeploys, which wipe the
            # container disk. The disk path only matters for rows uploaded
            # before file bytes were stored in the database.
            if resume.file_data:
                attachment_bytes = resume.file_data
            elif resume.file_path:
                try:
                    with open(resume.file_path, "rb") as fh:
                        attachment_bytes = fh.read()
                except OSError:
                    pass
            if attachment_bytes:
                attachment_filename = resume.filename or "resume.pdf"
    if not attachment_bytes:
        raise HTTPException(
            422,
            "The resume file for this draft is not stored on the server, and every application "
            "email must carry the resume attached as a document. This happens for resumes uploaded "
            "before attachments were added. Upload your resume once more, create a new draft, and "
            "send that one — from then on the file is kept in the database and survives every "
            "redeploy.",
        )

    try:
        if use_gmail:
            # The path that actually works from Render: HTTPS to the
            # Gmail API, never blocked, unlike raw SMTP on this host.
            # Preferred whenever both are connected, since it is also
            # the more reliable path on any host.
            refresh_token = crypto.decrypt(profile.gmail_refresh_token_encrypted)
            msg = email_service.build_message(
                sender_email=profile.gmail_address,
                recipient_email=e.recipient_email,
                subject=e.subject,
                body=e.body,
                attachment_bytes=attachment_bytes,
                attachment_filename=attachment_filename,
            )
            await gmail_service.send_message(refresh_token, msg)
        elif use_smtp:
            # The user connected their own address with a Gmail app
            # password. Render blocks outbound SMTP, so in production this
            # goes through the external relay (relay/), which does the SMTP
            # leg from a host that allows it — the message still leaves the
            # user's own mailbox. Falls back to a direct SMTP connection
            # only when no relay is configured (local dev / docker compose,
            # where outbound SMTP works).
            password = crypto.decrypt(profile.smtp_password_encrypted)
            smtp_args = dict(
                smtp_host=profile.smtp_host,
                smtp_port=profile.smtp_port or 587,
                smtp_username=profile.smtp_username,
                smtp_password=password,
                sender_email=profile.sender_email,
                recipient_email=e.recipient_email,
                subject=e.subject,
                body=e.body,
                attachment_bytes=attachment_bytes,
                attachment_filename=attachment_filename,
            )
            if email_service.relay_configured():
                await email_service.send_via_relay(**smtp_args)
            else:
                await email_service.send_email(**smtp_args)
        elif use_sendgrid:
            # The default path: works for every user with nothing set up
            # on their end. Reply To carries the applicant's own address
            # so a recruiter's reply still reaches them, even though the
            # message technically leaves from ApplyPilot's one verified
            # sender rather than the applicant's literal mailbox.
            rp = (resume.parsed_data or {}) if resume else {}
            reply_email = rp.get("email") or (profile.sender_email if profile else None) or u.email
            reply_name = rp.get("name") or u.full_name or "Applicant"
            msg = email_service.build_message(
                sender_email=settings.SENDGRID_FROM_EMAIL,
                recipient_email=e.recipient_email,
                subject=e.subject,
                body=e.body,
                attachment_bytes=attachment_bytes,
                attachment_filename=attachment_filename,
            )
            await sendgrid_service.send_message(msg, reply_email, reply_name)
        e.status = "sent"
        e.sent_at = datetime.now(timezone.utc)
        e.error_msg = None
        await db.commit()
    except gmail_service.GmailReauthRequired as ex:
        # The stored connection is genuinely dead (7 day Testing mode
        # expiry, or the user revoked access at myaccount.google.com) —
        # clearing it here is what makes Settings show Connect Gmail
        # again instead of a green Connected badge that lies.
        profile.gmail_address = None
        profile.gmail_refresh_token_encrypted = None
        profile.gmail_connected_at = None
        e.status = "failed"
        e.error_msg = str(ex)[:400]
        await db.commit()
        raise HTTPException(401, f"Could not send the email. {e.error_msg}")
    except Exception as ex:
        e.status = "failed"
        e.error_msg = str(ex)[:400]
        await db.commit()
        raise HTTPException(502, f"Could not send the email. {e.error_msg}")

    await db.refresh(e)
    return _out(e)
