from datetime import datetime, timedelta, timezone

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.models import (
    AgentConfig,
    Availability,
    Feedback,
    GameSession,
    Participant,
    RecommendationRecord,
    User,
)
from app.seed import seed_database


NOW = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)


def test_database_contains_all_mvp_tables(engine):
    table_names = set(inspect(engine).get_table_names())

    assert table_names == {
        "agent_config",
        "availability",
        "feedback",
        "participants",
        "recommendations",
        "sessions",
        "users",
    }


def test_seed_creates_six_users_and_three_sessions(engine):
    seed_database(engine, now=NOW)

    with Session(engine) as db:
        user_count = db.scalar(select(func.count()).select_from(User))
        session_count = db.scalar(select(func.count()).select_from(GameSession))
        availability_count = db.scalar(
            select(func.count()).select_from(Availability)
        )

    assert user_count == 6
    assert session_count == 3
    assert availability_count > 0


def test_seed_includes_one_admin(engine):
    seed_database(engine, now=NOW)

    with Session(engine) as db:
        admin_count = db.scalar(
            select(func.count()).select_from(User).where(User.is_admin.is_(True))
        )

    assert admin_count == 1


def test_seed_covers_future_full_and_ended_sessions(engine):
    seed_database(engine, now=NOW)

    with Session(engine) as db:
        sessions = db.scalars(select(GameSession)).all()
        future_open = next(
            session
            for session in sessions
            if session.status == "open" and session.start_at > NOW
        )
        full_session = next(
            session for session in sessions if session.status == "full"
        )
        ended_session = next(
            session for session in sessions if session.status == "completed"
        )
        full_count = db.scalar(
            select(func.count())
            .select_from(Participant)
            .where(Participant.session_id == full_session.id)
        )

    assert future_open.capacity > 1
    assert ended_session.end_at < NOW
    assert full_count == full_session.capacity


def test_seed_datetimes_round_trip_as_utc(engine):
    seed_database(engine, now=NOW)

    with Session(engine) as db:
        session = db.scalar(
            select(GameSession).where(GameSession.start_at > NOW)
        )

    assert session is not None
    assert session.start_at.utcoffset() == timedelta(0)
    assert session.end_at.utcoffset() == timedelta(0)


def test_seed_is_idempotent(engine):
    seed_database(engine, now=NOW)
    seed_database(engine, now=NOW)

    with Session(engine) as db:
        counts = {
            "users": db.scalar(select(func.count()).select_from(User)),
            "sessions": db.scalar(select(func.count()).select_from(GameSession)),
            "participants": db.scalar(
                select(func.count()).select_from(Participant)
            ),
            "feedback": db.scalar(select(func.count()).select_from(Feedback)),
            "recommendations": db.scalar(
                select(func.count()).select_from(RecommendationRecord)
            ),
            "agent_config": db.scalar(
                select(func.count()).select_from(AgentConfig)
            ),
        }

    assert counts["users"] == 6
    assert counts["sessions"] == 3
    assert counts["participants"] == 5
    assert counts["feedback"] == 0
    assert counts["recommendations"] == 0
    assert counts["agent_config"] == 1
