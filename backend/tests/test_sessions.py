import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GameSession, Participant
from app.seed import DEMO_SESSION_IDS, DEMO_USER_IDS


DEMO_USER_ID = DEMO_USER_IDS[1]

SESSION_PAYLOAD = {
    "start_at": "2026-11-04T11:00:00Z",
    "end_at": "2026-11-04T13:00:00Z",
    "area": "学校体育馆",
    "venue": "2号场",
    "format": "doubles",
    "purpose": "casual",
    "level_label": "beginner",
    "capacity": 4,
}


def test_create_session_adds_creator_as_participant(client, seeded_db):
    response = client.post(
        "/api/sessions",
        headers={"X-Demo-User-Id": DEMO_USER_ID},
        json=SESSION_PAYLOAD,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["creator_id"] == DEMO_USER_ID
    assert body["status"] == "open"
    assert body["participant_count"] == 1
    assert body["spots_remaining"] == 3

    with Session(seeded_db) as db:
        game_session = db.get(GameSession, body["id"])
        participant = db.scalar(
            select(Participant).where(
                Participant.session_id == body["id"],
                Participant.user_id == DEMO_USER_ID,
            )
        )

    assert game_session is not None
    assert participant is not None
    assert participant.status == "joined"


def test_list_sessions_returns_public_counts(client, seeded_db):
    response = client.get(
        "/api/sessions",
        headers={"X-Demo-User-Id": DEMO_USER_ID},
    )

    assert response.status_code == 200
    sessions = {item["id"]: item for item in response.json()}
    assert len(sessions) == 3
    assert sessions[DEMO_SESSION_IDS[0]]["participant_count"] == 1
    assert sessions[DEMO_SESSION_IDS[0]]["spots_remaining"] == 3
    assert sessions[DEMO_SESSION_IDS[1]]["participant_count"] == 2
    assert sessions[DEMO_SESSION_IDS[1]]["spots_remaining"] == 0
    assert sessions[DEMO_SESSION_IDS[2]]["participant_count"] == 2
    assert sessions[DEMO_SESSION_IDS[2]]["spots_remaining"] == 2

    for game_session in sessions.values():
        assert set(game_session) == {
            "id",
            "creator_id",
            "start_at",
            "end_at",
            "area",
            "venue",
            "format",
            "purpose",
            "level_label",
            "capacity",
            "status",
            "created_at",
            "participant_count",
            "spots_remaining",
        }


def test_list_sessions_requires_demo_identity(client, seeded_db):
    response = client.get("/api/sessions")

    assert response.status_code == 401


def test_create_session_requires_demo_identity(client, seeded_db):
    response = client.post("/api/sessions", json=SESSION_PAYLOAD)

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("start_at", "end_at"),
    [
        ("2026-11-04T11:00:00Z", "2026-11-04T11:00:00Z"),
        ("2026-11-04T13:00:00Z", "2026-11-04T11:00:00Z"),
    ],
)
def test_create_session_rejects_non_positive_duration(
    client, seeded_db, start_at, end_at
):
    response = client.post(
        "/api/sessions",
        headers={"X-Demo-User-Id": DEMO_USER_ID},
        json={**SESSION_PAYLOAD, "start_at": start_at, "end_at": end_at},
    )

    assert response.status_code == 422


def test_create_session_rejects_capacity_below_two(client, seeded_db):
    response = client.post(
        "/api/sessions",
        headers={"X-Demo-User-Id": DEMO_USER_ID},
        json={**SESSION_PAYLOAD, "capacity": 1},
    )

    assert response.status_code == 422


def test_create_session_rejects_naive_datetime(client, seeded_db):
    response = client.post(
        "/api/sessions",
        headers={"X-Demo-User-Id": DEMO_USER_ID},
        json={
            **SESSION_PAYLOAD,
            "start_at": "2026-11-04T11:00:00",
            "end_at": "2026-11-04T13:00:00",
        },
    )

    assert response.status_code == 422
