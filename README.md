<div align="center">

# ApplyPilot

**An AI job application assistant that fills real application forms and mails tailored applications — with a human reviewing every step.**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black?logo=next.js)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Groq](https://img.shields.io/badge/AI-Groq-F55036)](https://groq.com)

</div>

---

## What it does

A user builds a profile once — resume, a personal knowledge graph, an
optional email connection — then does two core things:

1. **Fill a form.** Paste a real Google Forms or Microsoft Forms link and
   get back a pre-filled link with every field answered from the resume and
   knowledge graph. The user reviews it and submits it themselves.
2. **Mail an application.** A tailored application email is drafted from the
   job description, then sent from the user's own address with the resume
   attached.

**Human in the loop, by design.** Nothing is ever submitted or sent
automatically. Autofill never clicks submit. Drafting and sending an email
are two separate, explicit steps. The AI gets it most of the way; the
person owns the final action.

## Stack

| Layer    | Choice                                                            |
| -------- | ---------------------------------------------------------------- |
| Backend  | FastAPI, async SQLAlchemy 2, asyncpg, Python 3.11                 |
| Browser  | Playwright (headless Chromium) drives the real form pages         |
| AI       | Groq (`openai/gpt-oss-120b`), every function has a regex fallback |
| Frontend | Next.js 14 App Router, React Query, Zustand, Tailwind, TypeScript |
| Database | Postgres (Neon in production)                                    |
| Deploy   | Backend on Render (Docker), frontend on Vercel, database on Neon  |

## Architecture

```
Browser (Next.js, JWT in Authorization header)
      │  REST
FastAPI backend
      ├── routers: auth · profile · resumes · jobs · applications · autofill · email
      ├── FastAPI BackgroundTasks (no Celery/Redis) for the slow work
      └── services:
             ai_service        every Groq call + a regex fallback each
             autofill_service  Playwright scrape + fill, SSRF-guarded URL allowlist
             email_service      MIME build, SMTP / relay send
             gmail_service      Gmail OAuth HTTPS send
             resume_service     PDF/DOCX/TXT text extraction
      │
      ├── Groq API (openai/gpt-oss-120b)
      └── PostgreSQL — users · profiles · resumes · jobs · applications · autofill_runs · email_sends
```

Every AI function keeps a non-AI fallback, so a Groq outage degrades
quality, never availability.

## Security posture

Written for reviewers — the controls that are actually in the code:

- **Authentication** — bcrypt password hashing; JWT bearer tokens carried
  in the `Authorization` header and held in `sessionStorage`, not cookies.
- **Access control** — every protected route resolves the user from the
  token server side, and every resource query is scoped to that user's id
  (no object reference is trusted from the client).
- **Secrets at rest** — the stored email app password and the Gmail refresh
  token are Fernet encrypted (`app/core/crypto.py`). Startup **fails** in
  production if `SECRET_KEY` is the shipped development default or shorter
  than 32 characters (`app/core/config.py`).
- **SSRF boundary** — the form URL that drives a Playwright navigation is
  validated by exact hostname allowlist over `https` only, never a
  substring match (`autofill_service.is_supported_form_url`).
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Cross-Origin-Opener-Policy`, and HSTS in production.
- **Reduced surface in production** — interactive docs, ReDoc, and the
  OpenAPI schema are disabled when `ENVIRONMENT=production`.
- **Human in the loop** — no form is submitted and no email is sent without
  an explicit user action on a reviewed draft.

## Running locally

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install --with-deps chromium
cp .env.example .env        # fill in the values
uvicorn main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Backend serves on `:8000`, frontend on `:3000`. A free Groq key from
[console.groq.com](https://console.groq.com) is the only thing needed to
make the AI work.

## Environment variables

Names only, never commit values. Template in `backend/.env.example`.

| Variable                                    | Purpose                                                     |
| ------------------------------------------- | ----------------------------------------------------------- |
| `DATABASE_URL`                              | `postgresql+asyncpg://...?ssl=require` (asyncpg driver)      |
| `SECRET_KEY`                                | JWT signing + Fernet key derivation; strong, never rotated  |
| `GROQ_API_KEY`                              | One key, or a comma separated list rotated on rate limit    |
| `GROQ_MODEL`                                | Defaults to `openai/gpt-oss-120b`                           |
| `FRONTEND_URL`                              | Exact origin allowed by CORS                                |
| `ENVIRONMENT`                               | `production` disables docs and enforces secret strength     |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Optional Gmail OAuth send path                              |
| `BACKEND_URL`                               | Public backend URL, for the OAuth redirect                  |
| `RELAY_URL` / `RELAY_SECRET`                | Optional SMTP relay for the app-password send path          |

## Email sending

No shared server side sender exists; every email leaves from the user's own
address. Paths, in preference order at send time:

1. **Open in my mail app** — universal, nothing to configure. Opens the
   user's own mail client pre-filled and downloads the resume for a one
   click attach (browsers block programmatic `mailto:` attachments).
2. **Gmail OAuth** — one click server side send from the user's own Gmail
   over the Gmail HTTPS API. While the OAuth app is unverified, only Google
   test users can connect.
3. **SMTP app password** — dormant in production (Render blocks outbound
   SMTP); works self-hosted, or through the optional `relay/` service.

## Schema changes

No migration tool. `db/init.sql` is kept in sync with `app/models.py` by
hand, and every schema change needs a manual `ALTER` run against the
database before the next deploy.

## License

MIT.
