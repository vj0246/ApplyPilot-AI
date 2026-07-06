"""
sendgrid_service.py
--------------------
Sends the application email through SendGrid's HTTP API, from one
verified sender address shared across every user of this app. This is
the mail path that works for literally anyone the moment they sign up,
no per person setup, no Google account, no waiting list.

The tradeoff, stated plainly: the email does not literally leave the
applicant's own Gmail account the way the OAuth path does. It leaves
from ApplyPilot's one verified sender, with the applicant's real name in
the display name and their real address set as Reply To, so a recruiter
who hits reply reaches the actual person, not this app. That distinction
is disclosed to the user before they send, in app/routers/email.py.

SendGrid was chosen specifically because its Single Sender Verification
needs no domain or DNS record — just clicking a confirmation link
SendGrid emails to one address — which is the whole point: this path
must never require anything from the app's users, and should require as
little as possible from whoever runs this app either.
"""
import base64
import logging
from email.mime.multipart import MIMEMultipart
from typing import Optional

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)

SEND_URL = "https://api.sendgrid.com/v3/mail/send"


def is_configured() -> bool:
    return bool(settings.SENDGRID_API_KEY and settings.SENDGRID_FROM_EMAIL)


def _extract_parts(msg: MIMEMultipart):
    """Pulls the plain text body, the HTML body, and any attachment back
    out of the MIME message built by email_service.build_message, so
    this path can reuse that exact same message construction instead of
    duplicating the layout and attachment logic a second time."""
    plain, html, attachment = None, None, None
    for part in msg.walk():
        ctype = part.get_content_type()
        disp = str(part.get("Content-Disposition") or "")
        if "attachment" in disp:
            attachment = {
                "content": base64.b64encode(part.get_payload(decode=True)).decode(),
                "filename": part.get_filename() or "resume.pdf",
                "type": ctype,
                "disposition": "attachment",
            }
        elif ctype == "text/plain" and plain is None:
            plain = part.get_payload(decode=True).decode(errors="replace")
        elif ctype == "text/html" and html is None:
            html = part.get_payload(decode=True).decode(errors="replace")
    return plain, html, attachment


async def send_message(
    msg: MIMEMultipart,
    reply_to_email: str,
    reply_to_name: str,
) -> None:
    subject = msg["Subject"]
    recipient = msg["To"]
    plain, html, attachment = _extract_parts(msg)

    content = []
    if plain:
        content.append({"type": "text/plain", "value": plain})
    if html:
        content.append({"type": "text/html", "value": html})

    payload = {
        "personalizations": [{"to": [{"email": recipient}]}],
        "from": {"email": settings.SENDGRID_FROM_EMAIL, "name": f"{reply_to_name} via ApplyPilot"},
        "reply_to": {"email": reply_to_email, "name": reply_to_name},
        "subject": subject,
        "content": content or [{"type": "text/plain", "value": ""}],
    }
    if attachment:
        payload["attachments"] = [attachment]

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            SEND_URL,
            headers={
                "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if resp.status_code not in (200, 202):
        log.error(f"SendGrid send failed: {resp.status_code} {resp.text[:500]}")
        reason = resp.text[:300]
        try:
            errors = resp.json().get("errors")
            if errors:
                reason = "; ".join(e.get("message", "") for e in errors)
        except Exception:
            pass
        raise RuntimeError(f"SendGrid refused to send the message (status {resp.status_code}): {reason}")
