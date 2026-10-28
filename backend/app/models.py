from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid4())


class UTCDateTime(TypeDecorator):
    """Store UTC as naive SQLite values and restore timezone-aware values."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "level IN ('newbie', 'beginner', 'skilled')",
            name="ck_users_level",
        ),
        CheckConstraint(
            "format_preference IN ('singles', 'doubles', 'either')",
            name="ck_users_format_preference",
        ),
        CheckConstraint(
            "purpose IN ('casual', 'training', 'either')",
            name="ck_users_purpose",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    area: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    level_description: Mapped[str] = mapped_column(String(200), nullable=False)
    format_preference: Mapped[str] = mapped_column(String(20), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )


class Availability(Base):
    __tablename__ = "availability"
    __table_args__ = (
        CheckConstraint(
            "weekday BETWEEN 0 AND 6",
            name="ck_availability_weekday",
        ),
        CheckConstraint(
            "start_minute >= 0 AND end_minute <= 1440 "
            "AND start_minute < end_minute",
            name="ck_availability_time_range",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)


class GameSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "format IN ('singles', 'doubles')",
            name="ck_sessions_format",
        ),
        CheckConstraint(
            "purpose IN ('casual', 'training')",
            name="ck_sessions_purpose",
        ),
        CheckConstraint(
            "status IN ('open', 'full', 'cancelled', 'completed')",
            name="ck_sessions_status",
        ),
        CheckConstraint("capacity >= 2", name="ck_sessions_capacity"),
        CheckConstraint("start_at < end_at", name="ck_sessions_time_range"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    creator_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    start_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    end_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    area: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    venue: Mapped[str] = mapped_column(String(120), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    level_label: Mapped[str] = mapped_column(String(50), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (
        UniqueConstraint("session_id", "user_id", name="uq_participant_session_user"),
        CheckConstraint(
            "status IN ('joined', 'cancelled')",
            name="ck_participants_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="joined"
    )
    joined_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        UniqueConstraint("session_id", "user_id", name="uq_feedback_session_user"),
        CheckConstraint(
            "rating IN ('suitable', 'average', 'unsuitable')",
            name="ck_feedback_rating",
        ),
        CheckConstraint(
            "reason_category IN "
            "('time', 'location', 'level', 'purpose', 'no_show', 'other')",
            name="ck_feedback_reason_category",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[str] = mapped_column(String(20), nullable=False)
    reason_category: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )


class RecommendationRecord(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    model_output: Mapped[dict] = mapped_column(JSON, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )


class AgentConfig(Base):
    __tablename__ = "agent_config"

    version: Mapped[str] = mapped_column(String(50), primary_key=True)
    changed_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
