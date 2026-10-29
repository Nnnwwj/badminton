from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models import GameSession, Participant
from app.schemas import CandidateQuery
from app.seed import DEMO_USER_IDS
from app.services.candidates import search_candidates


NOW = datetime(2026, 10, 29, 8, 0, tzinfo=timezone.utc)
CREATOR_ID = DEMO_USER_IDS[0]


def _add_candidate_session(
    engine,
    *,
    session_id: str,
    start_at: datetime,
    end_at: datetime,
    area: str,
    game_format: str = "doubles",
    purpose: str = "casual",
    status: str = "open",
    capacity: int = 4,
    participant_count: int = 0,
) -> None:
    with Session(engine) as db:
        db.add(
            GameSession(
                id=session_id,
                creator_id=CREATOR_ID,
                start_at=start_at,
                end_at=end_at,
                area=area,
                venue="测试球馆",
                format=game_format,
                purpose=purpose,
                level_label="不限",
                capacity=capacity,
                status=status,
                created_at=NOW,
            )
        )
        for index in range(participant_count):
            db.add(
                Participant(
                    session_id=session_id,
                    user_id=DEMO_USER_IDS[index + 1],
                    status="joined",
                    joined_at=NOW,
                )
            )
        db.commit()


def test_candidate_query_matches_overlapping_time_window(seeded_db):
    _add_candidate_session(
        seeded_db,
        session_id="50000000-0000-4000-8000-000000000001",
        start_at=NOW + timedelta(hours=2),
        end_at=NOW + timedelta(hours=4),
        area="时间测试区域",
    )
    _add_candidate_session(
        seeded_db,
        session_id="50000000-0000-4000-8000-000000000002",
        start_at=NOW,
        end_at=NOW + timedelta(hours=2),
        area="时间测试区域",
    )
    _add_candidate_session(
        seeded_db,
        session_id="50000000-0000-4000-8000-000000000003",
        start_at=NOW + timedelta(hours=5),
        end_at=NOW + timedelta(hours=6),
        area="时间测试区域",
    )
    query = CandidateQuery(
        start_at=NOW + timedelta(hours=3),
        end_at=NOW + timedelta(hours=5),
        area="时间测试区域",
    )

    with Session(seeded_db) as db:
        results = search_candidates(db, query, NOW)

    assert [result.id for result in results] == [
        "50000000-0000-4000-8000-000000000001"
    ]


@pytest.mark.parametrize(
    ("query", "expected_id"),
    [
        (
            CandidateQuery(area="东区筛选"),
            "50000000-0000-4000-8000-000000000011",
        ),
        (
            CandidateQuery(format="singles"),
            "50000000-0000-4000-8000-000000000011",
        ),
        (
            CandidateQuery(purpose="training"),
            "50000000-0000-4000-8000-000000000011",
        ),
    ],
    ids=["area", "format", "purpose"],
)
def test_candidate_query_applies_objective_filters(
    seeded_db, query: CandidateQuery, expected_id: str
):
    _add_candidate_session(
        seeded_db,
        session_id="50000000-0000-4000-8000-000000000011",
        start_at=NOW + timedelta(hours=1),
        end_at=NOW + timedelta(hours=2),
        area="东区筛选",
        game_format="singles",
        purpose="training",
    )
    _add_candidate_session(
        seeded_db,
        session_id="50000000-0000-4000-8000-000000000012",
        start_at=NOW + timedelta(hours=1),
        end_at=NOW + timedelta(hours=2),
        area="西区对照",
        game_format="doubles",
        purpose="casual",
    )

    with Session(seeded_db) as db:
        results = search_candidates(db, query, NOW)

    assert [result.id for result in results] == [expected_id]


def test_candidate_query_excludes_unavailable_and_full_sessions(seeded_db):
    suffix = 20
    cases = (
        (NOW + timedelta(hours=1), NOW + timedelta(hours=2), "open", 4, 1),
        (NOW + timedelta(hours=1), NOW + timedelta(hours=2), "open", 2, 2),
        (NOW + timedelta(hours=1), NOW + timedelta(hours=2), "full", 4, 1),
        (
            NOW + timedelta(hours=1),
            NOW + timedelta(hours=2),
            "cancelled",
            4,
            1,
        ),
        (
            NOW + timedelta(hours=1),
            NOW + timedelta(hours=2),
            "completed",
            4,
            1,
        ),
        (
            NOW - timedelta(hours=1),
            NOW - timedelta(minutes=1),
            "open",
            4,
            1,
        ),
    )
    for start_at, end_at, status, capacity, participant_count in cases:
        suffix += 1
        _add_candidate_session(
            seeded_db,
            session_id=f"50000000-0000-4000-8000-{suffix:012d}",
            start_at=start_at,
            end_at=end_at,
            area="不可用筛选",
            status=status,
            capacity=capacity,
            participant_count=participant_count,
        )

    with Session(seeded_db) as db:
        results = search_candidates(
            db,
            CandidateQuery(area="不可用筛选"),
            NOW,
        )

    assert [result.id for result in results] == [
        "50000000-0000-4000-8000-000000000021"
    ]


def test_candidate_query_counts_each_session_once_and_calculates_spots(
    seeded_db,
):
    _add_candidate_session(
        seeded_db,
        session_id="50000000-0000-4000-8000-000000000031",
        start_at=NOW + timedelta(hours=1),
        end_at=NOW + timedelta(hours=2),
        area="去重测试",
        capacity=5,
        participant_count=3,
    )

    with Session(seeded_db) as db:
        results = search_candidates(db, CandidateQuery(area="去重测试"), NOW)

    assert len(results) == 1
    assert results[0].participant_count == 3
    assert results[0].spots_remaining == 2


def test_candidate_query_returns_first_twenty_in_stable_order(seeded_db):
    for index in range(22, 0, -1):
        _add_candidate_session(
            seeded_db,
            session_id=f"50000000-0000-4000-8000-{index:012d}",
            start_at=NOW + timedelta(hours=(index + 1) // 2),
            end_at=NOW + timedelta(hours=(index + 1) // 2 + 1),
            area="排序测试",
        )

    with Session(seeded_db) as db:
        results = search_candidates(db, CandidateQuery(area="排序测试"), NOW)

    assert len(results) == 20
    assert [result.id for result in results] == [
        f"50000000-0000-4000-8000-{index:012d}" for index in range(1, 21)
    ]


def test_candidate_summary_contains_only_public_activity_fields(seeded_db):
    _add_candidate_session(
        seeded_db,
        session_id="50000000-0000-4000-8000-000000000041",
        start_at=NOW + timedelta(hours=1),
        end_at=NOW + timedelta(hours=2),
        area="隐私测试",
        participant_count=1,
    )

    with Session(seeded_db) as db:
        results = search_candidates(db, CandidateQuery(area="隐私测试"), NOW)

    assert len(results) == 1
    assert set(results[0].model_dump()) == {
        "id",
        "start_at",
        "end_at",
        "area",
        "venue",
        "format",
        "purpose",
        "level_label",
        "capacity",
        "participant_count",
        "spots_remaining",
    }
    assert "nickname" not in results[0].model_dump()
    assert "phone" not in results[0].model_dump()
