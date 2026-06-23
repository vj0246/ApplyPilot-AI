import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.database import get_db, AsyncSessionLocal
from app.models import Application, Job, Profile, Resume, User
from app.routers.auth import get_current_user
from app.services import ai_service

router = APIRouter(prefix="/applications", tags=["applications"])
log = logging.getLogger(__name__)


class GenerateIn(BaseModel):
    job_id: str
    resume_id: str
    extra_context: str = ""


class AnswerIn(BaseModel):
    questions: List[str]
    job_id: Optional[str] = None
    extra_context: str = ""


class UpdateIn(BaseModel):
    status: Optional[str] = None
    cover_letter: Optional[str] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    resume_adapted: Optional[str] = None
    answers: Optional[dict] = None
    user_notes: Optional[str] = None


def _out(a: Application, with_job: bool = False) -> dict:
    d = {
        "id": str(a.id), "status": a.status,
        "fit_score": float(a.fit_score) if a.fit_score is not None else None,
        "fit_breakdown": a.fit_breakdown,
        "skill_gaps": a.skill_gaps,
        "strategy": a.strategy,
        "cover_letter": a.cover_letter,
        "email_subject": a.email_subject,
        "email_body": a.email_body,
        "resume_adapted": a.resume_adapted,
        "answers": a.answers,
        "user_notes": a.user_notes,
        "error_msg": a.error_msg,
        "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }
    if with_job and a.job:
        d["job"] = {
            "id": str(a.job.id), "title": a.job.title, "company": a.job.company,
            "location": a.job.location, "work_type": a.job.work_type,
            "salary_min": a.job.salary_min, "salary_max": a.job.salary_max,
            "salary_currency": a.job.salary_currency or "USD",
            "required_skills": a.job.required_skills or [],
            "url": a.job.url,
        }
    return d


# POST /generate kicks off the whole pipeline: fit score -> cover letter
# -> email -> adapted resume, one Groq call each, ~10-20s total. Same
# create-row-then-202-then-poll pattern as resumes/jobs.

@router.post("/generate", status_code=202)
async def generate(
    body: GenerateIn,
    bg: BackgroundTasks,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    j = await db.get(Job, uuid.UUID(body.job_id))
    if not j or j.user_id != u.id:
        raise HTTPException(404, "Job not found")
    if j.status != "ready":
        raise HTTPException(409, f"Job is still '{j.status}'. Wait for it to finish processing.")

    r = await db.get(Resume, uuid.UUID(body.resume_id))
    if not r or r.user_id != u.id:
        raise HTTPException(404, "Resume not found")
    if r.status != "ready":
        raise HTTPException(409, "Resume is still processing. Wait for it to finish.")

    a = Application(user_id=u.id, job_id=j.id, resume_id=r.id, status="generating")
    db.add(a)
    await db.commit()
    await db.refresh(a)

    bg.add_task(_generate, str(a.id), str(u.id), body.extra_context)
    return {"id": str(a.id), "status": "generating",
            "message": "Generating your application — this takes ~15 seconds…"}


async def _generate(aid: str, uid: str, extra_context: str):
    # background task gets its own DB session — can't reuse the request's,
    # it'll be closed by the time this runs
    async with AsyncSessionLocal() as db:
        try:
            a = await db.get(Application, uuid.UUID(aid))
            if not a:
                return

            resume = await db.get(Resume, a.resume_id)
            job    = await db.get(Job, a.job_id)
            res    = await db.execute(select(Profile).where(Profile.user_id == uuid.UUID(uid)))
            prof   = res.scalar_one_or_none()

            rp = resume.parsed_data or {}
            jp = job.parsed_data or {}
            pp = {"skills": prof.skills or []} if prof else {}
            tone = prof.tone_preference if prof else "professional"

            fit = await ai_service.analyze_fit(rp, jp, pp)
            a.fit_score    = fit["overall"]
            a.fit_breakdown = fit
            a.skill_gaps   = fit.get("gaps", [])

            a.cover_letter = await ai_service.generate_cover_letter(rp, jp, fit, tone, extra_context)

            # resume parsing sometimes misses the name (bad PDF layout) —
            # fall back to the account name so the email isn't blank
            user = await db.get(User, uuid.UUID(uid))
            name = rp.get("name") or (user.full_name if user else "")
            email_data = await ai_service.generate_email(name, jp, fit, extra_context)
            a.email_subject = email_data.get("subject", "")
            a.email_body    = email_data.get("body", "")

            a.resume_adapted = await ai_service.adapt_resume_for_job(resume.raw_text or "", jp, fit)

            matched = ", ".join(list(fit.get("matched_skills", []))[:4]) or "core skills"
            missing = ", ".join(list(fit.get("missing_required", []))[:3])
            a.strategy = (
                f"Fit: {fit['overall']:.0f}/100. Strong matches: {matched}. "
                + (f"Address gaps: {missing}." if missing else "No critical gaps.")
            )

            a.status = "ready"
            await db.commit()
            log.info(f"Application {aid} generated. Fit={a.fit_score:.1f}")

        except Exception as e:
            log.error(f"Application {aid} failed: {e}")
            a2 = await db.get(Application, uuid.UUID(aid))
            if a2:
                a2.status    = "failed"
                a2.error_msg = str(e)[:400]
                await db.commit()


# POST /answer-questions is the standalone "form filler" tab — no DB row,
# synchronous since it's just one Groq call.

@router.post("/answer-questions")
async def answer_questions(
    body: AnswerIn,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.questions:
        raise HTTPException(422, "Provide at least one question.")

    res = await db.execute(
        select(Resume)
        .where(Resume.user_id == u.id, Resume.is_primary == True, Resume.status == "ready")
    )
    resume = res.scalar_one_or_none()
    if not resume:
        raise HTTPException(409, "No processed resume found. Upload and wait for processing first.")

    job_parsed = None
    if body.job_id:
        j = await db.get(Job, uuid.UUID(body.job_id))
        if j and j.user_id == u.id:
            job_parsed = j.parsed_data

    answers = await ai_service.answer_form_questions(
        questions=body.questions,
        resume_parsed=resume.parsed_data or {},
        job_parsed=job_parsed,
        extra_context=body.extra_context,
    )
    return {"answers": answers}


@router.get("/")
async def list_apps(
    status: Optional[str] = None,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Application).options(selectinload(Application.job)).where(Application.user_id == u.id)
    if status:
        q = q.where(Application.status == status)
    q = q.order_by(Application.created_at.desc())

    res   = await db.execute(q)
    items = res.scalars().all()

    stats: dict = {}
    for a in items:
        stats[a.status] = stats.get(a.status, 0) + 1

    return {"items": [_out(a, with_job=True) for a in items], "total": len(items), "stats": stats}


@router.get("/stats/summary")
async def stats_summary(
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func
    res = await db.execute(
        select(Application.status, func.count().label("n"))
        .where(Application.user_id == u.id)
        .group_by(Application.status)
    )
    return {r.status: r.n for r in res}


@router.get("/{aid}")
async def get_app(
    aid: uuid.UUID,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Application).options(selectinload(Application.job)).where(Application.id == aid)
    )
    a = res.scalar_one_or_none()
    if not a or a.user_id != u.id:
        raise HTTPException(404, "Application not found")
    return _out(a, with_job=True)


@router.patch("/{aid}")
async def update_app(
    aid: uuid.UUID,
    body: UpdateIn,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Application).options(selectinload(Application.job)).where(Application.id == aid)
    )
    a = res.scalar_one_or_none()
    if not a or a.user_id != u.id:
        raise HTTPException(404, "Application not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(a, field, value)

    if body.status == "submitted" and not a.submitted_at:
        a.submitted_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(a)
    return _out(a, with_job=True)


@router.delete("/{aid}", status_code=204)
async def delete_app(
    aid: uuid.UUID,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a = await db.get(Application, aid)
    if not a or a.user_id != u.id:
        raise HTTPException(404, "Application not found")
    await db.delete(a)
    await db.commit()
