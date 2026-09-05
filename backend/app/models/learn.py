from datetime import datetime, timezone
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LearnSession(Base):
    __tablename__ = "learn_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    note_id: Mapped[int | None] = mapped_column(ForeignKey("notes.id", ondelete="SET NULL"), nullable=True)
    goal: Mapped[str] = mapped_column(String(24))
    familiarity: Mapped[str] = mapped_column(String(24))
    plan: Mapped[dict] = mapped_column(JSON)
    objective_index: Mapped[int] = mapped_column(Integer, default=0)
    step_index: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="active")
    plan_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    ended_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    attempts: Mapped[list["LearnAttempt"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class LearnAttempt(Base):
    __tablename__ = "learn_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learn_sessions.id", ondelete="CASCADE"), index=True)
    objective_id: Mapped[str] = mapped_column(String(60))
    step_id: Mapped[str] = mapped_column(String(60))
    step_type: Mapped[str] = mapped_column(String(32))
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str] = mapped_column(String(24))
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    session: Mapped[LearnSession] = relationship(back_populates="attempts")

class LearnTutorEvent(Base):
    __tablename__ = "learn_tutor_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("learn_sessions.id", ondelete="CASCADE"), index=True, nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
