from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.database import get_db
from app.models import Profile, User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileIn(BaseModel):
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    target_roles: Optional[List[str]] = None
    experience_level: Optional[str] = None
    work_types: Optional[List[str]] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    tone_preference: Optional[str] = None
    skills: Optional[List[str]] = None
    onboarding_done: Optional[bool] = None


def _out(p: Profile) -> dict:
    return {
        "id": str(p.id),
        "user_id": str(p.user_id),
        "phone": p.phone,
        "location": p.location,
        "linkedin_url": p.linkedin_url,
        "github_url": p.github_url,
        "portfolio_url": p.portfolio_url,
        "target_roles": p.target_roles or [],
        "experience_level": p.experience_level,
        "work_types": p.work_types or [],
        "salary_min": p.salary_min,
        "salary_max": p.salary_max,
        "tone_preference": p.tone_preference or "professional",
        "skills": p.skills or [],
        "onboarding_done": p.onboarding_done,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("/")
async def get_profile(
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Profile).where(Profile.user_id == u.id))
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Profile not found")
    return _out(p)


@router.patch("/")
async def update_profile(
    body: ProfileIn,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Profile).where(Profile.user_id == u.id))
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Profile not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(p, field, value)

    await db.commit()
    await db.refresh(p)
    return _out(p)
