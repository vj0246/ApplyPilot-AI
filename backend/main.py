"""ApplyPilot — FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.ratelimit import limiter
from app.routers import auth, profile, resumes, jobs, applications, autofill, email, apply_chat

# Cap request bodies. The only large legitimate body is a resume upload, so
# allow the file limit plus a couple MB of multipart overhead and reject
# anything bigger before it is read into memory.
_MAX_BODY_BYTES = (settings.MAX_FILE_SIZE_MB + 2) * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


_IS_PROD = settings.ENVIRONMENT == "production"

app = FastAPI(
    title="ApplyPilot API",
    description="AI-powered job application assistant",
    version="1.0.0",
    # The interactive docs, ReDoc, and the OpenAPI schema enumerate every
    # route and body shape — useful in development, a free map of the
    # attack surface in production. Off when running as production.
    docs_url=None if _IS_PROD else "/docs",
    redoc_url=None if _IS_PROD else "/redoc",
    openapi_url=None if _IS_PROD else "/openapi.json",
    lifespan=lifespan,
)

# ── Rate limiting ─────────────────────────────────────────────
# The Limiter is shared from app.core.ratelimit so routers can decorate
# individual endpoints (see auth.py). A 429 is returned by slowapi's own
# handler when a bucket is exhausted.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Request body size cap ─────────────────────────────────────
@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > _MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Request body too large."})
    return await call_next(request)


# ── Security headers ──────────────────────────────────────────
@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if _IS_PROD:
        resp.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )
    return resp


# ── Middleware ────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    # Vercel serves preview deploys on generated subdomains like
    # applypilot-<hash>-<account>.vercel.app. The regex admits only this
    # project's own subdomains, not every *.vercel.app on the internet
    # (anyone can deploy one of those), which would otherwise be a trusted
    # cross origin.
    allow_origin_regex=r"https://apply-?pilot[a-z0-9-]*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────
app.include_router(auth.router,         prefix="/api/v1")
app.include_router(profile.router,      prefix="/api/v1")
app.include_router(resumes.router,      prefix="/api/v1")
app.include_router(jobs.router,         prefix="/api/v1")
app.include_router(applications.router, prefix="/api/v1")
app.include_router(autofill.router,     prefix="/api/v1")
app.include_router(email.router,        prefix="/api/v1")
app.include_router(apply_chat.router,   prefix="/api/v1")

# ── Health ────────────────────────────────────────────────────
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/.well-known/security.txt", include_in_schema=False)
async def security_txt():
    body = (
        "Contact: mailto:vivaan.jain246@gmail.com\n"
        "Preferred-Languages: en\n"
    )
    return PlainTextResponse(body, media_type="text/plain")


@app.exception_handler(404)
async def not_found(req, exc):
    return JSONResponse(status_code=404, content={"detail": "Not found"})


@app.exception_handler(500)
async def server_error(req, exc):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
