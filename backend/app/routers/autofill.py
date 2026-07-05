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
from typing import List, Optional

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


class AnswerEdit(BaseModel):
    index: int
    answer: str


class AnswersEditIn(BaseModel):
    answers: List[AnswerEdit]


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
        learned_answers = (profile.learned_answers if profile else None) or None

        try:
            result = await autofill_service.run_autofill(
                form_url=form_url,
                resume_parsed=resume.parsed_data or {} if resume else {},
                job_parsed=job_parsed,
                extra_context=extra_context,
                knowledge_graph=knowledge_graph,
                custom_instructions=custom_instructions,
                learned_answers=learned_answers,
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


@router.patch("/{run_id}/answers")
async def edit_answers(
    run_id: uuid.UUID,
    body: AnswersEditIn,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edit answers on a finished run right on the site, get back a fresh
    pre-filled link carrying the edits, and remember every correction.

    The remembering is the human in the loop half: an answer someone
    rewrote by hand is the strongest possible signal of what they wanted
    said, so each changed answer is stored on the profile as a learned
    answer, and every future form filling run feeds those to the model
    as the preferred answer for the same or a clearly similar question."""
    run = await db.get(AutofillRun, run_id)
    if not run or run.user_id != u.id:
        raise HTTPException(404, "Autofill run not found")
    if run.status != "ready" or not run.result or not run.result.get("fields"):
        raise HTTPException(409, "This run has no filled answers to edit.")

    fields = [dict(f) for f in run.result["fields"]]
    by_index = {f.get("index"): f for f in fields}

    corrections: List[dict] = []
    for edit in body.answers:
        f = by_index.get(edit.index)
        if not f:
            continue
        new_answer = edit.answer.strip()
        old_answer = (f.get("answer") or "").strip()
        if new_answer == old_answer:
            continue
        # A choice field only accepts what is actually on the form —
        # anything else would corrupt the pre-filled link the same way
        # the old sentinel bug did, so a non-matching edit is rejected
        # loudly rather than quietly breaking every other answer.
        options = f.get("options") or []
        if f.get("field_type") in ("radio", "dropdown") and options and new_answer:
            if new_answer not in options:
                raise HTTPException(
                    422,
                    f"\"{f.get('question','This question')}\" only accepts one of its own options: "
                    f"{', '.join(options)}",
                )
        if f.get("field_type") == "checkbox" and options and new_answer:
            chosen = [v.strip() for v in new_answer.split(",") if v.strip()]
            bad = [v for v in chosen if v not in options]
            if bad:
                raise HTTPException(
                    422,
                    f"\"{f.get('question','This question')}\" only accepts these options: "
                    f"{', '.join(options)}. Not recognized: {', '.join(bad)}",
                )
        f["answer"] = new_answer
        f["confidence"] = "high"   # a human wrote it, no guessing left
        if new_answer:
            corrections.append({"question": f.get("question", ""), "answer": new_answer})

    new_result = dict(run.result)
    new_result["fields"] = fields
    if autofill_service.is_google_form_url(run.form_url):
        new_result["prefilled_url"] = autofill_service.rebuild_prefilled_url(run.form_url, fields)
    run.result = new_result

    if corrections:
        res = await db.execute(select(Profile).where(Profile.user_id == u.id))
        profile = res.scalar_one_or_none()
        if profile:
            existing = list(profile.learned_answers or [])
            corrected_qs = {c["question"].strip().lower() for c in corrections}
            kept = [la for la in existing
                    if (la.get("question") or "").strip().lower() not in corrected_qs]
            # newest corrections first, capped so this never grows unbounded
            profile.learned_answers = (corrections + kept)[:100]

    await db.commit()
    await db.refresh(run)
    return _out(run)
