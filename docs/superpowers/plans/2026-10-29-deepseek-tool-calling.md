# DeepSeek Tool Calling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend-only DeepSeek recommendation agent exposed at `POST /api/agent/chat`, using validated read-only tools and verified structured output.

**Architecture:** A configuration module loads backend-only DeepSeek settings. A dedicated HTTP client performs OpenAI-compatible chat-completion calls with function tools. An agent service runs a bounded tool-call loop, executes only allow-listed read-only database queries, validates the final JSON against the actual candidate set, persists an audit record, and returns a stable API response. The FastAPI endpoint handles identity, request shape and safe public errors.

**Tech Stack:** Python 3.13, FastAPI, Pydantic 2, SQLAlchemy 2, SQLite, httpx, python-dotenv, pytest.

**Spec:** `羽毛球约球智能体_设计文档_v4.md` and `羽毛球约球智能体_提示词方案_v1.md`

## Global Constraints

- `DEEPSEEK_API_KEY` stays only in `backend/.env` or an injected environment variable. Never log, return, persist or commit it.
- Use `DEEPSEEK_MODEL` from the environment. The local configured model is `deepseek-4.1-flash`; code must not hard-code that name.
- Use `DEEPSEEK_BASE_URL` from the environment, defaulting to `https://api.deepseek.com`.
- Use `DEEPSEEK_PROMPT_VERSION` from the environment, defaulting to `v1`.
- The model receives only the current user's public profile, that user's feedback summary and public activity candidates.
- The recommendation phase exposes read-only tools only. It never joins an activity, creates an activity or submits feedback.
- Tool arguments and model output are untrusted input and must be validated by the backend.
- Final recommendations may reference only candidate IDs returned by `search_candidates` during the same request.
- Final status is one of `ask`, `recommend`, `no_match` or `error`.
- `ask` has at most two questions; `recommend` has at most three recommendations; a single model run has at most four remote calls.
- If the model returns empty content, malformed JSON, truncated JSON, an unknown candidate ID or an unavailable candidate, do not display the invalid recommendation; return a safe agent error.
- All model and candidate times use UTC in API data. The running context additionally states `Asia/Shanghai` and the current UTC time.
- Tests must not call the real DeepSeek service. The live smoke check runs separately using `backend/.env`.

## Review Focus

- A model tool call with unknown `area`, invalid enum, naive datetime or reversed range must be rejected without reaching the database query as malformed input.
- Prompt-injection text inside user messages or candidate data must not cause private feedback, other users' data or write operations to be exposed.
- A candidate can become unavailable between search and final validation; stale IDs must be rejected rather than returned.
- API, timeout, non-2xx, malformed response and truncated JSON failures must produce a clear `agent_unavailable` or `invalid_model_output` result without leaking secrets.
- Repeated or oversized tool calls must stop after the fixed loop limit and return a safe failure.

---

### Task 10: DeepSeek Client And Tool Boundary

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/services/deepseek.py`
- Create: `backend/app/services/agent_tools.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/pyproject.toml`
- Create: `backend/tests/test_deepseek.py`
- Create: `backend/tests/test_agent_tools.py`

**Interfaces:**
- Consumes: `CandidateQuery`, `CandidateSummary`, `search_candidates`, `Feedback`, `FeedbackReasonCounts`.
- Produces: `Settings.from_env()`; `DeepSeekClient.complete(messages, tools) -> ChatCompletion`; `tool_definitions() -> list[dict]`; `execute_tool(db, user_id, name, arguments, now) -> ToolExecution`.

- [x] **Step 1: Write failing client, config and tool tests**

Tests must cover:

- Environment loading with a model override and no secret in `repr`.
- Authorization uses `Bearer <configured key>` without the test asserting on the real key.
- A successful completion maps assistant content, tool calls and finish reason.
- A non-2xx response maps to `DeepSeekUnavailableError` without including the key.
- `search_candidates` arguments become a validated `CandidateQuery`.
- Invalid tool names, unknown fields, invalid enums, naive times and reversed ranges are rejected.
- User feedback summary uses only the current user's feedback and includes all six fixed categories.
- Tool responses contain no feedback comments or nicknames.

- [x] **Step 2: Run the tests and confirm failure**

Run: `cd backend && .venv/bin/pytest tests/test_deepseek.py tests/test_agent_tools.py -q`

Expected: FAIL because the client and tool modules do not exist.

- [x] **Step 3: Implement configuration, HTTP client and read-only tools**

Use `python-dotenv` to load `backend/.env`. Use synchronous `httpx.Client` because the existing FastAPI routes and test client are synchronous. Keep HTTP parsing in `deepseek.py`, tool schemas/dispatch in `agent_tools.py`, and secret-bearing settings in `config.py`.

- [x] **Step 4: Run focused tests and then the full suite**

Run: `cd backend && .venv/bin/pytest tests/test_deepseek.py tests/test_agent_tools.py -q && .venv/bin/pytest -q`

Expected: all pass.

- [x] **Step 5: Commit and push**

```bash
git add backend/app/config.py backend/app/services/deepseek.py backend/app/services/agent_tools.py backend/app/schemas.py backend/pyproject.toml backend/tests/test_deepseek.py backend/tests/test_agent_tools.py docs/superpowers/plans/2026-10-29-deepseek-tool-calling.md
git commit -m "feat: add DeepSeek client and agent tools"
git push origin main
```

### Task 11: Structured Recommendation Validation

**Files:**
- Create: `backend/app/services/agent_output.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/test_agent_output.py`

**Interfaces:**
- Consumes: raw final assistant text and the current request's `dict[str, CandidateSummary]`.
- Produces: `AgentReply`; `parse_agent_reply(content: str, candidates: dict[str, CandidateSummary]) -> AgentReply`.

- [x] **Step 1: Write failing structured-output tests**

Tests must cover:

- Valid `ask`, `recommend`, `no_match` and `error` payloads.
- At most two questions and at most three recommendations.
- Unknown fields, unknown status, invalid `suggested_action` and code-fenced JSON handling.
- Unknown, stale or duplicated candidate IDs are rejected.
- Candidate reason and tradeoff text may be returned but never private fields.

- [x] **Step 2: Run the tests and confirm failure**

Run: `cd backend && .venv/bin/pytest tests/test_agent_output.py -q`

Expected: FAIL because the output validator does not exist.

- [x] **Step 3: Implement strict JSON parsing and candidate verification**

Strip a single optional Markdown JSON fence, parse JSON, validate with Pydantic, then compare every recommendation ID against the candidate map collected during this run. Do not repair or invent missing fields.

- [x] **Step 4: Run focused tests and then the full suite**

Run: `cd backend && .venv/bin/pytest tests/test_agent_output.py -q && .venv/bin/pytest -q`

Expected: all pass.

- [x] **Step 5: Commit and push**

```bash
git add backend/app/services/agent_output.py backend/app/schemas.py backend/tests/test_agent_output.py
git commit -m "feat: validate agent recommendations"
git push origin main
```

### Task 12: Agent Orchestration And Persistence

**Files:**
- Create: `backend/app/services/agent.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/test_agent.py`

**Interfaces:**
- Consumes: `DeepSeekClient`, `execute_tool`, `parse_agent_reply`, `RecommendationRecord`.
- Produces: `run_agent(db, client, user, message, now) -> AgentReply`; persisted audit record containing request text, candidate snapshot, validated model output, model name and prompt version.

- [ ] **Step 1: Write failing orchestration tests**

Tests must cover:

- No-tool final answer for `ask` and `no_match`.
- Tool call round trip with candidate JSON sent back to the model.
- Unknown or invalid tool call returns a tool error message instead of executing arbitrary code.
- Candidate set is accumulated only from real `search_candidates` results.
- Model loop stops after four remote calls.
- Empty content, malformed JSON, unavailable API and invalid candidate ID become safe agent errors.
- Successful and error runs both persist an audit record without the API key.

- [ ] **Step 2: Run the tests and confirm failure**

Run: `cd backend && .venv/bin/pytest tests/test_agent.py -q`

Expected: FAIL because orchestration does not exist.

- [ ] **Step 3: Implement the bounded tool-call loop**

Build system/running-context messages, append tool results in OpenAI-compatible format, validate final output, and commit one audit record. Use dependency injection for the DeepSeek client and deterministic tests with a fake client or mocked HTTP transport.

- [ ] **Step 4: Run focused tests and then the full suite**

Run: `cd backend && .venv/bin/pytest tests/test_agent.py -q && .venv/bin/pytest -q`

Expected: all pass.

- [ ] **Step 5: Commit and push**

```bash
git add backend/app/services/agent.py backend/app/models.py backend/app/schemas.py backend/tests/test_agent.py
git commit -m "feat: orchestrate DeepSeek recommendations"
git push origin main
```

### Task 13: HTTP Endpoint, Live Smoke And Documentation

**Files:**
- Create: `backend/app/api/agent.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/dependencies.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_agent_api.py`
- Modify: `backend/tests/test_acceptance.py`
- Modify: `backend/tests/test_candidates.py`
- Modify: `backend/README.md`
- Modify: `docs/api-contract.md`

**Interfaces:**
- Consumes: `run_agent`, current user, current UTC time and configured `DeepSeekClient`.
- Produces: `AgentChatRequest`, `AgentReply`; `POST /api/agent/chat`; a dependency override seam for tests.

- [ ] **Step 1: Write failing HTTP and acceptance tests**

Tests must cover:

- Missing or invalid demo identity returns `401`.
- Successful `ask`, `recommend` and `no_match` responses.
- DeepSeek unavailability returns a stable safe error response.
- Malformed model output returns `invalid_model_output`.
- The end-to-end backend flow includes agent chat and verifies no secret appears in responses.

- [ ] **Step 2: Run the tests and confirm failure**

Run: `cd backend && .venv/bin/pytest tests/test_agent_api.py tests/test_acceptance.py -q`

Expected: FAIL because `/api/agent/chat` does not exist.

- [ ] **Step 3: Implement the endpoint and update the contract**

Add `/api/agent/chat` to the documented six design paths. Update the startup instructions to explain that a configured `DEEPSEEK_API_KEY` and `DEEPSEEK_MODEL` enable the endpoint. Keep the public error structure stable and never include raw provider errors containing credentials.

- [ ] **Step 4: Run full automated verification**

Run: `cd backend && .venv/bin/pytest -q`

Expected: all pass without network access or a real key.

- [ ] **Step 5: Run a guarded live smoke check**

Load `backend/.env`, request a short Chinese recommendation from the running API, print only status, model name and response structure, and confirm the configured model responds with valid JSON or a documented provider error. Never print the key or full authorization header.

- [ ] **Step 6: Commit and push**

```bash
git add backend/app/api/agent.py backend/app/main.py backend/app/dependencies.py backend/tests/conftest.py backend/tests/test_agent_api.py backend/tests/test_acceptance.py backend/tests/test_candidates.py backend/README.md docs/api-contract.md
git commit -m "feat: expose DeepSeek agent chat API"
git push origin main
```

## Phase Completion Conditions

- `POST /api/agent/chat` works with demo identity and the configured DeepSeek model.
- The provider receives only allow-listed read-only tools and scoped context.
- Invalid tool arguments, malformed output, timeout and provider errors fail safely.
- No recommendation references a candidate that was not returned by a real database tool call in that run.
- Recommendation audit records contain the model, prompt version, candidate snapshot and validated output, but never the API key.
- The automated suite passes without network access or a real API key.
- The live smoke check confirms the configured model and endpoint, or reports the exact provider-side blocker without exposing secrets.
