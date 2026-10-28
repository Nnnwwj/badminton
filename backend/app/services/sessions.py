from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import GameSession, Participant
from app.schemas import JoinConflictCode, SessionCreate


class SessionNotFoundError(Exception):
    """Raised when a requested activity does not exist."""


class JoinConflictError(Exception):
    def __init__(self, code: JoinConflictCode) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class JoinResult:
    game_session: GameSession
    participant_count: int


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


def _begin_immediate(db: Session) -> None:
    db.rollback()
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    else:
        db.begin()


def _conflict(db: Session, code: JoinConflictCode) -> None:
    db.rollback()
    raise JoinConflictError(code)


def join_session(
    db: Session,
    session_id: str,
    user_id: str,
    now: datetime,
) -> JoinResult:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    _begin_immediate(db)

    try:
        game_session = db.get(GameSession, session_id)
        if game_session is None:
            db.rollback()
            raise SessionNotFoundError(session_id)

        participant = db.scalar(
            select(Participant).where(
                Participant.session_id == session_id,
                Participant.user_id == user_id,
            )
        )
        if participant is not None and participant.status == "joined":
            _conflict(db, "already_joined")

        if game_session.status == "completed" or now >= game_session.end_at:
            _conflict(db, "session_ended")
        if game_session.status == "cancelled":
            _conflict(db, "session_unavailable")

        participant_count = count_joined_participants(db, session_id)
        if (
            game_session.status != "open"
            or participant_count >= game_session.capacity
        ):
            _conflict(db, "session_full")

        if participant is None:
            participant = Participant(
                session_id=session_id,
                user_id=user_id,
                status="joined",
                joined_at=now,
            )
            db.add(participant)
        else:
            participant.status = "joined"
            participant.joined_at = now

        db.flush()
        participant_count += 1
        if participant_count >= game_session.capacity:
            game_session.status = "full"
        db.commit()
    except (JoinConflictError, SessionNotFoundError):
        raise
    except IntegrityError:
        db.rollback()
        raise JoinConflictError("already_joined") from None
    except Exception:
        db.rollback()
        raise

    return JoinResult(
        game_session=game_session,
        participant_count=participant_count,
    )


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
