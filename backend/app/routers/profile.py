from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional

from app.core import crypto
from app.core.database import get_db
from app.models import Profile, User
from app.routers.auth import get_current_user
from app.services import ai_service

router = APIRouter(prefix="/profile", tags=["profile"])


# A short, fixed interview used to build the knowledge graph. Not meant to
# feel like a form, meant to surface the kind of concrete, personal detail
# that makes a form answer or an email sound like one particular human
# wrote it instead of anyone with a similar resume.
KNOWLEDGE_GRAPH_QUESTIONS = [
    "In two or three sentences, who are you professionally?",
    "Where have you worked or interned, and what did you actually do there?",
    "Which projects should an employer know about? For each: what it does, what you built it with, and the result.",
    "What work are you most proud of, and why?",
    "What do you know most deeply, and how did you learn it?",
    "What kind of problems do you enjoy solving?",
    "What are you working toward over the next few years?",
    "What do you value in a team, and what genuinely interests you outside work?",
]


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
    custom_instructions: Optional[str] = None


class KnowledgeGraphIn(BaseModel):
    answers: List[Dict[str, str]]  # [{"question": "...", "answer": "..."}]


class KnowledgeGraphEditIn(BaseModel):
    # The whole graph, exactly as the user wants it stored. This is the
    # "edit my memory directly" path, distinct from the interview path
    # below which merges AI extracted facts into what is already there.
    knowledge_graph: Dict


class EmailCredentialsIn(BaseModel):
    sender_email: str
    smtp_host: str
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str


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
        "custom_instructions": p.custom_instructions or "",
        "knowledge_graph": p.knowledge_graph or {},
        "email_account_configured": bool(p.smtp_password_encrypted),
        "sender_email": p.sender_email,
        "gmail_connected": bool(p.gmail_refresh_token_encrypted),
        "gmail_address": p.gmail_address,
        "gmail_connected_at": p.gmail_connected_at.isoformat() if p.gmail_connected_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


async def _get_profile(u: User, db: AsyncSession) -> Profile:
    res = await db.execute(select(Profile).where(Profile.user_id == u.id))
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Profile not found")
    return p


@router.get("/")
async def get_profile(
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    p = await _get_profile(u, db)
    return _out(p)


@router.patch("/")
async def update_profile(
    body: ProfileIn,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    p = await _get_profile(u, db)

    # exclude_unset, not exclude_none: a field the client did not send stays
    # untouched, but a field explicitly set to null is a deliberate clear and
    # must go through. The onboarding "confirm your links" step relies on
    # this to delete a wrong link the resume parser seeded — with
    # exclude_none that null was dropped and the bad link survived into every
    # email signature, which is exactly what that step exists to prevent.
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(p, field, value)

    await db.commit()
    await db.refresh(p)
    return _out(p)


@router.get("/knowledge-graph/questions")
async def get_knowledge_graph_questions():
    return {"questions": KNOWLEDGE_GRAPH_QUESTIONS}


@router.post("/knowledge-graph")
async def build_knowledge_graph(
    body: KnowledgeGraphIn,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.answers:
        raise HTTPException(422, "Answer at least one question so there is something to build from.")

    p = await _get_profile(u, db)
    new_fragment = await ai_service.build_knowledge_graph(body.answers)
    p.knowledge_graph = ai_service.merge_knowledge_graph(p.knowledge_graph, new_fragment)
    await db.commit()
    await db.refresh(p)
    return {"knowledge_graph": p.knowledge_graph}


@router.put("/knowledge-graph")
async def edit_knowledge_graph(
    body: KnowledgeGraphEditIn,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Direct replacement, no merge: this endpoint exists precisely so a
    # person can correct or remove something the interview path got wrong,
    # and a merge would resurrect the very fact they deleted.
    p = await _get_profile(u, db)
    p.knowledge_graph = body.knowledge_graph
    await db.commit()
    await db.refresh(p)
    return {"knowledge_graph": p.knowledge_graph}


@router.patch("/email-credentials")
async def set_email_credentials(
    body: EmailCredentialsIn,
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    p = await _get_profile(u, db)
    p.sender_email = body.sender_email
    p.smtp_host = body.smtp_host
    p.smtp_port = body.smtp_port
    p.smtp_username = body.smtp_username
    p.smtp_password_encrypted = crypto.encrypt(body.smtp_password)
    await db.commit()
    return {"email_account_configured": True, "sender_email": p.sender_email}


@router.delete("/email-credentials")
async def clear_email_credentials(
    u: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    p = await _get_profile(u, db)
    p.sender_email = None
    p.smtp_host = None
    p.smtp_port = None
    p.smtp_username = None
    p.smtp_password_encrypted = None
    await db.commit()
    return {"email_account_configured": False}
