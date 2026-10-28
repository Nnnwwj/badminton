from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import GameSession, Participant
from app.seed import DEMO_SESSION_IDS, DEMO_USER_IDS


NOW = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)
OPEN_SESSION_ID = DEMO_SESSION_IDS[0]
FULL_SESSION_ID = DEMO_SESSION_IDS[1]
ENDED_SESSION_ID = DEMO_SESSION_IDS[2]


def test_user_can_join_open_session(client, seeded_db):
    response = client.post(
        f"/api/sessions/{OPEN_SESSION_ID}/join",
        headers={"X-Demo-User-Id": DEMO_USER_IDS[0]},
    )

    assert response.status_code == 200
    assert response.json()["participant_count"] == 2
    assert response.json()["spots_remaining"] == 2


def test_join_rejects_duplicate_participant(client, seeded_db):
    response = client.post(
        f"/api/sessions/{OPEN_SESSION_ID}/join",
        headers={"X-Demo-User-Id": DEMO_USER_IDS[1]},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "already_joined"


def test_join_rejects_full_session(client, seeded_db):
    response = client.post(
        f"/api/sessions/{FULL_SESSION_ID}/join",
        headers={"X-Demo-User-Id": DEMO_USER_IDS[0]},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "session_full"


def test_join_rejects_ended_session(client, seeded_db):
    response = client.post(
        f"/api/sessions/{ENDED_SESSION_ID}/join",
        headers={"X-Demo-User-Id": DEMO_USER_IDS[0]},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "session_ended"


def test_join_returns_404_for_unknown_session(client, seeded_db):
    response = client.post(
        "/api/sessions/00000000-0000-4000-8000-999999999999/join",
        headers={"X-Demo-User-Id": DEMO_USER_IDS[0]},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "session_not_found"


def test_join_requires_demo_identity(client, seeded_db):
    response = client.post(f"/api/sessions/{OPEN_SESSION_ID}/join")

    assert response.status_code == 401


def test_concurrent_join_has_exactly_one_winner(client, seeded_db):
    last_spot_session_id = "40000000-0000-4000-8000-000000000001"
    creator_id = DEMO_USER_IDS[0]
    with Session(seeded_db) as db:
        db.add(
            GameSession(
                id=last_spot_session_id,
                creator_id=creator_id,
                start_at=NOW + timedelta(days=1),
                end_at=NOW + timedelta(days=1, hours=2),
                area="学校体育馆",
                venue="3号场",
                format="doubles",
                purpose="casual",
                level_label="beginner",
                capacity=2,
                status="open",
                created_at=NOW,
            )
        )
        db.add(
            Participant(
                session_id=last_spot_session_id,
                user_id=creator_id,
                status="joined",
                joined_at=NOW,
            )
        )
        db.commit()

    barrier = Barrier(2)

    def attempt_join(user_id):
        barrier.wait()
        return client.post(
            f"/api/sessions/{last_spot_session_id}/join",
            headers={"X-Demo-User-Id": user_id},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                attempt_join,
                [DEMO_USER_IDS[1], DEMO_USER_IDS[2]],
            )
        )

    assert sorted(response.status_code for response in responses) == [200, 409]
    conflict = next(
        response for response in responses if response.status_code == 409
    )
    assert conflict.json()["detail"]["code"] == "session_full"

    with Session(seeded_db) as db:
        joined_count = db.scalar(
            select(func.count())
            .select_from(Participant)
            .where(
                Participant.session_id == last_spot_session_id,
                Participant.status == "joined",
            )
        )
        game_session = db.get(GameSession, last_spot_session_id)

    assert joined_count == 2
    assert game_session.status == "full"
