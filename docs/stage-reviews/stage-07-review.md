# InternScout Agent 阶段7复习：Tool-Calling Agent Layer、Orchestrator 与架构解耦

> 阶段名称：Agent Architecture、Tool System、Model ClientAbstraction、AgentOrchestrator、Tool-Repository 解耦与最终加固
> 项目：InternScout Agent
> 最终测试：184 passed, 1 warning
> Agent Layer 测试：70 passed
> Codex最终审查：必须修改为无
> 阶段结论：完成最小可测试的 Tool-Calling Agent Layer，并形成“Model → ToolCall → ToolResult / Observation → Model → FinalAnswer”的可控执行闭环

---

## 目录

- [1. 阶段7完成了什么](#1-阶段7完成了什么)
- [2. 阶段7项目结构变化](#2-阶段7项目结构变化)
- [3. Agent Layer整体架构](#3-agent-layer整体架构)
- [4. Agent Contracts](#4-agent-contracts)
- [5. Agent State](#5-agent-state)
- [6. BaseTool与统一Tool执行协议](#6-basetool与统一tool执行协议)
- [7. ToolRegistry](#7-toolregistry)
- [8. Job Tools](#8-job-tools)
- [9. Tool与Repository解耦](#9-tool与repository解耦)
- [10. ModelClient抽象](#10-modelclient抽象)
- [11. FakeModelClient](#11-fakemodelclient)
- [12. AgentOrchestrator执行循环](#12-agentorchestrator执行循环)
- [13. Tool Failure与Observation](#13-tool-failure与observation)
- [14. Unknown Tool处理](#14-unknown-tool处理)
- [15. max_steps安全边界](#15-max_steps安全边界)
- [16. FinalAnswer终止与空白答案保护](#16-finalanswer终止与空白答案保护)
- [17. Agent Run状态隔离](#17-agent-run状态隔离)
- [18. 阶段7完整自动化测试](#18-阶段7完整自动化测试)
- [19. Codex最终审查与Hardening](#19-codex最终审查与hardening)
- [20. 本阶段实际遇到的问题](#20-本阶段实际遇到的问题)
- [21. 面试可能提问](#21-面试可能提问)
- [22. 一分钟阶段介绍](#22-一分钟阶段介绍)
- [23. 当前技术债与阶段边界](#23-当前技术债与阶段边界)
- [24. 阶段7验收清单](#24-阶段7验收清单)
- [25. 自测题](#25-自测题)

---

# 1. 阶段7完成了什么

阶段6结束时，项目已经具备：

```text
模拟招聘HTML
→ MockJobCrawler
→ JobCreate
→ Cleaning
→ Deduplication
→ SQLite
→ FastAPI
→ 岗位筛选 / 分页 / 详情 / 采集 / 健康检查
```

也就是说，项目已经解决：

```text
岗位从哪里来
岗位如何标准化
岗位如何去重
岗位如何保存
岗位如何查询
```

阶段7的核心目标是：

> 在已有后端能力之上，引入独立、可测试、可控的 Agent Layer，使模型可以根据用户目标决定是否调用工具，并根据工具执行产生的 Observation 继续决策，最终返回 FinalAnswer。

最终Agent闭环：

```text
User Goal
   ↓
AgentOrchestrator
   ↓
Model Decision
   ↓
ToolCall
   ↓
Tool Execution
   ↓
ToolResult / Observation
   ↓
Next Model Decision
   ↓
FinalAnswer
```

阶段7最终实现：

- Agent内部统一Contract
- Agent运行时State
- BaseTool统一工具协议
- ToolRegistry
- Job查询工具
- ModelClient抽象
- FakeModelClient
- AgentOrchestrator
- Direct FinalAnswer
- 多轮Sequential Tool Calling
- Tool Failure Observation
- Unknown Tool Observation
- FinalAnswer终止
- max_steps无限循环保护
- Tool与Repository的Port / Adapter解耦
- Tool未知参数拒绝
- 纯空白FinalAnswer拒绝
- 同一Orchestrator多次run状态隔离测试

最终：

```text
184 passed, 1 warning
```

其中：

```text
tests/agent
→ 70 passed
```

---

# 2. 阶段7项目结构变化

阶段7主要增加和修改：

```text
app/
├── agent/
│   ├── contracts.py
│   ├── exceptions.py
│   ├── model_client.py
│   ├── orchestrator.py
│   ├── state.py
│   │
│   └── tools/
│       ├── base.py
│       ├── job_query.py
│       ├── job_tools.py
│       └── registry.py
│
└── database/
    └── job_query_adapter.py

tests/
├── agent/
│   ├── fakes/
│   │   └── fake_model_client.py
│   │
│   ├── test_agent_exceptions.py
│   ├── test_base_tool.py
│   ├── test_contracts.py
│   ├── test_job_tools.py
│   ├── test_model_client.py
│   ├── test_orchestrator.py
│   ├── test_state.py
│   └── test_tool_registry.py
│
└── database/
    └── test_job_query_adapter.py
```

职责：

| 文件 | 作用 |
|---|---|
| `contracts.py` | 定义Agent内部统一协议 |
| `state.py` | 保存一次Agent Run的运行时状态 |
| `exceptions.py` | Agent Layer异常体系 |
| `model_client.py` | 模型供应商无关的抽象接口 |
| `orchestrator.py` | Agent Runtime与执行循环 |
| `tools/base.py` | Tool参数验证、执行与错误转换 |
| `tools/registry.py` | Tool注册、获取和Definition暴露 |
| `tools/job_tools.py` | 岗位搜索与岗位详情Tool |
| `tools/job_query.py` | Agent侧岗位查询Port |
| `database/job_query_adapter.py` | Repository到JobQueryPort的适配器 |

---

# 3. Agent Layer整体架构

阶段7最终依赖关系：

```text
                     User Message
                          ↓
                  AgentOrchestrator
                          ↓
                     ModelClient
                          ↓
                     ModelResponse
                  ┌───────┴────────┐
                  ↓                ↓
            ToolCallResponse   FinalAnswerResponse
                  ↓                ↓
             ToolRegistry       AgentResult
                  ↓
                Tool
                  ↓
             JobQueryPort
                  ↑
      RepositoryJobQueryAdapter
                  ↓
              Repository
                  ↓
              SQLAlchemy
                  ↓
                SQLite
```

核心架构原则：

```text
AgentOrchestrator
不直接依赖FastAPI / SQLAlchemy / Repository

ModelClient
不直接依赖Repository / Database / Job Service

Job Tool
不直接依赖SQLAlchemy Session / Repository

Repository
不反向依赖Agent Runtime
```

阶段7重点不是“接一个大模型API”，而是先把：

```text
Contract
State
Tool
Model abstraction
Runtime loop
Architecture boundary
```

建立稳定。

---

# 4. Agent Contracts

文件：

```text
app/agent/contracts.py
```

核心模型：

```text
ToolDefinition
ToolCall
ToolResult
ToolExecution
ModelRequest
ToolCallResponse
FinalAnswerResponse
AgentResult
```

---

## 4.1 ToolDefinition

表示：

> 模型可以使用什么Tool。

核心字段：

```text
name
description
parameters
```

例如：

```text
name
→ search_jobs

description
→ Search stored internship jobs...

parameters
→ Pydantic生成的JSON Schema
```

因此模型可以知道：

```text
有哪些Tool
每个Tool做什么
Tool需要哪些参数
参数有什么约束
```

---

## 4.2 ToolCall

表示：

> 模型决定执行什么Tool。

包含：

```text
call_id
tool_name
arguments
```

例如：

```json
{
  "call_id": "call_001",
  "tool_name": "search_jobs",
  "arguments": {
    "city": "深圳",
    "skill": "python"
  }
}
```

`call_id`用于将：

```text
ToolCall
```

和：

```text
ToolResult
```

准确关联。

---

## 4.3 ToolResult

表示：

> Tool执行完成后的Observation。

字段：

```text
call_id
tool_name
success
data
error
```

主要状态：

```text
成功：
success=True
data=...
error=None

失败：
success=False
data=None
error="..."
```

Contract还要求：

```text
success=True
→ 不允许error

success=False
→ 必须存在非空error
```

避免出现语义矛盾的数据。

---

## 4.4 ToolExecution

绑定：

```text
ToolCall
+
ToolResult
```

同时验证：

```text
call_id一致
tool_name一致
```

因此：

```text
call_001的search_jobs
```

不可能错误绑定到：

```text
call_002的get_job_detail
```

---

## 4.5 ModelRequest

每次调用模型时传入：

```text
user_message
tool_executions
tools
```

其中：

```text
tool_executions
```

代表之前发生过的Tool调用与Observation。

因此第二轮模型决策可以看到：

```text
用户原始目标
+
可用Tool
+
之前Tool执行发生了什么
```

---

## 4.6 ModelResponse

当前有两类：

```text
ToolCallResponse
FinalAnswerResponse
```

代表：

```text
还要继续调用Tool
```

或者：

```text
已经可以返回最终答案
```

这构成Agent控制流最核心的分支。

---

# 5. Agent State

文件：

```text
app/agent/state.py
```

核心：

```python
AgentState
```

保存：

```text
user_message
step_count
tool_executions
final_answer
```

它表示：

> 一次 Agent Run 当前运行到了什么位置。

例如：

```text
user_message
→ 帮我找深圳Python实习

step_count
→ 2

tool_executions
→ 已经执行过search_jobs

final_answer
→ None
```

表示模型已经进行过两次决策，还没有生成最终答案。

---

## 5.1 AgentState不是Memory

阶段7没有做长期记忆。

因此：

```text
AgentState
≠ Conversation Memory
≠ Database State
≠ Cross-session State
```

它只是：

```text
一次run
```

的临时Runtime State。

---

## 5.2 为什么不能使用self.state

错误方式：

```python
self.state = AgentState(...)
```

如果同一个Orchestrator对象被重复使用：

```text
run 1
→ step_count=2
→ 1个ToolExecution

run 2
→ 可能继承run 1状态
```

会造成请求污染。

当前实现：

```text
每次run()
→ 创建新的局部AgentState
```

不同run彼此隔离。

---

# 6. BaseTool与统一Tool执行协议

文件：

```text
app/agent/tools/base.py
```

核心：

```python
BaseTool
```

职责：

```text
生成ToolDefinition
验证ToolCall
验证arguments
执行Tool
转换错误
生成ToolResult
```

执行流程：

```text
ToolCall
↓
检查tool_name
↓
Pydantic验证arguments
↓
_run()
↓
ToolResult
```

---

## 6.1 Tool参数错误

例如：

```text
page=0
page_size=101
job_id=0
city="   "
ctiy="深圳"
```

都会在真正查询之前被Pydantic拒绝。

然后：

```text
ValidationError
↓
ToolResult(
    success=False,
    error="Invalid tool arguments: ..."
)
```

这意味着：

> 模型输入错误不会直接让整个Agent崩溃。

---

## 6.2 Tool内部异常

如果Tool业务执行内部发生异常：

```text
database connection failed
```

BaseTool不会直接把底层异常字符串暴露出去。

而是统一转换：

```text
ToolResult(
    success=False,
    error="Tool execution failed."
)
```

这样可以：

- 避免泄漏数据库内部信息
- 保持Tool错误格式统一
- 允许Agent下一轮继续决策

---

# 7. ToolRegistry

文件：

```text
app/agent/tools/registry.py
```

核心：

```python
ToolRegistry
```

能力：

```text
register()
get()
list_tools()
list_definitions()
```

规则：

```text
Tool name唯一
重复注册拒绝
Unknown Tool查找抛KeyError
注册顺序保持
Definition顺序保持
```

---

## 7.1 Registry为什么可以抛KeyError

`ToolRegistry`本身只是：

> Tool allowlist和查找组件。

它不知道：

```text
Unknown Tool是否应该终止Agent
```

这个控制流属于Orchestrator。

所以：

```text
ToolRegistry.get()
→ KeyError
```

是合理的。

随后：

```text
AgentOrchestrator
→ 捕获KeyError
→ 转换失败Observation
```

职责边界更清晰。

---

# 8. Job Tools

文件：

```text
app/agent/tools/job_tools.py
```

当前：

```text
SearchJobsTool
GetJobDetailTool
```

---

## 8.1 SearchJobsTool

参数：

```text
city
company
skill
page
page_size
```

支持：

```text
城市筛选
公司筛选
技能筛选
分页
空结果
超页结果
```

其中：

```text
page >= 1
1 <= page_size <= 100
```

---

## 8.2 GetJobDetailTool

参数：

```text
job_id
```

规则：

```text
job_id >= 1
```

岗位不存在时：

```text
success=True
data=None
```

这是因为：

> “没有找到岗位”是合法查询结果，而不是Tool执行异常。

---

## 8.3 Tool未知参数禁止

Codex最终审查发现：

Pydantic默认可能忽略extra fields。

例如模型输出：

```json
{
  "ctiy": "深圳"
}
```

如果：

```text
ctiy
```

被静默忽略，那么Tool可能执行：

```text
没有city条件的查询
```

最终返回大量与用户目标不一致的岗位。

最终增加：

```python
ConfigDict(
    extra="forbid"
)
```

因此：

```text
未知字段
→ ValidationError
→ ToolResult(success=False)
→ Observation
→ Model可以下一轮修正
```

这是Agent Tool中特别重要的一类输入安全保护。

---

# 9. Tool与Repository解耦

阶段7的Repo Reality Check发现：

原来的Job Tool实际上直接依赖：

```text
SQLAlchemy Session
Repository
```

依赖关系：

```text
SearchJobsTool
↓
Session
↓
query_jobs()

GetJobDetailTool
↓
Session
↓
get_job_by_id()
```

虽然功能测试全部通过，但这违反Stage 7冻结的架构要求：

> Tool与Repository解耦。

---

## 9.1 JobQueryPort

新增：

```text
app/agent/tools/job_query.py
```

核心：

```python
JobQueryPort
```

表达：

> Agent Tool需要什么查询能力。

而不是：

> 数据库具体如何查询。

能力：

```text
search_jobs(...)
get_job_by_id(...)
```

因此Job Tool现在只依赖：

```text
JobQueryPort
```

---

## 9.2 为什么Port不返回JobModel

如果：

```text
JobQueryPort
→ JobModel
```

虽然Tool没有直接import Repository，但仍然依赖SQLAlchemy ORM类型。

这种解耦只是表面的。

因此Port返回：

```text
JobRead
```

从而：

```text
Agent Layer
```

不需要认识：

```text
SQLAlchemy JobModel
```

---

## 9.3 RepositoryJobQueryAdapter

新增：

```text
app/database/job_query_adapter.py
```

核心：

```python
RepositoryJobQueryAdapter
```

职责：

```text
JobQueryPort
↓
Repository
↓
JobModel
↓
JobRead
```

它是唯一允许同时知道：

```text
Agent Port
+
Repository / Session
```

的边界组件。

---

## 9.4 为什么Adapter放database层

如果Adapter放：

```text
app/agent/
```

但内部仍然：

```text
import sqlalchemy
import app.database.repository
```

那么：

```text
agent package
```

依旧知道Database。

因此最终放在：

```text
app/database/job_query_adapter.py
```

这样Agent包本身保持基础设施无关。

---

## 9.5 为什么不新增Service Layer

这个阶段的问题只是：

```text
Job Tool
→ Repository
```

直接耦合。

通过：

```text
Port + Adapter
```

已经能够解决。

没有必要额外加入：

```text
AgentJobService
Generic Repository
Unit of Work
Dependency Injection Framework
```

否则会把一个明确的小问题扩大成架构重构。

---

# 10. ModelClient抽象

文件：

```text
app/agent/model_client.py
```

核心：

```python
ModelClient
```

接口：

```python
generate(
    request: ModelRequest
) -> ModelResponse
```

AgentOrchestrator只知道：

```text
给ModelRequest
→ 获得ModelResponse
```

它不知道真实模型是：

```text
OpenAI
Gemini
Claude
Local Model
Fake Model
```

这就是：

> Provider-neutral model abstraction。

---

## 10.1 为什么Stage 7不接真实LLM

如果Stage 7同时处理：

```text
Agent Loop
OpenAI API
API Key
网络错误
Provider协议
Token
费用
```

那么出现失败时很难判断：

```text
是Agent Runtime有问题
还是Provider有问题
```

所以Stage 7先：

```text
建立抽象
+
使用Fake
+
验证Runtime
```

真实Provider留到后续Stage。

---

# 11. FakeModelClient

文件：

```text
tests/agent/fakes/fake_model_client.py
```

作用：

```text
按顺序返回预设ModelResponse
记录收到的ModelRequest
保存Request snapshot
防止测试对象污染
响应耗尽时报错
```

---

## 11.1 为什么Agent测试需要Fake

Agent Loop可能是：

```text
第1轮
Model → ToolCall

第2轮
Model → ToolCall

第3轮
Model → FinalAnswer
```

测试必须能够准确控制：

```text
第一轮返回什么
第二轮返回什么
第三轮有没有发生
```

真实LLM无法稳定保证。

Fake可以：

```text
responses=[
    ToolCallResponse(...),
    ToolCallResponse(...),
    FinalAnswerResponse(...),
]
```

因此Agent Runtime可以被确定性测试。

---

# 12. AgentOrchestrator执行循环

文件：

```text
app/agent/orchestrator.py
```

核心：

```python
AgentOrchestrator
```

主要接口：

```python
run(user_message)
```

完整执行：

```text
normalize user_message
↓
创建AgentState
↓
while True
↓
检查max_steps
↓
build ModelRequest
↓
ModelClient.generate()
↓
step_count += 1
↓
检查ModelResponse
```

---

## 12.1 FinalAnswer分支

如果：

```text
FinalAnswerResponse
```

则：

```text
state.final_answer = response.answer
↓
_build_result()
↓
AgentResult
↓
return
```

Agent Run结束。

---

## 12.2 ToolCall分支

如果：

```text
ToolCallResponse
```

则：

```text
_handle_tool_call()
↓
ToolExecution
↓
append到state.tool_executions
↓
continue
↓
下一轮Model
```

形成：

```text
Model
→ Tool
→ Observation
→ Model
```

---

# 13. Tool Failure与Observation

阶段7一个很重要的设计：

> Tool Failure ≠ Agent Failure。

例如：

```text
模型第一次给出：
value=0

Tool要求：
value > 0
```

BaseTool得到：

```text
ValidationError
```

不会：

```text
raise
→ Agent结束
```

而是：

```text
ToolResult(success=False)
↓
写入AgentState
↓
下一轮ModelRequest
```

模型就可以看到：

```text
上一次工具执行失败
```

然后修正：

```text
value=1
```

最终成功。

---

## 13.1 为什么Observation重要

Agent与普通函数调用最大的差异之一：

普通函数：

```text
失败
→ raise
```

Agent：

```text
失败
→ Observation
→ 下一轮决策
```

因为模型需要有机会：

```text
修正参数
换一个Tool
改变策略
给出无法完成的最终说明
```

---

# 14. Unknown Tool处理

模型也可能产生：

```text
tool_name="missing_tool"
```

ToolRegistry找不到：

```text
KeyError
```

但Orchestrator不会直接让Agent崩溃。

而是生成：

```text
ToolResult(
    success=False,
    error="Tool is not available."
)
```

随后：

```text
Observation
→ 下一轮Model
```

这样：

```text
Model选择错误Tool
```

仍然是Agent可以恢复的决策错误。

---

# 15. max_steps安全边界

如果没有最大步数：

```text
Model
→ Tool
→ Model
→ Tool
→ Model
→ Tool
→ ...
```

理论上可能无限执行。

因此定义：

```python
AgentMaxStepsExceeded
```

并在：

```text
model.generate()
```

之前检查：

```text
step_count >= max_steps
```

---

## 15.1 max_steps限制什么

当前：

> max_steps限制的是Model调用次数。

例如：

```text
max_steps = 2
```

则最多：

```text
Model.generate()
Model.generate()
```

两次。

不会允许第三次Model调用。

---

## 15.2 为什么必须在generate之前检查

如果检查放在：

```text
generate之后
```

就可能出现：

```text
max_steps=2
实际上已经调用了第3次Model
然后才发现超限
```

形成off-by-one。

当前测试明确验证：

```text
Model只收到2个Request
第三个FinalAnswer不会被请求
```

---

# 16. FinalAnswer终止与空白答案保护

正常：

```text
FinalAnswerResponse
↓
AgentOrchestrator
↓
AgentResult
↓
Run结束
```

Codex最终审查发现一个边界：

```python
answer: str = Field(min_length=1)
```

无法阻止：

```text
"   "
```

因为空格字符串长度大于1。

最终在：

```text
FinalAnswerResponse
```

Contract层增加：

```text
strip后不能为空
```

现在：

```text
""
→ 拒绝

"   "
→ 拒绝

"找到3个岗位"
→ 接受
```

---

## 16.1 为什么在Contract层处理

这属于：

> 什么才算有效的FinalAnswer。

因此是：

```text
Data Contract
```

问题，而不是：

```text
Runtime Control Flow
```

问题。

所以没有为了这个边界修改AgentOrchestrator。

---

# 17. Agent Run状态隔离

Codex最终审查还建议增加：

```text
同一个Orchestrator连续run两次
```

的测试。

原因不是当前实现有bug。

当前实现本身已经：

```text
每次run创建独立AgentState
```

但缺少直接回归保护。

最终测试：

第一次：

```text
Tool
→ FinalAnswer

steps=2
tool_executions=1
```

第二次：

```text
FinalAnswer

steps=1
tool_executions=[]
```

确认第二次没有继承第一次：

```text
step_count
ToolExecution
final_answer
```

这把“Stateless per Run”架构约束正式锁进测试。

---

# 18. 阶段7完整自动化测试

阶段7测试覆盖：

```text
Agent Contracts
Agent State
Agent Exceptions
BaseTool
ToolRegistry
Job Tools
JobQueryPort边界
RepositoryJobQueryAdapter
ModelClient
FakeModelClient
AgentOrchestrator
Full Project Regression
```

---

## 18.1 Stage 7D targeted

执行：

```powershell
python -m pytest tests/agent/test_agent_exceptions.py tests/agent/test_orchestrator.py -v
```

结果：

```text
15 passed
```

验证：

- AgentMaxStepsExceeded继承AgentError
- Direct FinalAnswer
- Tool → FinalAnswer
- Multiple Tools
- Tool参数失败后的修正
- Tool内部异常
- Unknown Tool
- max_steps
- invalid max_steps
- 空用户输入
- user_message trim
- ModelClient exception
- Invalid Model Response

---

## 18.2 Tool / Adapter targeted

执行：

```powershell
python -m pytest tests/agent/test_job_tools.py tests/database/test_job_query_adapter.py -v
```

结果：

```text
14 passed
```

验证：

```text
Job Tool
→ JobQueryPort

RepositoryJobQueryAdapter
→ Repository
```

的边界。

---

## 18.3 Tool解耦后Agent Layer

执行：

```powershell
python -m pytest tests/agent -v
```

结果：

```text
66 passed
```

---

## 18.4 Tool解耦后Full Project

执行：

```powershell
python -m pytest -q
```

结果：

```text
180 passed, 1 warning
```

---

## 18.5 Final Hardening targeted

执行：

```powershell
python -m pytest tests/agent/test_contracts.py tests/agent/test_job_tools.py tests/agent/test_orchestrator.py -v
```

结果：

```text
49 passed
```

---

## 18.6 Final Agent Layer

执行：

```powershell
python -m pytest tests/agent -v
```

结果：

```text
70 passed
```

---

## 18.7 Final Full Project

执行：

```powershell
python -m pytest -q
```

最终：

```text
184 passed, 1 warning
```

warning仍然是既有：

```text
StarletteDeprecationWarning
fastapi.testclient / httpx
```

Stage 7没有新增warning。

---

# 19. Codex最终审查与Hardening

Stage 7最终只读审查：

```text
必须修改：
无
```

Codex结论：

```text
可以进入 Stage 7 最终收尾
```

审查确认：

```text
Agent Runtime边界清晰
每次run创建独立AgentState
ModelClient不依赖Database
Job Tool只依赖JobQueryPort
Repository与SQLAlchemy限制在Adapter
Tool Failure进入Observation
Unknown Tool进入Observation
FinalAnswer正常终止
max_steps没有off-by-one
```

---

## 19.1 建议1：Tool禁止未知字段

问题：

```text
ctiy
```

可能被静默忽略。

处理：

```text
ConfigDict(extra="forbid")
```

测试覆盖：

```text
search_jobs未知字段
get_job_detail未知字段
```

已处理。

---

## 19.2 建议2：FinalAnswer拒绝纯空白

问题：

```text
"   "
```

能通过：

```text
min_length=1
```

最终增加：

```text
strip后不能为空
```

测试已覆盖。

---

## 19.3 建议3：同一Orchestrator多run隔离测试

当前实现本身已经正确。

最终增加：

```text
test_orchestrator_keeps_runs_isolated
```

锁定：

```text
step_count不共享
tool_executions不共享
final_answer不共享
```

已处理。

---

# 20. 本阶段实际遇到的问题

## 20.1 Stage 7原对话过长导致Web端无法稳定继续

Stage 7开发过程中原Chat内容越来越长，最终迁移到新的对话。

迁移前生成：

```text
STAGE7_HANDOFF_2026-08-14.md
```

新对话接手后没有直接继续开发，而是先：

```text
State Recovery
↓
Repo Reality Check
```

经验：

> 长周期项目必须有正式Handoff，新会话接手后必须先恢复事实状态。

---

## 20.2 Handoff不是Repository最终真相

Handoff最后确认：

```text
162 passed, 1 warning
```

但Reality Check实际发现：

```text
177 passed, 1 warning
```

后续继续增加：

```text
180 passed, 1 warning
```

最终：

```text
184 passed, 1 warning
```

经验：

> Handoff负责恢复上下文，Git、当前文件和pytest负责决定真实状态。

---

## 20.3 Work执行环境无法启动PowerShell

最初尝试自动执行Repo Reality Check时出现：

```text
CreateProcessAsUserW failed: 5
```

这是：

```text
执行环境权限问题
```

不是：

```text
Git失败
pytest失败
项目代码失败
```

最终切回本机：

```text
VS Code Terminal
```

执行真实命令。

经验：

> 必须区分“工具环境失败”和“项目失败”。

---

## 20.4 `rg`命令不存在

尝试：

```powershell
rg "SearchJobsTool|GetJobDetailTool" app tests -n
```

本机没有ripgrep。

改用：

```powershell
Get-ChildItem app,tests -Recurse -Filter *.py |
Select-String "SearchJobsTool|GetJobDetailTool"
```

成功确认Tool实际引用位置。

经验：

> 非核心工具缺失时优先使用已有系统命令，不需要为了一个搜索命令增加环境维护工作。

---

## 20.5 Stage 7B历史“完成”，但Reality Check发现架构gap

Handoff中：

```text
Stage 7B
✅ 已完成
```

但实际读取：

```text
app/agent/tools/job_tools.py
```

发现直接：

```text
import SQLAlchemy Session
import Repository
```

因此：

```text
Tool与Repository解耦
```

实际上没有满足。

最终新增：

```text
JobQueryPort
RepositoryJobQueryAdapter
```

经验：

> “测试通过”不等于“架构验收通过”，必须检查真实依赖关系。

---

## 20.6 CRLF/LF警告继续出现

Git add时仍出现：

```text
CRLF will be replaced by LF
```

按照项目既有原则：

```powershell
git diff --cached --check
```

无输出即可继续。

没有为了非阻塞换行提示额外消耗开发精力。

---

# 21. 面试可能提问

## 1. 阶段7主要完成了什么？

参考回答：

> 阶段7我在现有FastAPI和SQLite后端之上实现了一个最小Tool-Calling Agent Layer，包括统一Agent Contract、AgentState、BaseTool、ToolRegistry、ModelClient抽象、FakeModelClient和AgentOrchestrator。Orchestrator能够完成Model→ToolCall→ToolResult/Observation→下一轮Model→FinalAnswer闭环，并支持多轮顺序Tool Calling、失败Observation、Unknown Tool和max_steps保护。后续还用JobQueryPort和RepositoryJobQueryAdapter把Job Tool与Repository和SQLAlchemy解耦，最终184个测试通过。

---

## 2. 什么是Tool-Calling Agent？

参考回答：

> 普通LLM只生成文本，而Tool-Calling Agent可以根据用户目标决定调用外部能力，比如搜索岗位。Tool执行以后把结果作为Observation返回给模型，模型再决定继续调用工具还是生成最终答案。

---

## 3. AgentOrchestrator负责什么？

参考回答：

> 它只负责Agent Runtime，包括创建单次运行State、调用ModelClient、分发ToolCall、记录ToolExecution、处理Observation、判断FinalAnswer和执行max_steps保护。它不直接做数据库查询，也不依赖FastAPI。

---

## 4. 为什么AgentOrchestrator不能直接访问Repository？

参考回答：

> Orchestrator的职责是控制Agent运行流程，如果它直接查询数据库，就会把Runtime和业务基础设施耦合。当前数据库能力通过Tool暴露，Orchestrator只处理统一Tool Contract。

---

## 5. ToolDefinition是什么？

参考回答：

> ToolDefinition是模型侧看到的工具定义，包含name、description和parameters。parameters由Pydantic Schema生成，模型因此能够知道Tool支持哪些输入字段和约束。

---

## 6. ToolCall和ToolResult有什么区别？

参考回答：

> ToolCall表示模型希望执行哪个Tool和使用什么参数；ToolResult表示Tool真正执行之后产生的Observation，包括success、data和error。

---

## 7. 为什么需要ToolExecution？

参考回答：

> ToolExecution把一条ToolCall和对应ToolResult绑定起来，形成完整Trace，同时校验call_id和tool_name一致，防止不同调用的结果被错误关联。

---

## 8. Tool Failure为什么不直接抛异常结束Agent？

参考回答：

> 模型可能给错参数，这种错误通常可以在下一轮修正。所以BaseTool把ValidationError或内部Tool失败转换成ToolResult(success=False)，让Orchestrator把失败结果作为Observation传给模型，而不是直接结束整个Agent。

---

## 9. Unknown Tool怎么处理？

参考回答：

> Registry查找未知Tool时会抛KeyError，Orchestrator捕获后转成`Tool is not available.`的失败ToolResult，再进入下一轮Model决策，所以模型选错Tool不会直接让Agent崩溃。

---

## 10. 什么是Agent Observation？

参考回答：

> Observation就是Agent执行Tool后获得的结果，包括成功数据或失败信息。下一轮ModelRequest会携带之前的ToolExecution，让模型根据实际执行反馈调整下一步策略。

---

## 11. max_steps解决什么问题？

参考回答：

> Agent可能不断在Model和Tool之间循环。max_steps给一次Run设置最大Model调用次数，超过后抛AgentMaxStepsExceeded，防止无限循环和失控消耗。

---

## 12. 为什么max_steps必须在generate之前检查？

参考回答：

> 如果generate以后才检查，可能已经多调用了一次Model。当前在下一次generate之前比较step_count和max_steps，因此能严格保证调用次数上限，没有off-by-one。

---

## 13. 为什么ModelClient要抽象？

参考回答：

> Agent Runtime不应该绑定OpenAI、Gemini或Claude。通过ModelClient统一`generate(ModelRequest) -> ModelResponse`，Orchestrator只依赖接口，未来新增真实Provider时不需要重写Agent Loop。

---

## 14. 为什么使用FakeModelClient？

参考回答：

> Agent Loop测试需要确定性，比如第一轮必须返回ToolCall、第二轮返回FinalAnswer。真实LLM输出不稳定、依赖网络而且有费用，所以使用FakeModelClient按预设顺序返回Response，并记录Request用于断言。

---

## 15. AgentState保存什么？

参考回答：

> 保存user_message、step_count、tool_executions和final_answer，只用于一次Agent Run的Runtime状态。

---

## 16. 为什么AgentState不能直接作为Memory？

参考回答：

> 当前State只服务一次run，生命周期非常短。长期Memory涉及跨请求持久化、检索和上下文管理，是后续独立能力，Stage 7没有把两者混在一起。

---

## 17. 为什么不能使用self.state？

参考回答：

> 如果Orchestrator被重复使用，self.state可能导致第二次run继承第一次的step_count和ToolExecution。当前每次run都创建新的局部AgentState，并有专门多run测试保证隔离。

---

## 18. Tool和Repository为什么要解耦？

参考回答：

> Tool属于Agent层，如果它直接持有SQLAlchemy Session并调用Repository，Agent层就绑定了数据库基础设施。最终我增加JobQueryPort，让Tool只依赖岗位查询能力，再用RepositoryJobQueryAdapter连接实际Repository。

---

## 19. JobQueryPort是什么？

参考回答：

> 它是Agent侧定义的只读岗位查询Contract，只表达search_jobs和get_job_by_id这两种能力，不关心这些数据来自SQLite、HTTP API还是Fake。

---

## 20. 为什么JobQueryPort不返回JobModel？

参考回答：

> JobModel是SQLAlchemy ORM类型，如果Port返回JobModel，Agent仍然间接依赖数据库模型。因此Adapter把JobModel转换成JobRead后再返回，Agent层不会看到ORM实现。

---

## 21. RepositoryJobQueryAdapter做什么？

参考回答：

> 它实现JobQueryPort，内部调用原有Repository，并把Repository返回的JobModel转换成JobRead。它是Agent Contract和数据库基础设施之间的边界适配器。

---

## 22. 为什么没有增加完整Service Layer？

参考回答：

> 当前实际问题只有Tool直接依赖Repository，使用一个很薄的Port/Adapter已经能解决。如果额外增加Generic Repository、Service、Unit of Work或DI Framework会扩大Stage范围，属于过度设计。

---

## 23. 为什么禁止未知Tool参数？

参考回答：

> 模型可能把city拼成ctiy。如果Pydantic忽略未知字段，Tool可能静默执行成无城市条件查询，返回误导性结果。所以参数模型使用extra="forbid"，未知字段会变成失败Observation，让模型修正。

---

## 24. 为什么`min_length=1`不能阻止空白FinalAnswer？

参考回答：

> `"   "`虽然语义为空，但字符长度大于1。所以FinalAnswerResponse还需要strip校验，确保纯空白答案不能作为有效FinalAnswer终止Agent。

---

## 25. 为什么空白FinalAnswer校验放Contract层？

参考回答：

> “什么才算有效FinalAnswer”属于数据契约，而不是Agent Runtime控制逻辑。放Contract可以让所有创建FinalAnswerResponse的代码统一遵守约束。

---

## 26. Stage 7为什么不接真实LLM？

参考回答：

> Stage 7先验证Agent Runtime本身。如果同时接真实Provider，会混入网络、认证和Provider协议问题。当前用ModelClient抽象和FakeModelClient把Runtime稳定下来，再把真实Provider留给后续阶段。

---

## 27. 你如何测试多轮Tool Calling？

参考回答：

> FakeModelClient依次返回ToolCall 1、ToolCall 2和FinalAnswer。测试验证Tool执行顺序、ToolExecution保存顺序以及后续ModelRequest中包含之前的Observation。

---

## 28. 你如何测试Tool失败后的恢复？

参考回答：

> 第一轮返回一个无法通过Pydantic验证的ToolCall，BaseTool生成失败ToolResult；第二轮ModelRequest包含这个失败Observation，然后Fake返回修正后的ToolCall，最终执行成功并生成FinalAnswer。

---

## 29. Stage 7最终测试结果是多少？

参考回答：

> 最终全项目184 passed、1 warning，其中Agent Layer是70 passed。Stage 7D Orchestrator targeted是15 passed，Tool和Adapter targeted是14 passed，最终Hardening targeted是49 passed。

---

## 30. Codex最终审查结果是什么？

参考回答：

> 必须修改为无，可以进入Stage 7最终收尾。Codex另外提出未知Tool参数、空白FinalAnswer和多run隔离三个低风险建议，我在收尾前全部处理并补了测试。

---

# 22. 一分钟阶段介绍

> 阶段7我在InternScout已有FastAPI、SQLite和岗位查询能力之上实现了一个最小可测试的Tool-Calling Agent Layer。我先定义了ToolDefinition、ToolCall、ToolResult、ModelRequest和FinalAnswer等统一Contract，再实现AgentState、BaseTool、ToolRegistry和ModelClient抽象。核心的AgentOrchestrator能够完成Model→ToolCall→ToolResult/Observation→下一轮Model→FinalAnswer的多轮闭环，并通过max_steps防止无限循环。Tool参数错误、内部失败以及Unknown Tool都不会直接让Agent崩溃，而是转换成Observation让模型继续决策。后续Reality Check发现Job Tool仍直接依赖Repository和SQLAlchemy，因此增加JobQueryPort和RepositoryJobQueryAdapter实现依赖反转。最终Codex审查没有必须修改项，并把未知参数、空白FinalAnswer和多run隔离三个建议全部加固，全项目184个测试通过，只有1个既有的Starlette弃用警告。

---

# 23. 当前技术债与阶段边界

Stage 7明确不继续实现：

- 真实OpenAI Provider
- 真实Gemini Provider
- 真实Claude Provider
- Agent HTTP API Endpoint
- Retry
- Memory
- RAG
- Parallel Tool Calling
- Streaming
- Agent Trace持久化
- Token统计
- Cost统计
- 多Agent
- 长期Conversation State
- 复杂Reliability机制
- Starlette TestClient/httpx既有弃用warning

这些属于：

```text
后续Stage
Provider Integration
Reliability
Memory / RAG
工程增强
```

而不是Stage 7阻塞项。

Stage 8具体规划：

```text
UNKNOWN
```

Stage 7正式合并完成后再规划。

---

# 24. 阶段7验收清单

## Agent Contract

- [x] ToolDefinition
- [x] ToolCall
- [x] ToolResult
- [x] ToolExecution
- [x] ModelRequest
- [x] ToolCallResponse
- [x] FinalAnswerResponse
- [x] AgentResult
- [x] ToolExecution校验call_id一致
- [x] ToolExecution校验tool_name一致
- [x] ToolResult成功状态约束
- [x] ToolResult失败状态约束
- [x] FinalAnswer拒绝纯空白

## Agent State

- [x] user_message
- [x] step_count
- [x] tool_executions
- [x] final_answer
- [x] 每次run创建独立State
- [x] 不使用self.state保存单次Runtime
- [x] 多run状态隔离测试

## Tool System

- [x] BaseTool
- [x] ToolDefinition自动生成
- [x] Pydantic参数验证
- [x] Tool Name一致性检查
- [x] ValidationError转换ToolResult
- [x] Tool内部异常转换ToolResult
- [x] Tool错误不泄漏底层异常
- [x] Tool未知参数禁止
- [x] ToolRegistry
- [x] Tool重复注册拒绝
- [x] Unknown Tool查找
- [x] 注册顺序保持
- [x] Definition顺序保持

## Job Tools

- [x] SearchJobsTool
- [x] GetJobDetailTool
- [x] 城市筛选参数
- [x] 公司筛选参数
- [x] 技能筛选参数
- [x] 分页
- [x] 空白筛选拒绝
- [x] 非法page拒绝
- [x] 非法page_size拒绝
- [x] 非法job_id拒绝
- [x] 未知参数拒绝
- [x] 空查询结果
- [x] 高页码空结果
- [x] 岗位不存在返回None

## Architecture

- [x] AgentOrchestrator与FastAPI解耦
- [x] AgentOrchestrator与Database解耦
- [x] ModelClient与Repository解耦
- [x] ModelClient与具体Tool解耦
- [x] Tool与Repository解耦
- [x] Tool与SQLAlchemy Session解耦
- [x] JobQueryPort
- [x] RepositoryJobQueryAdapter
- [x] Agent侧不消费JobModel
- [x] Repository不反向依赖Agent Runtime

## Model

- [x] ModelClient abstraction
- [x] FakeModelClient
- [x] Fake Response顺序
- [x] Request snapshot
- [x] Response copy保护
- [x] Response exhaustion
- [x] Stage 7不接真实LLM

## Agent Loop

- [x] Direct FinalAnswer
- [x] Tool → FinalAnswer
- [x] Multiple Sequential Tools
- [x] Tool Failure Observation
- [x] Tool参数修正
- [x] Tool内部失败Observation
- [x] Unknown Tool Observation
- [x] FinalAnswer正常终止
- [x] ModelClient异常传播
- [x] Invalid Model Response保护
- [x] max_steps保护
- [x] max_steps不额外调用Model
- [x] 空白user_message拒绝
- [x] user_message trim
- [x] 多run状态隔离

## Testing

- [x] Stage 7D targeted：15 passed
- [x] Tool / Adapter targeted：14 passed
- [x] Tool解耦后Agent Layer：66 passed
- [x] Tool解耦后Full Project：180 passed, 1 warning
- [x] Final Hardening targeted：49 passed
- [x] Final Agent Layer：70 passed
- [x] Final Full Project：184 passed, 1 warning
- [x] warning没有增加
- [x] git diff --cached --check通过

## Code Review

- [x] Stage 7 State Recovery完成
- [x] Repo Reality Check完成
- [x] Handoff与真实代码重新核对
- [x] 发现Tool→Repository架构gap
- [x] 完成Port / Adapter解耦
- [x] Codex最终必须修改为无
- [x] Codex允许进入最终收尾
- [x] 3项非阻塞建议全部处理

---

# 25. 自测题

请尝试不看前文回答：

1. Stage 7相比Stage 6最大的变化是什么？
2. 什么是Tool-Calling Agent？
3. AgentOrchestrator的核心职责是什么？
4. 为什么Orchestrator不能直接访问Repository？
5. ToolDefinition包含哪些字段？
6. ToolCall表示什么？
7. ToolResult表示什么？
8. ToolExecution为什么需要同时包含Call和Result？
9. 为什么需要call_id？
10. ToolExecution为什么要检查tool_name一致？
11. ToolResult为什么需要success？
12. successful ToolResult为什么不能带error？
13. failed ToolResult为什么必须带error？
14. ModelRequest包含哪些核心数据？
15. tool_executions为什么需要传给下一轮Model？
16. ModelResponse当前分为哪两类？
17. AgentState保存哪些数据？
18. AgentState和Memory有什么区别？
19. 为什么不能把一次run的State保存在self.state？
20. BaseTool.execute主要完成哪些工作？
21. Pydantic ValidationError为什么不直接结束Agent？
22. Tool内部异常为什么要隐藏具体错误？
23. ToolRegistry负责什么？
24. 重复Tool为什么应该拒绝？
25. Unknown Tool为什么由Orchestrator转换Observation？
26. SearchJobsTool支持哪些参数？
27. GetJobDetailTool的job_id有什么约束？
28. 岗位不存在为什么是success=True？
29. 为什么Tool参数要设置extra="forbid"？
30. `ctiy`被静默忽略会产生什么问题？
31. 原Job Tool为什么没有真正和Repository解耦？
32. 什么是JobQueryPort？
33. JobQueryPort为什么属于Agent Layer？
34. JobQueryPort为什么不能返回JobModel？
35. RepositoryJobQueryAdapter做什么？
36. 为什么Adapter放在Database Layer？
37. 为什么没有增加完整Service Layer？
38. ModelClient为什么需要抽象？
39. Stage 7为什么没有直接接OpenAI？
40. FakeModelClient为什么适合Agent Unit Test？
41. AgentOrchestrator完整循环是什么？
42. Direct FinalAnswer流程是什么？
43. ToolCall流程是什么？
44. Tool Failure为什么不等于Agent Failure？
45. Observation在Agent系统中的作用是什么？
46. Unknown Tool如何恢复？
47. max_steps解决什么问题？
48. max_steps限制的是Tool调用数还是Model调用数？
49. 为什么max_steps必须在generate之前检查？
50. 如何验证没有off-by-one？
51. FinalAnswer如何让Agent Loop结束？
52. 为什么`min_length=1`仍然允许空白字符串？
53. 如何拒绝纯空白FinalAnswer？
54. 为什么这个校验放Contract层？
55. 如何测试同一Orchestrator两次run之间不污染？
56. Stage 7D targeted有多少测试？
57. Tool / Adapter targeted有多少测试？
58. Final Hardening targeted有多少测试？
59. 最终Agent Layer有多少测试？
60. 最终全项目测试基线是多少？
61. 当前唯一warning是什么类型？
62. Codex最终审查有多少必须修改？
63. Codex提出的3个建议分别是什么？
64. 为什么这3个建议都在Stage 7收尾前处理了？
65. Stage 7明确不实现哪些能力？
66. 为什么Retry不属于Stage 7？
67. 为什么Memory不属于Stage 7？
68. 为什么RAG不属于Stage 7？
69. 为什么Parallel Tool Calling不属于Stage 7？
70. Repo Reality Check为什么重要？
71. 为什么Repository Reality优先于Handoff？
72. Stage 7迁移新Chat时为什么先做State Recovery？
73. `CreateProcessAsUserW failed: 5`为什么不是pytest失败？
74. 本机没有rg时使用了什么替代命令？
75. Stage 7最大的架构收益是什么？

---

## 阶段7总结

阶段7是InternScout Agent从：

```text
拥有稳定后端能力
```

进一步进入：

```text
拥有真正Agent Runtime
```

的重要阶段。

阶段6已经解决：

```text
岗位从哪里来
岗位如何清洗
岗位如何去重
岗位如何保存
岗位如何通过HTTP查询
```

阶段7进一步解决：

```text
模型如何表达Tool调用
Tool如何统一执行
参数如何验证
错误如何转换Observation
Observation如何返回模型
模型如何继续决策
Agent如何安全终止
Agent如何避免无限循环
Runtime如何与模型Provider解耦
Tool如何与Repository解耦
不同Agent Run如何保持状态隔离
```

最终项目从：

```text
Crawler
+
Cleaning
+
Deduplication
+
Persistence
+
FastAPI
```

升级成：

```text
Crawler
+
Cleaning
+
Deduplication
+
Persistence
+
FastAPI
+
Agent Contracts
+
Tool System
+
Model Abstraction
+
AgentOrchestrator
+
Tool-Calling Execution Loop
+
Port / Adapter Architecture
+
Automated Agent Testing
```

Stage 7没有急于连接真实LLM，而是先稳定：

```text
Contract
↓
State
↓
Tool
↓
Model Abstraction
↓
Orchestrator
↓
Observation Loop
↓
Safety Boundary
```

同时通过：

```text
JobQueryPort
+
RepositoryJobQueryAdapter
```

解决Agent Tool对SQLAlchemy和Repository的直接依赖。

最终：

```text
184 passed, 1 warning
```

Codex最终：

```text
必须修改：无
```

并且3个非阻塞Hardening建议：

```text
未知Tool参数禁止
纯空白FinalAnswer拒绝
多run状态隔离测试
```

均已完成。

一句话总结：

> 阶段7把InternScout Agent从一个稳定的岗位采集与查询后端，推进成了一个拥有统一Agent Contract、Tool System、模型抽象、可控执行循环、失败Observation、max_steps安全保护和清晰依赖边界的最小Tool-Calling Agent Runtime。