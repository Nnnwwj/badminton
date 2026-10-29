import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Feedback
from app.schemas import CandidateQuery
from app.services.candidates import search_candidates
from app.services.feedback import FEEDBACK_REASONS


class AgentToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class EmptyArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class ToolExecution:
    name: str
    content: dict[str, Any]


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "search_candidates",
                "description": (
                    "查询当前真实可报名的活动。日期时间必须使用带 Z 或时区偏移的 "
                    "ISO 8601 UTC 时间。只返回公开活动字段。"
                ),
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "start_at": {
                            "type": ["string", "null"],
                            "format": "date-time",
                            "description": "查询时间窗口起点，UTC ISO 8601",
                        },
                        "end_at": {
                            "type": ["string", "null"],
                            "format": "date-time",
                            "description": "查询时间窗口终点，UTC ISO 8601",
                        },
                        "area": {
                            "type": ["string", "null"],
                            "description": "用户明确要求的区域",
                        },
                        "format": {
                            "type": ["string", "null"],
                            "enum": ["singles", "doubles", None],
                        },
                        "purpose": {
                            "type": ["string", "null"],
                            "enum": ["casual", "training", None],
                        },
                    },
                    "required": ["start_at", "end_at", "area", "format", "purpose"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_my_feedback_summary",
                "description": "读取当前用户自己的历史反馈类别汇总，不返回反馈原文。",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {},
                },
            },
        },
    ]


def _parse_arguments(arguments: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            raise AgentToolError(
                "invalid_arguments", "Tool arguments must be valid JSON"
            ) from None
    if not isinstance(arguments, dict):
        raise AgentToolError("invalid_arguments", "Tool arguments must be an object")
    return arguments


def _search_candidates(
    db: Session,
    arguments: dict[str, Any],
    now: datetime,
) -> ToolExecution:
    try:
        query = CandidateQuery.model_validate(arguments)
    except ValidationError:
        raise AgentToolError(
            "invalid_arguments", "Unable to parse candidate query"
        ) from None
    candidates = search_candidates(db, query, now)
    return ToolExecution(
        name="search_candidates",
        content={
            "candidates": [
                candidate.model_dump(mode="json") for candidate in candidates
            ]
        },
    )


def _get_my_feedback_summary(
    db: Session,
    user_id: str,
    arguments: dict[str, Any],
) -> ToolExecution:
    try:
        EmptyArguments.model_validate(arguments)
    except ValidationError:
        raise AgentToolError(
            "invalid_arguments", "Feedback summary accepts no arguments"
        ) from None

    reason_counts = {reason: 0 for reason in FEEDBACK_REASONS}
    statement = (
        select(Feedback.reason_category, func.count(Feedback.id))
        .where(Feedback.user_id == user_id)
        .group_by(Feedback.reason_category)
    )
    for reason, count in db.execute(statement):
        reason_counts[reason] = count

    return ToolExecution(
        name="get_my_feedback_summary",
        content={
            "total": sum(reason_counts.values()),
            "reason_counts": reason_counts,
        },
    )


def execute_tool(
    db: Session,
    user_id: str,
    name: str,
    arguments: str | dict[str, Any],
    now: datetime,
) -> ToolExecution:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    parsed = _parse_arguments(arguments)

    if name == "search_candidates":
        return _search_candidates(db, parsed, now)
    if name == "get_my_feedback_summary":
        return _get_my_feedback_summary(db, user_id, parsed)
    raise AgentToolError("unknown_tool", "Tool is not available")
