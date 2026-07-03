"""
email_service.py
-----------------
Sends the application email from the user's own address, using their own
SMTP app password, not a shared mail server owned by this app. Plain
smtplib in a background thread rather than a third party email API, so the
message genuinely comes from the user's mailbox and nothing about the
content passes through another company's servers beyond the mail provider
the user already trusts with their inbox.

This module only ever runs from the explicit POST /email/{id}/send call in
app/routers/email.py, never automatically after a draft is written. Same
human in the loop rule as the form autofill: the AI drafts, a person
decides when it actually goes out.
"""
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


def _send_sync(
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    sender_email: str,
    recipient_email: str,
    subject: str,
    body: str,
) -> None:
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(sender_email, [recipient_email], msg.as_string())


async def send_email(
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    sender_email: str,
    recipient_email: str,
    subject: str,
    body: str,
) -> None:
    # smtplib is blocking, so this runs on a worker thread instead of
    # tying up the event loop for the several seconds a real SMTP
    # handshake and send can take
    await asyncio.to_thread(
        _send_sync,
        smtp_host, smtp_port, smtp_username, smtp_password,
        sender_email, recipient_email, subject, body,
    )
