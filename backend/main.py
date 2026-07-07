"""ApplyPilot — FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers import auth, profile, resumes, jobs, applications, autofill, email


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


# ── Security headers ──────────────────────────────────────────
@app.middleware("http")
async def security_headers(request, call_next):
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
    # Vercel serves every deployment on its own generated subdomain
    # (project-hash-account.vercel.app) besides the stable production
    # domain; the regex admits all of them so preview links work too.
    allow_origin_regex=r"https://.*\.vercel\.app",
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

# ── Health ────────────────────────────────────────────────────
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.exception_handler(404)
async def not_found(req, exc):
    return JSONResponse(status_code=404, content={"detail": "Not found"})


@app.exception_handler(500)
async def server_error(req, exc):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
