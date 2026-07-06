import uuid
import logging
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db, AsyncSessionLocal
from app.core.config import settings
from app.models import Profile, Resume, User
from app.routers.auth import get_current_user
from app.services import resume_service, ai_service

router = APIRouter(prefix="/resumes", tags=["resumes"])
log = logging.getLogger(__name__)
MAX = settings.MAX_FILE_SIZE_MB * 1024 * 1024


def _out(r: Resume) -> dict:
    return {
        "id": str(r.id), "filename": r.filename, "label": r.label,
        "status": r.status, "ats_score": r.ats_score, "is_primary": r.is_primary,
        "file_size": r.file_size, "mime_type": r.mime_type,
        "parsed_data": r.parsed_data, "error_msg": r.error_msg,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# Upload is instant — file goes to disk, row gets created, 202 comes back
# right away. extract_text + parse_resume + ats_score all happen after,
# in _process() below. Frontend polls GET /resumes/ every ~2.5s while
# anything's "processing".

@router.post("/upload", status_code=202)
async def upload(
    bg: BackgroundTasks,
    file: UploadFile = File(...),
    label: Optional[str] = Form(None),
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    mime = resume_service.get_mime(file.filename or "", file.content_type or "")
    ext  = Path(file.filename or "").suffix.lower()
    if mime not in resume_service.ALLOWED_MIME and ext not in resume_service.ALLOWED_EXT:
        raise HTTPException(415, "Please upload a PDF, DOCX, or TXT file.")

    data = await file.read()
    if len(data) > MAX:
        raise HTTPException(413, f"File exceeds {settings.MAX_FILE_SIZE_MB} MB limit.")
    if len(data) < 100:
        raise HTTPException(422, "File appears to be empty.")

    path = resume_service.save_file(data, file.filename or "resume.pdf", str(u.id))

    # whatever you just uploaded becomes the primary resume, old ones
    # get demoted — keeps the Apply page simple, it defaults to primary
    await db.execute(update(Resume).where(Resume.user_id == u.id).values(is_primary=False))

    r = Resume(
        user_id=u.id, filename=file.filename or "resume", file_path=path,
        file_data=data,
        file_size=len(data), mime_type=mime, status="processing",
        is_primary=True, label=label,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)

    bg.add_task(_process, str(r.id), str(u.id))
    return {"id": str(r.id), "status": "processing", "message": "Resume uploaded — AI is analysing it now…"}


async def _process(rid: str, uid: str):
    async with AsyncSessionLocal() as db:
        try:
            r = await db.get(Resume, uuid.UUID(rid))
            if not r:
                return

            text = resume_service.extract_text(r.file_path, r.mime_type)
            r.raw_text = text

            parsed      = await ai_service.parse_resume(text)
            r.parsed_data = parsed
            r.ats_score   = await ai_service.compute_ats_score(parsed)
            r.status      = "ready"

            # seed the profile's skill list from the resume if it's empty —
            # saves a manual step in Settings for new users
            res = await db.execute(select(Profile).where(Profile.user_id == uuid.UUID(uid)))
            prof = res.scalar_one_or_none()
            if prof and not prof.skills and parsed.get("skills"):
                prof.skills = parsed["skills"][:25]

            await db.commit()
            log.info(f"Resume {rid} ready — ATS score: {r.ats_score}")

        except Exception as e:
            # most common cause: scanned/image-only PDF with no real text layer
            log.error(f"Resume {rid} processing failed: {e}")
            r2 = await db.get(Resume, uuid.UUID(rid))
            if r2:
                r2.status    = "failed"
                r2.error_msg = str(e)[:400]
                await db.commit()


@router.get("/")
async def list_resumes(
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Resume).where(Resume.user_id == u.id)
        .order_by(Resume.is_primary.desc(), Resume.created_at.desc())
    )
    items = res.scalars().all()
    return {"items": [_out(r) for r in items], "total": len(items)}


@router.get("/{rid}")
async def get_resume(
    rid: uuid.UUID,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.get(Resume, rid)
    if not r or r.user_id != u.id:
        raise HTTPException(404, "Resume not found")
    return _out(r)


@router.patch("/{rid}")
async def patch_resume(
    rid: uuid.UUID,
    body: dict,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.get(Resume, rid)
    if not r or r.user_id != u.id:
        raise HTTPException(404, "Resume not found")
    if "label" in body:
        r.label = body["label"]
    if body.get("is_primary"):
        await db.execute(update(Resume).where(Resume.user_id == u.id).values(is_primary=False))
        r.is_primary = True
    await db.commit()
    await db.refresh(r)
    return _out(r)


@router.delete("/{rid}", status_code=204)
async def delete_resume(
    rid: uuid.UUID,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.get(Resume, rid)
    if not r or r.user_id != u.id:
        raise HTTPException(404, "Resume not found")
    try:
        Path(r.file_path).unlink(missing_ok=True)
    except Exception:
        pass
    await db.delete(r)
    await db.commit()
