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

## Test

```bash
cd backend
.venv/bin/pytest -q
```

Tests use isolated temporary SQLite databases and do not require network access
or `DEEPSEEK_API_KEY`.

The current backend MVP includes profile, activity, joining, feedback and admin
feedback summary endpoints. The design document API `/api/agent/chat` belongs to
the later DeepSeek tool-calling phase and is not implemented here.
