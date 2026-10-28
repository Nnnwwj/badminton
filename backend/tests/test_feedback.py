import pytest
from sqlalchemy.orm import Session

from app.models import Feedback
from app.seed import DEMO_SESSION_IDS, DEMO_USER_IDS


OPEN_SESSION_ID = DEMO_SESSION_IDS[0]
ENDED_SESSION_ID = DEMO_SESSION_IDS[2]
PARTICIPANT_ID = DEMO_USER_IDS[4]
NON_PARTICIPANT_ID = DEMO_USER_IDS[0]

FEEDBACK_PAYLOAD = {
    "rating": "suitable",
    "reason_category": "level",
    "comment": "双方节奏合适，希望下次继续。",
}


def test_non_participant_cannot_submit_feedback(client, seeded_db):
    response = client.post(
        f"/api/sessions/{ENDED_SESSION_ID}/feedback",
        headers={"X-Demo-User-Id": NON_PARTICIPANT_ID},
        json={"rating": "suitable", "reason_category": "level"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "not_participant"


def test_participant_can_submit_feedback_after_session_ends(client, seeded_db):
    response = client.post(
        f"/api/sessions/{ENDED_SESSION_ID}/feedback",
        headers={"X-Demo-User-Id": PARTICIPANT_ID},
        json=FEEDBACK_PAYLOAD,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["session_id"] == ENDED_SESSION_ID
    assert body["user_id"] == PARTICIPANT_ID
    assert body["rating"] == "suitable"
    assert body["reason_category"] == "level"
    assert body["comment"] == FEEDBACK_PAYLOAD["comment"]
    assert body["submitted_at"] == "2026-10-28T08:00:00Z"

    with Session(seeded_db) as db:
        persisted = db.get(Feedback, body["id"])

    assert persisted is not None
    assert persisted.session_id == ENDED_SESSION_ID


def test_feedback_is_rejected_before_session_ends(client, seeded_db):
    response = client.post(
        f"/api/sessions/{OPEN_SESSION_ID}/feedback",
        headers={"X-Demo-User-Id": DEMO_USER_IDS[1]},
        json=FEEDBACK_PAYLOAD,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "session_not_ended"


def test_participant_cannot_submit_feedback_twice(client, seeded_db):
    first_response = client.post(
        f"/api/sessions/{ENDED_SESSION_ID}/feedback",
        headers={"X-Demo-User-Id": PARTICIPANT_ID},
        json=FEEDBACK_PAYLOAD,
    )
    assert first_response.status_code == 201

    second_response = client.post(
        f"/api/sessions/{ENDED_SESSION_ID}/feedback",
        headers={"X-Demo-User-Id": PARTICIPANT_ID},
        json=FEEDBACK_PAYLOAD,
    )

    assert second_response.status_code == 409
    assert (
        second_response.json()["detail"]["code"]
        == "feedback_already_submitted"
    )


def test_feedback_returns_404_for_unknown_session(client, seeded_db):
    response = client.post(
        "/api/sessions/00000000-0000-4000-8000-999999999999/feedback",
        headers={"X-Demo-User-Id": PARTICIPANT_ID},
        json=FEEDBACK_PAYLOAD,
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "session_not_found"


def test_feedback_requires_demo_identity(client, seeded_db):
    response = client.post(
        f"/api/sessions/{ENDED_SESSION_ID}/feedback",
        json=FEEDBACK_PAYLOAD,
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {"rating": "great", "reason_category": "level"},
        {"rating": "suitable", "reason_category": "weather"},
    ],
)
def test_feedback_rejects_invalid_enum_values(
    client, seeded_db, invalid_payload
):
    response = client.post(
        f"/api/sessions/{ENDED_SESSION_ID}/feedback",
        headers={"X-Demo-User-Id": PARTICIPANT_ID},
        json=invalid_payload,
    )

    assert response.status_code == 422
