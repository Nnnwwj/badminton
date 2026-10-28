from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Feedback, GameSession, Participant
from app.schemas import FeedbackConflictCode, FeedbackCreate


class FeedbackSessionNotFoundError(Exception):
    """Raised when feedback targets an activity that does not exist."""


class FeedbackConflictError(Exception):
    def __init__(self, code: FeedbackConflictCode) -> None:
        super().__init__(code)
        self.code = code


def _conflict(db: Session, code: FeedbackConflictCode) -> None:
    db.rollback()
    raise FeedbackConflictError(code)


def submit_feedback(
    db: Session,
    session_id: str,
    user_id: str,
    payload: FeedbackCreate,
    now: datetime,
) -> Feedback:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)

    game_session = db.get(GameSession, session_id)
    if game_session is None:
        db.rollback()
        raise FeedbackSessionNotFoundError(session_id)

    participant = db.scalar(
        select(Participant).where(
            Participant.session_id == session_id,
            Participant.user_id == user_id,
            Participant.status == "joined",
        )
    )
    if participant is None:
        _conflict(db, "not_participant")

    if game_session.status != "completed" and now < game_session.end_at:
        _conflict(db, "session_not_ended")

    existing = db.scalar(
        select(Feedback).where(
            Feedback.session_id == session_id,
            Feedback.user_id == user_id,
        )
    )
    if existing is not None:
        _conflict(db, "feedback_already_submitted")

    feedback = Feedback(
        session_id=session_id,
        user_id=user_id,
        rating=payload.rating,
        reason_category=payload.reason_category,
        comment=payload.comment,
        submitted_at=now,
    )
    db.add(feedback)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise FeedbackConflictError("feedback_already_submitted") from None
    except Exception:
        db.rollback()
        raise

    return feedback
