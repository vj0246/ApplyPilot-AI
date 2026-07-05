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
import html
import logging
import re
import socket
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

log = logging.getLogger(__name__)


class _IPv4SMTP(smtplib.SMTP):
    """Plain smtplib.SMTP resolves the mail server's hostname with no
    address family preference, and on Render (and several other cloud
    hosts) the container only has an outbound route for IPv4. If Gmail's
    AAAA record comes back first, the connection attempt fails with
    "Network is unreachable" before IPv4 is ever tried. Forcing AF_INET at
    the socket level sidesteps that entirely; the hostname stored on the
    instance for the STARTTLS certificate check is untouched, so
    certificate validation still checks against the real mail server name,
    not the raw IP."""
    def _get_socket(self, host, port, timeout):
        addr_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        family, socktype, proto, _canonname, sockaddr = addr_info[0]
        sock = socket.socket(family, socktype, proto)
        if timeout is not None:
            sock.settimeout(timeout)
        sock.connect(sockaddr)
        return sock


_URL_RE = re.compile(r"https?://[^\s<>\"]+")


def _body_to_html(body: str) -> str:
    """The user drafts and edits plain text; the HTML version is derived
    from it at send time so what they approved and what goes out never
    drift apart. Paragraphs come from blank lines, single newlines become
    line breaks (that's what keeps the signature block stacked), and bare
    URLs become clickable links — which is the whole point of sending an
    HTML part at all: a signature reading github.com/... that the
    recipient can't click is a worse first impression than plain text."""
    paragraphs = []
    for para in re.split(r"\n\s*\n", body.strip()):
        escaped = html.escape(para)
        linked = _URL_RE.sub(
            lambda m: f'<a href="{m.group(0)}" style="color:#3730a3;">{m.group(0)}</a>',
            escaped,
        )
        paragraphs.append(
            f'<p style="margin:0 0 14px 0;">{linked.replace(chr(10), "<br>")}</p>'
        )
    return (
        '<div style="font-family:Georgia,serif;font-size:15px;line-height:1.6;'
        'color:#1f2937;max-width:640px;">'
        + "".join(paragraphs)
        + "</div>"
    )


def _build_message(
    sender_email: str,
    recipient_email: str,
    subject: str,
    body: str,
    attachment_bytes: Optional[bytes] = None,
    attachment_filename: Optional[str] = None,
) -> MIMEMultipart:
    # multipart/mixed wrapping multipart/alternative is the standard shape
    # for "formatted email with an attachment": clients that render HTML
    # show the formatted version, everything else falls back to the exact
    # plain text the user approved, and the resume rides alongside either
    # way.
    msg = MIMEMultipart("mixed")
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject

    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(body, "plain"))
    alternative.attach(MIMEText(_body_to_html(body), "html"))
    msg.attach(alternative)

    if attachment_bytes and attachment_filename:
        part = MIMEApplication(attachment_bytes, Name=attachment_filename)
        part["Content-Disposition"] = f'attachment; filename="{attachment_filename}"'
        msg.attach(part)
    return msg


def _send_starttls(smtp_host, port, smtp_username, smtp_password, sender_email, recipient_email, msg, timeout):
    with _IPv4SMTP(smtp_host, port, timeout=timeout) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(sender_email, [recipient_email], msg.as_string())


def _send_ssl(smtp_host, port, smtp_username, smtp_password, sender_email, recipient_email, msg, timeout):
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_host, port, timeout=timeout, context=context) as server:
        server.login(smtp_username, smtp_password)
        server.sendmail(sender_email, [recipient_email], msg.as_string())


def _send_sync(
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    sender_email: str,
    recipient_email: str,
    subject: str,
    body: str,
    attachment_bytes: Optional[bytes] = None,
    attachment_filename: Optional[str] = None,
) -> None:
    msg = _build_message(sender_email, recipient_email, subject, body,
                         attachment_bytes, attachment_filename)

    # The port the user configured is tried first. If it hangs rather than
    # cleanly refusing, that is the signature of a network in between
    # silently dropping the connection rather than a real login problem,
    # so falling back to the other common submission port on a fresh
    # connection is worth one extra attempt before giving up. Some cloud
    # hosts' outbound networks (and some receiving mail providers'
    # datacenter IP filtering) allow one of 587 or 465 and not the other.
    attempts = [smtp_port] + [p for p in (587, 465) if p != smtp_port]
    last_error: Exception | None = None

    for port in attempts:
        try:
            if port == 465:
                _send_ssl(smtp_host, port, smtp_username, smtp_password, sender_email, recipient_email, msg, timeout=15)
            else:
                _send_starttls(smtp_host, port, smtp_username, smtp_password, sender_email, recipient_email, msg, timeout=15)
            return
        except smtplib.SMTPAuthenticationError:
            # credentials are wrong, a different port will not fix that,
            # fail immediately with a message that says so plainly
            raise RuntimeError(
                "The mail server rejected the email address or app password. Double check both in "
                "settings, and confirm the app password was generated after two factor authentication "
                "was turned on."
            )
        except (socket.timeout, TimeoutError, OSError) as e:
            last_error = e
            log.warning(f"SMTP send via port {port} failed ({e}), trying next option if any remain")
            continue

    raise RuntimeError(
        f"Could not reach the mail server on any port ({', '.join(str(p) for p in attempts)}). "
        f"The connection attempt itself timed out rather than being refused, which usually means a "
        f"network in between is silently blocking outbound mail traffic rather than the address or "
        f"password being wrong. Last error: {last_error}"
    )


async def send_email(
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    sender_email: str,
    recipient_email: str,
    subject: str,
    body: str,
    attachment_bytes: Optional[bytes] = None,
    attachment_filename: Optional[str] = None,
) -> None:
    # smtplib is blocking, so this runs on a worker thread instead of
    # tying up the event loop for the several seconds a real SMTP
    # handshake and send can take
    await asyncio.to_thread(
        _send_sync,
        smtp_host, smtp_port, smtp_username, smtp_password,
        sender_email, recipient_email, subject, body,
        attachment_bytes, attachment_filename,
    )
