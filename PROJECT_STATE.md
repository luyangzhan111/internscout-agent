# InternScout Agent — Project State

> 本文件是 InternScout Agent 当前状态的唯一项目快照（Project Snapshot）。它记录仍然有效的项目能力、架构、技术决策、测试状态、限制、下一阶段与长期开发规范；它不是开发日志、完整 Debug 历史或 Stage Review。

---

# 1. Project Overview

InternScout Agent 是一个面向软件工程、AI 与 Agent 实习岗位的信息采集、处理、存储、查询与智能分析练习型软件工程项目。

当前已具备：

- 岗位数据模型、Mock HTML 采集、数据清洗、去重与 SQLite 持久化
- Repository 查询、REST API、筛选、分页与 HTTP 服务闭环
- provider-neutral Agent Contract、Tool System、Tool-Calling Agent Runtime 与 `AgentOrchestrator`
- Tool / Repository 的 Port / Adapter 解耦
- DeepSeek 真实 LLM Provider Adapter 与真实 Provider smoke 验证
- 每次请求独立运行的 Agent HTTP API
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

## Stage 9 Merge Identity

```text
30062fc
```

Full identity：

```text
30062fc5bdeef58bd54ede441f803450301378ad
```

对应 merge：

```text
Merge pull request #9 from luyangzhan111/feat/stage-09-agent-http-api
```

## Snapshot Basis

```text
Branch:
main

Stage 9 merge commit:
30062fc

Working tree before PROJECT_STATE update:
clean

Full regression:
219 passed, 0 warnings
```

`30062fc` 是 Stage 9 功能合并至 `main` 的版本身份。后续仅更新 `PROJECT_STATE.md` 的文档 commit 不替代 Stage 9 feature merge identity。

Historical Identity：Stage 8 merge commit 为 `796db56`，不表示当前版本。

# 4. Current Stage

## 已完成阶段

```text
Stage 0 ～ Stage 9
```

## Stage 9 状态

```text
Implementation: COMPLETE
Final Review: PASS
MUST FIX: 0
Real DeepSeek Agent Tool Loop: PASS
Real Agent HTTP Smoke: PASS
Post-merge main regression: PASS
```

## Next Stage

```text
Stage 10
```

Specific Goal：

```text
UNKNOWN
```

Stage 10 必须从 repository reality 开始正式 Planning；当前不猜测目标，也不开始实现。

# 5. Implemented Backend Capabilities

## FastAPI and job data

当前 HTTP API：

```text
GET  /
GET  /api/health
POST /api/crawl
GET  /api/jobs
GET  /api/jobs/{job_id}
POST /api/agent/query
```

`POST /api/agent/query` 表示每个 request 触发一次独立、无持久会话的 Agent run。公共 response 只包含：

```text
answer
steps
tool_execution_count
```

它不是 persistent chat，也不暴露内部 `ToolExecution` trace。

岗位服务支持健康与数据库检查、模拟岗位采集、岗位列表与详情查询、城市 / 公司 / 技能筛选、组合筛选与分页。岗位核心数据由 Pydantic 验证，数据库读取使用 `JobRead`，列表使用 `JobListResponse`；数据库内部 `identity_key` 不向 API 或 Agent Tool 暴露。

## Crawling, cleaning and persistence

`MockJobCrawler` 从 `app/fixtures/sample_jobs.html` 读取模拟招聘页面，解析并清洗岗位数据。`process_jobs` 执行 Cleaning → Deduplication。重复保护由输入列表业务去重、Repository 保存前检查和数据库 `identity_key` 唯一约束共同提供。

当前使用 SQLAlchemy 2.x + SQLite；技能字段使用 JSON 存储。Repository 支持 `city`、`company`、`skill`、`page`、`page_size` 查询、total 统计、空结果、超页与极大合法页码保护。技能查询使用 SQLite `json_each`，避免 `SQL` 误匹配 `NoSQL`。

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

`app/agent/contracts.py` 定义 provider-neutral contracts。`AgentState` 仅存在于单次 run；每次 `AgentOrchestrator.run()` 创建独立局部 state，不持久化、不跨 run 共享。

## Tool system and database boundary

`BaseTool` 统一处理 Tool Definition、参数验证、执行、异常转换与 `ToolResult` 生成。参数验证、Tool 内部异常与 Unknown Tool 都成为失败 Observation，模型仍可恢复并生成最终答案。

`ToolRegistry` 保持注册顺序并拒绝重复名称。当前 Job Tools 为 `SearchJobsTool` 与 `GetJobDetailTool`。两者只依赖 `JobQueryPort`；`RepositoryJobQueryAdapter` 隔离 Repository 与 SQLAlchemy：

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

`AgentOrchestrator` 负责执行控制、step boundary、Tool 调用与最终 `AgentResult`。仅支持 Sequential Tool Calling；Parallel Tool Calling 未实现。

# 7. Application Composition and HTTP Boundary

FastAPI composition root：

```text
app/api/dependencies.py
```

Production object graph：

```text
request-scoped SQLAlchemy Session
→ RepositoryJobQueryAdapter
→ SearchJobsTool
→ GetJobDetailTool
→ ToolRegistry
→ AgentOrchestrator
```

两个 Job Tools 共享同一个 request-scoped `RepositoryJobQueryAdapter`。Tool 注册顺序固定为：

1. `SearchJobsTool`
2. `GetJobDetailTool`

Lifecycle：

```text
request-scoped:
- Session
- RepositoryJobQueryAdapter
- Job Tools
- ToolRegistry
- AgentOrchestrator

application-level lazy reuse:
- DeepSeekModelClient
```

没有保留 `Session` 的对象被全局缓存。

## Model client configuration

Production FastAPI dependency 使用以下 server-side configuration：

```text
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
```

Provider construction 是 lazy 的。导入 `app.main` 不要求 DeepSeek configuration；没有 Provider configuration 时，non-agent endpoints 仍可使用。

## HTTP error boundary

当前第一版行为：

```text
invalid request
→ HTTP 422

missing DeepSeek configuration
→ sanitized HTTP 503

unexpected Agent / Model runtime error
→ sanitized HTTP 500

Agent max_steps exhaustion
→ sanitized HTTP 500

Tool failure followed by model recovery
→ HTTP 200
```

当前没有引入 provider-neutral exception taxonomy。

# 8. Real LLM Provider Layer

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

Provider-specific code 不进入 `AgentOrchestrator`、`AgentState`、Tool System、Database 或 FastAPI route。

## DeepSeek configuration and state

```text
Provider: DeepSeek
API: DeepSeek Responses API
Base URL: https://api.deepseek.com
SDK: OpenAI Python SDK
API key env: DEEPSEEK_API_KEY
Model env: DEEPSEEK_MODEL
```

`DeepSeekModelClient` 是 stateless。每次 `generate(ModelRequest)` 都根据当前 request 重建 Provider Input，不使用 provider conversation persistence 或 reasoning continuity。当前 integration 显式使用 `reasoning={"effort": "none"}`。

## Tool history mapping

存在 execution 时，Adapter 按原始 sequential execution 顺序重建：

```text
User Message
↓
function_call
↓
function_call_output
```

`function_call` 保留 `call_id`、name、arguments；Observation 包含 success、tool name，以及 data 或 error。

## Provider compatibility and defensive rules

真实 DeepSeek 可能返回：

```text
phase="commentary" message
+
single function_call
```

当前 mapping：

```text
commentary + function_call
→ ToolCallResponse

final_answer + function_call
→ explicit failure

unknown / missing / blank phase + function_call
→ explicit failure

multiple function calls
→ explicit failure
```

以下行为同样明确失败：

- invalid JSON arguments
- non-object arguments
- function call 与不兼容的 final output 混合
- empty / unsupported response
- request-side JSON serialization failure

Provider exception 继续传播。当前不实现 Retry。自动化测试不调用真实 DeepSeek；真实 Provider verification 与 pytest 分离。

# 9. Current Architecture

```text
HTTP Client → FastAPI
                 ├─ Health API → SELECT 1
                 ├─ Crawl API → ingest_jobs → MockCrawler → process_jobs
                 ├─ Jobs API → Repository → SQLAlchemy → SQLite
                 └─ Agent API → request-scoped AgentOrchestrator
                                  ├─ lazy DeepSeekModelClient → DeepSeek Responses API
                                  └─ ToolRegistry → Job Tools → JobQueryPort
                                                                    ↑
                                           RepositoryJobQueryAdapter → Repository
```

# 10. Frozen Architecture Decisions

Stage 7 decisions retained：

- `AgentOrchestrator` remains provider-neutral.
- `ModelClient` is the model boundary; `AgentState` is per-run.
- `BaseTool` and `ToolRegistry` remain the Tool System boundary.
- `JobQueryPort` and `RepositoryJobQueryAdapter` isolate Tools from database infrastructure.
- Sequential Tool Calling only.

Stage 8 decisions retained：

- DeepSeek Provider is isolated behind `ModelClient`.
- `DeepSeekModelClient` is stateless; no provider conversation persistence.
- API key comes from `DEEPSEEK_API_KEY`.
- OpenAI Python SDK is only the compatibility SDK.
- Current compatibility uses `reasoning={"effort": "none"}`.
- No parallel tool execution; multiple provider function calls fail explicitly.
- Automated tests never call the real provider; live verification is separate from pytest.

Stage 9 decisions：

- `POST /api/agent/query` represents one stateless Agent run.
- FastAPI-specific composition belongs in `app/api/dependencies.py`.
- The Session-retaining Agent object graph is request-scoped.
- Stateless `DeepSeekModelClient` may be lazily reused at application level.
- The HTTP public contract does not expose internal `ToolExecution` trace.
- The server controls Provider, model, `max_steps`, and tools.
- Agent Runtime remains provider-neutral.
- Automated tests do not call real DeepSeek.
- Real Provider / HTTP smoke remains separate from pytest.

# 11. Automated Testing, Review, and Real Verification

Current authoritative baseline：

```text
Provider targeted:
24 passed

Agent subsystem:
94 passed

Full project:
219 passed

Warnings:
0

Post-merge main regression:
219 passed, 0 warnings

Codex Final Review:
MUST FIX = 0

Final Verdict:
READY FOR STAGE 9 CLOSEOUT
```

Stage 8 full baseline `204 passed, 0 warnings` and Stage 7 baseline `184 passed, 1 warning` are historical only.

## Real DeepSeek Agent Tool Loop

```text
PASS

Observed:
steps: 2
tool_execution_count: 1
tool_name: search_jobs
tool_success: True
tool_error: None
```

## Real Agent HTTP Smoke

```text
PASS

POST /api/agent/query

Observed:
non-empty answer
steps: 2
tool_execution_count: 1
```

真实验证不记录或暴露 API key 内容。

# 12. Current Limitations

- 当前招聘数据源仍是 Mock HTML
- SQLite，不是生产数据库
- 没有 Alembic Migration
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

# 13. Repository Tree

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
        dependencies.py
        routes/
            __init__.py
            agent.py
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
        agent.py
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
        stage-09-review.md
    tasks/
        stage-08-task.md
        stage-09-task.md
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
    test_agent_api.py
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

# 14. Current Documentation and Development Workflow

Current Stage documentation：

```text
docs/tasks/stage-09-task.md
docs/stage-reviews/stage-09-review.md
docs/codex-workflow.md
docs/development-log.md
```

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
formal Planning from repository reality
→ feature branch
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

Next Stage 为 Stage 10，Specific Goal 为 `UNKNOWN`。必须先正式 Planning，不得从本快照推断或承诺未来功能。
