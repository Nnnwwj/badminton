import json

from app.config import Settings
from app.dependencies import get_deepseek_client
from app.main import app
from app.seed import DEMO_SESSION_IDS, DEMO_USER_IDS
from app.services.deepseek import ChatCompletion


USER_A_ID = DEMO_USER_IDS[0]
PARTICIPANT_B_ID = DEMO_USER_IDS[4]
ENDED_SESSION_ID = DEMO_SESSION_IDS[2]


def test_openapi_contains_the_stable_backend_contract(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert set(response.json()["paths"]) == {
        "/api/admin/feedback-summary",
        "/api/agent/chat",
        "/api/health",
        "/api/profile",
        "/api/sessions",
        "/api/sessions/{session_id}/feedback",
        "/api/sessions/{session_id}/join",
    }


def test_backend_mvp_flow(client, seeded_db):
    headers_a = {"X-Demo-User-Id": USER_A_ID}

    profile = client.get("/api/profile", headers=headers_a)
    assert profile.status_code == 200
    assert profile.json()["id"] == USER_A_ID

    updated_profile = client.put(
        "/api/profile",
        headers=headers_a,
        json={"area": "验收测试体育馆"},
    )
    assert updated_profile.status_code == 200
    assert updated_profile.json()["area"] == "验收测试体育馆"

    sessions = client.get("/api/sessions", headers=headers_a)
    assert sessions.status_code == 200
    candidate = next(
        session
        for session in sessions.json()
        if session["status"] == "open" and session["spots_remaining"] > 0
    )

    joined = client.post(
        f"/api/sessions/{candidate['id']}/join",
        headers=headers_a,
    )
    assert joined.status_code == 200
    assert joined.json()["participant_count"] == candidate["participant_count"] + 1
    assert joined.json()["spots_remaining"] == candidate["spots_remaining"] - 1

    duplicate = client.post(
        f"/api/sessions/{candidate['id']}/join",
        headers=headers_a,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "already_joined"

    feedback = client.post(
        f"/api/sessions/{ENDED_SESSION_ID}/feedback",
        headers={"X-Demo-User-Id": PARTICIPANT_B_ID},
        json={
            "rating": "suitable",
            "reason_category": "level",
            "comment": "验收流程反馈",
        },
    )
    assert feedback.status_code == 201
    assert feedback.json()["session_id"] == ENDED_SESSION_ID

    summary = client.get(
        "/api/admin/feedback-summary",
        headers=headers_a,
    )
    assert summary.status_code == 200
    assert summary.json() == {
        "total": 1,
        "reason_counts": {
            "time": 0,
            "location": 0,
            "level": 1,
            "purpose": 0,
            "no_show": 0,
            "other": 0,
        },
    }
    assert "验收流程反馈" not in summary.text

    class AcceptanceAgentClient:
        settings = Settings(
            api_key="acceptance-secret",
            base_url="https://example.test",
            model="acceptance-model",
            prompt_version="acceptance-v1",
            timeout_seconds=1,
        )

        def complete(self, *, messages, tools, response_format=None):
            return ChatCompletion(
                content=json.dumps(
                    {
                        "status": "no_match",
                        "message": "当前没有符合条件的新活动。",
                        "questions": [],
                        "recommendations": [],
                        "suggested_action": None,
                    },
                    ensure_ascii=False,
                ),
                tool_calls=(),
                finish_reason="stop",
            )

    app.dependency_overrides[get_deepseek_client] = AcceptanceAgentClient
    try:
        agent = client.post(
            "/api/agent/chat",
            headers=headers_a,
            json={"message": "帮我找明天的活动"},
        )
    finally:
        app.dependency_overrides.pop(get_deepseek_client, None)

    assert agent.status_code == 200
    assert agent.json()["status"] == "no_match"
    assert "acceptance-secret" not in agent.text
