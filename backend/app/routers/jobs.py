import uuid
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db, AsyncSessionLocal
from app.models import Job, User
from app.routers.auth import get_current_user
from app.services import job_service, ai_service

router = APIRouter(prefix="/jobs", tags=["jobs"])
log = logging.getLogger(__name__)


class JobIn(BaseModel):
    url: str = ""
    text: str = ""
    title: str = ""
    company: str = ""


def _out(j: Job) -> dict:
    return {
        "id": str(j.id), "source": j.source, "url": j.url,
        "title": j.title, "company": j.company, "location": j.location,
        "work_type": j.work_type, "salary_min": j.salary_min, "salary_max": j.salary_max,
        "salary_currency": j.salary_currency or "USD",
        "required_skills": j.required_skills or [], "keywords": j.keywords or [],
        "status": j.status, "parsed_data": j.parsed_data, "error_msg": j.error_msg,
        "created_at": j.created_at.isoformat() if j.created_at else None,
    }


# Same shape as resume upload: create row -> 202 -> _parse() in the
# background fetches/parses, frontend polls.

@router.post("/", status_code=202)
async def create_job(
    body: JobIn,
    bg: BackgroundTasks,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.url.strip() and not body.text.strip() and not body.title.strip():
        raise HTTPException(422, "Provide at least a URL, job description text, or job title.")

    source = "url" if body.url.strip() else ("text" if body.text.strip() else "manual")

    j = Job(
        user_id=u.id, source=source,
        url=body.url.strip() or None, title=body.title.strip() or None,
        company=body.company.strip() or None, description=body.text.strip() or None,
        status="processing",
    )
    db.add(j)
    await db.commit()
    await db.refresh(j)

    bg.add_task(_parse, str(j.id), body.url.strip(), body.text.strip())
    return {"id": str(j.id), "status": "processing", "message": "Job added — AI is parsing the description…"}


async def _parse(jid: str, url: str, text: str):
    async with AsyncSessionLocal() as db:
        try:
            j = await db.get(Job, uuid.UUID(jid))
            if not j:
                return

            # if we have a URL and no pasted text, scrape it. if that
            # comes back empty (site blocked us, JS-rendered page, etc),
            # just pass empty text through — better than erroring out
            description = text
            if url and not description:
                description = await job_service.fetch_from_url(url) or ""

            j.description = description
            parsed = await ai_service.parse_job(description, url)

            j.title          = parsed.get("title") or j.title or "Unknown Role"
            j.company        = parsed.get("company") or j.company or "Unknown Company"
            j.location       = parsed.get("location", "")
            j.work_type      = parsed.get("work_type", "")
            j.salary_min     = parsed.get("salary_min")
            j.salary_max     = parsed.get("salary_max")
            j.salary_currency = parsed.get("salary_currency") or "USD"
            j.required_skills = parsed.get("required_skills", [])
            j.keywords       = parsed.get("keywords", [])
            j.parsed_data    = parsed
            j.status         = "ready"
            await db.commit()
            log.info(f"Job {jid} parsed: {j.title} @ {j.company}")

        except Exception as e:
            log.error(f"Job {jid} failed: {e}")
            j2 = await db.get(Job, uuid.UUID(jid))
            if j2:
                j2.status = "failed"
                j2.error_msg = str(e)[:400]
                await db.commit()


@router.get("/")
async def list_jobs(
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Job).where(Job.user_id == u.id).order_by(Job.created_at.desc()))
    items = res.scalars().all()
    return {"items": [_out(j) for j in items], "total": len(items)}


@router.get("/{jid}")
async def get_job(
    jid: uuid.UUID,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    j = await db.get(Job, jid)
    if not j or j.user_id != u.id:
        raise HTTPException(404, "Job not found")
    return _out(j)


@router.delete("/{jid}", status_code=204)
async def delete_job(
    jid: uuid.UUID,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    j = await db.get(Job, jid)
    if not j or j.user_id != u.id:
        raise HTTPException(404, "Job not found")
    await db.delete(j)
    await db.commit()
