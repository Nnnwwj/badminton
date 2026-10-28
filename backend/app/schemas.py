from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Level = Literal["newbie", "beginner", "skilled"]
FormatPreference = Literal["singles", "doubles", "either"]
Purpose = Literal["casual", "training", "either"]


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
