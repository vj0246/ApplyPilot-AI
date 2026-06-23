# Contributing to ApplyPilot

Thanks for considering a contribution! 🎉

## Getting started

1. Fork the repo and clone your fork
2. Copy `.env.example` to `.env` and add your free [Groq API key](https://console.groq.com)
3. Run `docker compose up -d --build`
4. Make your changes
5. Test locally at `http://localhost:3000`

## Project structure

```
backend/    FastAPI app (Python)
  app/core/       config, database, auth
  app/models.py   SQLAlchemy models
  app/routers/    API endpoints
  app/services/   AI logic, file parsing, job scraping

frontend/   Next.js app (TypeScript)
  src/app/        pages (App Router)
  src/components/ reusable UI
  src/lib/        API client, utilities
  src/store/      Zustand state

db/init.sql       PostgreSQL schema
```

## Making changes

### Backend
- FastAPI auto-reloads on file change (`--reload` flag)
- New endpoints go in `backend/app/routers/`
- AI logic lives in `backend/app/services/ai_service.py`

### Frontend
- Pages use the Next.js App Router (`src/app/`)
- Keep the light theme — primary color is `indigo-600`
- Use existing components from `src/components/ui/`

## Pull requests

1. Create a branch: `git checkout -b feature/my-feature`
2. Commit with a clear message
3. Push and open a PR against `main`
4. Describe what changed and why

## Reporting bugs

Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- Docker logs if relevant (`make logs`)

## Code style

- Python: follow existing patterns, type hints where practical
- TypeScript: strict mode, no `any` unless necessary
- Keep functions small and readable

Thanks for helping make ApplyPilot better! 🚀
