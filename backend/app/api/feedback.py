from fastapi import APIRouter, HTTPException, status

from app.dependencies import CurrentTime, CurrentUser, DatabaseSession
from app.schemas import (
    FeedbackCreate,
    FeedbackResponse,
    FeedbackSummaryResponse,
)
from app.services.feedback import (
    FeedbackConflictError,
    FeedbackSessionNotFoundError,
    submit_feedback,
    summarize_feedback,
)


router = APIRouter(prefix="/api/sessions", tags=["feedback"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post(
    "/{session_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_session_feedback(
    session_id: str,
    payload: FeedbackCreate,
    db: DatabaseSession,
    current_user: CurrentUser,
    now: CurrentTime,
) -> FeedbackResponse:
    try:
        feedback = submit_feedback(
            db,
            session_id,
            current_user.id,
            payload,
            now,
        )
    except FeedbackSessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "session_not_found",
                "message": "Activity does not exist",
            },
        ) from None
    except FeedbackConflictError as error:
        messages = {
            "not_participant": "Only activity participants can submit feedback",
            "session_not_ended": "Feedback is available after the activity ends",
            "feedback_already_submitted": "Feedback was already submitted",
        }
        status_code = (
            status.HTTP_403_FORBIDDEN
            if error.code == "not_participant"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(
            status_code=status_code,
            detail={"code": error.code, "message": messages[error.code]},
        ) from None

    return FeedbackResponse.model_validate(feedback)


@admin_router.get(
    "/feedback-summary",
    response_model=FeedbackSummaryResponse,
)
def get_feedback_summary(
    db: DatabaseSession,
    current_user: CurrentUser,
) -> FeedbackSummaryResponse:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "admin_required",
                "message": "Administrator access is required",
            },
        )

    return summarize_feedback(db)
