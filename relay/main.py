"""
ApplyPilot SMTP relay
---------------------
Render blocks all outbound SMTP (ports 25, 587, 465) network wide on
every plan, so the main ApplyPilot backend cannot connect to
smtp.gmail.com directly. This tiny service runs on a host that DOES allow
outbound SMTP (Fly.io) and does exactly one thing: accept an already
built email over HTTPS from the backend and forward it once over SMTP,
using the sending user's own Gmail address and app password, so the
message genuinely leaves the user's own mailbox.

It stores nothing. The Gmail app password arrives in the request body
over HTTPS, is used for a single login, and is discarded when the request
ends. The one endpoint is guarded by a shared secret (RELAY_SECRET) so
only the ApplyPilot backend, which is the only other holder of that
secret, can ask it to send anything.
"""
import base64
import os
import smtplib
import ssl

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

RELAY_SECRET = os.environ["RELAY_SECRET"]

app = FastAPI(title="ApplyPilot SMTP relay", docs_url=None, redoc_url=None)


class SendIn(BaseModel):
    host: str
    port: int
    username: str
    password: str
    sender: str
    recipient: str
    raw_message_b64: str


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/send")
def send(body: SendIn, authorization: str = Header("")):
    # Constant-ish check is fine here; the secret is long and random, and
    # the endpoint is not otherwise discoverable. Reject anything that is
    # not our backend before doing any SMTP work.
    if authorization != f"Bearer {RELAY_SECRET}":
        raise HTTPException(401, "Bad relay secret")

    raw = base64.b64decode(body.raw_message_b64)
    ctx = ssl.create_default_context()

    try:
        if body.port == 465:
            with smtplib.SMTP_SSL(body.host, body.port, timeout=30, context=ctx) as server:
                server.login(body.username, body.password)
                server.sendmail(body.sender, [body.recipient], raw)
        else:
            with smtplib.SMTP(body.host, body.port, timeout=30) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                server.login(body.username, body.password)
                server.sendmail(body.sender, [body.recipient], raw)
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(
            401,
            "Gmail rejected the address and app password. Confirm two step verification is on "
            "and the sixteen character app password was generated for this account.",
        )
    except Exception as ex:  # noqa: BLE001 — surface any SMTP failure verbatim to the backend
        raise HTTPException(502, f"SMTP send failed: {ex}")
    return {"sent": True}
