# InternScout Agent — Stage 9 Task

## 1. Stage Identity

```text
Stage 9 — Agent HTTP API & Application Integration
```

Stage 9 基于 Stage 8 完成后的正式仓库状态继续开发。

进入 Stage 9 时的权威基线：

```text
Stage 0 ～ Stage 8: COMPLETE
Stage 8 merge identity: 796db56
Full regression: 204 passed
Warnings: 0
Real LLM Provider: DeepSeek
```

Stage 9 feature branch：

```text
feat/stage-09-agent-http-api
```

事实优先级：

```text
Repository Reality
>
PROJECT_STATE.md / Task Spec
>
Chat history / memory
```

如果实现过程中发现本 Task Spec 与真实仓库不一致：

```text
STOP
→ report repository reality
→ re-open Architecture Gate if needed
```

不得自行重构以强行满足文档。

---

# 2. Stage 9 Core Goal

Stage 9 的目标是：

> 将现有 provider-neutral Agent Runtime、DeepSeek Provider、Job Tools、Repository 查询能力与 FastAPI 正式组装成可通过 HTTP 调用的 Agent Application。

Stage 9 完成后的目标链路：

```text
HTTP Client
    ↓
POST /api/agent/query
    ↓
FastAPI
    ↓
Application Composition
    ↓
AgentOrchestrator
    ↓
ModelClient
    ↓
DeepSeekModelClient
    ↓
DeepSeek Responses API
    ↓
ToolCall
    ↓
ToolRegistry
    ↓
SearchJobsTool / GetJobDetailTool
    ↓
JobQueryPort
    ↓
RepositoryJobQueryAdapter
    ↓
Repository Functions
    ↓
SQLAlchemy Session
    ↓
SQLite
```

Stage 9 不是重新实现 Agent Runtime。

它负责：

```text
Application Integration
+
Dependency Wiring
+
HTTP Contract
+
HTTP Error Boundary
+
Offline HTTP Integration Testing
+
Real DeepSeek HTTP Smoke
```

---

# 3. Why Stage 9 Exists

Stage 6 已建立：

```text
FastAPI
+
Jobs REST API
+
Database HTTP workflow
```

Stage 7 已建立：

```text
provider-neutral Agent Runtime
+
Tool System
+
AgentOrchestrator
+
JobQueryPort / Adapter
```

Stage 8 已建立：

```text
DeepSeekModelClient
+
Real DeepSeek Provider integration
```

但 Stage 8 结束时：

```text
AgentOrchestrator
```

仍只能通过 Python 内部代码调用。

当前不存在：

```text
HTTP Client
→ AgentOrchestrator
```

Stage 9 要补齐这一 Application Boundary。

---

# 4. Stage 9 Architecture Principle

Stage 9 必须继续保持：

```text
Provider-neutral Agent Runtime
```

FastAPI 不得直接实现：

```text
Model Decision
Tool Execution Loop
Agent State
Repository Query Logic
```

DeepSeek Provider 不得直接认识：

```text
FastAPI
Repository
SQLAlchemy
Job Tools
```

Job Tools 不得直接访问：

```text
Repository Functions
SQLAlchemy Session
JobModel
```

Stage 9 只负责组合已有组件。

---

# 5. Frozen Stage 7 / Stage 8 Boundaries

以下架构在 Stage 9 中默认禁止重新设计。

## 5.1 Model Boundary

```text
ModelClient.generate(ModelRequest)
→ ModelResponse
```

`AgentOrchestrator` 继续只依赖：

```text
ModelClient
```

不得直接依赖：

```text
DeepSeekModelClient
OpenAI Python SDK
DeepSeek SDK details
```

---

## 5.2 Agent State

`AgentState` 继续保持：

```text
per-run
```

每次：

```text
AgentOrchestrator.run()
```

创建新的局部 state。

禁止：

```text
persistent AgentState
cross-request state
self.state
conversation memory
```

---

## 5.3 Tool / Database Boundary

保持：

```text
SearchJobsTool / GetJobDetailTool
            ↓
       JobQueryPort
            ↑
RepositoryJobQueryAdapter
            ↓
Repository Functions
            ↓
SQLAlchemy Session
            ↓
SQLite
```

Stage 9 不存在新的 `Repository` class。

当前 Repository 是：

```text
module functions
+
explicit SQLAlchemy Session
```

不要为 Stage 9 创建 Repository class。

---

## 5.4 Tool Failure

继续保持：

```text
Tool Failure
!=
Agent Failure
```

Tool failure 必须形成：

```text
ToolResult(success=False)
→ Observation
→ next Model decision
```

Unknown Tool 同样继续使用 failed Observation。

只要 Agent 最终产生有效 FinalAnswer：

```text
HTTP response = success
```

---

## 5.5 Sequential Tool Calling

Stage 9 继续：

```text
Sequential Tool Calling only
```

不实现：

```text
Parallel Tool Calling
```

---

## 5.6 Provider State

`DeepSeekModelClient` 继续保持：

```text
stateless
```

不使用：

```text
previous_response_id
persistent provider history
reasoning continuity
provider conversation state
```

---

## 5.7 Reasoning Boundary

继续使用 Stage 8：

```text
reasoning={"effort": "none"}
```

Stage 9 不修改 reasoning architecture。

---

# 6. HTTP Endpoint Contract

Stage 9 新增：

```text
POST /api/agent/query
```

不用：

```text
POST /api/chat
```

因为 Stage 9：

```text
没有 Persistent Conversation
没有 Memory
没有 Conversation Session
```

语义：

```text
1 HTTP request
=
1 AgentOrchestrator.run()
=
1 independent AgentState
```

---

# 7. HTTP Request Contract

新增 Schema：

```text
AgentQueryRequest
```

文件：

```text
app/schemas/agent.py
```

第一版只允许：

```json
{
  "user_message": "帮我找深圳的 Python 实习岗位"
}
```

字段：

```text
user_message: str
```

要求：

```text
required
non-empty
whitespace-only input rejected
```

Whitespace-only：

```text
""
"   "
"\t"
"\n"
```

必须在 HTTP validation boundary 被拒绝。

预期：

```text
HTTP 422
```

HTTP Client 不允许提供：

```text
provider
model
api_key
max_steps
reasoning
tools
tool_choice
conversation_id
```

以上全部属于 server-side policy。

Stage 9 不扩大 public request contract。

---

# 8. HTTP Response Contract

新增 Schema：

```text
AgentQueryResponse
```

第一版 public response：

```json
{
  "answer": "...",
  "steps": 2,
  "tool_execution_count": 1
}
```

字段：

```text
answer: str
steps: int
tool_execution_count: int
```

映射来源：

```text
AgentResult.final_answer
AgentResult.steps
len(AgentResult.tool_executions)
```

具体 symbol 名称必须以当前真实 `AgentResult` Contract 为准。

如果真实字段命名与上述描述不一致：

```text
use repository reality
do not modify AgentResult merely to match HTTP naming
```

---

# 9. Public Trace Boundary

HTTP Response 不允许直接暴露：

```text
ToolCall
Tool arguments
ToolResult
Observation
ToolExecution
raw model response
raw provider response
SDK objects
database ORM objects
```

原则：

```text
Internal Agent Trace
!=
Public HTTP Contract
```

Stage 9 只公开：

```text
answer
steps
tool_execution_count
```

---

# 10. Application Composition Root

新增：

```text
app/api/dependencies.py
```

它是 Stage 9 的：

```text
FastAPI / Application Composition Root
```

只有这个最外层 wiring layer 可以同时认识：

```text
get_session
DeepSeekModelClient
RepositoryJobQueryAdapter
SearchJobsTool
GetJobDetailTool
ToolRegistry
AgentOrchestrator
```

职责：

```text
construct concrete dependencies
connect existing abstractions
provide FastAPI override seams
```

不得把 composition logic 放入：

```text
AgentOrchestrator
DeepSeekModelClient
Job Tools
Repository functions
```

---

# 11. Request-Scoped Object Graph

每次 Agent HTTP request 使用：

```text
SQLAlchemy Session
        ↓
RepositoryJobQueryAdapter
        ↓
SearchJobsTool
GetJobDetailTool
        ↓
ToolRegistry
        ↓
AgentOrchestrator
```

这些对象保持：

```text
request-scoped
```

禁止：

```text
global AgentOrchestrator
global ToolRegistry containing request tools
global RepositoryJobQueryAdapter
global SQLAlchemy Session
```

原因：

```text
RepositoryJobQueryAdapter
retains request Session
```

全局缓存会产生 closed-session / cross-request lifecycle risk。

---

# 12. Tool Registration Order

生产 Composition 必须固定：

```text
1. SearchJobsTool
2. GetJobDetailTool
```

`ToolRegistry` 保持注册顺序，而且该顺序会暴露给模型。

因此注册顺序属于：

```text
observable behavior
```

不要任意交换。

---

# 13. ModelClient Dependency

新增 override seam：

```text
get_model_client()
```

要求：

```text
lazy
overrideable
server-side configuration only
```

禁止：

```text
module import
→ immediately create DeepSeekModelClient
```

禁止：

```text
FastAPI startup
→ unconditionally require DeepSeek configuration
```

必须保证在没有 DeepSeek 配置的情况下：

```text
import app.main
GET /api/health
GET /api/jobs
existing automated tests
```

仍可正常运行。

只有真正访问 Agent dependency 时才需要 Provider configuration。

---

# 14. ModelClient Lifecycle

`DeepSeekModelClient` 是 stateless。

Stage 9 允许：

```text
lazy application-level reuse
```

以避免每个 HTTP request 都重新建立底层 Provider SDK connection pool。

推荐允许使用：

```text
functools.lru_cache
```

或其他简单 lazy cache。

但具体缓存实现不是 Architecture Contract。

真正必须满足的是：

```text
no eager construction
+
dependency override remains possible
```

Stage 9 不新增 Provider shutdown / close architecture。

如果当前 `DeepSeekModelClient` 没有显式 resource close contract：

```text
do not modify provider only to add one
```

---

# 15. DeepSeek Server Configuration

Stage 9 正式使用：

```text
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
```

二者都属于：

```text
server-side configuration
```

不得来自：

```text
HTTP request
```

不得：

```text
hardcode API key
hardcode permanent model default
commit secrets
log secrets
return secrets through HTTP errors
```

Stage 8 smoke 使用过的：

```text
deepseek-v4-flash
```

只是历史 live verification model。

它不是 Stage 9 应用层永久 hardcoded default。

Stage 9 不增加 `.env` loading architecture。

---

# 16. AgentOrchestrator Dependency

新增 dependency：

```text
get_agent_orchestrator(...)
```

其输入至少包括：

```text
request SQLAlchemy Session
ModelClient
```

内部组装：

```text
Session
↓
RepositoryJobQueryAdapter
↓
SearchJobsTool
GetJobDetailTool
↓
ToolRegistry
↓
AgentOrchestrator
```

Stage 9 使用现有：

```text
AgentOrchestrator default max_steps
```

HTTP Client 不允许设置 `max_steps`。

如果当前默认值为：

```text
5
```

继续使用现有默认，不在 Stage 9 重复定义另一套 policy。

---

# 17. FastAPI Dependency Injection

Production：

```text
FastAPI
↓
get_model_client
↓
DeepSeekModelClient
```

以及：

```text
FastAPI
↓
get_session
+
get_model_client
↓
get_agent_orchestrator
```

Automated API tests 应 override：

```text
get_session
get_model_client
```

Automated API tests 不得 override：

```text
get_agent_orchestrator
RepositoryJobQueryAdapter
ToolRegistry
SearchJobsTool
GetJobDetailTool
```

目标是保留真实 integration path。

---

# 18. Offline HTTP Integration Path

核心测试必须真正覆盖：

```text
HTTP Request
↓
FastAPI
↓
real Agent route
↓
real AgentOrchestrator
↓
FakeModelClient
↓
real ToolRegistry
↓
real Job Tools
↓
real RepositoryJobQueryAdapter
↓
real Repository functions
↓
temporary SQLite
↓
Observation
↓
FakeModelClient
↓
FinalAnswer
↓
HTTP Response
```

自动化测试唯一替换的 Provider Boundary：

```text
DeepSeekModelClient
→ FakeModelClient
```

pytest 不允许访问真实 DeepSeek 网络。

---

# 19. Database Test Lifecycle

当前真实仓库存在两个不同 database seams：

```text
app.state.database_engine
```

控制：

```text
FastAPI lifespan database initialization
```

而：

```text
get_session()
```

绑定当前 global `SessionLocal`。

因此 Stage 9 API integration test 必须继续使用现有项目的双重 test database pattern：

```text
1. app.state.database_engine = test_engine

2. app.dependency_overrides[get_session]
   = test_session_dependency
```

不能只做其中一个。

否则可能出现：

```text
lifespan database
!=
request database
```

Stage 9 不重构这一 database architecture。

---

# 20. FakeModelClient Test Isolation

现有 `FakeModelClient` 保存：

```text
response position
request history
```

因此测试中：

```text
one test / one independent fake
```

不要创建一个全局 mutable FakeModelClient 供多个测试或并发请求复用。

---

# 21. HTTP Route Execution Model

新增 Agent route 必须使用：

```python
def
```

而不是为了“现代化”改成：

```python
async def
```

当前：

```text
AgentOrchestrator
DeepSeekModelClient
SQLAlchemy Session
```

都是同步执行体系。

Stage 9 不引入 async Agent runtime。

---

# 22. HTTP Error Boundary

## 22.1 Request Validation

以下输入：

```text
missing user_message
invalid type
blank / whitespace-only user_message
```

由 HTTP Schema validation 拒绝。

预期：

```text
422 Unprocessable Entity
```

---

## 22.2 Provider Configuration Missing

以下 server configuration 不可用：

```text
DEEPSEEK_API_KEY missing / blank
DEEPSEEK_MODEL missing / blank
```

Agent endpoint 应返回：

```text
503 Service Unavailable
```

Response detail 必须 sanitized。

不得暴露：

```text
API key
environment content
SDK internals
stack trace
```

非 Agent endpoint 不应因为缺少这些配置而失败。

---

## 22.3 AgentMaxStepsExceeded

现有：

```text
AgentMaxStepsExceeded
```

如果越过 Agent boundary：

```text
HTTP 500
```

返回 sanitized server error。

Stage 9 不改变 max_steps semantics。

---

## 22.4 Provider Runtime Exception

Stage 8 当前行为：

```text
Provider exception
→ propagate
```

当前 `ModelClient` 没有 provider-neutral：

```text
ProviderError
ProviderUnavailableError
RateLimitError
```

因此 Stage 9：

```text
DO NOT
```

让 FastAPI route import：

```text
OpenAI SDK exceptions
DeepSeek-specific exception types
```

Stage 9 也不为了 HTTP status 重构 `ModelClient`。

Provider runtime exception 当前进入：

```text
HTTP 500
```

不得返回底层 exception detail。

Stage 9 不映射：

```text
502
429
provider-specific 503
```

更精细的 provider-neutral error taxonomy 属于未来独立 Architecture Decision。

---

## 22.5 Tool Failure

以下情况如果 Agent 能继续并最终产生 FinalAnswer：

```text
Tool validation failure
Tool internal failure
Unknown Tool
```

HTTP 仍然：

```text
200 OK
```

原则：

```text
Tool Failure
!=
Agent Failure
!=
HTTP Failure
```

---

# 23. Stage 9 New Files

新增：

```text
app/api/dependencies.py
app/api/routes/agent.py
app/schemas/agent.py
tests/test_agent_api.py
docs/tasks/stage-09-task.md
```

Stage closeout 后新增：

```text
docs/stage-reviews/stage-09-review.md
```

---

# 24. Stage 9 Modified Files

正常预计修改：

```text
app/api/routes/__init__.py
app/api/__init__.py
app/main.py
app/schemas/__init__.py
docs/development-log.md
```

`PROJECT_STATE.md`：

```text
only after Stage 9 PR merge
and after real Stage 9 merge identity exists
```

不得在 PR merge 前写入最终 merge identity。

---

# 25. Frozen Files / Architecture Gate Trigger

Stage 9 正常情况下不应修改：

```text
app/agent/contracts.py
app/agent/exceptions.py
app/agent/model_client.py
app/agent/orchestrator.py
app/agent/state.py

app/agent/providers/deepseek_client.py

app/agent/tools/base.py
app/agent/tools/job_query.py
app/agent/tools/job_tools.py
app/agent/tools/registry.py

app/database/repository.py
app/database/job_query_adapter.py
app/database/session.py
```

如果实现要求修改上述任何文件：

```text
STOP
```

必须：

```text
report why existing boundary is insufficient
↓
re-open Architecture Gate
↓
human approval
↓
only then modify
```

Codex 不得自行扩大 scope。

---

# 26. Explicit Non-Goals

Stage 9 不做：

```text
Memory
Persistent Conversation
Conversation Session
RAG
Vector DB
Streaming
Retry
Parallel Tool Calling
Multi-Agent
reasoning continuity
new Agent Tools
real recruitment websites
async Agent Runtime
token / cost accounting
Repository refactor
database dependency redesign
app factory refactor
shared tests/conftest.py refactor
provider exception taxonomy redesign
provider shutdown lifecycle redesign
```

Stage 9：

```text
!= Chat System
```

---

# 27. Existing Test Infrastructure Refactor

Codex 已发现现有 API tests 中存在重复：

```text
temporary SQLite engine
Session factory
dependency override
app.state mutation
cleanup
engine disposal
```

Stage 9 不处理该技术债。

不要为了减少重复而新增：

```text
tests/conftest.py
```

除非后续单独批准。

`tests/test_agent_api.py` 可以沿用当前现有 API test pattern。

---

# 28. Stage 9 Substages

## 9A — Architecture & API Contract

Status：

```text
COMPLETE
FROZEN
```

已确定：

```text
endpoint contract
request / response boundary
composition root
object lifecycle
dependency override seams
provider configuration
error boundary
test strategy
file scope
non-goals
```

---

## 9B — Application Composition & Dependencies

目标：

新增：

```text
app/api/dependencies.py
```

实现：

```text
lazy get_model_client
request-scoped get_agent_orchestrator
RepositoryJobQueryAdapter wiring
Job Tools wiring
ToolRegistry wiring
AgentOrchestrator wiring
```

必须保证：

```text
import app.main
```

在没有：

```text
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
```

时仍正常。

不得修改 Agent Runtime。

9B 优先做：

```text
targeted dependency tests / lightweight validation
```

如果没有必要，不为 dependency 本身新增过度 unit tests；核心行为将在 9D HTTP integration 中验证。

---

## 9C — HTTP Schemas & Agent Route

新增：

```text
app/schemas/agent.py
app/api/routes/agent.py
```

修改 Router exports 与：

```text
app/main.py
```

实现：

```text
POST /api/agent/query
```

要求：

```text
sync route
AgentQueryRequest
AgentQueryResponse
dependency injection
sanitized HTTP mapping
```

不得在 route 中重写 Agent Runtime logic。

---

## 9D — Offline HTTP Integration & Error Boundary

新增：

```text
tests/test_agent_api.py
```

核心测试至少覆盖：

### Direct Final Answer

```text
HTTP
→ AgentOrchestrator
→ FakeModelClient
→ FinalAnswer
→ HTTP 200
```

验证：

```text
answer
steps
tool_execution_count = 0
```

---

### SearchJobsTool Full Path

准备 temporary SQLite seed data。

FakeModelClient scripted responses：

```text
ToolCall(search_jobs)
↓
Observation
↓
FinalAnswer
```

验证：

```text
HTTP 200
steps reflect two model decisions
tool_execution_count = 1
```

并确认 FakeModelClient 收到的下一轮 `ModelRequest` 中存在来自真实 Tool / test database 的 Observation。

---

### GetJobDetailTool Full Path

使用 test database 中存在的岗位。

执行：

```text
ToolCall(get_job_detail)
↓
real adapter
↓
real repository query
↓
Observation
↓
FinalAnswer
```

验证 HTTP contract 与 tool count。

---

### Tool Failure Recovery

构造能够使真实 Tool 产生：

```text
ToolResult(success=False)
```

的 scripted call。

随后 FakeModelClient 返回 FinalAnswer。

验证：

```text
HTTP 200
```

而不是 HTTP error。

---

### Request Validation

至少覆盖：

```text
missing user_message
empty user_message
whitespace-only user_message
```

预期：

```text
422
```

---

### Missing Provider Configuration

没有：

```text
DEEPSEEK_API_KEY
and/or
DEEPSEEK_MODEL
```

时访问 Agent endpoint。

预期：

```text
503
```

同时验证：

```text
existing non-agent endpoints remain usable
```

---

### Agent Max Steps

构造无法在 `max_steps` 内产生 FinalAnswer 的 FakeModel flow。

预期：

```text
500
```

不得泄漏内部 exception detail。

---

### Unexpected Model / Provider Failure

使用 FakeModelClient 模拟 model boundary exception。

预期：

```text
500
```

不得出现：

```text
SDK-specific HTTP mapping
raw exception detail
```

---

### Dependency Cleanup

每个测试结束：

```text
remove dependency overrides
restore app.state.database_engine
dispose temporary engine
```

不得让测试互相污染。

---

# 29. Stage 9 Automated Test Rules

Automated tests：

```text
MUST NOT
```

访问：

```text
DeepSeek network
real LLM
real API key
```

Automated tests 使用：

```text
FakeModelClient
```

真实 Provider verification：

```text
manual smoke only
```

---

# 30. Stage 9 Test Execution Strategy

每个实现部分完成后：

```text
Targeted Tests
↓
Agent / API relevant tests
↓
Full Regression
```

Stage 9 完成前至少执行：

```powershell
python -m pytest tests/test_agent_api.py -v
```

然后根据实际影响执行相关 Agent tests，例如：

```powershell
python -m pytest tests/agent -q
```

最后：

```powershell
python -m pytest -q
```

进入 Stage 9 前 baseline：

```text
204 passed
0 warnings
```

Stage 9 最终测试总数：

```text
UNKNOWN until implementation completes
```

不得预先伪造最终 passed 数字。

验收要求：

```text
all pre-existing tests remain passing
all new Stage 9 tests pass
0 current warnings unless a new externally-caused warning is explicitly reviewed
```

---

# 31. Stage 9E — Real DeepSeek HTTP Smoke

真实 smoke 与 pytest 严格分离。

在 Human local environment 中设置：

```text
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
```

不要把值写进：

```text
repository
tests
docs
logs
screenshots containing secrets
```

启动真实 FastAPI application。

建议先确保 local database 中有岗位数据，例如通过现有 crawl workflow。

随后通过：

```text
POST /api/agent/query
```

完成真实 HTTP request。

目标真实链路：

```text
HTTP Client
↓
FastAPI
↓
real AgentOrchestrator
↓
real DeepSeekModelClient
↓
DeepSeek
↓
ToolCall
↓
real SearchJobsTool / GetJobDetailTool
↓
SQLite
↓
Observation
↓
DeepSeek
↓
FinalAnswer
↓
HTTP Response
```

Smoke 必须验证至少：

```text
HTTP 200
nonblank answer
steps >= 1
tool_execution_count >= 1
```

若希望强制验证 Tool loop，应使用明确要求查询当前数据库后再回答的 smoke prompt。

不要依赖模型自由选择 Direct FinalAnswer 来证明 Tool integration。

Live model 名称来自：

```text
DEEPSEEK_MODEL
```

不在应用代码中 hardcode。

---

# 32. Stage 9F — Final Regression & Review

实现完成后：

```text
Stage 9 targeted tests
↓
Agent subsystem tests
↓
Full regression
↓
git diff --check
↓
Human review
↓
Codex Final Read-Only Review
```

Codex Final Review 使用 high-reasoning model。

Final Review 必须检查：

```text
HTTP contract
dependency lifecycle
session lifetime
provider isolation
no eager API-key requirement
Tool registration order
offline test isolation
no Provider-specific exception coupling in route
no secret leakage
no Stage 7/8 architecture regression
no out-of-scope refactor
```

最终：

```text
MUST FIX = 0
```

才允许 Stage closeout。

---

# 33. Documentation Closeout

Stage 9 implementation 与 review 完成后：

新增：

```text
docs/stage-reviews/stage-09-review.md
```

更新：

```text
docs/development-log.md
```

然后：

```text
PR
↓
merge to main
↓
main full regression
↓
obtain real Stage 9 merge identity
↓
update PROJECT_STATE.md
↓
commit PROJECT_STATE update
↓
branch cleanup
```

`PROJECT_STATE.md` 不得在 merge 前猜测：

```text
Stage 9 merge commit
final test baseline
final repository tree
```

---

# 34. Stage 9 Acceptance Criteria

Stage 9 只有同时满足以下条件才算完成。

## HTTP

```text
POST /api/agent/query exists
```

Request：

```text
AgentQueryRequest
```

Response：

```text
AgentQueryResponse
```

Validation：

```text
blank input → 422
```

---

## Application Integration

真实 production object graph：

```text
FastAPI
→ AgentOrchestrator
→ ModelClient
→ ToolRegistry
→ Job Tools
→ JobQueryPort
→ RepositoryJobQueryAdapter
→ Repository
→ SQLite
```

---

## Lifecycle

```text
Session request-scoped
Adapter request-scoped
Tools request-scoped
Registry request-scoped
Orchestrator request-scoped
```

没有 request-bound object 被全局缓存。

---

## Provider

```text
DeepSeek remains behind ModelClient
```

Provider configuration：

```text
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
```

均为 server-side。

没有 eager Provider initialization。

---

## Agent Architecture

保持：

```text
AgentState per-run
Sequential Tool Calling only
Tool Failure as Observation
provider-neutral AgentOrchestrator
stateless DeepSeek adapter
```

---

## Testing

Offline integration：

```text
PASS
```

Real DeepSeek HTTP smoke：

```text
PASS
```

Full regression：

```text
PASS
```

Existing Stage 8 baseline：

```text
204 passed, 0 warnings
```

必须保持无回归。

---

## Review

```text
Codex Final Read-Only Review
MUST FIX = 0
```

---

## Documentation

```text
stage-09-review.md complete
development-log.md updated
PR merged
main regression passed
PROJECT_STATE updated after real merge identity
branch cleanup complete
```

---

# 35. Codex Workflow Rules

Routine implementation model：

```text
Luna
```

High reasoning 仅用于：

```text
complex architecture issue
difficult debugging
Stage Final Read-Only Review
```

每次开始 Codex 前确认模型。

如果默认是：

```text
Sol High
```

Routine implementation 前先切回：

```text
Luna
```

---

# 36. Codex Git Safety

Codex 默认禁止：

```text
git add
git commit
git push
create PR
merge
delete branch
```

Codex 可以：

```text
read repository
git status
git diff
git log
git diff --check
run pytest
modify explicitly allowed files
```

所有 Git publication decisions 由 Human 完成。

---

# 37. Scope Safety

Codex 实现时如果认为“顺便”应该：

```text
refactor database dependencies
create app factory
move repository into class
add async
add retry
add Memory
add RAG
add streaming
add new tool
add shared conftest
change ModelClient exception architecture
```

必须：

```text
DO NOT IMPLEMENT
```

只报告建议。

Stage 9 的目标是：

> 用最小、明确、可测试的 Application Layer 将已经完成的 Agent Runtime 接入现有 FastAPI，而不是把项目整体重新设计一次。

---

# 38. Current Execution State

Stage 9 当前进度：

```text
9A Architecture & API Contract
COMPLETE

9B Application Composition & Dependencies
NEXT
```

Stage 9 当前唯一下一实现目标：

```text
app/api/dependencies.py
```

在 9B 开始前：

```text
Task Spec must be reviewed and frozen
working tree state must be known
Codex model must be Luna
```