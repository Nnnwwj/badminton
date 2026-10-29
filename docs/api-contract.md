# Backend MVP API Contract

This contract describes the stable backend surface delivered by Tasks 1-9. The
six paths below are present in the generated OpenAPI document.

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

## Deferred Design API

`POST /api/agent/chat` is listed in the product design but is intentionally not
part of this backend foundation. It will be introduced in the later DeepSeek
tool-calling phase together with prompt, tool-call validation, model-output
verification, timeout handling and error recovery.

The objective candidate search in `app.services.candidates` is currently an
internal service consumed by the later agent phase, not a public HTTP path.
