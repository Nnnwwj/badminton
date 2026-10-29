from datetime import datetime, timezone

import pytest

from app.schemas import CandidateSummary
from app.services.agent_output import AgentOutputError, parse_agent_reply


CANDIDATE_ID = "10000000-0000-4000-8000-000000000001"
CANDIDATES = {
    CANDIDATE_ID: CandidateSummary(
        id=CANDIDATE_ID,
        start_at=datetime(2026, 10, 29, 11, tzinfo=timezone.utc),
        end_at=datetime(2026, 10, 29, 13, tzinfo=timezone.utc),
        area="学校体育馆",
        venue="2号场",
        format="doubles",
        purpose="casual",
        level_label="入门-熟练",
        capacity=4,
        participant_count=1,
        spots_remaining=3,
    )
}


def test_parse_ask_reply():
    reply = parse_agent_reply(
        '{"status":"ask","message":"还需要确认时间。",'
        '"questions":["你计划哪天去？"],'
        '"recommendations":[],"suggested_action":null}',
        CANDIDATES,
    )

    assert reply.status == "ask"
    assert reply.questions == ["你计划哪天去？"]


def test_parse_recommend_reply_with_code_fence():
    reply = parse_agent_reply(
        "```json\n"
        '{"status":"recommend","message":"找到一场活动。",'
        '"questions":[],"recommendations":[{"candidate_id":"'
        + CANDIDATE_ID
        + '","reason":"时间和区域符合。","tradeoff":"水平还需确认。"}],'
        '"suggested_action":"join_session"}\n```',
        CANDIDATES,
    )

    assert reply.status == "recommend"
    assert reply.recommendations[0].candidate_id == CANDIDATE_ID


@pytest.mark.parametrize("status", ["no_match", "error"])
def test_parse_empty_recommendation_statuses(status):
    reply = parse_agent_reply(
        '{"status":"'
        + status
        + '","message":"当前无法推荐。","questions":[],'
        '"recommendations":[],"suggested_action":null}',
        CANDIDATES,
    )

    assert reply.status == status
    assert reply.recommendations == []


@pytest.mark.parametrize(
    "content",
    [
        "",
        "not json",
        "```json\n{}\n```\ntrailing",
        '{"status":"unknown","message":"x","questions":[],'
        '"recommendations":[],"suggested_action":null}',
        '{"status":"ask","message":"x","questions":[],'
        '"recommendations":[],"suggested_action":null}',
        '{"status":"ask","message":"x","questions":["a","b","c"],'
        '"recommendations":[],"suggested_action":null}',
        '{"status":"recommend","message":"x","questions":[],'
        '"recommendations":[],"suggested_action":"join_session"}',
        '{"status":"no_match","message":"x","questions":[],'
        '"recommendations":[],"suggested_action":"delete_session"}',
        '{"status":"ask","message":"x","questions":["a"],'
        '"recommendations":[],"suggested_action":null,"extra":true}',
    ],
)
def test_invalid_reply_shape_is_rejected(content):
    with pytest.raises(AgentOutputError) as error:
        parse_agent_reply(content, CANDIDATES)

    assert error.value.code == "invalid_model_output"


def test_reply_rejects_unknown_candidate_id():
    with pytest.raises(AgentOutputError) as error:
        parse_agent_reply(
            '{"status":"recommend","message":"x","questions":[],'
            '"recommendations":[{"candidate_id":"fake","reason":"x",'
            '"tradeoff":"y"}],"suggested_action":"join_session"}',
            CANDIDATES,
        )

    assert error.value.code == "invalid_model_output"


def test_reply_rejects_duplicate_candidate_ids():
    recommendation = (
        '{"candidate_id":"'
        + CANDIDATE_ID
        + '","reason":"x","tradeoff":"y"}'
    )
    content = (
        '{"status":"recommend","message":"x","questions":[],'
        '"recommendations":['
        + recommendation
        + ","
        + recommendation
        + '],"suggested_action":"join_session"}'
    )

    with pytest.raises(AgentOutputError):
        parse_agent_reply(content, CANDIDATES)
