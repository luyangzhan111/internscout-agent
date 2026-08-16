# Stage 08 Review — Real LLM Provider Integration

> 项目：InternScout Agent
> Stage：8
> 主题：Real LLM Provider Integration
> 最终 Provider：DeepSeek
> Provider API：DeepSeek Responses API
> Provider SDK：OpenAI Python SDK（兼容客户端）
> Stage 8 最终本地测试基线：`204 passed, 0 warnings`

---

# 1. Stage 8 完成了什么

Stage 8 的核心目标不是简单地“成功调用一次大模型 API”，而是验证：

```text
Stage 7 已经建立的 provider-neutral Agent Runtime
可以在不重新设计核心架构的情况下
接入一个真实 LLM Provider。
```

最终完成的真实链路：

```text
User
↓
AgentOrchestrator
↓
ModelClient
↓
DeepSeekModelClient
↓
DeepSeek Responses API
↓
ToolCallResponse / FinalAnswerResponse
↓
Existing Tool System
↓
ToolResult
↓
Observation
↓
DeepSeekModelClient
↓
DeepSeek Responses API
↓
FinalAnswerResponse
↓
AgentResult
```

Stage 8 最终证明：

```text
Agent Runtime
和
LLM Provider
之间已经形成稳定的 Adapter Boundary。
```

---

# 2. Stage 8 最重要的架构成果

## 2.1 Provider-Neutral Runtime

Stage 7 已经建立：

```python
ModelClient.generate(
    request: ModelRequest
) -> ModelResponse
```

Stage 8 没有修改这个核心 Contract。

`AgentOrchestrator` 仍然只依赖：

```text
ModelClient
```

而不知道：

```text
DeepSeek
OpenAI Python SDK
Responses API
API Key
Provider Response Object
Provider Function Tool Format
```

因此架构仍然保持：

```text
AgentOrchestrator
        │
        ▼
    ModelClient
        │
        ▼
Provider Adapter
```

这属于典型的：

```text
Dependency Inversion
+
Adapter Pattern
```

---

# 3. 为什么需要 ModelClient

如果 `AgentOrchestrator` 直接调用 DeepSeek：

```python
client.responses.create(...)
```

那么 Orchestrator 将同时承担：

```text
Agent Loop
Provider API 调用
Provider Request Mapping
Provider Response Parsing
API Key 配置
Provider Error Handling
```

这样会导致：

```text
Agent Runtime
和
具体 Provider
高度耦合
```

以后如果：

```text
DeepSeek → OpenAI
DeepSeek → Gemini
DeepSeek → 本地模型
```

就可能需要修改 Orchestrator。

现在通过：

```text
ModelClient
```

Orchestrator 只关心：

```text
ModelRequest
→
ModelResponse
```

Provider 的实现细节全部放入 Adapter。

---

# 4. Provider Adapter 是什么

Stage 8 新增的核心实现：

```text
app/agent/providers/deepseek_client.py
```

核心 Class：

```text
DeepSeekModelClient
```

它的职责只有：

```text
InternScout Internal Contract
            ↕
DeepSeek Provider Contract
```

具体负责：

```text
ModelRequest
↓
Provider Input

ToolDefinition
↓
DeepSeek Function Tool

DeepSeek Function Call
↓
ToolCallResponse

DeepSeek Final Text
↓
FinalAnswerResponse
```

它不负责：

```text
执行 Tool
控制 Agent Loop
访问 Database
访问 Repository
保存 AgentState
Retry
Memory
RAG
HTTP API
```

---

# 5. 为什么底层还是 OpenAI Python SDK

虽然最终 Provider 是：

```text
DeepSeek
```

但当前 DeepSeek Responses API 可以通过 OpenAI-compatible SDK 调用。

因此项目架构是：

```text
Provider：
DeepSeek

SDK：
OpenAI Python SDK

base_url：
https://api.deepseek.com
```

这两件事并不冲突。

SDK 是：

```text
客户端实现工具
```

Provider 才是：

```text
真正提供模型推理服务的一方
```

因此 Class 命名必须是：

```text
DeepSeekModelClient
```

而不是：

```text
OpenAIModelClient
```

---

# 6. DeepSeekModelClient 构造逻辑

真实 Client 创建逻辑的核心语义：

```python
OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)
```

模型名称：

```text
不是硬编码到 Runtime
```

而是：

```python
DeepSeekModelClient(
    model="..."
)
```

通过 constructor 传入。

这样：

```text
deepseek-v4-flash
deepseek-v4-pro
未来其他模型
```

都不需要修改 Agent Runtime。

---

# 7. Dependency Injection 在 Stage 8 中的作用

`DeepSeekModelClient` 支持：

```python
DeepSeekModelClient(
    model="...",
    client=fake_client,
)
```

如果注入 Fake Client：

```text
不需要 DEEPSEEK_API_KEY
不访问真实网络
```

如果没有注入 Client：

```text
读取 DEEPSEEK_API_KEY
↓
构造真实 SDK Client
```

这个设计使：

```text
Production
和
Automated Test
```

使用同一个 Provider Adapter，而不需要真实 API。

这是 Stage 8 测试设计的关键。

---

# 8. API Key 安全

Stage 8 的 API Key 原则：

```text
不得硬编码
不得写进 Git
不得写进测试
不得写进 PROJECT_STATE
不得写进 Stage Review
不得打印真实 Secret
```

真实 Key 使用：

```text
DEEPSEEK_API_KEY
```

环境变量提供。

缺失 Key 且没有注入 Client 时：

```text
fail fast
```

不会等到真正 API 请求时才暴露问题。

---

# 9. ModelRequest 如何映射到 Provider Request

Stage 8 有两种主要情况。

---

## 9.1 第一次模型调用

如果：

```text
tool_executions == []
```

Provider Input 保持最简单形式：

```text
user_message
```

例如：

```text
"帮我查询深圳的 AI 实习岗位"
```

不需要为了统一格式而构造复杂 conversation state。

---

## 9.2 Tool 已经执行过

如果：

```text
tool_executions != []
```

Provider Adapter 根据当前 `ModelRequest` 重新构造历史。

例如：

```text
User Message
↓
Function Call
↓
Function Call Output
```

如果发生多个 Sequential Tool Execution：

```text
User
↓
Function Call 1
↓
Function Call Output 1
↓
Function Call 2
↓
Function Call Output 2
```

所有历史 execution：

```text
按原顺序保留
```

不会只发送最后一次 ToolResult。

---

# 10. 什么是 Stateless Provider Adapter

Stage 8 明确没有使用：

```text
self.history
self.last_response
previous_response_id
Provider Conversation State
Database-backed Conversation
```

每次：

```python
generate(request)
```

都仅根据：

```text
当前 ModelRequest
```

构造完整 Provider Request。

因此 Provider Adapter 是：

```text
Stateless
```

好处包括：

```text
容易测试
容易理解
避免 Run 之间状态泄漏
降低 Provider-specific state 对 Agent Runtime 的影响
```

---

# 11. ToolDefinition → Function Tool

InternScout 内部：

```text
ToolDefinition
```

包含：

```text
name
description
parameters
```

Provider Adapter 将其转换为 function tool。

关键是：

```text
Provider Adapter 不重新定义业务 Tool Schema。
```

真正的参数规则仍然来自：

```text
BaseTool.args_schema
↓
Pydantic JSON Schema
↓
ToolDefinition
↓
Provider Function Tool
```

因此：

```text
业务参数定义
```

仍然只有一个权威来源。

---

# 12. Provider Function Call → ToolCallResponse

DeepSeek 如果返回：

```text
function_call
```

Adapter 将其转换为：

```text
ToolCallResponse
```

其中：

```text
call_id
tool_name
arguments
```

进入 InternScout 自己的 Contract。

Provider arguments 必须：

```text
是合法 JSON
并且解析后必须是 object / dict
```

以下情况会明确失败：

```text
invalid JSON
[]
"abc"
1
```

不会伪造或修补 Provider 参数。

---

# 13. call_id 为什么重要

模型生成 Tool Call 时会带：

```text
call_id
```

InternScout 在后续 Tool Execution 中保留这个 ID。

下一次返回 Provider 时：

```text
function_call
```

和：

```text
function_call_output
```

必须通过相同：

```text
call_id
```

建立关联。

因此：

```text
Provider Tool Call
↓
ToolCall.call_id
↓
ToolResult.call_id
↓
function_call_output.call_id
```

必须保持一致。

Adapter 不重新生成 call_id。

---

# 14. Tool Result 为什么必须重新给模型

Agent 的 Tool 执行和模型推理是两个不同阶段。

模型第一次可能只知道：

```text
我要查询岗位
```

然后发出：

```text
ToolCall
```

真正岗位数据由 Tool 执行得到。

所以第二次模型调用必须看到：

```text
ToolResult
```

否则模型不知道 Tool 到底返回了什么。

完整链路：

```text
Model
↓
ToolCall
↓
Tool
↓
ToolResult
↓
Observation
↓
Model
↓
FinalAnswer
```

Observation 是 Agent Loop 的关键组成部分。

---

# 15. Success Observation

成功 ToolResult：

```text
success = True
```

Provider Observation 至少包含：

```json
{
    "success": true,
    "tool_name": "...",
    "data": ...
}
```

最重要的是：

```text
不能只告诉模型 Tool 成功了。
```

还必须传回：

```text
实际 data
```

否则模型无法基于岗位数据继续推理。

---

# 16. Failed Observation

Tool Failure 不等于 Agent Failure。

失败 Observation：

```json
{
    "success": false,
    "tool_name": "...",
    "error": "..."
}
```

然后继续交给模型。

因此模型有机会：

```text
发现参数错误
↓
修正参数
↓
再次 ToolCall
```

Stage 8 继续保持 Stage 7 的原则：

```text
Tool Failure != Agent Failure
```

---

# 17. function_call_output

ToolResult 返回模型时，通过：

```text
function_call_output
```

表达。

核心包含：

```text
call_id
output
```

其中：

```text
output
```

被序列化成 JSON string。

项目使用：

```python
json.dumps(
    value,
    ensure_ascii=False,
)
```

这样中文：

```text
深圳
后端实习
AI 应用工程师
```

不会全部变成 Unicode escape。

---

# 18. JSON Serialization Fail-Fast

如果 Tool Result 中存在不能 JSON 序列化的对象：

```text
不得使用 str()
不得使用 repr()
不得偷偷丢字段
```

当前策略：

```text
明确抛错
```

原因：

如果 Provider 收到被错误字符串化的数据：

```text
可能产生难以定位的 Agent 行为错误。
```

因此在 Provider Request 发出之前：

```text
Fail Fast
```

更安全。

---

# 19. FinalAnswerResponse

如果 Provider：

```text
没有请求 Tool
并且提供有效文本
```

Adapter 转换：

```text
Provider Final Text
↓
FinalAnswerResponse
```

如果：

```text
空字符串
纯空白
没有有效 ToolCall
```

则明确失败。

不会制造假的 FinalAnswer。

---

# 20. 为什么多个 Function Calls 当前必须拒绝

Stage 7 / Stage 8 当前 Contract：

```text
一次 Model Response
只能表达：

一个 ToolCall
或
一个 FinalAnswer
```

因此如果 DeepSeek 一次返回：

```text
ToolCall A
+
ToolCall B
```

当前不能安全映射到：

```text
ToolCallResponse
```

所以 Adapter：

```text
明确失败
```

而不是：

```text
只执行第一个
忽略第二个
```

否则会产生：

```text
Silent Data Loss
```

---

# 21. Sequential Tool Calling 与 Parallel Tool Calling

需要区分：

## Sequential

```text
Model
↓
Tool A
↓
Model
↓
Tool B
↓
Model
```

这是当前支持的。

因此历史中可以存在：

```text
多个 ToolExecution
```

---

## Parallel

```text
Model
↓
同时返回 Tool A + Tool B
```

当前：

```text
不支持
```

Stage 8 不修改 Orchestrator 去实现 Parallel Tool Calling。

---

# 22. 为什么不能依赖 parallel_tool_calls=False

最初 OpenAI Provider 版本发送过：

```text
parallel_tool_calls=False
```

切换到 DeepSeek 后发现：

```text
Provider 不能被这个参数可靠地限制为 Sequential。
```

因此真正的安全边界必须在：

```text
InternScout Adapter
```

中实现。

当前策略：

```text
response function_call count > 1
↓
明确失败
```

这属于：

```text
Defensive Programming
```

---

# 23. DeepSeek Thinking Mode 边界

Stage 8 当前只验证：

```text
non-reasoning integration
```

DeepSeek 请求显式发送：

```python
reasoning={
    "effort": "none"
}
```

原因是 Stage 8 当前没有实现：

```text
reasoning item persistence
reasoning continuity
reasoning provider state
```

如果未来支持 reasoning model：

```text
需要单独 Architecture Decision
```

不能偷偷把 reasoning state 塞入现有 Contract。

---

# 24. Provider Exception 为什么直接传播

Stage 8 不实现：

```text
Retry
Fallback
Circuit Breaker
```

因此 Provider SDK 抛异常时：

```text
继续向上传播
```

不会：

```text
吞掉错误
生成假的 FinalAnswer
```

错误：

```text
必须看起来像错误
```

而不是假装 Agent 已经成功回答。

---

# 25. FakeModelClient 与 Fake SDK Client 的区别

Stage 7：

```text
FakeModelClient
```

测试的是：

```text
Agent Runtime
```

也就是：

```text
AgentOrchestrator
Tool Loop
Agent State
Runtime Contract
```

Stage 8：

```text
Fake DeepSeek/OpenAI-compatible SDK Client
```

测试的是：

```text
Provider Adapter
```

也就是：

```text
Provider Request Mapping
Provider Response Mapping
API Boundary
```

两种 Fake 的职责不同。

---

# 26. 为什么 pytest 不调用真实 API

自动化测试要求：

```text
fast
deterministic
repeatable
offline
```

如果 pytest 调真实 API：

```text
需要网络
需要 API Key
会产生费用
Provider 可能波动
模型输出可能不同
CI 环境需要 Secret
```

都会降低测试稳定性。

因此：

```text
Automated Tests
→ Fake SDK

Live Verification
→ Real API
```

严格分离。

---

# 27. Offline Agent Integration Test

Stage 8 不仅测试：

```text
DeepSeekModelClient.generate()
```

还进行了完整离线 Agent Loop：

```text
Fake Provider
↓
ToolCallResponse
↓
AgentOrchestrator
↓
BaseTool
↓
ToolResult
↓
Observation
↓
Fake Provider
↓
FinalAnswerResponse
↓
AgentResult
```

覆盖：

```text
成功 Tool Observation
失败 Tool Observation
```

这验证的不只是一个 Mapping Function，而是：

```text
Stage 7 Runtime
+
Stage 8 Provider Adapter
```

之间真正能够协作。

---

# 28. Stage 8 Real Smoke Test A

真实测试：

```text
Real DeepSeek
↓
FinalAnswerResponse
```

输入要求模型只回复：

```text
smoke-ok
```

真实结果：

```text
response_type:
FinalAnswerResponse

answer:
smoke-ok
```

结果：

```text
PASS
```

这证明：

```text
DeepSeekModelClient
→
真实 DeepSeek Responses API
```

基本连接成功。

---

# 29. Stage 8 Real Smoke Test B

这是 Stage 8 最关键的真实验收。

真实流程：

```text
User
↓
Real DeepSeek
↓
ToolCallResponse
↓
AgentOrchestrator
↓
get_smoke_code
↓
ToolResult
↓
Observation
↓
Real DeepSeek
↓
FinalAnswerResponse
↓
AgentResult
```

实际结果：

```text
result_type:
AgentResult

steps:
2

tool_execution_count:
1

tool_name:
get_smoke_code

arguments:
{"request": "stage8d2"}

success:
True

data.code:
DEEPSEEK_TOOL_SMOKE_OK

error:
None
```

最终模型回答包含：

```text
DEEPSEEK_TOOL_SMOKE_OK
```

结果：

```text
PASS
```

这证明：

```text
真实模型 Tool Calling
+
InternScout Tool System
+
Observation
+
第二次真实模型决策
```

完整打通。

---

# 30. Stage 8 测试数量变化

Stage 7 merge 后基线：

```text
184 passed
1 warning
```

Stage 8B OpenAI Provider Core：

```text
197 passed
```

Stage 8C Observation Mapping：

```text
202 passed
0 warnings
```

DeepSeek Provider Alignment 后最终：

```text
204 passed
0 warnings
```

最终 Stage 8 本地 Full Regression：

```text
204 passed
0 warnings
```

---

# 31. 为什么 warning 从 1 变成 0

Stage 7 曾存在：

```text
StarletteDeprecationWarning
```

与 TestClient / httpx 兼容层有关。

Stage 8 安装 OpenAI Python SDK 时同时引入了：

```text
httpx2
```

之后历史 warning 消失。

Stage 8 最终基线：

```text
0 warnings
```

重要：

```text
warning 消失不是通过修改业务代码“隐藏 warning”实现的。
```

---

# 32. Stage 8 中 Provider 从 OpenAI 切换 DeepSeek

Stage 8 最开始选择：

```text
OpenAI
```

因此早期 Commit 包括：

```text
feat: add OpenAI model client core
feat: add OpenAI tool observation mapping
```

之后项目需求调整：

```text
OpenAI Provider
↓
DeepSeek Provider
```

最终提交：

```text
refactor: switch model provider to DeepSeek
```

并没有：

```text
reset
重写 Git History
删除旧 Commit
```

这些历史 Commit 是：

```text
真实开发过程
```

不是错误。

---

# 33. Provider 切换为什么没有导致 Runtime 重构

这是 Stage 8 最值得在面试中讲的地方之一。

因为 Stage 7 已经建立：

```text
AgentOrchestrator
↓
ModelClient
```

Stage 8 Provider 实现被隔离在：

```text
app/agent/providers/
```

所以：

```text
OpenAI
↓
DeepSeek
```

主要修改集中在：

```text
Provider Adapter
Provider Tests
Stage Task Documentation
```

而：

```text
AgentOrchestrator
ModelClient Contract
AgentState
Tool System
Database
FastAPI
```

都不需要重新设计。

这直接验证了：

```text
provider-neutral architecture
```

不是理论设计，而是真的产生了实际工程收益。

---

# 34. Stage 8 没有做什么

Stage 8 明确没有实现：

```text
Agent HTTP API
Retry
Memory
RAG
Vector Database
Streaming
Parallel Tool Execution
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

原因：

```text
Stage 8 只验证真实 Provider Integration。
```

保持 Scope 小，可以更准确判断：

```text
Provider Adapter
是否真的工作。
```

---

# 35. Stage 7 与 Stage 8 的边界

Stage 7：

```text
Agent Runtime
```

负责：

```text
Model / Tool execution loop
AgentState
ToolRegistry
Tool execution
Observation accumulation
Final AgentResult
```

Stage 8：

```text
Provider Layer
```

负责：

```text
Internal Contract
↕
Real LLM Provider Contract
```

可以理解成：

```text
Stage 7：
“Agent 怎么运行？”

Stage 8：
“Agent 怎么和真实 LLM 对话？”
```

---

# 36. 关键设计原则总结

Stage 8 最重要的设计原则：

```text
1. Provider-Neutral Runtime

2. Adapter Pattern

3. Dependency Inversion

4. Dependency Injection

5. Stateless Provider Mapping

6. Fail Fast

7. Explicit Failure > Silent Data Loss

8. Tool Failure != Agent Failure

9. Automated Test 与 Live API Test 分离

10. Sequential Tool Calling Boundary

11. API Key 使用 Environment Variable

12. Repository Reality > Documentation Assumption
```

---

# 37. 面试题：为什么 AgentOrchestrator 不直接调用 DeepSeek SDK？

回答思路：

> 因为 Orchestrator 的职责应该是控制 Agent Loop，而不是处理某一个模型 Provider 的 API 协议。我在项目里定义了 provider-neutral 的 ModelClient 接口，Orchestrator 只依赖 ModelRequest 和 ModelResponse。DeepSeek 的请求格式、API Key、Responses API 和 function call 解析都封装在 DeepSeekModelClient Adapter 里。这样更换 Provider 时，不需要修改 Agent Runtime。

---

# 38. 面试题：什么是 Adapter Pattern？

回答思路：

> Adapter Pattern 的作用是把一个外部接口转换成项目内部已经约定的接口。在 InternScout Agent 中，DeepSeek API 返回的是 Provider-specific response，而 Agent Runtime 只认识 ToolCallResponse 和 FinalAnswerResponse。DeepSeekModelClient 就负责在这两套 Contract 之间转换。

---

# 39. 面试题：为什么需要 Dependency Injection？

回答思路：

> 如果 DeepSeekModelClient 内部永远自己创建真实 SDK Client，那么单元测试就会依赖网络和 API Key。我允许 constructor 注入 fake client，这样生产环境可以创建真实 DeepSeek Client，而测试可以注入 Fake SDK Client，验证 request 和 response mapping，不产生真实 API 调用。

---

# 40. 面试题：ToolResult 为什么要再传回模型？

回答思路：

> 模型发出的 ToolCall 只是请求执行工具，真正的数据由 Tool 执行得到。如果 ToolResult 不重新提供给模型，模型不知道工具执行结果，就无法继续推理。因此 Agent Loop 是 Model → ToolCall → ToolResult Observation → Model，而不是 Model 调完 Tool 后直接结束。

---

# 41. 面试题：为什么 Tool Failure 不直接终止 Agent？

回答思路：

> Tool 失败可能只是模型参数错误，而不是整个任务无法完成。项目把失败转换成结构化 Observation，例如 success=false 和 error，再交给下一轮模型。模型可以根据错误修改参数并继续执行。因此 Tool Failure 和 Agent Failure 是不同层级。

---

# 42. 面试题：为什么多个 Function Calls 当前直接报错？

回答思路：

> 当前 Runtime Contract 一次 ModelResponse 只表达一个 ToolCall 或一个 FinalAnswer。如果 Provider 一次返回多个并行 calls，而 Adapter 只取第一个，就会产生 silent data loss。所以当前版本选择明确失败，等未来真正设计 Parallel Tool Calling 时再扩展 Contract 和 Orchestrator。

---

# 43. 面试题：为什么 Provider Adapter 要 Stateless？

回答思路：

> 我希望 Agent 的运行状态由 Agent Runtime 管理，而不是隐藏在某个 Provider Client 内部。每次 generate 都根据 ModelRequest 重建当前请求，不依赖 self.history 或 previous response，这样可以减少 Run 之间状态泄漏，也让测试更容易重复。

---

# 44. 面试题：为什么 pytest 不调用真实 DeepSeek？

回答思路：

> 自动化测试必须稳定、可重复，而且 CI 不应该必须持有真实 API Key。真实模型输出也可能存在非确定性并产生费用。所以 Provider Adapter 使用 Fake SDK Client 做离线测试，真实 API 只在独立的 Smoke Test 阶段做最小验证。

---

# 45. 面试题：为什么从 OpenAI 换 DeepSeek 没有大改代码？

回答思路：

> 因为 Stage 7 就已经把 Runtime 和 Provider 解耦了。AgentOrchestrator 依赖的是 ModelClient，而不是 OpenAI 或 DeepSeek。因此 Provider 切换主要发生在 Adapter 层。这也是这个架构设计最实际的验证：Provider abstraction 不只是为了代码好看，而是真的降低了替换外部服务的成本。

---

# 46. 面试题：为什么 DeepSeekModelClient 仍然 import OpenAI？

回答思路：

> DeepSeek 提供 OpenAI-compatible API，因此可以复用 OpenAI Python SDK 作为 HTTP/API 客户端。但真正的 Provider 仍然是 DeepSeek，因为使用的是 DeepSeek API Key、DeepSeek base URL 和 DeepSeek model。SDK 和 Provider 是不同概念。

---

# 47. 面试题：为什么显式设置 reasoning effort none？

回答思路：

> 当前 Stage 8 的 Contract 没有设计 reasoning item persistence 或 reasoning continuity，因此为了保持 Provider Adapter stateless，并避免引入 Provider-specific reasoning state，我把第一版兼容边界限定为 non-reasoning。以后如果支持 reasoning model，需要单独做架构设计，而不是偷偷加入隐藏状态。

---

# 48. 面试题：什么是 Fail Fast？

回答思路：

> 如果系统已经知道一个输入无法安全处理，就应该尽早明确失败，而不是继续执行产生更难排查的问题。例如 Provider function arguments 不是 JSON object、ToolResult 无法 JSON 序列化、Provider 返回多个 function calls，当前都会在边界处直接报错。

---

# 49. 如果面试官让你描述 Stage 8

可以用以下版本：

> Stage 8 我给自己前面实现的 Agent Runtime 接入了真实 LLM Provider。我没有让 Orchestrator 直接调用 DeepSeek，而是保留 ModelClient 抽象，用 DeepSeekModelClient 做 Provider Adapter。它负责把内部 ModelRequest、ToolDefinition、ToolExecution 映射到 DeepSeek Responses API，再把 function call 或最终文本映射回 ToolCallResponse 和 FinalAnswerResponse。
>
> Tool 执行结果会通过 function_call_output 重新作为 Observation 发送给模型，并且成功和失败结果都支持。Provider Adapter 保持 stateless，不保存隐藏 conversation state。
>
> 自动化测试全部使用 Fake SDK Client，真实 API 只做两个独立 smoke tests。最后真实验证了 FinalAnswer，以及 DeepSeek → ToolCall → Tool → Observation → DeepSeek → FinalAnswer 的完整链路。
>
> 这个阶段中途还把 Provider 从 OpenAI 切成了 DeepSeek，但因为 Runtime 是 provider-neutral 的，Orchestrator 和 Tool System 不需要重构，这也验证了原来的架构设计。

---

# 50. Stage 8 最终结果

最终实现：

```text
DeepSeekModelClient
DeepSeek Responses API Integration
Tool Definition Mapping
Tool Call Mapping
Final Answer Mapping
Tool Observation Mapping
Successful Tool Observation
Failed Tool Observation
Sequential Tool History Reconstruction
API Key Environment Handling
Offline Provider Tests
Offline Agent Integration Tests
Real DeepSeek Smoke Tests
```

最终本地 Full Regression：

```text
204 passed
0 warnings
```

真实 Smoke Test：

```text
Smoke A
Real DeepSeek → FinalAnswer
PASS
```

```text
Smoke B
Real DeepSeek
→ ToolCall
→ Tool
→ Observation
→ DeepSeek
→ FinalAnswer
PASS
```

Codex Final Read-Only Review：

```text
MUST FIX:
0

FINAL VERDICT:
READY FOR STAGE 8 CLOSEOUT
```

---

# 51. Stage 8 核心收获

Stage 8 最重要的收获不是：

```text
“学会调用 DeepSeek API”
```

而是理解：

```text
如何把真实 LLM Provider
作为一个可替换的基础设施组件
接入自己的 Agent Runtime。
```

核心工程能力包括：

```text
Contract Design
Provider Abstraction
Adapter Pattern
Dependency Injection
Function Calling
Observation Loop
Stateless Mapping
Error Boundary
Secret Management
Offline Testing
Live Smoke Verification
Architecture Regression Protection
```

这些能力比单纯调用一个 SDK 更接近真正的：

```text
AI Application Engineer
Agent Engineer
LLM Application Engineer
```

所需要解决的问题。
