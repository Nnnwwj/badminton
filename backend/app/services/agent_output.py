import json

from pydantic import ValidationError

from app.schemas import AgentReply, CandidateSummary


class AgentOutputError(Exception):
    def __init__(self, message: str = "Model output was invalid") -> None:
        super().__init__(message)
        self.code = "invalid_model_output"


def _strip_optional_json_fence(content: str) -> str:
    text = content.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) < 3 or lines[-1].strip() != "```":
        raise AgentOutputError()
    return "\n".join(lines[1:-1]).strip()


def parse_agent_reply(
    content: str,
    candidates: dict[str, CandidateSummary],
) -> AgentReply:
    text = _strip_optional_json_fence(content)
    try:
        payload = json.loads(text)
        reply = AgentReply.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError):
        raise AgentOutputError() from None

    candidate_ids = [
        recommendation.candidate_id
        for recommendation in reply.recommendations
    ]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise AgentOutputError()
    if any(candidate_id not in candidates for candidate_id in candidate_ids):
        raise AgentOutputError()
    return reply
