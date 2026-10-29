# Badminton Backend

FastAPI + SQLAlchemy backend for the badminton partner matching MVP.

## Requirements

- Python 3.13
- SQLite (bundled with Python)

## Setup

From the repository root:

```bash
python3.13 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e 'backend[dev]'
```

Initialize the SQLite schema and idempotent demo data:

```bash
cd backend
.venv/bin/python -c "from app.database import Base; from app.dependencies import engine; from app.seed import seed_database; Base.metadata.create_all(engine); seed_database(engine)"
```

The default database is `backend/data/badminton.db`. Runtime databases are not
committed to Git.

## Run

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --port 8000
```

- API documentation: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>
- Health check: <http://127.0.0.1:8000/api/health>

Business endpoints require the demo identity header:

```http
X-Demo-User-Id: 00000000-0000-4000-8000-000000000001
```

The fixed demo identities and activities are defined in `app/seed.py`. The first
demo user is the administrator.

## DeepSeek Agent

Create `backend/.env` from `.env.example` and set the backend-only values:

```dotenv
DEEPSEEK_API_KEY=your-secret-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_PROMPT_VERSION=v1
DEEPSEEK_TIMEOUT_SECONDS=30
```

The local project is configured for `deepseek-flash`. The model name comes
from `DEEPSEEK_MODEL`; it is not hard-coded in application logic.

`POST /api/agent/chat` exposes the read-only recommendation agent. The model may
query available activities and the current user's feedback summary. Final JSON
is validated by the backend, and every recommended activity ID must come from a
real tool result in the same request. Recommendation audits are stored in the
`recommendations` table without the API key.

## Test

```bash
cd backend
.venv/bin/pytest -q
```

Tests use isolated temporary SQLite databases and mocked model responses. They do
not require network access or `DEEPSEEK_API_KEY`.

The backend includes profile, activity, joining, feedback, admin summary and
DeepSeek agent chat endpoints.
