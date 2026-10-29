from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Level = Literal["newbie", "beginner", "skilled"]
FormatPreference = Literal["singles", "doubles", "either"]
Purpose = Literal["casual", "training", "either"]
SessionFormat = Literal["singles", "doubles"]
SessionPurpose = Literal["casual", "training"]
SessionStatus = Literal["open", "full", "cancelled", "completed"]
JoinConflictCode = Literal[
    "already_joined",
    "session_full",
    "session_ended",
    "session_unavailable",
]
FeedbackRating = Literal["suitable", "average", "unsuitable"]
FeedbackReason = Literal[
    "time",
    "location",
    "level",
    "purpose",
    "no_show",
    "other",
]
FeedbackConflictCode = Literal[
    "not_participant",
    "session_not_ended",
    "feedback_already_submitted",
]


class AvailabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weekday: int = Field(ge=0, le=6)
    start_minute: int = Field(ge=0, le=1440)
    end_minute: int = Field(ge=0, le=1440)


class ProfileResponse(BaseModel):
    id: str
    nickname: str
    area: str
    level: Level
    level_description: str
    format_preference: FormatPreference
    purpose: Purpose
    is_admin: bool
    availabilities: list[AvailabilityResponse]


class AvailabilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: int = Field(ge=0, le=6)
    start_minute: int = Field(ge=0, le=1440)
    end_minute: int = Field(ge=0, le=1440)

    @model_validator(mode="after")
    def validate_time_range(self) -> "AvailabilityUpdate":
        if self.start_minute >= self.end_minute:
            raise ValueError("start_minute must be before end_minute")
        return self


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area: str | None = Field(default=None, min_length=1, max_length=100)
    level: Level | None = None
    level_description: str | None = Field(
        default=None, min_length=1, max_length=200
    )
    format_preference: FormatPreference | None = None
    purpose: Purpose | None = None
    availabilities: list[AvailabilityUpdate] | None = None


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_at: datetime
    end_at: datetime
    area: str = Field(min_length=1, max_length=100)
    venue: str = Field(min_length=1, max_length=120)
    format: SessionFormat
    purpose: SessionPurpose
    level_label: str = Field(min_length=1, max_length=50)
    capacity: int = Field(ge=2)

    @model_validator(mode="after")
    def validate_session_time(self) -> "SessionCreate":
        if self.start_at.utcoffset() is None or self.end_at.utcoffset() is None:
            raise ValueError("session times must include a timezone")
        self.start_at = self.start_at.astimezone(timezone.utc)
        self.end_at = self.end_at.astimezone(timezone.utc)
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class SessionResponse(BaseModel):
    id: str
    creator_id: str
    start_at: datetime
    end_at: datetime
    area: str
    venue: str
    format: SessionFormat
    purpose: SessionPurpose
    level_label: str
    capacity: int
    status: SessionStatus
    created_at: datetime
    participant_count: int
    spots_remaining: int


class CandidateQuery(BaseModel):
    """Objective filters; start/end define an overlapping query window."""

    model_config = ConfigDict(extra="forbid")

    start_at: datetime | None = None
    end_at: datetime | None = None
    area: str | None = Field(default=None, min_length=1, max_length=100)
    format: SessionFormat | None = None
    purpose: SessionPurpose | None = None

    @model_validator(mode="after")
    def validate_query_time(self) -> "CandidateQuery":
        if self.start_at is not None:
            if self.start_at.utcoffset() is None:
                raise ValueError("start_at must include a timezone")
            self.start_at = self.start_at.astimezone(timezone.utc)
        if self.end_at is not None:
            if self.end_at.utcoffset() is None:
                raise ValueError("end_at must include a timezone")
            self.end_at = self.end_at.astimezone(timezone.utc)
        if (
            self.start_at is not None
            and self.end_at is not None
            and self.end_at <= self.start_at
        ):
            raise ValueError("end_at must be after start_at")
        return self


class CandidateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    start_at: datetime
    end_at: datetime
    area: str
    venue: str
    format: SessionFormat
    purpose: SessionPurpose
    level_label: str
    capacity: int = Field(ge=2)
    participant_count: int = Field(ge=0)
    spots_remaining: int = Field(ge=0)


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: FeedbackRating
    reason_category: FeedbackReason
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    user_id: str
    rating: FeedbackRating
    reason_category: FeedbackReason
    comment: str | None
    submitted_at: datetime


class FeedbackReasonCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time: int = Field(ge=0)
    location: int = Field(ge=0)
    level: int = Field(ge=0)
    purpose: int = Field(ge=0)
    no_show: int = Field(ge=0)
    other: int = Field(ge=0)


class FeedbackSummaryResponse(BaseModel):
    total: int = Field(ge=0)
    reason_counts: FeedbackReasonCounts
