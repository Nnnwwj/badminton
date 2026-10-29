from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.models import Feedback
from app.seed import DEMO_SESSION_IDS, DEMO_USER_IDS
from app.services.agent_tools import AgentToolError, execute_tool, tool_definitions


NOW = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)
USER_ID = DEMO_USER_IDS[0]
OPEN_SESSION_ID = DEMO_SESSION_IDS[0]


def test_tool_definitions_are_read_only_and_have_strict_schemas():
    tools = tool_definitions()

    assert {tool["function"]["name"] for tool in tools} == {
        "search_candidates",
        "get_my_feedback_summary",
    }
    search_schema = tools[0]["function"]["parameters"]
    assert search_schema["additionalProperties"] is False
    assert set(search_schema["properties"]) == {
        "start_at",
        "end_at",
        "area",
        "format",
        "purpose",
    }


def test_search_candidates_tool_returns_public_candidate_data(seeded_db):
    with Session(seeded_db) as db:
        execution = execute_tool(
            db,
            USER_ID,
            "search_candidates",
            {
                "start_at": "2026-10-29T10:00:00Z",
                "end_at": "2026-10-29T14:00:00Z",
                "area": "学校体育馆",
                "format": "doubles",
                "purpose": "casual",
            },
            NOW,
        )

    assert execution.name == "search_candidates"
    assert [candidate["id"] for candidate in execution.content["candidates"]] == [
        OPEN_SESSION_ID
    ]
    candidate = execution.content["candidates"][0]
    assert candidate["spots_remaining"] == 3
    assert "nickname" not in candidate
    assert "phone" not in candidate


def test_feedback_tool_uses_only_current_user(seeded_db):
    with Session(seeded_db) as db:
        db.add_all(
            [
                Feedback(
                    session_id=OPEN_SESSION_ID,
                    user_id=USER_ID,
                    rating="unsuitable",
                    reason_category="time",
                    comment="当前用户私人反馈",
                    submitted_at=NOW,
                ),
                Feedback(
                    session_id=DEMO_SESSION_IDS[2],
                    user_id=DEMO_USER_IDS[1],
                    rating="average",
                    reason_category="level",
                    comment="其他用户私人反馈",
                    submitted_at=NOW,
                ),
            ]
        )
        db.commit()
        execution = execute_tool(
            db,
            USER_ID,
            "get_my_feedback_summary",
            {},
            NOW,
        )

    assert execution.content == {
        "total": 1,
        "reason_counts": {
            "time": 1,
            "location": 0,
            "level": 0,
            "purpose": 0,
            "no_show": 0,
            "other": 0,
        },
    }
    assert "私人反馈" not in str(execution.content)
    assert "nickname" not in execution.content


@pytest.mark.parametrize(
    ("name", "arguments", "code"),
    [
        ("write_session", {}, "unknown_tool"),
        ("search_candidates", {"unknown": 1}, "invalid_arguments"),
        ("search_candidates", {"format": "mixed"}, "invalid_arguments"),
        ("search_candidates", {"start_at": "2026-10-29T10:00:00"}, "invalid_arguments"),
        (
            "search_candidates",
            {
                "start_at": "2026-10-29T12:00:00Z",
                "end_at": "2026-10-29T10:00:00Z",
            },
            "invalid_arguments",
        ),
        ("get_my_feedback_summary", {"user_id": "someone-else"}, "invalid_arguments"),
    ],
)
def test_invalid_tool_calls_are_rejected(
    seeded_db, name, arguments, code
):
    with Session(seeded_db) as db:
        with pytest.raises(AgentToolError) as error:
            execute_tool(db, USER_ID, name, arguments, NOW)

    assert error.value.code == code
