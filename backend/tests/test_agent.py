import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import GameSession, RecommendationRecord, User
from app.seed import DEMO_SESSION_IDS, DEMO_USER_IDS
from app.services.agent import AgentRunError, run_agent
from app.services.deepseek import (
    ChatCompletion,
    DeepSeekUnavailableError,
    ToolCall,
)


NOW = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)
USER_ID = DEMO_USER_IDS[0]
OPEN_SESSION_ID = DEMO_SESSION_IDS[0]


def _final_reply(
    status: str = "no_match",
    candidate_id: str | None = None,
) -> str:
    recommendations = []
    suggested_action = None
    if candidate_id is not None:
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


class FakeClient:
    def __init__(self, responses):
        self.settings = Settings(
            api_key="never-persist-this",
            base_url="https://example.test",
            model="test-model",
            prompt_version="test-v1",
            timeout_seconds=1,
        )
        self.responses = list(responses)
        self.calls = []

    def complete(self, *, messages, tools, response_format=None):
        self.calls.append(
            {
                "messages": [dict(message) for message in messages],
                "tools": tools,
                "response_format": response_format,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            return response()
        return response


def _completion(content: str | None = None, tool_calls=()) -> ChatCompletion:
    return ChatCompletion(
        content=content,
        tool_calls=tuple(tool_calls),
        finish_reason="tool_calls" if tool_calls else "stop",
    )


def _search_tool_call() -> ToolCall:
    return ToolCall(
        call_id="call-search",
        name="search_candidates",
        arguments=json.dumps(
            {
                "start_at": "2026-10-29T10:00:00Z",
                "end_at": "2026-10-29T14:00:00Z",
                "area": "学校体育馆",
                "format": "doubles",
                "purpose": "casual",
            },
            ensure_ascii=False,
        ),
    )


def test_run_agent_returns_ask_without_tools_and_persists_audit(seeded_db):
    client = FakeClient([_completion(_final_reply("ask"))])

    with Session(seeded_db) as db:
        user = db.get(User, USER_ID)
        reply = run_agent(db, client, user, "我想打球", NOW)
        record = db.scalar(select(RecommendationRecord))

    assert reply.status == "ask"
    assert client.calls[0]["response_format"] is None
    assert "只输出 JSON" in client.calls[0]["messages"][0]["content"]
    assert record.request_text == "我想打球"
    assert record.model_name == "test-model"
    assert record.prompt_version == "test-v1"
    assert record.candidate_snapshot == []
    assert record.model_output["status"] == "ask"
    assert "never-persist-this" not in json.dumps(
        record.model_output, ensure_ascii=False
    )


def test_run_agent_executes_search_and_verifies_candidate(seeded_db):
    client = FakeClient(
        [
            _completion(tool_calls=[_search_tool_call()]),
            _completion(_final_reply("recommend", OPEN_SESSION_ID)),
        ]
    )

    with Session(seeded_db) as db:
        user = db.get(User, USER_ID)
        reply = run_agent(db, client, user, "找学校体育馆双打", NOW)
        record = db.scalar(select(RecommendationRecord))

    assert reply.status == "recommend"
    assert reply.recommendations[0].candidate_id == OPEN_SESSION_ID
    second_messages = client.calls[1]["messages"]
    tool_message = next(
        message for message in second_messages if message["role"] == "tool"
    )
    assert OPEN_SESSION_ID in tool_message["content"]
    assert record.candidate_snapshot[0]["id"] == OPEN_SESSION_ID


def test_unknown_tool_is_returned_to_model_as_safe_error(seeded_db):
    client = FakeClient(
        [
            _completion(
                tool_calls=[
                    ToolCall(
                        call_id="call-write",
                        name="create_session",
                        arguments="{}",
                    )
                ]
            ),
            _completion(_final_reply("ask")),
        ]
    )

    with Session(seeded_db) as db:
        user = db.get(User, USER_ID)
        run_agent(db, client, user, "发布活动", NOW)

    tool_message = next(
        message
        for message in client.calls[1]["messages"]
        if message["role"] == "tool"
    )
    assert "unknown_tool" in tool_message["content"]


def test_run_agent_rejects_candidate_that_became_unavailable(seeded_db):
    def cancel_candidate():
        with Session(seeded_db) as mutation_db:
            game_session = mutation_db.get(GameSession, OPEN_SESSION_ID)
            game_session.status = "cancelled"
            mutation_db.commit()
        return _completion(_final_reply("recommend", OPEN_SESSION_ID))

    client = FakeClient(
        [_completion(tool_calls=[_search_tool_call()]), cancel_candidate]
    )

    with Session(seeded_db) as db:
        user = db.get(User, USER_ID)
        with pytest.raises(AgentRunError) as error:
            run_agent(db, client, user, "找活动", NOW)
        record = db.scalar(select(RecommendationRecord))

    assert error.value.code == "invalid_model_output"
    assert record.model_output["error"]["code"] == "invalid_model_output"


def test_run_agent_rejects_invalid_candidate_id(seeded_db):
    client = FakeClient(
        [_completion(_final_reply("recommend", "not-a-candidate"))]
    )

    with Session(seeded_db) as db:
        user = db.get(User, USER_ID)
        with pytest.raises(AgentRunError) as error:
            run_agent(db, client, user, "找活动", NOW)

    assert error.value.code == "invalid_model_output"


def test_run_agent_stops_after_four_tool_rounds(seeded_db):
    tool_response = _completion(tool_calls=[_search_tool_call()])
    client = FakeClient([tool_response] * 4)

    with Session(seeded_db) as db:
        user = db.get(User, USER_ID)
        with pytest.raises(AgentRunError) as error:
            run_agent(db, client, user, "找活动", NOW)
        record = db.scalar(select(RecommendationRecord))

    assert len(client.calls) == 4
    assert error.value.code == "agent_loop_limit"
    assert record.model_output["error"]["code"] == "agent_loop_limit"


def test_provider_timeout_is_safe_and_audited(seeded_db):
    client = FakeClient(
        [DeepSeekUnavailableError("DeepSeek request timed out")]
    )

    with Session(seeded_db) as db:
        user = db.get(User, USER_ID)
        with pytest.raises(AgentRunError) as error:
            run_agent(db, client, user, "找活动", NOW)
        record = db.scalar(select(RecommendationRecord))

    assert error.value.code == "agent_unavailable"
    assert record.model_output["error"]["code"] == "agent_unavailable"


def test_empty_model_content_is_invalid_and_audited(seeded_db):
    client = FakeClient([_completion("")])

    with Session(seeded_db) as db:
        user = db.get(User, USER_ID)
        with pytest.raises(AgentRunError) as error:
            run_agent(db, client, user, "找活动", NOW)

    assert error.value.code == "invalid_model_output"
