from datetime import datetime, time, timedelta, timezone

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.models import (
    AgentConfig,
    Availability,
    GameSession,
    Participant,
    User,
)


DEMO_USER_IDS = tuple(
    f"00000000-0000-4000-8000-{number:012d}" for number in range(1, 7)
)
DEMO_SESSION_IDS = tuple(
    f"10000000-0000-4000-8000-{number:012d}" for number in range(1, 4)
)
DEMO_ADMIN_ID = DEMO_USER_IDS[0]


def _at_utc(now: datetime, day_delta: int, hour: int) -> datetime:
    target_date = (now + timedelta(days=day_delta)).date()
    return datetime.combine(target_date, time(hour=hour), tzinfo=timezone.utc)


def _add_if_missing(db: Session, model, record_id: str, **values) -> None:
    if db.get(model, record_id) is None:
        primary_key_columns = model.__table__.primary_key.columns
        if len(primary_key_columns) != 1:
            raise ValueError(f"{model.__name__} must have exactly one primary key")
        primary_key_name = next(iter(primary_key_columns)).key
        db.add(model(**{primary_key_name: record_id}, **values))


def seed_database(engine: Engine, *, now: datetime | None = None) -> None:
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)

    user_rows = (
        (
            "李晨",
            "学校体育馆",
            "beginner",
            "能连续对打，想先以提高稳定性为主",
            "doubles",
            "casual",
            True,
        ),
        (
            "王雨",
            "学校体育馆",
            "beginner",
            "打球约半年，喜欢休闲双打",
            "doubles",
            "casual",
            False,
        ),
        (
            "陈舟",
            "东区球馆",
            "skilled",
            "有固定训练习惯，可以配合练习",
            "doubles",
            "training",
            False,
        ),
        (
            "赵宁",
            "学校体育馆",
            "newbie",
            "刚开始学球，希望节奏轻松",
            "either",
            "casual",
            False,
        ),
        (
            "周岚",
            "西区球馆",
            "skilled",
            "单双打都可以，注重练习质量",
            "either",
            "training",
            False,
        ),
        (
            "孙禾",
            "学校体育馆",
            "beginner",
            "以周末休闲运动为主",
            "doubles",
            "casual",
            False,
        ),
    )

    with Session(engine) as db:
        for user_id, row in zip(DEMO_USER_IDS, user_rows, strict=True):
            nickname, area, level, level_description, format_pref, purpose, admin = row
            _add_if_missing(
                db,
                User,
                user_id,
                nickname=nickname,
                area=area,
                level=level,
                level_description=level_description,
                format_preference=format_pref,
                purpose=purpose,
                is_admin=admin,
                created_at=now,
            )

        for index, user_id in enumerate(DEMO_USER_IDS, start=1):
            _add_if_missing(
                db,
                Availability,
                f"20000000-0000-4000-8000-{index:012d}",
                user_id=user_id,
                weekday=2,
                start_minute=19 * 60,
                end_minute=21 * 60,
            )

        session_rows = (
            (
                DEMO_USER_IDS[1],
                _at_utc(now, 1, 11),
                _at_utc(now, 1, 13),
                "学校体育馆",
                "2号场",
                "doubles",
                "casual",
                "入门-熟练",
                4,
                "open",
                (DEMO_USER_IDS[1],),
            ),
            (
                DEMO_USER_IDS[2],
                _at_utc(now, 2, 11),
                _at_utc(now, 2, 12),
                "东区球馆",
                "1号场",
                "doubles",
                "training",
                "熟练",
                2,
                "full",
                (DEMO_USER_IDS[2], DEMO_USER_IDS[3]),
            ),
            (
                DEMO_USER_IDS[4],
                _at_utc(now, -2, 11),
                _at_utc(now, -2, 13),
                "西区球馆",
                "3号场",
                "doubles",
                "casual",
                "入门",
                4,
                "completed",
                (DEMO_USER_IDS[4], DEMO_USER_IDS[5]),
            ),
        )

        participant_number = 1
        for session_id, row in zip(DEMO_SESSION_IDS, session_rows, strict=True):
            (
                creator_id,
                start_at,
                end_at,
                area,
                venue,
                game_format,
                purpose,
                level_label,
                capacity,
                status,
                participant_ids,
            ) = row
            _add_if_missing(
                db,
                GameSession,
                session_id,
                creator_id=creator_id,
                start_at=start_at,
                end_at=end_at,
                area=area,
                venue=venue,
                format=game_format,
                purpose=purpose,
                level_label=level_label,
                capacity=capacity,
                status=status,
                created_at=now,
            )
            db.flush()

            for user_id in participant_ids:
                participant_id = (
                    f"30000000-0000-4000-8000-{participant_number:012d}"
                )
                _add_if_missing(
                    db,
                    Participant,
                    participant_id,
                    session_id=session_id,
                    user_id=user_id,
                    status="joined",
                    joined_at=now,
                )
                participant_number += 1

        _add_if_missing(
            db,
            AgentConfig,
            "v1",
            changed_at=now,
            change_reason="Initial prompt plan",
        )
        db.commit()
