# InternScout Agent — Project State

> 本文件是 InternScout Agent 当前状态的唯一项目快照（Project Snapshot）。它记录仍然有效的项目能力、架构、技术决策、测试状态、限制、下一阶段与长期开发规范；它不是开发日志、完整 Debug 历史或 Stage Review。

---

# 1. Project Overview

InternScout Agent 是一个面向软件工程、AI 与 Agent 实习岗位的信息采集、处理、存储、查询，并逐步扩展智能分析能力的练习型软件工程项目。

当前已具备：

- 岗位数据模型、Mock HTML 采集、数据清洗、去重与 SQLite 持久化
- Repository 查询、REST API、筛选、分页与 HTTP 服务闭环
- provider-neutral Agent Contract、Tool System、Tool-Calling Agent Runtime 与 AgentOrchestrator
- Tool / Repository 的 Port / Adapter 解耦
- DeepSeek 真实 LLM Provider Adapter 与真实 Provider smoke 验证
- 自动化测试、Git / GitHub / Pull Request Workflow 与 Codex Review

# 2. Core Technology Stack

- Python 3.12
- FastAPI
- Pydantic
- BeautifulSoup
- SQLAlchemy 2.x
- SQLite
- pytest
- OpenAI Python SDK（作为 DeepSeek OpenAI-compatible API 客户端）
- DeepSeek Responses API
- Git、GitHub、Codex、VS Code

开发环境：Windows、PowerShell、Python Virtual Environment（`.venv`）。

# 3. Current Version Identity

## Current branch

```text
main
```

## Stage 8 Merge Identity

```text
796db56
```

对应：

```text
Merge pull request #8 from luyangzhan111/feat/stage-08-real-model-provider
```

Stage 8 feature branch：

```text
feat/stage-08-real-model-provider
```

## Snapshot Basis

```text
Branch:
main

Stage 8 merge commit:
796db56

Working tree before PROJECT_STATE update:
clean

Full regression:
204 passed, 0 warnings
```

`796db56` 是 Stage 8 功能合并至 `main` 的版本身份；后续仅更新 `PROJECT_STATE.md` 的文档 commit 不替代该身份。

Historical Identity：Stage 7 merge commit 为 `5c5f528`，不表示当前版本。

# 4. Current Stage

## 已完成阶段

```text
Stage 0 ～ Stage 8
```

## Stage 8 状态

Stage 8 已完成、Final Review PASS、Real DeepSeek Smoke PASS、Full Regression PASS，并已合并至 `main`。

最终能力包括：

- `DeepSeekModelClient` 与 DeepSeek Responses API integration
- Provider Adapter、`ModelRequest` / `ToolDefinition` mapping
- FinalAnswer / Function Call mapping
- ToolExecution history reconstruction，包含 success / failed Observation 与多个 sequential execution
- `call_id` preservation 与 JSON serialization fail-fast
- API key environment handling、stateless provider mapping 与 non-reasoning boundary
- sequential tool-call defensive boundary
- offline provider tests、offline Agent integration tests
- real FinalAnswer smoke 与 real ToolCall → Observation → FinalAnswer smoke

## Next Stage

```text
Stage 9
```

Specific Goal：

```text
UNKNOWN
```

Stage 9 具体目标必须在独立 Stage Planning 中确定；当前不提前设计。

# 5. Implemented Backend Capabilities

## FastAPI and job data

当前 HTTP API：

```text
GET  /
GET  /api/health
POST /api/crawl
GET  /api/jobs
GET  /api/jobs/{job_id}
```

服务支持健康与数据库检查、模拟岗位采集、岗位列表与详情查询、城市 / 公司 / 技能筛选、组合筛选与分页。岗位核心数据由 Pydantic 验证，数据库读取使用 `JobRead`，列表使用 `JobListResponse`；数据库内部 `identity_key` 不向 API 或 Agent Tool 暴露。

## Crawling, cleaning and persistence

`MockJobCrawler` 从 `app/fixtures/sample_jobs.html` 读取模拟招聘页面，解析岗位名称、公司、城市、薪资、描述、技能、链接与发布日期。清洗包含城市、公司、技能标准化，空白与重复技能处理，并保持原始技能顺序。

`process_jobs` 执行 Cleaning → Deduplication。重复保护由输入列表业务去重、Repository 保存前检查和数据库 `identity_key` 唯一约束共同提供。当前使用 SQLAlchemy 2.x + SQLite；技能字段使用 JSON 存储。

Repository 支持 `city`、`company`、`skill`、`page`、`page_size` 查询、total 统计、空结果、超页与极大合法页码保护。技能查询使用 SQLite `json_each`，避免 `SQL` 误匹配 `NoSQL`。

## Lifecycle and workflow

FastAPI lifespan 在启动时初始化数据库并创建缺失表。`GET /api/health` 执行真实 `SELECT 1`；数据库不可用时返回 HTTP 503，且不泄漏底层异常。`POST /api/crawl` 复用 `ingest_jobs`：

```text
sample_jobs.html
→ MockJobCrawler
→ JobCreate
→ process_jobs
→ Cleaning + Deduplication
→ ingest_jobs
→ Repository
→ SQLAlchemy
→ SQLite
```

# 6. Agent Layer

Agent Layer 位于 `app/agent/`，提供最小 provider-neutral Tool-Calling Runtime：

```text
User Goal
→ AgentOrchestrator
→ Model Decision
→ ToolCall
→ Tool Execution
→ ToolResult / Observation
→ Next Model Decision
→ FinalAnswer
```

## Contracts and state

`app/agent/contracts.py` 定义 provider-neutral 的 `ToolDefinition`、`ToolCall`、`ToolResult`、`ToolExecution`、`ModelRequest`、`ToolCallResponse`、`FinalAnswerResponse` 与 `AgentResult`。`ToolExecution` 保证 call/result 的 `call_id` 与 tool name 一致；成功结果不含 error，失败结果必须含有效 error。

`AgentState` 仅存在于单次 run，保存 user message、step count、tool executions 与 final answer。每次 `AgentOrchestrator.run()` 创建独立局部 state；它不持久化、不跨 run 共享，也不保存在 `self.state`。

## Tool system and database boundary

`BaseTool` 统一处理 Tool Definition、参数验证、执行、异常转换与 `ToolResult` 生成。参数验证和 Tool 内部异常都会成为失败 Observation；Unknown Tool 也由 Orchestrator 转为 `ToolResult(success=False, error="Tool is not available.")`。

`ToolRegistry` 保持注册顺序，拒绝重复名称。当前 Job Tools：`SearchJobsTool` 与 `GetJobDetailTool`。参数模型使用 `extra="forbid"`，避免拼写错误被静默忽略。

Job Tool 仅依赖 `JobQueryPort`；`RepositoryJobQueryAdapter` 将 Repository 结果转换为 `JobRead`。Agent Tool 不直接依赖 Repository、SQLAlchemy Session 或 `JobModel`：

```text
SearchJobsTool / GetJobDetailTool
            ↓
       JobQueryPort
            ↑
RepositoryJobQueryAdapter
            ↓
        Repository → SQLAlchemy → SQLite
```

## Orchestration

`AgentOrchestrator` 负责执行控制：规范化 user message、创建 state、在每次 `ModelClient.generate()` 前检查 `max_steps`、构建 `ModelRequest`、执行 Tool，并在 FinalAnswer 时产生 `AgentResult`。

仅支持 Sequential Tool Calling：

```text
Model → Tool A → Observation A → Model → Tool B → Observation B → Model → FinalAnswer
```

Tool Failure 不等于 Agent Failure；失败 Observation 会返回给模型进行下一轮决策。Parallel Tool Calling 未实现。

# 7. Real LLM Provider Layer

文件：`app/agent/providers/deepseek_client.py`
Class：`DeepSeekModelClient`

```text
AgentOrchestrator
↓
ModelClient
↓
DeepSeekModelClient
↓
DeepSeek Responses API
```

`DeepSeekModelClient` 负责 Internal Contract ↕ Provider Contract 的映射。Provider-specific code 不进入 `AgentOrchestrator`、`AgentState`、Tool System、Database 或 FastAPI。

## DeepSeek configuration

```text
Provider: DeepSeek
API: DeepSeek Responses API
Base URL: https://api.deepseek.com
SDK: OpenAI Python SDK
API key env: DEEPSEEK_API_KEY
Model name: constructor/config input
Live Stage 8 verification model: deepseek-v4-flash
```

当前 LLM Provider 是 DeepSeek；OpenAI Python SDK 仅是其 OpenAI-compatible API 的兼容客户端，不是当前 Provider。

## Provider state and reasoning boundary

Stage 8 Provider Adapter 是 stateless。每次 `generate(ModelRequest)` 都根据当前 request 重建 Provider Input，且不使用：

```text
previous_response_id
self.history
self.last_response
persistent provider conversation
reasoning continuity
```

Stage 8 是 non-reasoning DeepSeek integration；每次请求显式使用：

```text
reasoning={"effort": "none"}
```

未来 reasoning support 需要单独的 Architecture Decision。

## Tool history mapping

无 `ToolExecution` 时，直接发送 user message。存在 execution 时，按原始执行顺序重建：

```text
User Message
↓
function_call
↓
function_call_output
```

多个 Sequential `ToolExecution` 全部按该顺序重建。`function_call` 保留 `call_id`、name、arguments。successful observation 包含 `success`、`tool_name`、`data`；failed observation 包含 `success`、`tool_name`、`error`。

## Sequential and error boundary

Sequential Tool Calling only：历史中的多个 sequential ToolExecution 受支持；单次 Provider Response 的多个 Function Calls 明确失败。DeepSeek 不能依赖 `parallel_tool_calls=False` 作为 sequential guarantee；Adapter 自身防御该边界。

以下 Provider 行为均 fail：

- invalid JSON arguments
- non-object arguments
- multiple function calls
- mixed function call + final answer
- empty / unsupported response
- JSON serialization failure（在 provider request 前）

Provider exception 继续传播。Stage 8 不实现 Retry。

## API key safety

真实 key 仅来自 `DEEPSEEK_API_KEY`，不得 hardcode、commit、log、写入 tests 或本快照。Injected Fake Client 不要求 API key。自动化测试从不调用真实 Provider；live provider verification 与 pytest 分离。

# 8. Current Architecture

```text
HTTP Client → FastAPI
                 ├─ Health API → SELECT 1
                 ├─ Crawl API → ingest_jobs → MockCrawler → process_jobs
                 └─ Jobs API → Repository → SQLAlchemy → SQLite

User Goal → AgentOrchestrator → ModelClient → DeepSeekModelClient
                                              ↓
                                     DeepSeek Responses API
                                              ↓
                         ToolCallResponse / FinalAnswerResponse
                                      ↓
                               ToolRegistry → Tool → JobQueryPort
                                                    ↑
                                   RepositoryJobQueryAdapter → Repository
```

# 9. Frozen Architecture Decisions

Stage 7 decisions retained:

- `AgentOrchestrator` remains provider-neutral.
- `ModelClient` is the model boundary; `AgentState` is per-run.
- `BaseTool` and `ToolRegistry` remain the Tool System boundary.
- `JobQueryPort` and `RepositoryJobQueryAdapter` isolate Tools from database infrastructure.
- Sequential Tool Calling only.

Stage 8 decisions:

- DeepSeek Provider is isolated behind `ModelClient`.
- `DeepSeekModelClient` is stateless; no provider conversation persistence.
- API key comes from `DEEPSEEK_API_KEY`.
- OpenAI Python SDK is only the compatibility SDK.
- Stage 8 compatibility uses `reasoning={"effort": "none"}`.
- No parallel tool execution; multiple provider function calls fail explicitly.
- Automated tests never call the real provider; live verification is separate from pytest.

# 10. Automated Testing and Review Status

Current authoritative baseline:

```text
Provider targeted: 20 passed
Agent subsystem: 90 passed
Full project: 204 passed
Warnings: 0

Post-merge main regression: 204 passed, 0 warnings
Codex Final Review: MUST FIX = 0
Final Verdict: READY FOR STAGE 8 CLOSEOUT
```

Real DeepSeek Smoke A PASS：

```text
Real DeepSeek → FinalAnswerResponse
response_type: FinalAnswerResponse
answer: smoke-ok
```

Real DeepSeek Smoke B PASS：

```text
Real DeepSeek → ToolCall → AgentOrchestrator → Tool → ToolResult
→ Observation → Real DeepSeek → FinalAnswerResponse → AgentResult

steps: 2
tool_execution_count: 1
tool_name: get_smoke_code
arguments: {"request": "stage8d2"}
success: True
data.code: DEEPSEEK_TOOL_SMOKE_OK
error: None
```

The former Stage 7 baseline (`184 passed, 1 warning`) is historical only. The former Starlette TestClient/httpx warning is no longer a current warning. Codex sandbox `tmp_path` / `.pytest_cache` PermissionError is environment-only historical debugging information, not a project warning or failure.

# 11. Current Limitations

- 当前招聘数据源仍是 Mock HTML
- SQLite，不是生产数据库
- 没有 Alembic Migration
- Agent 没有 HTTP API
- 没有 Retry
- 没有 Memory
- 没有 RAG
- 没有 Vector DB
- 没有 Streaming
- 没有 Parallel Tool Calling
- 没有 Multi-Agent
- 没有 Persistent Conversation
- 没有 reasoning continuity
- 没有 token/cost accounting

# 12. Repository Tree

以下为当前真实 tracked files：

```text
.gitattributes
.gitignore
PROJECT_STATE.md
README.md
app/
    __init__.py
    agent/
        __init__.py
        contracts.py
        exceptions.py
        model_client.py
        orchestrator.py
        providers/
            __init__.py
            deepseek_client.py
        state.py
        tools/
            __init__.py
            base.py
            job_query.py
            job_tools.py
            registry.py
    api/
        __init__.py
        routes/
            __init__.py
            crawl.py
            health.py
            jobs.py
    crawlers/
        __init__.py
        base.py
        mock_crawler.py
    database/
        __init__.py
        job_query_adapter.py
        models.py
        repository.py
        session.py
    fixtures/
        sample_jobs.html
    main.py
    schemas/
        __init__.py
        crawl_response.py
        health_response.py
        job.py
        job_response.py
    services/
        __init__.py
        cleaner.py
        deduplicator.py
        processor.py
    workflows/
        __init__.py
        job_ingestion.py
docs/
    codex-workflow.md
    development-log.md
    stage-reviews/
        stage-01-review.md
        stage-02-review.md
        stage-03-review.md
        stage-04-review.md
        stage-05-review.md
        stage-06-review.md
        stage-07-review.md
        stage-08-review.md
    tasks/
        stage-08-task.md
requirements.txt
tests/
    agent/
        __init__.py
        fakes/
            __init__.py
            fake_model_client.py
        providers/
            __init__.py
            test_deepseek_client.py
        test_agent_exceptions.py
        test_base_tool.py
        test_contracts.py
        test_job_tools.py
        test_model_client.py
        test_orchestrator.py
        test_state.py
        test_tool_registry.py
    database/
        test_job_query_adapter.py
    test_cleaner.py
    test_crawl_api.py
    test_database.py
    test_database_session.py
    test_deduplicator.py
    test_health.py
    test_job_api.py
    test_job_detail_api.py
    test_job_ingestion.py
    test_job_query_repository.py
    test_job_repository.py
    test_job_response_schema.py
    test_job_schema.py
    test_mock_crawler.py
    test_processor.py
    test_stage6_api_flow.py
```

`requirements.txt` includes the OpenAI Python SDK dependency. `.venv` and database temporary files are not tracked and are intentionally absent.

# 13. Stage 8 Documentation

Current Stage 8 documentation:

```text
docs/tasks/stage-08-task.md
docs/stage-reviews/stage-08-review.md
docs/codex-workflow.md
docs/development-log.md
```

Stage 8 review and log are complete.

# 14. Development Workflow

长期工作方式：

```text
Architecture-First
+
Codex-Driven Implementation
+
Human Verification
```

Routine Codex implementation 使用 Luna。High reasoning 用于 complex architecture、difficult debugging 和 Stage Final Read-Only Review。

Codex 默认禁止：

```text
git add
git commit
git push
PR
merge
branch deletion
```

事实优先级：

```text
Repository Reality
>
Task docs
>
Chat history
```

每个 Stage 的标准流：

```text
feature branch
→ implementation
→ tests
→ Final Read-Only Review
→ Stage Review
→ Development Log
→ PR
→ merge
→ main regression
→ PROJECT_STATE
→ branch cleanup
```
