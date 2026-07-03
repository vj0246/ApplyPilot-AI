"""
crypto.py
---------
Encrypts the one genuinely sensitive value this app stores: the user's own
email app password, kept so the background email sender can use it later.
Derives a Fernet key from SECRET_KEY rather than asking for a second secret
to manage. Not a substitute for a real secrets manager in production, but
far better than the plain text column this replaced.
"""
import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet() -> Fernet:
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
