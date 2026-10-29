import json
from datetime import datetime, timezone

import pytest

from app.config import Settings
from app.dependencies import get_deepseek_client
from app.main import app
from app.seed import DEMO_SESSION_IDS, DEMO_USER_IDS
from app.services.deepseek import (
    ChatCompletion,
    DeepSeekUnavailableError,
    ToolCall,
)


USER_ID = DEMO_USER_IDS[0]
OPEN_SESSION_ID = DEMO_SESSION_IDS[0]


class FakeAgentClient:
    def __init__(self, responses):
        self.settings = Settings(
            api_key="api-test-secret",
            base_url="https://example.test",
            model="api-test-model",
            prompt_version="api-test-v1",
            timeout_seconds=1,
        )
        self.responses = list(responses)

    def complete(self, *, messages, tools, response_format=None):
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _reply(status="ask", candidate_id=None):
    recommendations = []
    suggested_action = None
    if candidate_id:
        recommendations = [
            {
                "candidate_id": candidate_id,
                "reason": "时间和区域符合。",
                "tradeoff": "水平还需确认。",
            }
        ]
        suggested_action = "join_session"
    return json.dumps(
        {
            "status": status,
            "message": "测试回复",
            "questions": ["你计划哪天去？"] if status == "ask" else [],
            "recommendations": recommendations,
            "suggested_action": suggested_action,
        },
        ensure_ascii=False,
    )


def _completion(content=None, tool_calls=()):
    return ChatCompletion(
        content=content,
        tool_calls=tuple(tool_calls),
        finish_reason="tool_calls" if tool_calls else "stop",
    )


@pytest.fixture
def agent_client_override(client):
    def install(fake_client):
        app.dependency_overrides[get_deepseek_client] = lambda: fake_client

    yield install
    app.dependency_overrides.pop(get_deepseek_client, None)


def test_agent_chat_requires_demo_identity(client, seeded_db):
    response = client.post("/api/agent/chat", json={"message": "找活动"})

    assert response.status_code == 401


def test_agent_chat_rejects_empty_message(
    client, seeded_db, agent_client_override
):
    agent_client_override(FakeAgentClient([]))

    response = client.post(
        "/api/agent/chat",
        headers={"X-Demo-User-Id": USER_ID},
        json={"message": ""},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("status", ["ask", "no_match"])
def test_agent_chat_returns_simple_statuses(
    client, seeded_db, agent_client_override, status
):
    agent_client_override(FakeAgentClient([_completion(_reply(status))]))

    response = client.post(
        "/api/agent/chat",
        headers={"X-Demo-User-Id": USER_ID},
        json={"message": "找活动"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == status


def test_agent_chat_returns_verified_recommendation(
    client, seeded_db, agent_client_override
):
    search_call = ToolCall(
        call_id="call-search",
        name="search_candidates",
        arguments=json.dumps(
            {
                "start_at": "2026-10-28T10:00:00Z",
                "end_at": "2026-10-30T14:00:00Z",
                "area": "学校体育馆",
                "format": "doubles",
                "purpose": "casual",
            },
            ensure_ascii=False,
        ),
    )
    agent_client_override(
        FakeAgentClient(
            [
                _completion(tool_calls=[search_call]),
                _completion(_reply("recommend", OPEN_SESSION_ID)),
            ]
        )
    )

    response = client.post(
        "/api/agent/chat",
        headers={"X-Demo-User-Id": USER_ID},
        json={"message": "学校体育馆双打"},
    )

    assert response.status_code == 200
    assert response.json()["recommendations"][0]["candidate_id"] == OPEN_SESSION_ID


def test_agent_chat_maps_provider_failure_to_safe_503(
    client, seeded_db, agent_client_override
):
    agent_client_override(
        FakeAgentClient(
            [DeepSeekUnavailableError("provider said api-test-secret")]
        )
    )

    response = client.post(
        "/api/agent/chat",
        headers={"X-Demo-User-Id": USER_ID},
        json={"message": "找活动"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "agent_unavailable"
    assert "api-test-secret" not in response.text


def test_agent_chat_maps_malformed_output_to_safe_502(
    client, seeded_db, agent_client_override
):
    agent_client_override(FakeAgentClient([_completion("not json")]))

    response = client.post(
        "/api/agent/chat",
        headers={"X-Demo-User-Id": USER_ID},
        json={"message": "找活动"},
    )

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "invalid_model_output"
