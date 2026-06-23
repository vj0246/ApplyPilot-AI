<div align="center">

# ApplyPilot

**I was tired of writing the same cover letter 40 times with tiny tweaks. So I built something that does it for me.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black?logo=next.js)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Groq](https://img.shields.io/badge/AI-Groq%20(Free)-F55036)](https://groq.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://docker.com)

[**Live Demo**](https://applypilot.vercel.app) &nbsp;·&nbsp; [**Source**](https://github.com/yourusername/applypilot) &nbsp;·&nbsp; [**Report a bug**](https://github.com/yourusername/applypilot/issues)

*(swap the demo/source links above for your real ones once it's pushed — placeholders for now)*

</div>

---

## 60-second overview

Upload your resume. Paste a job posting. 15 seconds later you have a cover
letter, an application email, a fit score, reworded resume bullets, and
answers to whatever the application form is asking — all written so it
doesn't read like a robot wrote it.

It's a normal 3-tier app: **Next.js** frontend, **FastAPI** backend,
**Postgres** for storage. The "AI" part is just a handful of well-tuned
prompts sent to **Groq's free API** (Llama 3.3 70B) — no OpenAI key, no
credit card, no usage limits that'll surprise you. Everything runs in
Docker, one command, on your own machine.

I built this for myself first. Putting it out there in case it's useful
to anyone else doing the same 100-applications grind.

---

## What I actually built

A working end-to-end product, not a demo:

- **Auth** — register/login with JWT, nothing fancy, no OAuth dance to debug
- **Resume pipeline** — upload PDF/DOCX → AI extracts your whole profile (experience, skills, education, projects) → ATS score
- **Job pipeline** — paste a URL (Greenhouse, Lever, LinkedIn, etc.) or raw text → AI extracts requirements, salary, culture signals
- **Generation pipeline** — the actual "apply" button: fit score → cover letter → email → adapted resume bullets, all in one background job
- **Form filler** — paste any application's questions (Google Form, a custom portal, whatever) and get grounded, specific answers back, not generic filler
- **Application tracker** — a real status pipeline (ready → approved → submitted → interviewing → offered/rejected) with inline editing and notes
- **Settings** — tone preference, job preferences, salary range — feeds into how the AI writes for you

Everything's editable. The AI gets you 90% there; you still own the last
10% before you hit send.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                          BROWSER                                  │
│                Next.js 14 (App Router) · TypeScript                │
│         React Query (server cache) · Zustand (auth state)         │
└───────────────────────────┬─────────────────────────────────────┘
                            │  REST, JWT in Authorization header
┌───────────────────────────▼─────────────────────────────────────┐
│                       FASTAPI BACKEND                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐ │
│  │   auth     │  │  resumes   │  │    jobs    │  │applications│ │
│  │  router    │  │  router    │  │   router   │  │   router   │ │
│  └────────────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘ │
│                        │                │                │       │
│              FastAPI BackgroundTasks (no Celery/Redis)   │       │
│                        │                │                │       │
│         ┌──────────────▼──────┐ ┌───────▼────────┐       │       │
│         │  resume_service.py  │ │  job_service.py │       │       │
│         │  PDF/DOCX → text    │ │  scrape job URL │       │       │
│         └──────────┬───────────┘ └───────┬────────┘       │       │
│                    │                    │                │       │
│                    └────────┬───────────┘                │       │
│                            │                              │       │
│                  ┌──────────▼──────────┐                  │       │
│                  │   ai_service.py     │◄─────────────────┘       │
│                  │  every Groq call    │                          │
│                  │  + regex fallbacks  │                          │
│                  └──────────┬──────────┘                          │
└─────────────────────────────┼─────────────────────────────────────┘
                              │
                   ┌──────────▼──────────┐         ┌──────────────┐
                   │   Groq API (free)   │         │  PostgreSQL  │
                   │  llama-3.3-70b      │         │  5 tables    │
                   └─────────────────────┘         └──────────────┘
```

### The actual "apply" flow, step by step

This is the part people care about, so here's exactly what happens when
you click **Generate**:

```
[resume.parsed_data]      [job.parsed_data]
         │                       │
         └───────────┬───────────┘
                     ▼
            analyze_fit()
       (pure Python, no AI call —
        set intersection on skills,
        weighted score 0–100)
                     │
                     ▼
        generate_cover_letter()
   (Groq call #1 — banned-phrases list
    so it doesn't say "I am excited
    to apply" like every other AI)
                     │
                     ▼
           generate_email()
        (Groq call #2 — subject
         + 3-sentence body)
                     │
                     ▼
       adapt_resume_for_job()
   (Groq call #3 — rewords bullets
    to hit JD keywords, never invents
    a skill you don't have)
                     │
                     ▼
        status = "ready", saved to DB
        frontend was polling, picks
        it up, shows the review page
```

Three Groq calls, ~10-20 seconds total, all inside one background task.
No queue, no worker pool — `FastAPI BackgroundTasks` is genuinely enough
at the scale this needs to run at.

---

## Key decisions (and why)

I went through a real pivot building this, worth being honest about:

### 1. Started with the "proper" enterprise stack — scrapped it

First pass used LangGraph + Celery + Redis + MinIO + Ollama. Technically
more "correct" for a production SaaS, but it meant five extra containers,
a message broker to debug, and a local LLM that needed real hardware to
be fast. For a tool meant to be cloned and run by anyone in one command,
that's the wrong trade. Cut it down to FastAPI + Postgres +
BackgroundTasks. Three containers. If this ever needs to handle real
concurrent load, swapping BackgroundTasks for Celery is a contained
change — it's not architecturally locked in.

### 2. Groq over OpenAI, and over local models (Ollama)

OpenAI means a paid key — dead on arrival for an open-source tool people
should be able to clone and run for free. Local models (Ollama) are free
but need real hardware (8GB+ RAM minimum to not be painfully slow) and a
multi-GB download before the app even works. Groq's free tier
(14,400 requests/min on Llama 3.3 70B) gives free, fast, and zero setup
beyond pasting a key — the best of both.

### 3. No vector DB, no embeddings

Early spec considered storing resume embeddings for "smart" job matching.
Cut it — `analyze_fit()` does a straightforward skill-set intersection
and it's transparent: you can see exactly *why* your fit score is what it
is. A black-box embedding similarity score would be harder to trust and
debug, for a feature most users barely need at this scale.

### 4. Background tasks poll, they don't push

Frontend polls every ~2.5s while something's processing rather than using
WebSockets. Less code, no extra connection to manage, and a few seconds
of polling latency genuinely doesn't matter for something that takes
15-20 seconds anyway.

### 5. The AI never invents experience

This was non-negotiable from the start. `adapt_resume_for_job()` has
explicit, repeated rules in its prompt: never add a skill, never change a
date or title, only reword what's already there. Tested specifically by
feeding it a resume missing an obvious JD keyword to confirm it reframes
existing bullets instead of just sprinkling the missing skill in. A
cover letter tool that makes you look qualified for something you're not
isn't a feature — it's a liability for the person using it.

---

## Quick start

```bash
git clone https://github.com/yourusername/applypilot
cd applypilot
cp .env.example .env
```

Get a free Groq key at [console.groq.com](https://console.groq.com)
(30 seconds, no card), paste it into `.env` as `GROQ_API_KEY=`.

```bash
docker compose up -d
```

Open `http://localhost:3000`. Demo login (run `make seed` first):
`demo@applypilot.dev` / `Demo1234!`

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind | App Router, light theme, no CSS framework fights |
| State | React Query + Zustand | Server cache vs. client auth state, kept separate on purpose |
| Backend | FastAPI, async SQLAlchemy 2 | Async all the way down, matches the polling-heavy workload |
| Database | PostgreSQL 16 | 5 tables, nothing exotic — see `db/init.sql` |
| AI | Groq, `llama-3.3-70b-versatile` | Free, fast, no local GPU needed |
| Auth | Plain JWT | No OAuth provider to configure for a side project |
| Infra | Docker Compose | One command, three containers |

---

## Project layout

```
backend/
  main.py                  FastAPI app, mounts every router
  app/core/                 config, db session, jwt
  app/models.py             users · profiles · resumes · jobs · applications
  app/routers/               one file per resource
  app/services/
    ai_service.py            every Groq call + fallback logic lives here
    resume_service.py         file saving + PDF/DOCX text extraction
    job_service.py             job URL scraping

frontend/
  src/app/
    (app)/                   everything behind login
    auth/                     login / register
  src/lib/api.ts              one function per backend endpoint
  src/components/ui/           Card, Badge, ScoreCircle — nothing exotic
```

---

## Known rough edges

Being upfront about this rather than pretending it's flawless:

- **Job scraping is best-effort.** LinkedIn and Workday especially like
  to block or JS-render around scrapers. If a URL fails, paste the JD
  text instead — works identically.
- **Background tasks aren't durable.** If the backend container restarts
  mid-generation, that job is gone. Just re-trigger it.
- **Resume adaptation rewrites text, not the PDF.** You'll manually copy
  the suggested wording into your actual resume document.
- **Groq's free tier can rate-limit under heavy use.** There's a
  regex-based fallback for every AI call, but it's noticeably dumber.

---

## What's next

Roughly in the order I'd actually build them:

- **Playwright autofill** — go from "here's your cover letter, copy it"
  to actually filling the Greenhouse/Lever form for you
- **Email response detection** — parse your inbox for "we regret to
  inform you" / interview invites and auto-update application status
- **Resume diff view** — side-by-side original vs. AI-adapted bullets
  instead of a flat text block
- **Browser extension** — generate an application without leaving the
  job posting tab
- **Multi-resume strategy** — auto-pick which resume version fits a
  given job best, when you have more than one uploaded

---

## Contributing

Fork it, branch, PR. See [CONTRIBUTING.md](CONTRIBUTING.md) for how the
code's laid out.

## License

MIT — do whatever you want with it.
