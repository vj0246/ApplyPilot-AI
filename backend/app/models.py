import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    profile: Mapped[Optional["Profile"]] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    resumes: Mapped[List["Resume"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    jobs: Mapped[List["Job"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    applications: Mapped[List["Application"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(2048))
    github_url: Mapped[Optional[str]] = mapped_column(String(2048))
    portfolio_url: Mapped[Optional[str]] = mapped_column(String(2048))
    target_roles: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    experience_level: Mapped[Optional[str]] = mapped_column(String(50))
    work_types: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    salary_min: Mapped[Optional[int]] = mapped_column(Integer)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer)
    tone_preference: Mapped[str] = mapped_column(String(50), default="professional")
    skills: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False)

    # Structured facts about the person, built from their own answers to a
    # personality and background interview. Read back into every form
    # answer and email so the writing is grounded in who they actually are.
    knowledge_graph: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Free text the user writes themselves about how they want everything
    # written for them: tone, format, phrases to prefer or avoid. Appended
    # to every AI writing prompt after the app's own writing standards.
    custom_instructions: Mapped[Optional[str]] = mapped_column(Text)

    # Answers the person corrected by hand on a filled form, newest first,
    # as [{"question": ..., "answer": ...}]. The human in the loop signal:
    # a correction someone typed themselves beats anything generated, so
    # when a future form asks the same or a clearly similar question, the
    # corrected answer is offered to the model as the preferred one.
    learned_answers: Mapped[Optional[list]] = mapped_column(JSONB, default=list)

    # The user's own mailbox, used to send the job application email as
    # them, not as this app. smtp_password_encrypted is a Fernet token, the
    # plain app password is never stored and never leaves this column
    # decrypted except in memory for the single send call.
    sender_email: Mapped[Optional[str]] = mapped_column(String(320))
    smtp_host: Mapped[Optional[str]] = mapped_column(String(255))
    smtp_port: Mapped[Optional[int]] = mapped_column(Integer)
    smtp_username: Mapped[Optional[str]] = mapped_column(String(320))
    smtp_password_encrypted: Mapped[Optional[str]] = mapped_column(Text)

    # Gmail API connection — the sending path that actually works from
    # Render (SMTP egress is blocked there). The refresh token is Fernet
    # encrypted like the SMTP password and exchanged for a short lived
    # access token at each send.
    gmail_address: Mapped[Optional[str]] = mapped_column(String(320))
    gmail_refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    # While the Google OAuth app is in Testing mode, Google expires every
    # refresh token after 7 days regardless of use — this timestamp is
    # what lets the frontend warn someone before that happens instead of
    # their next send just failing.
    gmail_connected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="profile")


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500))
    file_path: Mapped[str] = mapped_column(String(1024))
    # The actual file bytes. The disk copy at file_path is a cache at
    # best — on Render the container filesystem is wiped on every deploy,
    # and the resume must survive that because every application email
    # attaches it. Postgres is the only storage this app has that
    # persists, and a resume is well under the 10 MB upload cap.
    file_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    file_size: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="processing")
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    parsed_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    ats_score: Mapped[Optional[int]] = mapped_column(Integer)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    label: Mapped[Optional[str]] = mapped_column(String(255))
    error_msg: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="resumes")
    applications: Mapped[List["Application"]] = relationship(back_populates="resume")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="text")
    url: Mapped[Optional[str]] = mapped_column(String(2048))
    title: Mapped[Optional[str]] = mapped_column(String(500))
    company: Mapped[Optional[str]] = mapped_column(String(500))
    location: Mapped[Optional[str]] = mapped_column(String(500))
    work_type: Mapped[Optional[str]] = mapped_column(String(50))
    salary_min: Mapped[Optional[int]] = mapped_column(Integer)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer)
    salary_currency: Mapped[str] = mapped_column(String(10), default="USD")
    description: Mapped[Optional[str]] = mapped_column(Text)
    parsed_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    required_skills: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    keywords: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    error_msg: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="jobs")
    applications: Mapped[List["Application"]] = relationship(back_populates="job")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    resume_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="generating")
    fit_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    fit_breakdown: Mapped[Optional[dict]] = mapped_column(JSONB)
    skill_gaps: Mapped[Optional[dict]] = mapped_column(JSONB)
    strategy: Mapped[Optional[str]] = mapped_column(Text)
    cover_letter: Mapped[Optional[str]] = mapped_column(Text)
    email_subject: Mapped[Optional[str]] = mapped_column(String(500))
    email_body: Mapped[Optional[str]] = mapped_column(Text)
    resume_adapted: Mapped[Optional[str]] = mapped_column(Text)
    answers: Mapped[Optional[dict]] = mapped_column(JSONB)
    user_notes: Mapped[Optional[str]] = mapped_column(Text)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_msg: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="applications")
    job: Mapped["Job"] = relationship(back_populates="applications")
    resume: Mapped["Resume"] = relationship(back_populates="applications")


class AutofillRun(Base):
    """A single Google Form autofill attempt. Used to be an in-memory dict
    in the autofill router — moved here so a run survives a backend
    restart and is visible across replicas if this ever scales past one
    process. Not meant as permanent history; safe to prune rows older
    than a day or two."""
    __tablename__ = "autofill_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))
    resume_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=False)
    form_url: Mapped[str] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(50), default="running")
    result: Mapped[Optional[dict]] = mapped_column(JSONB)
    error_msg: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EmailSend(Base):
    """The application email that goes out from the user's own address about
    a job description. Split into a draft step and a separate send step on
    purpose, same human in the loop rule as AutofillRun: the AI writes it,
    a person can edit it, and only the explicit send call puts it on the
    wire."""
    __tablename__ = "email_sends"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))
    resume_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"))
    recipient_email: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(500), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="draft")
    error_msg: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
