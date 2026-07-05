"""
autofill.py
-----------
   POST /autofill/form   { form_url, resume_id, job_id? } -> 202, { id }
   GET  /autofill/{id}   -> { status, result }   (frontend polls)

Accepts a Google Forms or a Microsoft Forms link — autofill_service picks
the right scraper based on the URL, everything else about the flow is
identical.

Runs are stored in autofill_runs, same create-row-then-202-then-poll
pattern as resumes/jobs/applications. Used to be an in-memory dict in this
process, which meant a run vanished on a backend restart and would be
invisible to a different replica if this ever ran behind more than one.
A real table fixes both.

Lives in its own router rather than inside applications.py because
filling a form spins up a real browser and takes 10-30s — different
enough from the fast DB-bound stuff in that file to deserve its own home.
"""
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, AsyncSessionLocal
from app.models import AutofillRun, Job, Profile, Resume, User
from app.routers.auth import get_current_user
from app.services import autofill_service

router = APIRouter(prefix="/autofill", tags=["autofill"])
log = logging.getLogger(__name__)


class AutofillIn(BaseModel):
    form_url: str
    resume_id: str
    job_id: Optional[str] = None
    extra_context: str = ""


def _out(run: AutofillRun) -> dict:
    return {
        "id": str(run.id), "status": run.status, "result": run.result,
        "error": run.error_msg,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.post("/form", status_code=202)
async def start_autofill(
    body: AutofillIn,
    bg: BackgroundTasks,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not autofill_service.is_supported_form_url(body.form_url):
        raise HTTPException(
            422,
            "That doesn't look like a Google Forms or Microsoft Forms link "
            "(expected a docs.google.com/forms/... or forms.office.com/... URL).",
        )

    resume = await db.get(Resume, uuid.UUID(body.resume_id))
    if not resume or resume.user_id != u.id:
        raise HTTPException(404, "Resume not found")
    if resume.status != "ready":
        raise HTTPException(409, "Resume is still processing. Wait for it to finish.")

    job_id = None
    if body.job_id:
        job = await db.get(Job, uuid.UUID(body.job_id))
        if job and job.user_id == u.id:
            job_id = job.id

    run = AutofillRun(
        user_id=u.id, job_id=job_id, resume_id=resume.id,
        form_url=body.form_url, status="running",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    bg.add_task(_run, str(run.id), body.form_url, body.extra_context)

    return {"id": str(run.id), "status": "running",
            "message": "Opening the form and filling it in — this takes 15-30 seconds…"}


async def _run(run_id: str, form_url: str, extra_context: str):
    # background task gets its own DB session, same as every other
    # background job in this app
    async with AsyncSessionLocal() as db:
        run = await db.get(AutofillRun, uuid.UUID(run_id))
        if not run:
            return

        resume = await db.get(Resume, run.resume_id)
        job_parsed = None
        if run.job_id:
            job = await db.get(Job, run.job_id)
            if job:
                job_parsed = job.parsed_data

        res = await db.execute(select(Profile).where(Profile.user_id == run.user_id))
        profile = res.scalar_one_or_none()
        knowledge_graph = (profile.knowledge_graph if profile else None) or None
        custom_instructions = (profile.custom_instructions if profile else None) or ""

        try:
            result = await autofill_service.run_autofill(
                form_url=form_url,
                resume_parsed=resume.parsed_data or {} if resume else {},
                job_parsed=job_parsed,
                extra_context=extra_context,
                knowledge_graph=knowledge_graph,
                custom_instructions=custom_instructions,
            )
            run.status = "ready"
            run.result = result
            await db.commit()
            log.info(f"Autofill {run_id} done — {len(result['fields'])} fields, {result['unfilled_count']} unfilled")
        except autofill_service.FormScrapeError as e:
            # carries a screenshot of whatever page Playwright actually
            # saw, so a bot check page and a genuinely unrecognized layout
            # don't look identical from the error message alone
            log.error(f"Autofill {run_id} found no fields: {e}")
            run.status = "failed"
            run.error_msg = str(e)[:400]
            run.result = {"debug_screenshot_base64": e.screenshot_b64} if e.screenshot_b64 else None
            await db.commit()
        except Exception as e:
            log.error(f"Autofill {run_id} failed: {e}")
            run.status = "failed"
            run.error_msg = str(e)[:400]
            await db.commit()


@router.get("/{run_id}")
async def get_autofill_status(
    run_id: uuid.UUID,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(AutofillRun, run_id)
    if not run or run.user_id != u.id:
        raise HTTPException(404, "Autofill run not found")
    return _out(run)
