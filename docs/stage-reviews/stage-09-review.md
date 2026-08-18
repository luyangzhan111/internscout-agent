# InternScout Agent — Stage 9 Review

## 1. Stage Overview

### Stage

```text
Stage 9 — Agent HTTP API & Application Integration
```

### Stage Goal

Stage 9 的核心目标是：

> 将 Stage 7 已完成的 provider-neutral Agent Runtime、Stage 8 已完成的 DeepSeek Provider Adapter，以及现有 FastAPI、Job Tools、Repository 与 SQLite 数据层正式组合为一个可以通过 HTTP 调用的 Agent Application。

Stage 9 完成后的核心链路：

```text
HTTP Client
↓
POST /api/agent/query
↓
FastAPI
↓
AgentQueryRequest
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
↓
Observation
↓
DeepSeek
↓
FinalAnswer
↓
AgentQueryResponse
↓
HTTP Response
```

Stage 9 不是重新设计 Agent Runtime，而是完成：

```text
Application Integration
+
Dependency Wiring
+
HTTP Contract
+
HTTP Error Boundary
+
Offline HTTP Integration Tests
+
Real DeepSeek HTTP Smoke
```

---

# 2. Starting Baseline

Stage 9 开始时：

```text
Completed:
Stage 0 ～ Stage 8

Stage 8 Merge Identity:
796db56

Full Regression:
204 passed

Warnings:
0

Real Provider:
DeepSeek
```

Stage 8 已经具备：

```text
DeepSeekModelClient
Real DeepSeek FinalAnswer Smoke
Real ToolCall → Observation → FinalAnswer Smoke
```

但 Agent Runtime 尚未通过 FastAPI 向外部客户端暴露。

---

# 3. Stage 9 Final Status

Stage 9 当前实现与 Final Review 已完成。

```text
Stage 9A — Architecture & API Contract
PASS

Stage 9B — Application Composition & Dependencies
PASS

Stage 9C — HTTP Schemas & Agent Route
PASS

Stage 9D — Offline HTTP Integration & Error Boundary
PASS

Stage 9E — Real DeepSeek HTTP Smoke
PASS

Stage 9F — Final Review
PASS
```

Codex Final Read-Only Review：

```text
MUST FIX = 0
```

Final Verdict：

```text
READY FOR STAGE 9 CLOSEOUT
```

Stage 9 当前尚未完成：

```text
PR merge
post-merge main regression
PROJECT_STATE update
branch cleanup
```

因此：

```text
Stage 9 Merge Identity:
UNKNOWN
```

必须等真实 PR merge 后再确定。

---

# 4. Stage 9 Commit History

当前 Stage 9 feature branch：

```text
feat/stage-09-agent-http-api
```

主要 commits：

```text
10b602e
docs: add stage 9 task spec

d2eaa9e
feat: add agent application dependencies

b8fcdc5
feat: add agent query API

465d524
test: add agent API integration coverage

b9b7181
fix: support DeepSeek commentary tool calls
```

注意：

```text
10b602e
```

是 Repository Reality 中真实的 Stage 9 Task Spec commit。

---

# 5. Stage 9 Architecture Decisions

## 5.1 HTTP Endpoint

新增：

```text
POST /api/agent/query
```

没有使用：

```text
POST /api/chat
```

原因：

当前 Agent：

```text
没有 Memory
没有 Persistent Conversation
没有 Conversation Session
```

Stage 9 的语义保持：

```text
1 HTTP Request
=
1 AgentOrchestrator.run()
=
1 independent AgentState
```

---

# 6. HTTP Request Contract

新增：

```text
AgentQueryRequest
```

核心字段：

```text
user_message: str
```

要求：

```text
required
trim whitespace
blank rejected
unexpected fields rejected
```

非法 Request：

```text
HTTP 422
```

HTTP Client 不允许控制：

```text
provider
model
API key
max_steps
reasoning
tools
tool_choice
conversation_id
```

这些继续属于 server-side policy。

---

# 7. HTTP Response Contract

新增：

```text
AgentQueryResponse
```

Public response：

```text
answer
steps
tool_execution_count
```

Stage 9 明确保持：

```text
Internal Agent Trace
!=
Public HTTP Contract
```

因此没有向客户端暴露：

```text
ToolCall
Tool arguments
ToolResult
ToolExecution
Observation
Provider raw response
SDK object
ORM object
```

这样避免内部 Agent Runtime 结构过早成为稳定的公共 API Contract。

---

# 8. Application Composition Root

新增：

```text
app/api/dependencies.py
```

作为：

```text
FastAPI / Application Composition Root
```

它负责组装：

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

只有最外层 Composition Layer 同时认识这些 concrete implementations。

以下模块仍保持自己的边界：

```text
app/agent/*
app/database/*
```

没有因为 Stage 9 而依赖 FastAPI。

---

# 9. Dependency Lifecycle

Stage 9 保持：

```text
SQLAlchemy Session:
request-scoped

RepositoryJobQueryAdapter:
request-scoped

SearchJobsTool:
request-scoped

GetJobDetailTool:
request-scoped

ToolRegistry:
request-scoped

AgentOrchestrator:
request-scoped
```

没有任何持有 SQLAlchemy Session 的对象被全局缓存。

Tool 注册顺序固定：

```text
1. SearchJobsTool
2. GetJobDetailTool
```

因为 `ToolRegistry` 注册顺序会暴露给 Model，因此该顺序属于可观察行为。

---

# 10. ModelClient Dependency

新增：

```text
get_model_client()
```

Production Provider：

```text
DeepSeekModelClient
```

配置：

```text
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
```

两者都属于：

```text
server-side configuration
```

没有通过 HTTP Request 暴露。

`DeepSeekModelClient` 使用 lazy application-level reuse。

关键行为：

```text
import app.main
```

不会立即要求 DeepSeek API 配置。

因此：

```text
/api/health
/api/jobs
existing automated tests
```

不会因为未设置 DeepSeek API Key 而失效。

---

# 11. Preserved Stage 7 / Stage 8 Architecture

Stage 9 没有重新设计：

```text
ModelClient
AgentOrchestrator
AgentState
BaseTool
ToolRegistry
JobQueryPort
RepositoryJobQueryAdapter
```

继续保持：

```text
ModelClient.generate(ModelRequest)
→ ModelResponse
```

`AgentOrchestrator` 仍然 provider-neutral。

---

# 12. AgentState Lifecycle

Stage 9 继续保持：

```text
AgentState = per-run
```

每次：

```text
AgentOrchestrator.run()
```

创建新的本地 state。

没有实现：

```text
Persistent Conversation
Cross-request State
Memory
Provider Conversation State
```

因此 Stage 9 HTTP API 仍然是 stateless Agent query API，而不是 Chat System。

---

# 13. Tool / Database Boundary

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
SQLAlchemy
            ↓
SQLite
```

Stage 9 没有引入 Repository class。

当前 Repository 继续采用：

```text
module functions
+
explicit Session
```

Job Tools 不直接认识：

```text
SQLAlchemy Session
JobModel
Repository implementation
```

---

# 14. Error Boundary

Stage 9 第一版 HTTP Error Boundary：

## Request Validation

```text
invalid request
→ HTTP 422
```

包括：

```text
missing user_message
empty user_message
whitespace-only user_message
unexpected field
```

---

## Missing Provider Configuration

```text
DEEPSEEK_API_KEY missing
or
DEEPSEEK_MODEL missing
```

结果：

```text
HTTP 503
```

返回 sanitized message：

```text
Agent model service is unavailable.
```

不会泄漏：

```text
API key
environment value
provider internals
traceback
```

---

## Unexpected Agent / Model Failure

结果：

```text
HTTP 500
```

返回：

```text
Agent service encountered an unexpected error.
```

不会将 raw exception 直接暴露给 Client。

Stage 9 没有引入 provider-specific HTTP exception mapping。

---

## Agent Max Steps

Agent 无法在默认 `max_steps` 内完成：

```text
HTTP 500
```

测试同时确认：

```text
FakeModelClient received exactly 5 requests
```

因此测试证明的是：

```text
real AgentOrchestrator max_steps boundary
```

而不是 Fake response exhaustion。

---

# 15. Tool Failure Semantics

继续保持 Stage 7 设计：

```text
Tool Failure
!=
Agent Failure
!=
HTTP Failure
```

例如：

```text
Tool argument validation failure
↓
ToolResult(success=False)
↓
Observation
↓
Model continues
↓
FinalAnswer
↓
HTTP 200
```

Unknown Tool 同样保持 failed Observation 语义。

---

# 16. Offline HTTP Integration Tests

新增：

```text
tests/test_agent_api.py
```

核心原则：

自动化测试只替换：

```text
get_session
get_model_client
```

不会替换：

```text
get_agent_orchestrator
AgentOrchestrator
ToolRegistry
SearchJobsTool
GetJobDetailTool
RepositoryJobQueryAdapter
Repository functions
```

因此测试真实覆盖：

```text
HTTP
↓
FastAPI
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
real Repository
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

---

# 17. Stage 9D Test Coverage

新增 11 个 Agent HTTP integration tests。

覆盖：

```text
Direct FinalAnswer

SearchJobsTool full integration path

GetJobDetailTool full integration path

Tool validation failure recovery

Missing user_message

Empty user_message

Whitespace-only user_message

Unexpected HTTP request field

Missing Provider configuration

Agent default max_steps boundary

Unexpected Model boundary failure
```

Stage 9D 初次实现曾出现：

```text
Expected HTTP 422
Actual HTTP 503
```

原因不是 Production bug。

根因是 Validation Test 没有 override：

```text
get_model_client
```

因此非法 HTTP Request 同时触发了：

```text
missing Provider configuration
```

测试修复后：

```text
invalid HTTP validation
```

和：

```text
missing Provider configuration
```

两个场景被独立验证。

最终：

```text
11 passed
```

---

# 18. Temporary SQLite Test Lifecycle

Stage 9 沿用当前 Repository Reality。

测试存在两个独立 database seams：

```text
app.state.database_engine
```

负责 lifespan 初始化。

以及：

```text
get_session
```

负责 Request DB Session。

因此测试同时设置：

```text
app.state.database_engine = test_engine
```

和：

```text
dependency_overrides[get_session]
```

测试完成后恢复：

```text
dependency overrides
app.state.database_engine
provider dependency cache
temporary engine resources
```

Stage 9 没有顺手重构 database dependency architecture。

---

# 19. Real DeepSeek Provider Compatibility Issue

Stage 9E 真实 DeepSeek Tool Calling Smoke 暴露了 Stage 8 离线测试未发现的 Provider Contract mismatch。

第一次真实 Agent Tool Loop：

```text
FAILED
```

异常：

```text
ValueError:
DeepSeek response cannot contain both a function call and a final answer.
```

---

# 20. Provider Raw Response Diagnosis

通过 Raw Provider Diagnostic，确认 DeepSeek 真实返回：

```text
ResponseOutputMessage

phase:
commentary

text:
我来为您查询数据库中深圳的实习岗位。
```

随后：

```text
ResponseFunctionToolCall

name:
search_jobs
```

即：

```text
commentary message
+
function_call
```

旧版 Adapter 将：

```text
non-empty output_text
```

直接等价为：

```text
FinalAnswer
```

因此错误拒绝了合法 Tool Call。

---

# 21. Provider Compatibility Fix

修改：

```text
app/agent/providers/deepseek_client.py
tests/agent/providers/test_deepseek_client.py
```

新的 response mapping：

## Function Call Only

```text
function_call
→ ToolCallResponse
```

## Commentary + Function Call

```text
phase="commentary"
+
function_call
→ ToolCallResponse
```

## Final Answer + Function Call

```text
phase="final_answer"
+
function_call
→ ValueError
```

## Unsupported Phase + Function Call

例如：

```text
phase=None
phase=""
phase="future_phase"
```

结果：

```text
ValueError
```

原则：

> Provider Adapter 只接受明确知道的合法 response shape；未知 Provider shape defensive fail。

---

# 22. Other Provider Defensive Boundaries

继续保持：

```text
multiple function calls
→ fail

invalid JSON arguments
→ fail

non-object JSON arguments
→ fail

empty / unsupported response
→ fail

non-JSON-serializable Tool history
→ fail before Provider request

Provider SDK exception
→ propagate
```

Sequential Tool Calling only。

没有实现：

```text
Parallel Tool Calling
```

---

# 23. Real DeepSeek Agent Tool Loop

修复后重新执行真实 Agent：

```text
SUCCESS
```

真实结果：

```text
steps:
2

tool_execution_count:
1

tool_name:
search_jobs

tool_success:
True

tool_error:
None
```

最终回答基于真实 SQLite 岗位：

```text
Python后端实习生
DevOps实习生
```

说明链路真实完成：

```text
Real DeepSeek
↓
commentary
↓
ToolCall
↓
SearchJobsTool
↓
SQLite
↓
Observation
↓
Real DeepSeek
↓
FinalAnswer
```

---

# 24. Real HTTP Agent Smoke

随后启动 FastAPI 并执行：

```text
POST /api/agent/query
```

真实 HTTP 请求：

```text
请查询当前岗位数据库中深圳的实习岗位，
并根据数据库查询结果告诉我有哪些岗位。
不要根据常识直接回答，
必须先使用可用的岗位查询工具。
```

最终：

```text
HTTP success

answer:
non-empty

steps:
2

tool_execution_count:
1
```

回答内容包含当前数据库中的：

```text
Python后端实习生
DevOps实习生
```

因此 Stage 9 的完整目标链路已经经过真实 Provider + HTTP 验证。

---

# 25. Final Automated Test Baseline

Stage 9 Final Review 时：

```text
Provider targeted:
24 passed

Agent subsystem:
94 passed

Full project:
219 passed

Warnings:
0
```

`git diff --check`：

```text
PASS
```

Stage 8 historical baseline：

```text
204 passed, 0 warnings
```

Stage 9 增加：

```text
15 automated tests
```

最终增长为：

```text
219 passed
```

---

# 26. Codex Sandbox Behavior

Stage 9 期间 Codex sandbox 再次出现：

```text
PermissionError
```

与 pytest temporary directory / cache 有关。

该问题：

```text
不是 application assertion failure
不是 project warning
不是 production bug
```

Human local `.venv` 测试作为 authoritative result。

---

# 27. Final Codex Review

Stage 9 Final Read-Only Review 使用 High Reasoning Model。

结果：

```text
MUST FIX = 0
```

Architecture Compliance：

```text
HTTP contract:
PASS

Composition root:
PASS

Dependency lifecycle:
PASS

Provider-neutral Agent Runtime:
PASS

Tool / database boundary:
PASS

AgentState per-run:
PASS

Sequential Tool Calling:
PASS

Provider isolation:
PASS

Provider commentary compatibility:
PASS

Offline test isolation:
PASS

Secret safety:
PASS

Stage 9 scope control:
PASS
```

Final Verdict：

```text
READY FOR STAGE 9 CLOSEOUT
```

---

# 28. Final Review SHOULD FIX

Final Review 提出一个非阻塞 SHOULD FIX：

```text
恢复 legacy mixed response shape 的显式 regression test
```

当前 production behavior 已经保留：

```text
non-message output_text
+
function_call
→ reject
```

但在 Provider Compatibility Test 调整后，该 legacy branch 缺少独立 regression test。

状态：

```text
Non-blocking
Not required for Stage 9 closeout
```

Stage 9 当前不为该 SHOULD FIX 扩大 closeout scope。

---

# 29. Explicit Stage 9 Non-Goals

Stage 9 没有加入：

```text
Memory
Persistent Conversation
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
provider-neutral error taxonomy
```

这些缺失项不属于 Stage 9 defect。

---

# 30. Important Engineering Lessons

## 30.1 Application Composition Root

业务模块应该依赖 abstraction。

真正认识 concrete implementations 的地方应该集中在系统最外层：

```text
Composition Root
```

Stage 9 使用：

```text
app/api/dependencies.py
```

完成这一职责。

---

## 30.2 Dependency Lifetime

依赖生命周期必须与其持有资源保持一致。

因为：

```text
RepositoryJobQueryAdapter
```

持有 SQLAlchemy Session，所以：

```text
Adapter
Tools
Registry
Orchestrator
```

均采用 request scope。

不能为了“性能”简单全局缓存。

---

## 30.3 Public Contract vs Internal Trace

Agent 内部拥有大量：

```text
ToolCall
ToolExecution
Observation
```

但公共 API 不应该默认暴露全部内部实现。

保持：

```text
Public HTTP Contract
```

尽可能小，有利于后续内部 Agent Runtime 演进。

---

## 30.4 Unit Test Green != Real Provider Compatible

Stage 8：

```text
Provider tests PASS
Real smoke PASS
```

但 Stage 9 真实 HTTP Tool Calling 仍然发现：

```text
Provider response shape mismatch
```

原因：

真实 Provider 的行为包含：

```text
commentary message
+
function_call
```

而 Fake Provider 没有覆盖该真实形态。

因此真实外部系统 integration 必须保留：

```text
Offline Contract Tests
+
Real Provider Smoke
```

两层验证。

---

## 30.5 Provider Adapter 的真正价值

Provider Adapter 不只是：

```text
SDK wrapper
```

它承担的是：

```text
External Provider Contract
↕
Internal Stable Agent Contract
```

Provider 的特殊行为应该被限制在：

```text
DeepSeekModelClient
```

而不是泄漏到：

```text
AgentOrchestrator
Tool System
FastAPI
Database
```

Stage 9 的真实 Provider mismatch 最终只修改 Provider Adapter，即证明该架构边界有效。

---

# 31. Interview Knowledge Points

Stage 9 涉及的核心面试知识点：

## FastAPI

- `Depends`
- Dependency Injection
- `dependency_overrides`
- synchronous route
- request validation
- response model
- HTTP 422 / 500 / 503
- lifespan 与 request dependency 的区别

---

## Architecture

- Composition Root
- Dependency Inversion
- Port / Adapter
- Provider Adapter
- Public Contract vs Internal Contract
- Resource Lifecycle
- Request Scope vs Application Scope
- Separation of Concerns

---

## Agent Engineering

- Tool Calling
- Agent Orchestration
- Tool Observation
- Tool Failure Recovery
- Agent max steps
- Sequential Tool Calling
- Stateless Agent Runtime
- Provider-neutral Model Boundary

---

## LLM Provider Integration

- OpenAI-compatible API
- Provider-specific response mapping
- `function_call`
- ToolExecution history reconstruction
- Provider response shape mismatch
- defensive parsing
- real-provider smoke testing

---

## Testing

- Unit Test
- Integration Test
- Offline Fake Provider
- Temporary SQLite
- Dependency Override
- Test Isolation
- Cleanup
- False-positive test
- Real External Service Smoke
- Regression Baseline

---

# 32. Potential Interview Questions

### Q1：为什么 AgentOrchestrator 不直接创建 DeepSeekModelClient？

因为：

```text
AgentOrchestrator
```

依赖的是：

```text
ModelClient abstraction
```

而不是 concrete provider。

这样 Agent Runtime 可以：

```text
切换 Provider
离线测试
保持 Provider-neutral
```

---

### Q2：为什么 Tool 不直接查询 Repository？

为了隔离：

```text
Agent Layer
```

和：

```text
Database Infrastructure
```

Tool 依赖：

```text
JobQueryPort
```

真实实现：

```text
RepositoryJobQueryAdapter
```

这样可以替换数据库实现并保持 Agent Tool 独立。

---

### Q3：为什么 AgentOrchestrator 采用 request scope？

因为 Orchestrator 持有 ToolRegistry，而 Tools 持有 session-bound Adapter。

如果全局复用：

```text
HTTP request结束
↓
Session关闭
↓
下一 request 仍使用旧 Tool / Adapter
```

可能发生 closed-session 问题。

---

### Q4：为什么 DeepSeekModelClient 可以缓存？

因为当前：

```text
DeepSeekModelClient
```

设计为 stateless。

它不保存：

```text
AgentState
Conversation
ToolExecution history
```

所以可以 application-level reuse。

---

### Q5：为什么自动化测试不用真实 DeepSeek？

真实 API：

```text
不稳定
有费用
需要网络
依赖外部服务
可能限流
不可重复
```

自动化测试使用 Fake Provider。

真实 Provider 通过独立 manual smoke 验证。

---

### Q6：Stage 9 发现的真实 Provider bug 是什么？

DeepSeek Tool Calling 可能返回：

```text
commentary message
+
function_call
```

旧 Adapter 错把 commentary 的 `output_text` 当成 FinalAnswer，因此拒绝合法 Tool Call。

最终修复在 Provider Adapter 中区分：

```text
commentary
final_answer
unsupported phase
```

没有修改 Agent Runtime。

---

### Q7：为什么 Tool Failure 不直接返回 HTTP 500？

因为：

```text
Tool failure
```

只是 Agent decision loop 中的一个 Observation。

Model 可能根据失败结果：

```text
修正参数
调用其他 Tool
直接解释失败原因
```

只有整个 Agent Run 无法完成时才是 HTTP-level failure。

---

# 33. Resume Value

Stage 9 可以形成较强的项目描述：

> 基于 FastAPI 将 provider-neutral Tool-Calling Agent Runtime 暴露为 HTTP Agent 服务，通过 Dependency Injection 组装 DeepSeek LLM、AgentOrchestrator、Job Tools、Repository Adapter 与 SQLAlchemy/SQLite 数据层，并使用 Fake ModelClient + 临时 SQLite 构建离线端到端集成测试。

也可以突出真实 Provider compatibility：

> 在真实 DeepSeek Tool-Calling Smoke 中定位 `commentary message + function_call` 与内部 Agent Contract 的响应映射差异，将 Provider-specific compatibility fix 隔离在 Adapter 层，并保持 Orchestrator、Tool System 与 HTTP Layer 无需修改。

---

# 34. Stage 9 Final Capability

Stage 9 后 InternScout Agent 已经能够完成：

```text
Natural Language User Goal
↓
HTTP Request
↓
FastAPI
↓
AgentOrchestrator
↓
Real DeepSeek
↓
Tool Decision
↓
Job Database Query
↓
Observation
↓
Real DeepSeek
↓
Natural Language Final Answer
↓
HTTP Response
```

这意味着项目首次从：

```text
独立 Agent Runtime
```

升级为：

```text
可通过 HTTP 调用的 Agent Application Backend
```

---

# 35. Stage 9 Completion Boundary

截至本 Review：

```text
Implementation:
COMPLETE

Automated Tests:
PASS

Real Provider Tool Loop:
PASS

Real Agent HTTP Smoke:
PASS

Codex Final Review:
PASS

MUST FIX:
0
```

仍需完成 procedural closeout：

```text
development-log.md update
documentation commit
push
PR
merge
post-merge main regression
PROJECT_STATE update
branch cleanup
```

最终 Stage 9 merge identity：

```text
UNKNOWN
```

必须以真实 Git merge commit 为准。