"""
http.py
-------
Small HTTP layer helpers shared across routers.
"""
import uuid

from fastapi import HTTPException


def parse_uuid(value: str, name: str = "id") -> uuid.UUID:
    """Parse a client supplied id string into a UUID, turning a malformed
    value into a clean 404 instead of letting uuid.UUID() raise ValueError
    and surface as an unhandled 500. Used for ids that arrive inside a JSON
    body (path params are already validated by FastAPI's uuid.UUID type)."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        raise HTTPException(404, f"{name} not found")
