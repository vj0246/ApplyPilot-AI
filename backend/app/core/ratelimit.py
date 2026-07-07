"""
ratelimit.py
------------
A single shared slowapi Limiter, keyed by the real client IP. Behind
Render's proxy request.client.host is the proxy, so the client address
has to come from the first hop in X-Forwarded-For or every user would
share one bucket. In memory storage is fine for a single instance; move
to Redis storage here if this ever scales past one process.
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip)
