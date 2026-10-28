from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import GameSession, Participant
from app.schemas import SessionCreate


def create_game_session(
    db: Session,
    creator_id: str,
    payload: SessionCreate,
) -> GameSession:
    game_session = GameSession(
        creator_id=creator_id,
        status="open",
        **payload.model_dump(),
    )
    db.add(game_session)

    try:
        db.flush()
        db.add(
            Participant(
                session_id=game_session.id,
                user_id=creator_id,
                status="joined",
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return game_session


def count_joined_participants(db: Session, session_id: str) -> int:
    count = db.scalar(
        select(func.count())
        .select_from(Participant)
        .where(
            Participant.session_id == session_id,
            Participant.status == "joined",
        )
    )
    return count or 0


def list_sessions_with_participant_counts(
    db: Session,
) -> list[tuple[GameSession, int]]:
    participant_count = (
        select(func.count())
        .select_from(Participant)
        .where(
            Participant.session_id == GameSession.id,
            Participant.status == "joined",
        )
        .correlate(GameSession)
        .scalar_subquery()
    )
    statement = select(
        GameSession,
        participant_count.label("participant_count"),
    ).order_by(GameSession.start_at, GameSession.id)
    return [
        (game_session, count)
        for game_session, count in db.execute(statement).all()
    ]
