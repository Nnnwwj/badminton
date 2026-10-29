from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import GameSession, Participant
from app.schemas import CandidateQuery, CandidateSummary


CANDIDATE_LIMIT = 20


def search_candidates(
    db: Session,
    query: CandidateQuery,
    now: datetime,
) -> list[CandidateSummary]:
    """Return available activities matching objective filters only."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)

    participant_count = (
        select(func.count(Participant.id))
        .where(
            Participant.session_id == GameSession.id,
            Participant.status == "joined",
        )
        .correlate(GameSession)
        .scalar_subquery()
    )

    conditions = [
        GameSession.status == "open",
        GameSession.end_at > now,
        participant_count < GameSession.capacity,
    ]
    if query.start_at is not None:
        conditions.append(GameSession.end_at > query.start_at)
    if query.end_at is not None:
        conditions.append(GameSession.start_at < query.end_at)
    if query.area is not None:
        conditions.append(GameSession.area == query.area)
    if query.format is not None:
        conditions.append(GameSession.format == query.format)
    if query.purpose is not None:
        conditions.append(GameSession.purpose == query.purpose)

    statement = (
        select(
            GameSession,
            participant_count.label("participant_count"),
        )
        .where(*conditions)
        .order_by(GameSession.start_at, GameSession.id)
        .limit(CANDIDATE_LIMIT)
    )

    return [
        CandidateSummary(
            id=game_session.id,
            start_at=game_session.start_at,
            end_at=game_session.end_at,
            area=game_session.area,
            venue=game_session.venue,
            format=game_session.format,
            purpose=game_session.purpose,
            level_label=game_session.level_label,
            capacity=game_session.capacity,
            participant_count=count,
            spots_remaining=game_session.capacity - count,
        )
        for game_session, count in db.execute(statement).all()
    ]
