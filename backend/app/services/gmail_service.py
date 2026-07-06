"""
gmail_service.py
-----------------
Sends the application email through the Gmail API over HTTPS, from the
user's own Gmail account, after they connect it once with OAuth.

This exists because Render blocks outbound SMTP (ports 25, 587, 465)
network wide on every plan — raw SMTP delivery can never leave a Render
container, no matter how the sockets are built. HTTPS on port 443 is
never blocked, and the Gmail API accepts a full RFC 822 message, so the
exact same MIME message the SMTP path builds (plain text plus HTML plus
the resume attachment) goes out unchanged, genuinely from the user's own
mailbox.

Scope requested is gmail.send only — this app can send as the user, it
can never read their inbox. The refresh token is stored Fernet encrypted
on the profile, same treatment as the SMTP app password, and exchanged
for a short lived access token on every send.
"""
import base64
import logging
from email.mime.multipart import MIMEMultipart
from typing import Optional
from urllib.parse import urlencode

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)

class GmailReauthRequired(RuntimeError):
    """Raised specifically when Google rejects the stored refresh token
    itself (expired, revoked, or the account disconnected access) rather
    than some other send failure. The router catches this exact type to
    clear the stale connection, so the profile stops claiming Gmail is
    connected when Google no longer honors it — a bare RuntimeError here
    would leave the UI showing 'connected' forever after the 7 day
    Testing mode expiry actually hits."""


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
SCOPES = "https://www.googleapis.com/auth/gmail.send openid email"


def is_configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def redirect_uri() -> str:
    return f"{settings.BACKEND_URL.rstrip('/')}/api/v1/email/oauth/callback"


def build_auth_url(state: str) -> str:
    # access_type=offline + prompt=consent is what makes Google return a
    # refresh token — without both, reconnecting silently yields only a
    # short lived access token and sending breaks an hour later.
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    """Trade the one time authorization code for tokens. Returns the raw
    token response; the caller keeps refresh_token and reads the account
    email out of the id_token."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(TOKEN_URL, data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri(),
        })
    if resp.status_code != 200:
        log.error(f"Gmail code exchange failed: {resp.status_code} {resp.text[:300]}")
        raise RuntimeError("Google rejected the authorization code. Try connecting again.")
    return resp.json()


def email_from_id_token(id_token: str) -> Optional[str]:
    # The id_token is a JWT from Google over TLS on the token endpoint —
    # its payload is read here for the account email, not used as an
    # authentication proof, so decoding without signature verification is
    # fine in this one spot.
    try:
        payload_b64 = id_token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        import json
        return json.loads(base64.urlsafe_b64decode(payload_b64)).get("email")
    except Exception:
        return None


async def _access_token(refresh_token: str) -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(TOKEN_URL, data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
    if resp.status_code != 200:
        log.error(f"Gmail token refresh failed: {resp.status_code} {resp.text[:300]}")
        try:
            error_code = resp.json().get("error")
        except Exception:
            error_code = None
        if error_code == "invalid_grant":
            raise GmailReauthRequired(
                "This Gmail connection has expired or was revoked. Connect Gmail again in settings."
            )
        raise RuntimeError(
            "Google could not refresh this Gmail connection right now. Try again shortly, or "
            "disconnect and reconnect Gmail in settings if this keeps happening."
        )
    return resp.json()["access_token"]


async def send_message(refresh_token: str, msg: MIMEMultipart) -> None:
    """Send a fully built MIME message through the Gmail API. Gmail sets
    the authenticated account as the real sender regardless of the From
    header, which is exactly the honesty this app wants."""
    token = await _access_token(refresh_token)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            SEND_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"raw": raw},
        )
    if resp.status_code not in (200, 202):
        log.error(f"Gmail send failed: {resp.status_code} {resp.text[:500]}")
        # Google's own error message is the only way to tell "Gmail API
        # not enabled on this project" apart from "scope was never
        # actually granted" apart from "account not a registered test
        # user" — three completely different fixes that all produce a
        # bare 403 with no other signal, so it is surfaced verbatim
        # instead of guessed at.
        reason = resp.text[:300]
        try:
            reason = resp.json().get("error", {}).get("message", reason)
        except Exception:
            pass
        raise RuntimeError(
            f"Gmail refused to send the message (status {resp.status_code}): {reason}"
        )
