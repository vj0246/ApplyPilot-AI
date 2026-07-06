# ApplyPilot — CLAUDE.md

AI job application assistant, multi tenant, live in production. Users build a
profile (resume, personal knowledge graph, email account), then two core
actions: fill a real Google/Microsoft form from a pasted link, and mail a
tailored application email from their own address with the resume attached.

## Stack

- **Backend**: FastAPI + async SQLAlchemy 2 + asyncpg, Python 3.11.
  Playwright (headless Chromium) drives real form pages. Groq is the only
  LLM provider.
- **Frontend**: Next.js 14 App Router, React Query, Zustand, Tailwind.
- **Database**: Postgres (Neon in production, `db/init.sql` is the schema).
- **Deploy**: backend = Render Docker web service (`render.yaml`,
  `backend/Dockerfile`), frontend = Vercel (root directory `frontend`),
  database = Neon.

## Layout

```
backend/
  main.py                    FastAPI app, CORS
  app/core/config.py         settings; GROQ_API_KEY accepts comma separated keys
  app/core/crypto.py         Fernet encrypt/decrypt keyed by SHA256(SECRET_KEY)
  app/models.py              User, Profile, Resume, Job, Application,
                             AutofillRun, EmailSend
  app/routers/               auth, profile, resumes, jobs, applications,
                             autofill, email
  app/services/
    ai_service.py            ALL AI calls; every function has a regex fallback
    autofill_service.py      form scraping/filling + pre-filled link building
    email_service.py         SMTP send, dual stack connect, HTML alternative
    resume_service.py        file save + text extraction
frontend/src/
  app/(app)/apply/page.tsx   the two core actions (tab in URL: ?tab=googleform|email)
  app/(app)/settings/page.tsx  profile, custom instructions, My Memory editor
  app/(app)/dashboard/page.tsx hub: two action cards + setup checklist
  components/layout/Sidebar.tsx  nav sections: Apply / Your Profile / More Tools
  lib/api.ts                 all API clients
db/init.sql                  full schema; keep in sync with models.py BY HAND
render.yaml                  Render blueprint (backend only)
```

## Product rules (do not violate)

1. **Human in the loop, always.** Nothing is ever submitted or sent
   automatically. Autofill never clicks submit. Email drafting and sending
   are two separate explicit calls. Never "fix" this by auto submitting.
2. **Writing standards** (`WRITING_STANDARDS` in `ai_service.py`), applied to
   every generated text: no abbreviations or acronyms, never any hyphen or
   dash, high impact humanized prose, and **all money exclusively in Indian
   Rupees**.
3. **Application email layout is fixed** (user specified sample): Dear Hiring
   Team, / I hope you are doing well. / interest paragraph / projects
   paragraph / honest alignment paragraph / contribution paragraph / thanks /
   Kind regards, name, "Resume Attached", "LinkedIn: <link>", "GitHub:
   <link>". Links copied character for character from the parsed resume.
4. **Resume attachment is compulsory** on every send; refuse loudly if the
   file is unavailable rather than sending without it.
5. **Never store or replay a user's real Google password.** Sign in walls on
   Google Forms (file upload questions) stay manual by explicit decision.
6. **Memory grows, never silently shrinks.** The knowledge graph interview
   merges additively (`merge_knowledge_graph`). Only the explicit
   PUT /profile/knowledge-graph (the memory editor) replaces it.

## AI layer

- Model: `openai/gpt-oss-120b` on Groq (`GROQ_MODEL`). **llama-3.3-70b was
  retired from the Groq lineup** — a missing model name fails every call and
  everything silently degrades to regex-fallback quality. If all output goes
  generic across the board, check the model name against Groq's model list
  FIRST, then quota.
- `GROQ_API_KEY` accepts a comma separated key list; `_chat()` rotates to the
  next key on RateLimitError/AuthenticationError/PermissionDeniedError. Groq
  rate limits are per account, so extra keys only help if they come from
  genuinely separate accounts.
- gpt-oss sometimes returns a JSON array or a wrapper object where a dict was
  requested. Every `_json_chat` call site coerces shape (see the
  `isinstance(result, list)` guards). Keep that pattern for new AI functions.
- Every AI function must keep a non-AI fallback so a Groq outage degrades
  quality, never availability, and the email fallback must keep the exact
  layout above.
- Personalization inputs threaded into prompts: `Profile.knowledge_graph`,
  `Profile.custom_instructions` (user's own standing tone/format
  instructions), `Profile.learned_answers` (see below). New writer functions
  should accept and inject all three.

## Form autofill (the hard-won knowledge)

- Google publishes no forms API. Scraping is ARIA role based
  (`div[role='listitem']`, `[role='radio']`, `[role='checkbox']`,
  `[role='listbox']`).
- **Pre-filled link**: `entry.<id>=value` params on the viewform URL. The id
  MUST be the **nested** number in `data-params` (after `[[`), NOT the first
  number (that is the question id — using it makes Google silently render the
  form blank). See `_read_entry_id`. Entry ids must be pure digits; one
  malformed param (for example `entry.X_sentinel`) makes Google discard
  prefilling for the ENTIRE page.
- **Grid questions** (`_looks_like_grid`: option labels contain ", response
  for ") are skipped entirely — they scrape as one garbled flat question and
  their ids are grid plumbing.
- Choice fields with unreadable options are left blank rather than stuffed
  with free text (free text in a choice param corrupts the link).
- Answer length hints ride on each question: "single line box" vs "long
  answer box". Keep them when touching `get_answers_for_fields`.
- Result fields carry `index`, `entry_id`, `options` so answers are editable
  on the site afterward: PATCH `/autofill/{id}/answers` validates choice
  edits against options, rebuilds the link (`rebuild_prefilled_url`), and
  stores each correction in `Profile.learned_answers` (newest first, cap
  100). Those learned answers are injected into every future form run as
  preferred answers — the human in the loop learning path.

## Email sending

- From the user's own mailbox: SMTP app password, Fernet encrypted at rest
  (`smtp_password_encrypted`), decrypted only in memory at send time.
- Message shape: multipart/mixed [ multipart/alternative [ plain, HTML
  derived from the plain text at send time ], resume attachment ]. Plain
  text is what the user approved; HTML is derived so they never drift.
- Connect logic (`_connect_any`): resolve all addresses, IPv4 first, then
  IPv6; try configured port, then 587 STARTTLS, then 465 implicit TLS.
  SMTPAuthenticationError short circuits (a different port never fixes bad
  credentials).
- **Render blocks outbound SMTP (25/587/465) network wide on all plans.**
  Raw SMTP delivery cannot work from Render, period, no matter how the
  sockets are built. That is why `gmail_service.py` exists: it sends the
  exact same MIME message (built once in `email_service.build_message`,
  shared by both paths) through the Gmail API over HTTPS instead, which is
  never blocked. `POST /email/{id}/send` prefers Gmail whenever
  `Profile.gmail_refresh_token_encrypted` is set, and falls back to SMTP
  otherwise — SMTP still works fine locally and in docker compose, and stays
  as the path for any provider besides Gmail.
- Gmail OAuth flow: `GET /email/oauth/start` (authenticated) returns
  Google's consent URL, with the caller's own JWT as the `state` parameter —
  the callback is a plain browser redirect from Google with no Authorization
  header, so the JWT round tripped through `state` is what tells
  `GET /email/oauth/callback` (public) whose profile to attach the refresh
  token to. Requires `access_type=offline` and `prompt=consent` on every
  request or Google omits the refresh token on a repeat consent — if a user
  reports "noconsent", the fix is revoking access at
  myaccount.google.com/permissions once, not a code change. Needs
  `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `BACKEND_URL` set (see
  `render.yaml` comment for the exact Google Cloud console setup); with them
  unset the whole feature hides itself (`GET /email/oauth/status`) rather
  than breaking the SMTP path.

## Storage gotchas

- **Render's container disk is wiped on every deploy.** Anything that must
  survive lives in Postgres. Resume file bytes are stored in
  `resumes.file_data` (BYTEA); the disk path is only a same-deploy cache.
  Never design a feature that depends on an uploaded file still being on
  disk later.
- No migration tool. `db/init.sql` is kept in sync with `models.py` by hand,
  and **every schema change needs a manual ALTER run in the Neon SQL editor**
  or production 500s on the next deploy. Applied so far beyond the base
  schema: profiles.custom_instructions TEXT, profiles.learned_answers JSONB
  DEFAULT '[]', resumes.file_data BYTEA, profiles.gmail_address VARCHAR(320),
  profiles.gmail_refresh_token_encrypted TEXT.

## Deploy pitfalls (each cost a real outage)

- `python:3.11-slim` drifted to Debian trixie and broke
  `playwright install --with-deps` → base image pinned to
  `python:3.11-slim-bookworm`. Keep `--with-deps` (without it Chromium lacks
  OS libraries: "Missing libraries: libglib-2.0.so.0 ...").
- `passlib==1.7.4` breaks against `bcrypt>=4.1` → `bcrypt==4.0.1` pinned as
  its own line in requirements.txt. Do not "upgrade" it.
- Neon connection string: `postgresql+asyncpg://...?ssl=require`. asyncpg
  rejects `?sslmode=require` and `&channel_binding=require` (Neon's copy
  button includes both).
- CORS: exact `FRONTEND_URL` plus `allow_origin_regex=r"https://.*\.vercel\.app"`
  for preview deploys.
- Render and Vercel deploy independently and asynchronously from GitHub.
  When live behavior contradicts pushed code, confirm the commit hash shown
  as Live in the Render Events tab before debugging anything else.
- `render.yaml` env values (like GROQ_MODEL) do not reliably overwrite an
  env var that already exists on the service — change it in the Render
  dashboard Environment tab too.

## Frontend conventions

- Pages using `useSearchParams` are a thin `<Suspense>` shell around an
  Inner component or `next build` fails prerendering.
- The `Textarea` UI component has no forwardRef — react-hook-form
  `register()` silently fails on it; use a plain `<textarea>` for RHF.
- Tab state that the sidebar links into lives in the URL (`?tab=`), with a
  `useEffect` on the param so in-page navigation follows.
- Demo account is removed on purpose. Do not reintroduce seed credentials
  anywhere user visible.

## Verify before pushing

```
cd backend && python -m py_compile app/services/ai_service.py app/routers/*.py
cd frontend && npx tsc --noEmit && npx next build
```

Production smoke test (register a disposable account against
`https://applypilot-ai.onrender.com/api/v1`, upload a text resume, run
`/autofill/form` against a test Google Form, draft an email) is how every
real bug in this project was found. The pre-filled link is only proven by
opening it in a real browser (Playwright locally) and reading input values —
Google applies prefill client side, curl shows nothing.
