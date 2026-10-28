# 羽毛球约球智能体：MVP 数据与事务底座 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个可独立运行和验收的 FastAPI + SQLite 后端底座，用真实数据支持资料、活动、报名、反馈、管理员统计和候选查询。

**Architecture:** FastAPI 只处理 HTTP、身份、参数和统一错误；业务事务放在 service 层；SQLAlchemy 持久化到 SQLite。候选查询只返回符合客观条件和当前状态的真实活动，不排序、不评分、不执行规则兜底；推荐顺序留给后续 DeepSeek 阶段。

**Tech Stack:** Python 3.13、FastAPI、Pydantic 2、SQLAlchemy 2、SQLite、Uvicorn、pytest、httpx。

**Spec:** `羽毛球约球智能体_设计文档_v4.md`

## Global Constraints

- 演示身份通过请求头 `X-Demo-User-Id` 传递；没有或找不到该用户时返回 401，本阶段不实现真实登录。
- 所有公开资源 ID 使用 UUID 字符串；演示种子也使用固定 UUID，不使用可猜测的自增 ID。
- 所有时间在数据库和 API 中使用带时区的 UTC ISO 8601；Asia/Shanghai 只在展示或解析用户表达时使用。
- 当前时间必须通过可注入的 `get_now()` 获得，测试不得依赖系统真实时间。
- 用户资料不得包含手机号；API 不返回其他用户的私人反馈原文。
- `DEEPSEEK_API_KEY` 只允许出现在后端环境变量中，不进入代码、数据库、前端或 Git。
- 本阶段没有智能体排序，也没有规则兜底；`/api/agent/chat` 不在本计划范围内。
- 候选查询只支持可报名活动。直接邀请单个用户涉及活动创建、双方确认和去重，等设计明确后再实现。
- SQLite 业务数据库默认路径为 `backend/data/badminton.db`，测试必须使用临时数据库。
- 报名写操作必须在单个事务内完成状态、容量和重复报名检查。

## Review Focus

- 同一用户并发提交两次报名时，只允许产生一条有效报名；由 Task 5 的并发测试覆盖。
- 创建者自动占一个名额后，最后一名参与者加入不能使人数超过上限；由 Task 5 的满员测试覆盖。
- 用户可能报名结束后提交反馈，也可能让非参与者提交反馈；由 Task 6 的授权和时间测试覆盖。
- 候选查询可能返回已满、取消、结束或时间不符的活动；由 Task 8 的过滤测试覆盖。
- “周三晚上”等自然语言和浏览器本地时区可能被误解；本阶段 API 只接受 ISO 时间，Task 8 使用显式 UTC 范围测试，Task 9 验收 UTC 契约。

---

### Task 1: 项目骨架与可重复的测试环境

**Files:**
- Create: `.gitignore`
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`
- Create: `.env.example`

**Interfaces:**
- Consumes: Python 3.13 可执行文件。
- Produces: `backend.app.main:app`；测试命令 `cd backend && .venv/bin/pytest -q`。

- [ ] **Step 1: 初始化 Git 和 Python 虚拟环境**

Run:

```bash
cd /Users/ningwenjie/Desktop/badminton
git init
python3.13 -m venv backend/.venv
```

Expected: Git 创建 `.git`，Python 报告版本 3.13。

- [ ] **Step 2: 写入项目配置和失败测试**

`backend/pyproject.toml` 必须声明 FastAPI、Pydantic、SQLAlchemy、Uvicorn、pytest 和 httpx，并提供 `dev` optional dependencies。

测试内容：

```python
def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

`.gitignore` 至少包含 `.venv/`、`__pycache__/`、`.pytest_cache/`、`backend/data/*.db`、`.env`、`.playwright-cli/`、`output/playwright/` 和 `.DS_Store`。

- [ ] **Step 3: 安装项目依赖**

Run:

```bash
cd /Users/ningwenjie/Desktop/badminton
backend/.venv/bin/python -m pip install --index-url https://mirrors.aliyun.com/pypi/simple -e 'backend[dev]'
```

Expected: 安装成功，`backend/.venv/bin/pytest --version` 可运行。

- [ ] **Step 4: 运行测试并确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_health.py -q`

Expected: FAIL，原因是 `backend.app.main` 或 `/api/health` 尚不存在。

- [ ] **Step 5: 实现最小 FastAPI 应用**

在 `backend/app/main.py` 中定义 `app = FastAPI(title="羽毛球约球助手")` 和 `GET /api/health`，返回 `{"status": "ok"}`。

- [ ] **Step 6: 运行测试并确认通过**

Run: `cd backend && .venv/bin/pytest -q`

Expected: 全部测试 PASS。

- [ ] **Step 7: 提交**

```bash
git add .gitignore .env.example backend
git commit -m "chore: bootstrap FastAPI test harness"
```

### Task 2: 数据库模型与可重复种子数据

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/models.py`
- Create: `backend/app/seed.py`
- Create: `backend/tests/test_seed.py`

**Interfaces:**
- Consumes: Task 1 的 FastAPI 应用和测试环境。
- Produces: `Base`、`User`、`Availability`、`GameSession`、`Participant`、`Feedback`、`RecommendationRecord`、`AgentConfig`；`seed_database(engine) -> None`。

- [ ] **Step 1: 写种子数据失败测试**

测试内容：

```python
def test_seed_creates_six_users_and_three_sessions(engine):
    seed_database(engine)
    with sqlalchemy.orm.Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 6
        assert db.scalar(select(func.count()).select_from(GameSession)) == 3
```

测试还应断言至少一场活动在未来、一场已结束，并存在一名管理员。

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_seed.py -q`

Expected: FAIL，模型和 `seed_database` 尚不存在。

- [ ] **Step 3: 实现最小表结构**

必须包含：

- `users`：UUID、昵称、区域、水平、水平描述、项目偏好、打球目的、`is_admin`。
- `availability`：UUID、用户 UUID、星期 0–6、开始分钟、结束分钟。
- `sessions`：UUID、发起人、开始/结束 UTC 时间、区域、场地、项目、目的、水平说明、人数上限、状态。
- `participants`：活动与用户联合唯一、报名时间。
- `feedback`：活动与用户联合唯一、满意度、原因类别、补充文字、提交时间。
- `recommendations`：需求文本、候选快照 JSON、模型输出 JSON、模型名称、提示词版本、时间。
- `agent_config`：版本、修改时间、修改原因。

- [ ] **Step 4: 实现六用户、三活动种子**

种子必须可重复执行且不产生重复行；三个活动分别覆盖未来可报名、已满员、已结束。固定 UUID 只用于演示数据。

- [ ] **Step 5: 运行测试并确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_seed.py -q`

Expected: PASS；连续执行两次后计数仍为 6 和 3。

- [ ] **Step 6: 提交**

```bash
git add backend/app/database.py backend/app/models.py backend/app/seed.py backend/tests/test_seed.py
git commit -m "feat: add database models and demo seed"
```

### Task 3: 演示身份与用户资料 API

**Files:**
- Create: `backend/app/dependencies.py`
- Create: `backend/app/schemas.py`
- Create: `backend/app/api/profile.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_profile.py`

**Interfaces:**
- Consumes: `get_db()`、`User`、`Availability`。
- Produces: `get_current_user(x_demo_user_id: str | None, db) -> User`；`ProfileResponse`、`ProfileUpdate`；`GET /api/profile`、`PUT /api/profile`。

- [ ] **Step 1: 写资料 API 失败测试**

测试必须覆盖：

```python
def test_get_profile_returns_current_user(client, seeded_db):
    response = client.get(
        "/api/profile",
        headers={"X-Demo-User-Id": DEMO_USER_ID},
    )
    assert response.status_code == 200
    assert response.json()["id"] == DEMO_USER_ID


def test_put_profile_persists_new_area(client, seeded_db):
    response = client.put(
        "/api/profile",
        headers={"X-Demo-User-Id": DEMO_USER_ID},
        json={"area": "新体育馆"},
    )
    assert response.status_code == 200
    assert response.json()["area"] == "新体育馆"
```

另测缺失请求头返回 401。

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_profile.py -q`

Expected: FAIL，路由或身份依赖尚不存在。

- [ ] **Step 3: 实现身份依赖和资料读写**

`PUT /api/profile` 只允许修改问答字段和当前用户自己的空闲时段，不允许修改 `id` 或 `is_admin`。更新区域、水平、项目偏好、目的或空闲时段后返回完整资料。

- [ ] **Step 4: 运行测试并确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_profile.py -q`

Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/dependencies.py backend/app/schemas.py backend/app/api/profile.py backend/app/main.py backend/tests/test_profile.py
git commit -m "feat: add demo profile API"
```

### Task 4: 活动列表与发布 API

**Files:**
- Create: `backend/app/services/sessions.py`
- Create: `backend/app/api/sessions.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_sessions.py`

**Interfaces:**
- Consumes: `get_current_user()`、`GameSession`、`Participant`。
- Produces: `SessionCreate`、`SessionResponse`；`GET /api/sessions`、`POST /api/sessions`。

- [ ] **Step 1: 写活动 API 失败测试**

测试必须覆盖：

```python
def test_create_session_adds_creator_as_participant(client, seeded_db):
    response = client.post(
        "/api/sessions",
        headers={"X-Demo-User-Id": DEMO_USER_ID},
        json={
            "start_at": "2026-11-04T11:00:00Z",
            "end_at": "2026-11-04T13:00:00Z",
            "area": "学校体育馆",
            "venue": "2号场",
            "format": "doubles",
            "purpose": "casual",
            "level_label": "beginner",
            "capacity": 4,
        },
    )
    assert response.status_code == 201
    assert response.json()["participant_count"] == 1
```

另测 `end_at <= start_at` 返回 422，`capacity < 2` 返回 422。

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_sessions.py -q`

Expected: FAIL，活动路由尚不存在。

- [ ] **Step 3: 实现活动 schema、列表和发布**

发布时在同一事务内创建活动和创建者的 `joined` 参与记录。列表返回公开活动字段、参与者数量和剩余名额，不返回参与者昵称或私人资料。

- [ ] **Step 4: 运行测试并确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_sessions.py -q`

Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/sessions.py backend/app/api/sessions.py backend/app/schemas.py backend/app/main.py backend/tests/test_sessions.py
git commit -m "feat: add session listing and creation"
```

### Task 5: 原子报名事务

**Files:**
- Modify: `backend/app/services/sessions.py`
- Modify: `backend/app/api/sessions.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/test_join_session.py`

**Interfaces:**
- Consumes: 活动、参与者和可注入的 `get_now()`。
- Produces: `JoinResult`；`join_session(db, session_id, user_id, now) -> JoinResult`；`POST /api/sessions/{session_id}/join`。

- [ ] **Step 1: 写报名规则失败测试**

测试必须覆盖：

- 未满活动加入成功，参与人数加 1。
- 同一用户重复加入返回 409，并明确标识 `already_joined`。
- 已满活动返回 409，并明确标识 `session_full`。
- 已结束活动返回 409，并明确标识 `session_ended`。
- 不存在活动返回 404。
- 两个不同用户并发争抢最后一个名额，只允许一个成功。

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_join_session.py -q`

Expected: FAIL，报名接口尚不存在。

- [ ] **Step 3: 实现单事务报名**

SQLite 写入使用 `BEGIN IMMEDIATE`。在事务内依次检查活动存在、状态可报名、未结束、用户未加入和剩余名额，然后插入参与记录。业务冲突返回 409，不通过“先查询、后另行写入”的两步流程。

- [ ] **Step 4: 运行测试并确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_join_session.py -q`

Expected: 全部 PASS，并发测试恰好一个成功、一个冲突。

- [ ] **Step 5: 运行完整后端测试**

Run: `cd backend && .venv/bin/pytest -q`

Expected: 全部 PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/sessions.py backend/app/api/sessions.py backend/app/schemas.py backend/tests/test_join_session.py
git commit -m "feat: make session joining transactional"
```

### Task 6: 约球反馈 API

**Files:**
- Create: `backend/app/services/feedback.py`
- Create: `backend/app/api/feedback.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_feedback.py`

**Interfaces:**
- Consumes: `Participant`、`GameSession`、`Feedback`、`get_now()`。
- Produces: `FeedbackCreate`、`FeedbackResponse`；`POST /api/sessions/{session_id}/feedback`。

- [ ] **Step 1: 写反馈失败测试**

测试覆盖：

```python
def test_non_participant_cannot_submit_feedback(client, seeded_db):
    response = client.post(
        f"/api/sessions/{ENDED_SESSION_ID}/feedback",
        headers={"X-Demo-User-Id": NON_PARTICIPANT_ID},
        json={"rating": "suitable", "reason_category": "level"},
    )
    assert response.status_code == 403
```

另测未结束活动返回 409、参与者成功提交、同一用户再次提交返回 409。

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_feedback.py -q`

Expected: FAIL，反馈路由尚不存在。

- [ ] **Step 3: 实现反馈授权与持久化**

原因类别只允许 `time`、`location`、`level`、`purpose`、`no_show`、`other`。只允许活动参与者、活动结束后、且未提交过反馈的用户写入。

- [ ] **Step 4: 运行测试并确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_feedback.py -q`

Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/feedback.py backend/app/api/feedback.py backend/app/schemas.py backend/app/main.py backend/tests/test_feedback.py
git commit -m "feat: add authorized feedback submission"
```

### Task 7: 管理员反馈统计

**Files:**
- Modify: `backend/app/services/feedback.py`
- Modify: `backend/app/api/feedback.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/test_feedback_summary.py`

**Interfaces:**
- Consumes: `Feedback`、`User.is_admin`。
- Produces: `FeedbackSummaryResponse`；`GET /api/admin/feedback-summary`。

- [ ] **Step 1: 写统计失败测试**

测试必须断言：

- 普通用户请求返回 403。
- 管理员得到全部反馈总数。
- 每种原因类别返回准确计数，零次类别仍返回 0。
- 响应不包含反馈补充文字或用户昵称。

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_feedback_summary.py -q`

Expected: FAIL，统计接口尚不存在。

- [ ] **Step 3: 实现管理员统计**

使用数据库聚合查询，不把全部反馈记录加载到 Python 后计数。固定返回六类原因。

- [ ] **Step 4: 运行测试并确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_feedback_summary.py -q`

Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/feedback.py backend/app/api/feedback.py backend/app/schemas.py backend/tests/test_feedback_summary.py
git commit -m "feat: summarize feedback for admins"
```

### Task 8: 客观候选查询服务

**Files:**
- Create: `backend/app/services/candidates.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/test_candidates.py`

**Interfaces:**
- Consumes: 当前 UTC 时间、活动和参与记录。
- Produces: `CandidateQuery`；`search_candidates(db, query: CandidateQuery, now: datetime) -> list[CandidateSummary]`。

- [ ] **Step 1: 写候选过滤失败测试**

测试必须覆盖：

- 时间范围、区域、项目和目的过滤准确。
- 已结束、取消、满员活动不出现在结果中。
- 剩余名额计算正确。
- 返回最多 20 条，并按开始时间升序产生稳定数据库顺序。
- 相同查询不会返回重复活动。
- 结果只含公开活动字段，不含电话或其他用户私人资料。

注意事项：这里的时间升序只是稳定候选集顺序，不是推荐排序，也不得暴露给后续模型作为固定权重。

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_candidates.py -q`

Expected: FAIL，`search_candidates` 尚不存在。

- [ ] **Step 3: 实现数据库过滤**

查询只应用用户或模型明确提供的客观条件，并无条件排除失效活动。不得在本服务内计算匹配分数、选择“最佳”候选或生成推荐理由。

- [ ] **Step 4: 运行测试并确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_candidates.py -q`

Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/candidates.py backend/app/schemas.py backend/tests/test_candidates.py
git commit -m "feat: add objective candidate query service"
```

### Task 9: 后端验收与接口契约

**Files:**
- Create: `backend/tests/test_acceptance.py`
- Create: `docs/api-contract.md`
- Modify: `backend/README.md`

**Interfaces:**

- Consumes: Tasks 1–8 的全部公开 API。
- Produces: 可执行的本地启动说明、OpenAPI 路径清单和完整后端验收测试。

- [ ] **Step 1: 写端到端失败测试**

单个测试完成以下流程：

1. 用户 A 查看并修改资料。
2. 用户 A 查询未满活动。
3. 用户 A 报名成功。
4. 用户 A 重复报名得到 409。
5. 已结束活动的参与者 B 提交反馈。
6. 管理员读取原因统计并看到对应计数。

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_acceptance.py -q`

Expected: FAIL，直到整个流程和测试数据一致。

- [ ] **Step 3: 修正接口衔接并补齐文档**

`docs/api-contract.md` 必须列出设计文档中的六个公开路径、请求头、成功结构、主要错误码和 UTC 时间格式。`backend/README.md` 给出：

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Expected: 浏览器可访问 `http://127.0.0.1:8000/docs`。

- [ ] **Step 4: 运行完整验证**

Run:

```bash
cd backend
.venv/bin/pytest -q
.venv/bin/uvicorn app.main:app --port 8000
```

Expected: pytest 全部 PASS；Uvicorn 在 8000 端口启动且 `/api/health` 返回 200。

- [ ] **Step 5: 提交**

```bash
git add backend/tests/test_acceptance.py backend/README.md docs/api-contract.md
git commit -m "test: verify backend MVP flow"
```

## 阶段完成条件

- 六用户、三活动的种子数据可重复生成。
- 六个设计文档 API 均可用，且错误码和 UTC 时间契约稳定。
- 并发报名不超卖、不重复，反馈权限正确。
- 候选查询只返回真实可用活动，不包含推荐分数或规则排序。
- 完整 pytest 在无网络、无 `DEEPSEEK_API_KEY` 的条件下通过。
- 下一阶段的输入是稳定的 `docs/api-contract.md`，不是当前前端临时假设。

## 后续独立计划

1. **DeepSeek 工具调用阶段：** 系统提示词、工具参数校验、JSON Output、候选 ID 复核、超时和错误恢复。
2. **React 前端阶段：** 资料、聊天、活动、报名确认、反馈和管理页面。
3. **端到端阶段：** Playwright 验收、演示数据切换、失败恢复和视觉检查。
