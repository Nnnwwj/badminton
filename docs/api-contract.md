# Backend MVP API Contract

This contract describes the stable backend surface delivered by the MVP and
DeepSeek tool-calling phases. The six product-design paths plus the health check
are present in the generated OpenAPI document.

## Common Rules

- Base URL in local development: `http://127.0.0.1:8000`
- API documentation: `GET /docs`
- OpenAPI document: `GET /openapi.json`
- All business endpoints require `X-Demo-User-Id` with an existing demo user
  UUID. `GET /api/health` does not require the header.
- Activity IDs are UUID strings.
- Timestamps use ISO 8601 with a timezone. Inputs may contain an explicit UTC
  offset; the server normalizes them to UTC. Responses use UTC (`Z` suffix).
- Clients should convert user-facing Asia/Shanghai times to UTC before calling
  the API.
- JSON request bodies reject unknown fields.
- Domain errors use `{"detail": {"code": "...", "message": "..."}}`. FastAPI may
  return `{"detail": [...]}` for request validation (`422`) and a string for
  missing or invalid demo identity (`401`).

## Implemented Paths

### `GET /api/health`

Returns service health.

```json
{"status": "ok"}
```

Status: `200`.

### `POST /api/agent/chat`

Runs the DeepSeek recommendation agent. The backend supplies the current UTC
time, Asia/Shanghai timezone, the current user's public profile and validated
read-only tools. The model can query available activities and the current user's
feedback category summary. It cannot perform writes.

Request:

```json
{
  "message": "周三晚上想在学校体育馆打双打，偏休闲"
}
```

Success response:

```json
{
  "status": "recommend",
  "message": "找到一场时间和区域都比较合适的活动。",
  "questions": [],
  "recommendations": [
    {
      "candidate_id": "10000000-0000-4000-8000-000000000001",
      "reason": "活动在学校体育馆，形式为双打，目的是休闲交流。",
      "tradeoff": "双方具体水平还需要进一步确认。"
    }
  ],
  "suggested_action": "join_session"
}
```

Status meanings:

- `ask`: one or two follow-up questions are required; recommendations are empty.
- `recommend`: one to three verified candidate IDs are returned.
- `no_match`: no currently available activity matched.
- `error`: the agent could not complete the recommendation safely.

Every `candidate_id` must have been returned by a real `search_candidates` tool
call during the same request and must still be open and available when the reply
is validated. The response never includes feedback comments, phone numbers or
other users' private data. `suggested_action` is advisory only and does not
perform a write.

Statuses:

- `200`: validated agent reply
- `401`: missing or invalid demo identity
- `422`: empty, overlong or unknown request fields
- `502`: `invalid_model_output` or `agent_loop_limit`
- `503`: `agent_unavailable` or `agent_not_configured`

### `GET /api/profile`

Returns the current user's profile and sorted availability windows.

```json
{
  "id": "00000000-0000-4000-8000-000000000002",
  "nickname": "王雨",
  "area": "学校体育馆",
  "level": "beginner",
  "level_description": "打球约半年，喜欢休闲双打",
  "format_preference": "doubles",
  "purpose": "casual",
  "is_admin": false,
  "availabilities": [
    {"weekday": 2, "start_minute": 1140, "end_minute": 1260}
  ]
}
```

Statuses: `200`, `401`.

### `PUT /api/profile`

Updates only the current user's questionnaire fields or availability windows.
`id` and `is_admin` cannot be changed. Optional fields use `null` to leave the
current value unchanged; supplying `availabilities` replaces the full list.

Request example:

```json
{
  "area": "新体育馆",
  "availabilities": [
    {"weekday": 3, "start_minute": 1080, "end_minute": 1215}
  ]
}
```

Success returns the same structure as `GET /api/profile`.

Statuses: `200`, `401`, `422` (protected fields, invalid enum, invalid time
range, or unknown fields).

### `GET /api/sessions`

Returns all activities with public activity fields and current participant
counts. This endpoint is not a recommendation ranking.

```json
[
  {
    "id": "10000000-0000-4000-8000-000000000001",
    "creator_id": "00000000-0000-4000-8000-000000000002",
    "start_at": "2026-10-29T11:00:00Z",
    "end_at": "2026-10-29T13:00:00Z",
    "area": "学校体育馆",
    "venue": "2号场",
    "format": "doubles",
    "purpose": "casual",
    "level_label": "入门-熟练",
    "capacity": 4,
    "status": "open",
    "created_at": "2026-10-28T08:00:00Z",
    "participant_count": 1,
    "spots_remaining": 3
  }
]
```

Statuses: `200`, `401`.

### `POST /api/sessions`

Creates an activity and automatically adds the creator as a participant.

Request example:

```json
{
  "start_at": "2026-11-04T11:00:00Z",
  "end_at": "2026-11-04T13:00:00Z",
  "area": "学校体育馆",
  "venue": "2号场",
  "format": "doubles",
  "purpose": "casual",
  "level_label": "入门-熟练",
  "capacity": 4
}
```

Success returns one session object with `201`.

Statuses: `201`, `401`, `422` (missing timezone, non-positive duration, capacity
below 2, invalid enum, or unknown fields).

### `POST /api/sessions/{session_id}/join`

Joins an available activity after checking current status, capacity and duplicate
participation in one transaction. Success returns the updated session object.

Statuses:

- `200`: joined successfully
- `401`: missing or invalid demo identity
- `404`: `session_not_found`
- `409`: `already_joined`, `session_full`, `session_ended`, or
  `session_unavailable`

### `POST /api/sessions/{session_id}/feedback`

Submits one feedback record for a participant after the activity has ended.

Request example:

```json
{
  "rating": "suitable",
  "reason_category": "level",
  "comment": "双方节奏合适，希望下次继续。"
}
```

Allowed ratings: `suitable`, `average`, `unsuitable`. Allowed reason categories:
`time`, `location`, `level`, `purpose`, `no_show`, `other`.

Success returns the created feedback record with `201`.

Statuses:

- `201`: created
- `401`: missing or invalid demo identity
- `403`: `not_participant`
- `404`: `session_not_found`
- `409`: `session_not_ended` or `feedback_already_submitted`
- `422`: invalid payload

### `GET /api/admin/feedback-summary`

Returns aggregate feedback counts for an administrator. Every reason category is
always present. The response never includes comments, nicknames or other private
user fields.

```json
{
  "total": 3,
  "reason_counts": {
    "time": 1,
    "location": 0,
    "level": 2,
    "purpose": 0,
    "no_show": 0,
    "other": 0
  }
}
```

Statuses:

- `200`: administrator summary
- `401`: missing or invalid demo identity
- `403`: `admin_required`

## Internal Services

The objective candidate search in `app.services.candidates` is an internal
service used by the agent's `search_candidates` tool. It is not a public HTTP
path. The agent's only tools are `search_candidates` and
`get_my_feedback_summary`; both are read-only.
