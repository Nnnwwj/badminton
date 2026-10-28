import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Availability
from app.seed import DEMO_USER_IDS


DEMO_USER_ID = DEMO_USER_IDS[1]
OTHER_USER_ID = DEMO_USER_IDS[2]


def test_get_profile_returns_current_user(client, seeded_db):
    response = client.get(
        "/api/profile",
        headers={"X-Demo-User-Id": DEMO_USER_ID},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": DEMO_USER_ID,
        "nickname": "王雨",
        "area": "学校体育馆",
        "level": "beginner",
        "level_description": "打球约半年，喜欢休闲双打",
        "format_preference": "doubles",
        "purpose": "casual",
        "is_admin": False,
        "availabilities": [
            {
                "weekday": 2,
                "start_minute": 19 * 60,
                "end_minute": 21 * 60,
            }
        ],
    }


def test_get_profile_requires_demo_identity(client, seeded_db):
    response = client.get("/api/profile")

    assert response.status_code == 401


def test_get_profile_rejects_unknown_demo_identity(client, seeded_db):
    response = client.get(
        "/api/profile",
        headers={"X-Demo-User-Id": "00000000-0000-4000-8000-999999999999"},
    )

    assert response.status_code == 401


def test_put_profile_persists_new_area(client, seeded_db):
    response = client.put(
        "/api/profile",
        headers={"X-Demo-User-Id": DEMO_USER_ID},
        json={"area": "新体育馆"},
    )

    assert response.status_code == 200
    assert response.json()["area"] == "新体育馆"

    persisted = client.get(
        "/api/profile",
        headers={"X-Demo-User-Id": DEMO_USER_ID},
    )
    assert persisted.status_code == 200
    assert persisted.json()["area"] == "新体育馆"
    assert persisted.json()["level_description"] == "打球约半年，喜欢休闲双打"


def test_put_profile_replaces_only_current_users_availability(client, seeded_db):
    response = client.put(
        "/api/profile",
        headers={"X-Demo-User-Id": DEMO_USER_ID},
        json={
            "availabilities": [
                {
                    "weekday": 3,
                    "start_minute": 18 * 60,
                    "end_minute": 20 * 60 + 15,
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["availabilities"] == [
        {
            "weekday": 3,
            "start_minute": 18 * 60,
            "end_minute": 20 * 60 + 15,
        }
    ]

    with Session(seeded_db) as db:
        current_user_availability = db.scalars(
            select(Availability).where(Availability.user_id == DEMO_USER_ID)
        ).all()
        other_user_availability = db.scalars(
            select(Availability).where(Availability.user_id == OTHER_USER_ID)
        ).all()

    assert len(current_user_availability) == 1
    assert current_user_availability[0].weekday == 3
    assert len(other_user_availability) == 1
    assert other_user_availability[0].weekday == 2


@pytest.mark.parametrize(
    "protected_fields",
    [
        {"id": DEMO_USER_IDS[2]},
        {"is_admin": True},
    ],
)
def test_put_profile_rejects_protected_fields(
    client, seeded_db, protected_fields
):
    response = client.put(
        "/api/profile",
        headers={"X-Demo-User-Id": DEMO_USER_ID},
        json=protected_fields,
    )

    assert response.status_code == 422


def test_put_profile_rejects_invalid_availability_range(client, seeded_db):
    response = client.put(
        "/api/profile",
        headers={"X-Demo-User-Id": DEMO_USER_ID},
        json={
            "availabilities": [
                {
                    "weekday": 3,
                    "start_minute": 20 * 60,
                    "end_minute": 18 * 60,
                }
            ]
        },
    )

    assert response.status_code == 422
