# InternScout Agent — Stage 8 Task Specification

> Stage：8
> 名称：Real LLM Provider Integration
> 开发模式：Architecture-First + Codex-Driven Implementation + Human Verification
> 默认 Codex 模型：Luna / 常规开发档
> High-Reasoning 模型：仅用于复杂架构问题、疑难 Debug 和 Final Review
> 前置状态：Stage 0 ～ Stage 7 Complete
> Stage 7 merge identity：`5c5f528`
> Stage 7 merge 后测试基线：`184 passed, 1 warning`

---

# 1. Stage Goal

Stage 8 的目标是：

> 在保持 Stage 7 Agent Runtime 和 provider-neutral Contract 不变的前提下，为 InternScout Agent 接入第一个真实 LLM Provider，使现有 `AgentOrchestrator` 能通过真实模型产生 `ToolCallResponse` 或 `FinalAnswerResponse`。

第一版 Provider：

```text
DeepSeek
```

第一版 API：

```text
DeepSeek Responses API
```

Stage 8 完成后，目标链路：

```text
User Goal
↓
AgentOrchestrator
↓
ModelClient
↓
DeepSeekModelClient
↓
DeepSeek Responses API
↓
Provider Response
↓
ToolCallResponse
或
FinalAnswerResponse
↓
Existing Agent Runtime
```

---

# 2. Core Success Condition

Stage 8 最重要的验收目标：

```text
现有 Agent Runtime
无需重新设计
即可接入真实模型 Provider
```

必须证明 Stage 7 的以下抽象有效：

```text
ModelRequest
↓
ModelClient
↓
ModelResponse
```

并且：

```text
AgentOrchestrator
```

不需要知道：

```text
OpenAI SDK
Responses API
API Key
Provider Response Object
Provider Tool Schema
```

---

# 3. Current Repository Baseline

开始 Stage 8 前：

```text
Branch:
main

Completed:
Stage 0 ～ Stage 7

Full regression:
184 passed, 1 warning
```

当前 Agent Layer 已包含：

```text
app/agent/contracts.py
app/agent/exceptions.py
app/agent/model_client.py
app/agent/orchestrator.py
app/agent/state.py

app/agent/tools/base.py
app/agent/tools/job_query.py
app/agent/tools/job_tools.py
app/agent/tools/registry.py
```

现有核心接口：

```python
ModelClient.generate(
    request: ModelRequest
) -> ModelResponse
```

Stage 8 必须建立在该接口之上。

---

# 4. Locked Architecture Decisions

以下设计在 Stage 8 开始前冻结。

Codex 不得自行重新设计。

---

## 4.1 AgentOrchestrator Remains Provider-Neutral

禁止在：

```text
app/agent/orchestrator.py
```

加入：

```text
DeepSeek
Responses API
API Key
Provider-specific parsing
```

Orchestrator 仍然只依赖：

```text
ModelClient
```

---

## 4.2 Existing ModelClient Contract Remains Stable

Stage 8 默认不得修改：

```text
ModelClient.generate(
    ModelRequest
) -> ModelResponse
```

真实 Provider 必须适配现有 Contract。

如果 Codex 判断当前 Contract 无法正确实现 Stage 8：

```text
STOP
→ 报告具体原因
→ 不自行修改 Contract
```

等待 Architecture Decision。

---

## 4.3 Provider Adapter Isolated

DeepSeek 专属实现放入：

```text
app/agent/providers/
```

建议结构：

```text
app/agent/providers/
├── __init__.py
└── deepseek_client.py
```

核心实现：

```text
DeepSeekModelClient
```

Provider-specific code 不进入：

```text
AgentOrchestrator
AgentState
Job Tools
Repository
FastAPI Routes
```

---

## 4.4 Stateless Provider Mapping

Stage 8 不引入：

```text
Conversation Memory
Persistent Provider State
Database-backed Agent State
```

每次：

```python
generate(request)
```

必须根据当前：

```text
ModelRequest
```

生成当前 Provider Request。

不得依赖前一次 Agent Run 的残留状态。

---

## 4.5 Sequential Tool Calling Only

Stage 8 保持 Stage 7 决策：

```text
Sequential Tool Calling
```

现有 Contract 一次 Model Response 只表达：

```text
一个 ToolCall
或
一个 FinalAnswer
```

如果 Provider 一次返回多个并行 function calls：

```text
不得静默只选择第一个
不得丢弃其他调用
```

当前 Stage 应产生明确错误。

Parallel Tool Calling：

```text
OUT OF SCOPE
```

---

## 4.6 No Real API Calls In Automated Tests

所有自动化测试必须：

```text
offline
deterministic
repeatable
```

不得在：

```text
pytest
```

过程中访问真实 DeepSeek API。

不得要求 CI 拥有真实 API Key。

---

## 4.7 Stage 8 Model Compatibility Boundary

Stage 8 第一版 DeepSeek Provider 只要求支持：

```text
non-reasoning DeepSeek models
```

本轮使用 DeepSeek Responses API：

```text
base_url = https://api.deepseek.com
models = deepseek-v4-flash / deepseek-v4-pro
reasoning = {"effort": "none"}
```

底层继续使用 OpenAI Python SDK 作为兼容 SDK。模型名称必须通过
constructor / configuration 传入，Runtime 不硬编码模型名。DeepSeek
Responses API 是 stateless；Stage 8 不支持 reasoning continuity、reasoning
item persistence 或 provider conversation state。

DeepSeek 可能忽略 `parallel_tool_calls` 并返回多个 function calls，因此该
参数不能作为 Sequential guarantee。Adapter 必须拒绝一次响应中的多个
function calls；Stage 8 仍只支持 Sequential Tool Calling。

---

## 4.8 Model Name Must Not Be Hard-Coded Into Runtime Architecture

具体模型名称属于运行配置。

不得把某一个具体模型永久写死到：

```text
AgentOrchestrator
ModelClient contract
Agent Contract
```

`DeepSeekModelClient` 可以通过 constructor / configuration 获得 model name。

具体 smoke-test 模型在执行 live verification 时根据当时可用模型单独确定。

---

# 5. Proposed New Files

Stage 8 预计新增：

```text
app/agent/providers/__init__.py
app/agent/providers/deepseek_client.py

tests/agent/providers/__init__.py
tests/agent/providers/test_deepseek_client.py
```

可能修改：

```text
requirements.txt
```

是否需要修改其他文件：

```text
必须先通过 Repository Reality Check 判断
```

不要因为 Task 中列出预计文件就强制创建不必要文件。

---

# 6. Files That Should Remain Unchanged

默认禁止修改：

```text
app/agent/orchestrator.py
app/agent/state.py
app/agent/contracts.py

app/agent/tools/base.py
app/agent/tools/job_query.py
app/agent/tools/job_tools.py
app/agent/tools/registry.py

app/database/
app/api/
app/crawlers/
app/services/
app/workflows/
```

如果实现真实 Provider 必须修改其中任何一个：

```text
STOP
```

先报告：

```text
为什么必须修改
现有 Contract 哪里不足
最小修改方案
影响范围
```

等待确认。

---

# 7. Dependency Policy

Stage 8 允许评估加入：

```text
Official OpenAI Python SDK
```

不得加入：

```text
LangChain
LlamaIndex
AutoGen
CrewAI
新的 Agent Framework
```

Stage 8 的目的：

```text
验证自建 Agent Runtime
+
真实 Provider
```

而不是用外部 Agent Framework 替换现有架构。

---

# 8. DeepSeekModelClient Responsibilities

`DeepSeekModelClient` 只负责：

```text
Internal Contract
↕
DeepSeek Provider Contract
```

具体职责：

```text
ModelRequest
↓
构造 Provider Input
↓
转换 ToolDefinition
↓
调用 Responses API
↓
读取 Provider Output
↓
转换为 ToolCallResponse
或
FinalAnswerResponse
```

不得负责：

```text
执行 Tool
访问 Repository
查询 Database
控制 Agent Loop
保存 AgentState
Retry Loop
HTTP Route
```

---

# 9. Tool Definition Mapping

现有：

```text
ToolDefinition
```

包含：

```text
name
description
parameters
```

Stage 8 必须将其转换成 DeepSeek function/tool definition。

映射必须保留：

```text
name
description
JSON Schema parameters
```

不得在 Provider Adapter 中重新定义 Job Tool 参数规则。

Tool 参数真实来源仍然是：

```text
BaseTool.args_schema
↓
Pydantic JSON Schema
↓
ToolDefinition
```

---

# 10. User Message Mapping

`ModelRequest.user_message` 必须进入 Provider Request。

不得：

```text
静默丢弃
自行改写用户目标
加入与 Stage 8 无关的长期 Memory
```

如需 system/developer instruction：

必须保持：

```text
最小、明确、Provider Adapter 所需
```

不得在 Stage 8 引入复杂 Prompt Framework。

---

# 11. Tool Execution Mapping

`ModelRequest.tool_executions` 表示之前已经发生的：

```text
ToolCall
+
ToolResult
```

真实模型下一次决策必须能够看到这些 Observation。

因此 Provider Adapter 必须把已有：

```text
ToolExecution
```

转换成 Provider 能理解的：

```text
tool call history
+
tool result/output
```

要求保留：

```text
call_id
tool_name
success
data
error
```

使真实模型能够基于之前 Tool 执行结果继续决策。

---

# 12. Successful Tool Observation

例如：

```text
ToolResult(
    success=True,
    data={
        "items": [...],
        "total": 3
    }
)
```

Provider 下一轮必须能够看到：

```text
Tool执行成功
+
实际结构化结果
```

不能只告诉模型：

```text
success
```

而丢失实际岗位数据。

---

# 13. Failed Tool Observation

例如：

```text
ToolResult(
    success=False,
    error="Invalid tool arguments: ..."
)
```

Provider 下一轮必须能够看到失败 Observation。

这样真实模型才有机会：

```text
修正参数
↓
再次 ToolCall
```

Stage 8 不改变：

```text
Tool Failure ≠ Agent Failure
```

原则。

---

# 14. Provider Response Mapping

DeepSeekModelClient 必须将 Provider Response 严格映射成现有：

```text
ToolCallResponse
或
FinalAnswerResponse
```

---

## 14.1 Function Call

如果 Provider 返回一个合法 function/tool call：

转换：

```text
Provider Function Call
↓
ToolCall(
    call_id=...,
    tool_name=...,
    arguments=...
)
↓
ToolCallResponse
```

arguments 必须是：

```text
dict
```

如果 Provider arguments 无法解析为合法 JSON object：

```text
不得伪造参数
不得静默忽略
```

应产生明确错误。

---

## 14.2 Final Answer

如果 Provider 没有请求 Tool，并返回有效最终文本：

转换：

```text
Provider Text
↓
FinalAnswerResponse
```

纯空白：

```text
不得视为有效 FinalAnswer
```

现有 Contract 的空白保护必须继续生效。

---

## 14.3 Multiple Tool Calls

如果 Provider 在一次 Response 中返回多个 function calls：

当前 Stage：

```text
明确拒绝
```

原因：

```text
Stage 7 / Stage 8
只支持 Sequential Tool Calling
```

不得：

```text
只取第一个
忽略其他调用
```

---

## 14.4 Unsupported / Ambiguous Response

如果 Provider Response：

```text
没有合法ToolCall
也没有有效FinalAnswer
```

或者存在无法安全映射的歧义：

```text
必须失败
```

不得生成虚假的：

```text
FinalAnswerResponse
```

---

# 15. Provider Error Handling

Stage 8 不实现 Retry。

Provider / SDK 错误：

```text
不得被吞掉
不得假装成成功FinalAnswer
```

保持现有：

```text
ModelClient error
→ AgentOrchestrator传播
```

行为。

如果需要非常小的 Provider-specific error wrapper：

```text
必须说明原因
```

不要借此建立大型异常体系。

---

# 16. API Key Handling

API Key：

```text
不得硬编码
不得写入Repository
不得写入测试
不得写入PROJECT_STATE
不得写入Stage Review
```

真实 API Key 必须来自运行环境。

例如：

```text
DEEPSEEK_API_KEY
```

Stage 8 不为了加载 `.env` 自动引入额外配置 Framework。

如需要配置机制：

```text
优先保持最小实现
```

---

# 17. Automated Testing Requirements

Stage 8 自动化测试必须使用：

```text
Fake / Mock DeepSeek SDK-compatible Client
```

不得产生真实网络请求。

至少覆盖以下场景。

---

## 17.1 Final Answer Mapping

模拟 Provider 返回最终文本。

验证：

```text
DeepSeekModelClient.generate()
↓
FinalAnswerResponse
```

---

## 17.2 Tool Definition Mapping

输入：

```text
ModelRequest.tools
```

验证传给 Provider 的 Tool Definition 保留：

```text
name
description
parameters
```

---

## 17.3 Single Tool Call Mapping

模拟 Provider 返回一个 function call。

验证：

```text
call_id
tool_name
arguments
```

正确映射到：

```text
ToolCallResponse
```

---

## 17.4 Tool Observation Mapping

构造：

```text
ModelRequest(
    tool_executions=[...]
)
```

验证：

```text
成功ToolResult
失败ToolResult
```

均正确进入 Provider Input。

---

## 17.5 Invalid Tool Arguments JSON

Provider 返回无法解析或非 object 的 Tool arguments。

验证：

```text
明确失败
```

不得静默生成错误 ToolCall。

---

## 17.6 Multiple Tool Calls

Provider 一次返回多个 function calls。

验证：

```text
明确失败
```

不得只选择第一个。

---

## 17.7 Empty Provider Output

Provider：

```text
无ToolCall
无有效文本
```

验证：

```text
明确失败
```

---

## 17.8 Provider Exception

Mock SDK 抛异常。

验证：

```text
异常不会被转换成虚假FinalAnswer
```

---

# 18. Existing Regression Requirements

Stage 8 实现不得破坏已有：

```text
Agent Contracts
AgentState
BaseTool
ToolRegistry
Job Tools
AgentOrchestrator
JobQueryPort
RepositoryJobQueryAdapter
FastAPI
Database
Crawler
```

Stage 7 baseline：

```text
184 passed, 1 warning
```

新增 Stage 8 测试后：

```text
测试总数应增加
```

但：

```text
failure = 0
```

现有 warning 不得因 Stage 8 增加。

---

# 19. Live Smoke Test

自动化测试全部通过后，Stage 8 最后执行少量真实 API Smoke Test。

Live Test：

```text
不属于pytest
```

不要把真实网络依赖放进自动化测试。

至少验证：

### Smoke A

```text
User
↓
Real DeepSeekModelClient
↓
FinalAnswer
```

### Smoke B

```text
User
↓
Real DeepSeekModelClient
↓
ToolCall
↓
Existing Tool
↓
Observation
↓
Real DeepSeekModelClient
↓
FinalAnswer
```

Smoke Test 必须使用：

```text
默认模型：deepseek-v4-flash
测试用途数据
最少调用次数
```

避免无意义 API 消耗。

---

# 20. Stage 8 Substage Plan

Stage 8 建议拆为以下执行阶段。

---

## Stage 8A — Provider Reality & SDK Boundary

目标：

```text
确认当前 DeepSeek Responses API 接口（使用 OpenAI Python SDK）
确认Responses API调用方式
确认Function Tool格式
确认Provider Response结构
```

Codex：

```text
只读分析优先
```

输出：

```text
建议修改文件
依赖变化
Request Mapping
Response Mapping
风险
```

在 8A 结束前：

```text
不要大规模实现
```

---

## Stage 8B — DeepSeekModelClient Core

目标：

实现：

```text
DeepSeekModelClient
```

包括：

```text
ModelRequest mapping
ToolDefinition mapping
Provider call
FinalAnswer mapping
single ToolCall mapping
```

优先使用：

```text
Luna / 常规开发模型
```

---

## Stage 8C — Observation & Edge Cases

目标：

完成：

```text
ToolExecution history mapping
success observation
failure observation
invalid arguments
multiple tool calls
empty output
provider exception
```

并补齐 Unit Tests。

---

## Stage 8D — Regression & Live Verification

执行：

```text
Provider targeted tests
↓
tests/agent
↓
full pytest
↓
minimal real API smoke test
```

Stage 8D 不新增功能。

---

## Stage 8E — Final Review & Closeout

使用高推理模型执行：

```text
Codex Final Read-Only Review
```

重点检查：

```text
Provider isolation
Contract compatibility
API key safety
error handling
sequential tool-call boundary
test quality
hidden provider state
regression
```

随后：

```text
Stage Review
Development Log
PR
Merge
PROJECT_STATE
Branch Cleanup
```

---

# 21. Out of Scope

Stage 8 明确不实现：

```text
Agent HTTP API
Retry
Memory
RAG
Vector Database
Streaming
Parallel Tool Calling
Multi-Agent
Persistent Conversation
Agent Trace Persistence
Token Accounting
Cost Accounting
Prompt Management Framework
LangChain
LlamaIndex
AutoGen
CrewAI
```

以上能力不能因为 Codex 认为“顺便实现更完整”而加入 Stage 8。

---

# 22. Codex Execution Rules

Codex 开始每一个 Stage 8 子任务前必须读取：

```text
PROJECT_STATE.md
docs/codex-workflow.md
docs/tasks/stage-08-task.md
相关源码
相关tests
```

然后执行：

```powershell
git branch --show-current
git status
```

如果 Repository Reality 与 Task 不一致：

```text
STOP
→ 报告 discrepancy
```

---

# 23. Git Rules

Stage 8 开发必须使用独立 feature branch。

Branch 名建议：

```text
feat/stage-08-real-model-provider
```

Codex 不负责：

```text
git commit
git push
PR
merge
branch deletion
```

除非开发者未来明确改变规则。

---

# 24. Testing Flow

每个实现子阶段必须遵守：

```text
Targeted Test
↓
Agent Subsystem Test
↓
Full Regression
```

任何测试失败：

```text
Failure
↓
Root Cause
↓
Affected Scope
↓
Minimum Fix
```

不得立即大规模重构。

---

# 25. Acceptance Criteria

Stage 8 只有全部满足以下条件才算完成。

- [ ] DeepSeek Provider 与现有 `ModelClient` 对接
- [ ] 使用 Responses API
- [ ] AgentOrchestrator 不包含 Provider-specific code
- [ ] 现有 ModelClient Contract 保持稳定
- [ ] ToolDefinition 可以映射到 Provider Function Tool
- [ ] 一个 Provider Function Call 可以映射为 ToolCallResponse
- [ ] Provider Final Text 可以映射为 FinalAnswerResponse
- [ ] Tool success Observation 可以返回真实 Model
- [ ] Tool failure Observation 可以返回真实 Model
- [ ] 非法 Tool arguments 不会被静默接受
- [ ] 多 Tool Call 不会被静默截断
- [ ] Empty / Unsupported Provider Response 会明确失败
- [ ] Provider Exception 不会生成虚假成功结果
- [ ] API Key 不进入 Git
- [ ] Automated Tests 不访问真实 API
- [ ] Agent Tests 全部通过
- [ ] Full Regression 全部通过
- [ ] Warning 数量没有因 Stage 8 增加
- [ ] 至少一次真实 FinalAnswer Smoke Test 成功
- [ ] 至少一次真实 ToolCall → Observation → FinalAnswer Smoke Test 成功
- [ ] Codex Final Review 无必须修改项
- [ ] Stage 8 Review 完成
- [ ] Development Log 更新
- [ ] PR Merge 完成
- [ ] main merge 后 regression 通过
- [ ] PROJECT_STATE 更新
- [ ] feature branch 清理

---

# 26. Knowledge Requirements

Stage 8 完成后开发者必须能够解释：

1. 为什么需要 `ModelClient`
2. 为什么 AgentOrchestrator 不应该直接调用 OpenAI SDK
3. 什么是 Provider Adapter
4. Responses API 在项目中承担什么角色
5. ToolDefinition 如何映射到 Function Tool
6. ToolCall 如何从 Provider Response 转换
7. ToolResult 为什么必须重新提供给下一轮 Model
8. 为什么 Stage 8 不使用 Provider persistent state
9. 为什么 Automated Test 不调用真实 API
10. 为什么一次多个 Function Calls 当前必须拒绝
11. API Key 为什么不能硬编码
12. 为什么 Provider Error 不应该转成 FinalAnswer
13. FakeModelClient 和 Mock OpenAI SDK Client 的测试职责有什么区别
14. Stage 7 Runtime 与 Stage 8 Provider Layer 的边界在哪里

---

# 27. Stage Completion Definition

Stage 8 的真正成功标准不是：

```text
成功调用了一次 DeepSeek API
```

而是：

```text
InternScout Agent已经证明：

稳定的Provider-neutral Agent Runtime
可以在不重新设计核心架构的情况下
接入真实LLM Provider，
同时保持Tool Calling、
Observation、
Testing和Dependency Boundary正确。
```
