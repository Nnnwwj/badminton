from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Feedback
from app.seed import DEMO_SESSION_IDS, DEMO_USER_IDS


ADMIN_ID = DEMO_USER_IDS[0]
REGULAR_USER_ID = DEMO_USER_IDS[1]
ENDED_SESSION_ID = DEMO_SESSION_IDS[2]
OPEN_SESSION_ID = DEMO_SESSION_IDS[0]
FULL_SESSION_ID = DEMO_SESSION_IDS[1]


def test_regular_user_cannot_view_feedback_summary(client, seeded_db):
    response = client.get(
        "/api/admin/feedback-summary",
        headers={"X-Demo-User-Id": REGULAR_USER_ID},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "admin_required"


def test_admin_gets_aggregate_counts_without_private_feedback_text(
    client, seeded_db
):
    submitted_at = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)
    with Session(seeded_db) as db:
        db.add_all(
            [
                Feedback(
                    session_id=ENDED_SESSION_ID,
                    user_id=DEMO_USER_IDS[3],
                    rating="unsuitable",
                    reason_category="time",
                    comment="私人反馈：时间临时变化",
                    submitted_at=submitted_at,
                ),
                Feedback(
                    session_id=ENDED_SESSION_ID,
                    user_id=DEMO_USER_IDS[4],
                    rating="average",
                    reason_category="level",
                    comment="私人反馈：水平不一致",
                    submitted_at=submitted_at,
                ),
                Feedback(
                    session_id=OPEN_SESSION_ID,
                    user_id=REGULAR_USER_ID,
                    rating="unsuitable",
                    reason_category="level",
                    comment="私人反馈：强度太高",
                    submitted_at=submitted_at,
                ),
                Feedback(
                    session_id=FULL_SESSION_ID,
                    user_id=DEMO_USER_IDS[2],
                    rating="average",
                    reason_category="other",
                    comment="私人反馈：其他原因",
                    submitted_at=submitted_at,
                ),
            ]
        )
        db.commit()

    response = client.get(
        "/api/admin/feedback-summary",
        headers={"X-Demo-User-Id": ADMIN_ID},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "total": 4,
        "reason_counts": {
            "time": 1,
            "location": 0,
            "level": 2,
            "purpose": 0,
            "no_show": 0,
            "other": 1,
        },
    }
    assert "私人反馈" not in response.text
    assert "王雨" not in response.text
    assert "nickname" not in response.text
