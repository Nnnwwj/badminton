from fastapi import APIRouter
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser, DatabaseSession
from app.models import Availability, User
from app.schemas import AvailabilityResponse, ProfileResponse, ProfileUpdate


router = APIRouter(prefix="/api/profile", tags=["profile"])


def _profile_response(db: Session, user: User) -> ProfileResponse:
    availability = db.scalars(
        select(Availability)
        .where(Availability.user_id == user.id)
        .order_by(Availability.weekday, Availability.start_minute)
    ).all()
    return ProfileResponse(
        id=user.id,
        nickname=user.nickname,
        area=user.area,
        level=user.level,
        level_description=user.level_description,
        format_preference=user.format_preference,
        purpose=user.purpose,
        is_admin=user.is_admin,
        availabilities=[
            AvailabilityResponse.model_validate(row) for row in availability
        ],
    )


@router.get("", response_model=ProfileResponse)
def read_profile(db: DatabaseSession, current_user: CurrentUser) -> ProfileResponse:
    return _profile_response(db, current_user)


@router.put("", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ProfileResponse:
    changes = payload.model_dump(exclude_unset=True)
    availability_changes = changes.pop("availabilities", None)

    for field, value in changes.items():
        if value is not None:
            setattr(current_user, field, value)

    if availability_changes is not None:
        db.execute(
            delete(Availability).where(Availability.user_id == current_user.id)
        )
        for availability in payload.availabilities or []:
            db.add(
                Availability(
                    user_id=current_user.id,
                    **availability.model_dump(),
                )
            )

    db.commit()
    return _profile_response(db, current_user)
