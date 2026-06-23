import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import create_token, hash_password, verify_password, decode_token
from app.models import Profile, User

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ───────────────────────────────────────────────────
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=100)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UpdateMeIn(BaseModel):
    full_name: str | None = None


# ── Dependency ────────────────────────────────────────────────
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(h[7:])
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or inactive")
    return user


def _user_out(u: User) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "full_name": u.full_name,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


# ── Routes ────────────────────────────────────────────────────
@router.post("/register", status_code=201)
async def register(body: RegisterIn, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "An account with this email already exists")

    user = User(
        email=body.email.lower(),
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.flush()
    db.add(Profile(user_id=user.id))
    await db.commit()
    await db.refresh(user)

    return {"access_token": create_token(str(user.id), user.email),
            "token_type": "bearer", "user": _user_out(user)}


@router.post("/login")
async def login(body: LoginIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account is inactive")

    return {"access_token": create_token(str(user.id), user.email),
            "token_type": "bearer", "user": _user_out(user)}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return _user_out(current_user)


@router.patch("/me")
async def update_me(
    body: UpdateMeIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.full_name is not None:
        current_user.full_name = body.full_name.strip()
    await db.commit()
    await db.refresh(current_user)
    return _user_out(current_user)
