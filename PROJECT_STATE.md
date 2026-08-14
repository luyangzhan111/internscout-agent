# InternScout Agent — Project State

> 本文件是 InternScout Agent 当前状态的唯一项目快照（Project Snapshot）。
>
> 它不是开发日志，也不记录完整 Debug 过程。
>
> 本文件只维护当前仍然有效的：
>
> - 项目能力
> - 系统架构
> - 技术决策
> - 测试状态
> - 已知问题
> - 下一阶段目标
> - 长期开发规范
>
> 每完成一个主要 Stage 后更新一次。

---

# 1. Project Overview

## 项目名称

InternScout Agent

## 项目定位

InternScout Agent 是一个面向软件工程、AI 与 Agent 实习岗位的信息采集、处理、存储、查询，并逐步扩展智能分析能力的练习型软件工程项目。

当前项目已经从基础 FastAPI 服务逐步实现：

- 岗位数据模型
- 招聘信息爬取
- 数据清洗与标准化
- 岗位去重
- SQLite 持久化
- Repository 查询
- REST API
- 筛选与分页
- HTTP 服务闭环
- 自动化测试
- Agent Contract
- Tool System
- Model Client Abstraction
- Tool-Calling Agent Runtime
- AgentOrchestrator
- Tool / Repository 架构解耦

项目同时承担以下学习目标：

- Python 工程实践
- FastAPI
- Pydantic
- Web Crawling
- BeautifulSoup
- SQLAlchemy 2.x
- SQLite
- Repository Pattern
- Port / Adapter Pattern
- pytest
- Unit Testing
- Integration Testing
- Git / GitHub / Pull Request Workflow
- Codex Code Review
- Agent Development
- Tool Calling
- 软件工程与 AI / Agent 岗位面试准备

---

# 2. Core Technology Stack

当前主要技术栈：

- Python 3.12
- FastAPI
- Pydantic
- BeautifulSoup
- SQLAlchemy 2.x
- SQLite
- pytest
- Git
- GitHub
- Codex
- VS Code

开发环境：

- Windows
- PowerShell
- Python Virtual Environment (`.venv`)

---

# 3. Current Version Identity

## 当前主分支

```text
main
```

## Stage 7 Merge Identity

```text
5c5f528
```

对应：

```text
Merge pull request #7 from luyangzhan111/feat/stage-07-agent-layer
```

Stage 7 功能分支：

```text
feat/stage-07-agent-layer
```

已成功合并至：

```text
main
```

## Snapshot Basis

本 Project State 基于 Stage 7 合并后的真实 main 状态：

```text
Branch:
main

Stage 7 merge commit:
5c5f528

Working tree before PROJECT_STATE update:
clean

Full regression:
184 passed, 1 warning
```

`5c5f528` 表示 Stage 7 合并进入 main 的版本身份，不表示后续仅更新 PROJECT_STATE.md 产生的文档提交。

---

# 4. Current Stage

## 已完成阶段

```text
Stage 0 ～ Stage 7
```

## 当前状态

Stage 7：

**已完成、通过最终代码审查、通过完整回归测试，并已合并至 main。**

Stage 7 最终完成：

- Agent Contract
- Agent State
- Agent Exception
- BaseTool
- ToolRegistry
- SearchJobsTool
- GetJobDetailTool
- ModelClient Abstraction
- FakeModelClient
- AgentOrchestrator
- Tool-Calling Execution Loop
- Sequential Tool Calling
- Tool Failure Observation
- Unknown Tool Observation
- FinalAnswer Termination
- max_steps Protection
- Agent Run State Isolation
- JobQueryPort
- RepositoryJobQueryAdapter
- Tool / Repository Decoupling
- Final Hardening
- Stage 7 自动化测试
- Codex 最终只读代码审查
- `docs/stage-reviews/stage-07-review.md`
- `docs/development-log.md` Stage 7 更新

## 下一阶段

```text
Stage 8
```

Stage 8 的具体目标：

```text
UNKNOWN
```

Stage 8 必须在独立阶段规划中确定；当前文件不提前设计 Stage 8。

---

# 5. Implemented Backend Capabilities

## 5.1 FastAPI Application

当前 HTTP API：

```text
GET  /
GET  /api/health
POST /api/crawl
GET  /api/jobs
GET  /api/jobs/{job_id}
```

当前 HTTP 服务能够：

- 检查服务状态
- 检查数据库状态
- 触发模拟岗位采集
- 查询岗位列表
- 按城市筛选
- 按公司筛选
- 按技能筛选
- 组合筛选
- 分页
- 查询岗位详情

## 5.2 Job Data Model

岗位核心数据使用 Pydantic 模型进行验证。

主要岗位字段：

- title
- company
- city
- salary
- description
- skills
- source
- source_url
- published_at

数据库读取接口使用：

```text
JobRead
```

列表响应使用：

```text
JobListResponse
```

数据库内部：

```text
identity_key
```

不会通过 JobRead 暴露给 API 或 Agent Tool。

## 5.3 Crawling

当前实现：

```text
BaseJobCrawler
MockJobCrawler
```

MockJobCrawler 从：

```text
app/fixtures/sample_jobs.html
```

读取模拟招聘页面。

支持解析：

- 岗位名称
- 公司
- 城市
- 薪资
- 描述
- 技能
- 岗位链接
- 发布日期

当前数据源仍然是 Mock HTML，尚未接入真实招聘网站。

## 5.4 Data Cleaning

当前数据清洗能力包括：

- 城市标准化
- 公司名称标准化
- 技能名称标准化
- 空白技能删除
- 重复技能删除
- 保持技能原始顺序

城市标准化使用受控别名映射，不使用“删除所有城市名末尾市字”的不安全规则。

公司名称写入与查询使用相同的标准化规则。

## 5.5 Deduplication

业务层：

```text
process_jobs
```

执行：

```text
Cleaning
→ Deduplication
```

数据库层使用：

```text
identity_key
```

并有唯一约束。

当前重复保护包括：

```text
输入列表业务去重
+
Repository 保存前检查
+
数据库 identity_key 唯一约束
```

## 5.6 Database Persistence

当前使用：

```text
SQLAlchemy 2.x
+
SQLite
```

数据库 ORM：

```text
JobModel
```

Repository 当前负责：

- 保存单个岗位
- 批量保存岗位
- 根据岗位身份查询
- 根据数据库 ID 查询岗位
- 岗位筛选
- 岗位分页
- total 统计

技能字段使用 JSON 存储。

## 5.7 Job Query

当前 Repository 支持：

```text
city
company
skill
page
page_size
```

岗位查询支持：

- 城市精确筛选
- 公司精确筛选
- 技能完整元素匹配
- 多条件组合
- total
- pagination
- 空结果
- 超页查询
- 极大合法页码保护

技能查询使用 SQLite：

```text
json_each
```

避免 `SQL` 错误匹配 `NoSQL`。

## 5.8 FastAPI Lifespan

FastAPI 启动阶段使用 lifespan 初始化数据库：

```text
FastAPI startup
→ lifespan
→ init_database
→ create missing tables
→ accept HTTP requests
```

当前 `create_all()` 只负责创建不存在的表，不是正式数据库 Migration 工具。

## 5.9 Health Check

当前：

```text
GET /api/health
```

执行真实：

```text
SELECT 1
```

数据库正常返回 HTTP 200，数据库不可用返回 HTTP 503，并避免向客户端泄漏底层数据库异常。

## 5.10 Crawl Workflow

当前岗位入库流程：

```text
sample_jobs.html
↓
MockJobCrawler
↓
JobCreate
↓
process_jobs
↓
Cleaning
↓
Deduplication
↓
ingest_jobs
↓
Repository
↓
SQLAlchemy
↓
SQLite
```

`POST /api/crawl` 复用 `ingest_jobs`，不会在 Route 中重复实现采集和数据库逻辑。

重复执行 crawl 不会重复增加相同岗位。

---

# 6. Agent Layer

Stage 7 新增：

```text
app/agent/
```

Agent Layer 当前具备最小 Tool-Calling Runtime。

目标执行闭环：

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

---

# 7. Agent Contracts

文件：

```text
app/agent/contracts.py
```

当前 Contract：

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

这些 Contract 是 provider-neutral，不绑定某个真实 LLM Provider。

## 7.1 ToolDefinition

描述：

```text
name
description
parameters
```

用于告诉 Model：

- 有哪些 Tool
- Tool 的用途
- Tool 接受什么参数
- 参数 Schema 是什么

## 7.2 ToolCall

表示 Model 决定调用某个 Tool。

主要字段：

```text
call_id
tool_name
arguments
```

## 7.3 ToolResult

表示 Tool 执行产生的 Observation。

主要字段：

```text
call_id
tool_name
success
data
error
```

Contract 保证：

```text
success=True
→ 不允许存在 error

success=False
→ 必须存在有效 error
```

## 7.4 ToolExecution

表示：

```text
ToolCall
+
ToolResult
```

并保证：

```text
call_id 一致
tool_name 一致
```

用于形成 Agent Execution Trace。

---

# 8. Agent State

文件：

```text
app/agent/state.py
```

`AgentState` 保存：

```text
user_message
step_count
tool_executions
final_answer
```

AgentState 只存在于单次 Agent Run。

当前不会：

- 保存到数据库
- 作为长期 Memory
- 跨请求共享
- 保存在 `self.state`

每次 `AgentOrchestrator.run()` 都创建新的局部 AgentState。

---

# 9. Tool System

## 9.1 BaseTool

文件：

```text
app/agent/tools/base.py
```

BaseTool 统一负责：

```text
Tool Definition
Tool 参数验证
Tool 执行
异常转换
ToolResult 生成
```

参数错误：

```text
ValidationError
→ ToolResult(success=False)
```

Tool 内部异常：

```text
Exception
→ ToolResult(
    success=False,
    error="Tool execution failed."
)
```

底层实现细节不会直接泄漏给 Model。

## 9.2 ToolRegistry

文件：

```text
app/agent/tools/registry.py
```

当前支持：

```text
register()
get()
list_tools()
list_definitions()
```

规则：

- Tool name 必须唯一
- 重复注册拒绝
- Unknown Tool 查询抛 KeyError
- 保持注册顺序
- 保持 Definition 顺序

Unknown Tool 的 Runtime 行为由 AgentOrchestrator 负责。

## 9.3 Current Job Tools

当前 Tool：

```text
SearchJobsTool
GetJobDetailTool
```

SearchJobsTool 支持：

```text
city
company
skill
page
page_size
```

GetJobDetailTool 支持：

```text
job_id
```

岗位不存在时：

```text
success=True
data=None
```

因为“没有找到资源”属于合法查询结果，而不是 Tool 执行异常。

## 9.4 Unknown Tool Arguments

Tool 参数模型使用：

```text
extra="forbid"
```

例如：

```text
ctiy="深圳"
```

不会被静默忽略，而会：

```text
ValidationError
→ ToolResult(success=False)
→ Observation
```

避免参数拼写错误导致错误的宽泛查询。

---

# 10. Tool / Repository Architecture Boundary

Stage 7 最终建立：

```text
JobQueryPort
RepositoryJobQueryAdapter
```

Agent Tool 当前依赖：

```text
JobQueryPort
```

而不是直接依赖：

```text
SQLAlchemy Session
Repository
JobModel
```

最终关系：

```text
SearchJobsTool / GetJobDetailTool
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

## 10.1 JobQueryPort

文件：

```text
app/agent/tools/job_query.py
```

提供：

```text
search_jobs(...)
get_job_by_id(...)
```

Port 描述 Agent Tool 所需要的岗位查询能力，不描述数据库具体实现。

## 10.2 RepositoryJobQueryAdapter

文件：

```text
app/database/job_query_adapter.py
```

Adapter 负责：

```text
调用现有 Repository
↓
获得数据库记录
↓
转换为 JobRead
↓
返回 Agent Tool
```

它是 Agent Query Contract 与 Database Infrastructure 之间的边界组件。

## 10.3 Dependency Rule

当前冻结：

```text
Agent Tool
不得直接依赖 Repository
```

```text
Agent Tool
不得直接依赖 SQLAlchemy Session
```

```text
Agent Layer
不得使用 JobModel 作为岗位查询返回 Contract
```

---

# 11. Model Client Abstraction

文件：

```text
app/agent/model_client.py
```

当前：

```text
ModelClient
```

接口：

```text
generate(ModelRequest)
→ ModelResponse
```

AgentOrchestrator 不关心真实 Provider。

Stage 7 没有接入真实 LLM。

## 11.1 FakeModelClient

测试使用：

```text
tests/agent/fakes/fake_model_client.py
```

FakeModelClient 用于：

- 预设 ModelResponse
- 控制响应顺序
- 保存 ModelRequest
- 测试多轮 Agent 执行
- 验证 max_steps
- 验证 Observation

Agent Runtime Unit Test 不依赖真实网络或 LLM。

---

# 12. AgentOrchestrator

文件：

```text
app/agent/orchestrator.py
```

AgentOrchestrator 只负责 Agent Runtime。

核心流程：

```text
normalize user_message
↓
create AgentState
↓
check max_steps
↓
build ModelRequest
↓
ModelClient.generate()
↓
increment step_count
↓
handle ModelResponse
```

## 12.1 Direct FinalAnswer

如果 Model 返回 `FinalAnswerResponse`：

```text
set final_answer
→ build AgentResult
→ terminate run
```

## 12.2 ToolCall

如果 Model 返回 `ToolCallResponse`：

```text
ToolRegistry
↓
Tool execution
↓
ToolResult
↓
ToolExecution
↓
AgentState
↓
Next ModelRequest
```

## 12.3 Sequential Tool Calling

Stage 7 当前只支持：

```text
Sequential Tool Calling
```

例如：

```text
Model
→ Tool A
→ Observation A
→ Model
→ Tool B
→ Observation B
→ Model
→ FinalAnswer
```

Stage 7 不支持 Parallel Tool Calling。

## 12.4 Tool Failure Observation

冻结原则：

```text
Tool Failure ≠ Agent Failure
```

Tool 参数错误或 Tool 内部错误都会转成失败 ToolResult，作为 Observation 进入下一轮 Model Decision。

## 12.5 Unknown Tool Observation

如果 Model 请求不存在的 Tool：

```text
ToolRegistry KeyError
```

Orchestrator 转换为：

```text
ToolResult(
    success=False,
    error="Tool is not available."
)
```

然后进入下一轮 Model Decision。

## 12.6 FinalAnswer Protection

FinalAnswerResponse 不允许：

```text
""
```

也不允许：

```text
"   "
```

纯空白 FinalAnswer 会在 Contract 层被拒绝。

## 12.7 max_steps

`max_steps` 限制：

```text
单次 Agent Run 的 Model 调用次数
```

检查顺序：

```text
check step_count >= max_steps
↓
Model.generate()
```

必须在下一次 `Model.generate()` 前检查，避免 off-by-one 和额外 Model 调用。

## 12.8 Run Isolation

同一个 AgentOrchestrator 可以重复调用 `run()`。

不同 Run 不共享：

- step_count
- ToolExecution
- final_answer

每次 Run 创建独立 AgentState。

---

# 13. Current Architecture

Backend：

```text
                    HTTP Client
                         ↓
                      FastAPI
                         ↓
         ┌───────────────┼────────────────┐
         ↓               ↓                ↓
     Health API       Crawl API        Jobs API
         ↓               ↓                ↓
     SELECT 1        ingest_jobs       Repository
                         ↓                ↓
                    MockCrawler        SQLAlchemy
                         ↓                ↓
                     JobCreate         SQLite
                         ↓
                    process_jobs
                         ↓
                 Cleaning + Dedup
```

Agent Layer：

```text
                     User Goal
                         ↓
                  AgentOrchestrator
                         ↓
                    ModelClient
                         ↓
                   ModelResponse
                ┌────────┴─────────┐
                ↓                  ↓
          ToolCallResponse   FinalAnswerResponse
                ↓                  ↓
           ToolRegistry        AgentResult
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

---

# 14. Architecture Boundaries

## FastAPI

FastAPI Route 负责：

```text
HTTP 输入
HTTP 输出
依赖获取
状态码
```

不重新实现：

```text
Crawler
Cleaning
Deduplication
Repository 逻辑
Agent Runtime
```

## Repository

Repository 负责：

```text
Database Read / Write
Query
Pagination
Persistence
```

不负责：

```text
HTTP
Agent Runtime
Model Decision
```

## AgentOrchestrator

AgentOrchestrator 负责：

```text
Agent Execution Control
```

不得直接负责：

```text
FastAPI
Repository
SQLAlchemy
Crawler
```

## ModelClient

ModelClient 不得直接访问：

```text
Repository
Database
Job Service
```

## Job Tools

Job Tool 只依赖：

```text
JobQueryPort
```

不得直接依赖：

```text
Repository
SQLAlchemy Session
```

---

# 15. Frozen Stage 7 Decisions

以下决策已经确定，后续不应在没有新需求的情况下重新设计。

## Orchestration

使用：

```text
AgentOrchestrator
```

不因为“架构更完整”随意改成：

```text
AgentService
Controller
Generic Chain
```

## Model

Stage 7 只建立：

```text
ModelClient abstraction
+
FakeModelClient
```

不接真实 LLM。

## Tool Failure

Tool Failure 不是 Agent fatal error，而是：

```text
ToolResult(success=False)
→ Observation
```

## Unknown Tool

Unknown Tool 不得直接导致 Agent 崩溃，必须转换为失败 Observation。

## max_steps

max_steps 限制 Model 调用次数，并在下一次 `Model.generate()` 之前检查。

## Tool Calling

Stage 7：

```text
Sequential only
```

不实现 Parallel Tool Calling。

## Agent State

AgentState：

```text
不持久化
不跨 Run 共享
不保存在 self.state
```

## Database Boundary

Job Tool 不得直接访问 Repository / SQLAlchemy。

使用：

```text
JobQueryPort
+
RepositoryJobQueryAdapter
```

---

# 16. Automated Testing

当前完整测试基线：

```text
184 passed, 1 warning
```

Stage 7 合并至 main 后重新执行：

```powershell
python -m pytest -q
```

结果：

```text
184 passed, 1 warning in 8.87s
```

## 16.1 Agent Layer Tests

当前：

```text
tests/agent
→ 70 passed
```

## 16.2 Stage 7 Key Test Baselines

Stage 7D targeted：

```text
15 passed
```

Tool / Adapter targeted：

```text
14 passed
```

Final Hardening targeted：

```text
49 passed
```

Agent Layer：

```text
70 passed
```

Full Project：

```text
184 passed, 1 warning
```

## 16.3 Current Warning

当前唯一已知 warning：

```text
StarletteDeprecationWarning
```

来源：

```text
fastapi.testclient
/
starlette.testclient
/
httpx
```

当前提示：

```text
Using `httpx` with `starlette.testclient` is deprecated;
install `httpx2` instead.
```

该 warning：

- Stage 7 之前已经存在
- Stage 7 没有新增 warning
- 当前不影响项目测试通过
- 不属于 Stage 7 阻塞项

---

# 17. Code Review Status

Stage 7 最终 Codex 只读代码审查：

```text
必须修改：
无
```

最终结论：

```text
可以进入 Stage 7 最终收尾
```

Codex确认：

- Agent Runtime 边界清晰
- 每次 run 使用独立 AgentState
- ModelClient 不依赖数据库层
- Job Tool 只依赖 JobQueryPort
- Repository 和 SQLAlchemy 被限制在 Adapter 边界
- Tool Failure 正确进入 Observation
- Unknown Tool 正确进入 Observation
- FinalAnswer 正确终止
- max_steps 没有 off-by-one
- 未发现额外 Model 调用

Codex提出的3项非阻塞建议：

```text
Tool 未知参数禁止
FinalAnswer 空白保护
Orchestrator 多 Run 隔离测试
```

已经全部处理。

---

# 18. Current Known Limitations / Technical Debt

## Database

- 默认 SQLite 路径仍依赖进程当前工作目录
- 尚未引入 Alembic Migration
- save_jobs 当前仍采用逐条保存策略
- identity_key 当前不是固定长度 Hash

## Query

- SQLite 字符串大小写行为不等于完整 Unicode Case Folding
- 当前查询能力仍以已有城市、公司、技能精确筛选为主

## Testing

- 部分 API 测试 Fixture 仍存在重复
- FastAPI TestClient / httpx 仍存在弃用 warning

## Crawling

- 当前正式数据源仍然是 Mock HTML
- 尚未接真实招聘网站

## Agent

- 尚未接真实 LLM Provider
- 尚未实现 Agent HTTP API
- 尚未实现 Retry
- 尚未实现 Memory
- 尚未实现 RAG
- 尚未实现 Parallel Tool Calling
- 尚未实现 Streaming
- 尚未实现 Multi-Agent
- 尚未实现 Agent Trace 持久化
- 尚未实现长期 Conversation State
- 尚未实现 Token / Cost 统计

以上属于后续能力扩展，不属于 Stage 7 未完成项。

---

# 19. Out of Scope Until Explicitly Planned

当前不要提前加入：

```text
Real LLM Provider
Retry
Memory
RAG
Parallel Tool Calling
Multi-Agent
Streaming
Persistent Agent State
```

是否进入下一 Stage 必须重新规划，不因为“Agent 项目以后可能需要”就提前加入当前代码。

---

# 20. Current Repository Tree

以下目录基于 Stage 7 合并至 main 后实际执行：

```powershell
git ls-files
```

得到。

```text
internscout-agent/
├── .gitattributes
├── .gitignore
├── PROJECT_STATE.md
├── README.md
├── requirements.txt
│
├── app/
│   ├── __init__.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── contracts.py
│   │   ├── exceptions.py
│   │   ├── model_client.py
│   │   ├── orchestrator.py
│   │   ├── state.py
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── job_query.py
│   │       ├── job_tools.py
│   │       └── registry.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── crawl.py
│   │       ├── health.py
│   │       └── jobs.py
│   ├── crawlers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── mock_crawler.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── job_query_adapter.py
│   │   ├── models.py
│   │   ├── repository.py
│   │   └── session.py
│   ├── fixtures/
│   │   └── sample_jobs.html
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── crawl_response.py
│   │   ├── health_response.py
│   │   ├── job.py
│   │   └── job_response.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── cleaner.py
│   │   ├── deduplicator.py
│   │   └── processor.py
│   ├── workflows/
│   │   ├── __init__.py
│   │   └── job_ingestion.py
│   └── main.py
│
├── docs/
│   ├── development-log.md
│   └── stage-reviews/
│       ├── stage-01-review.md
│       ├── stage-02-review.md
│       ├── stage-03-review.md
│       ├── stage-04-review.md
│       ├── stage-05-review.md
│       ├── stage-06-review.md
│       └── stage-07-review.md
│
└── tests/
    ├── agent/
    │   ├── __init__.py
    │   ├── fakes/
    │   │   ├── __init__.py
    │   │   └── fake_model_client.py
    │   ├── test_agent_exceptions.py
    │   ├── test_base_tool.py
    │   ├── test_contracts.py
    │   ├── test_job_tools.py
    │   ├── test_model_client.py
    │   ├── test_orchestrator.py
    │   ├── test_state.py
    │   └── test_tool_registry.py
    ├── database/
    │   └── test_job_query_adapter.py
    ├── test_cleaner.py
    ├── test_crawl_api.py
    ├── test_database.py
    ├── test_database_session.py
    ├── test_deduplicator.py
    ├── test_health.py
    ├── test_job_api.py
    ├── test_job_detail_api.py
    ├── test_job_ingestion.py
    ├── test_job_query_repository.py
    ├── test_job_repository.py
    ├── test_job_response_schema.py
    ├── test_job_schema.py
    ├── test_mock_crawler.py
    ├── test_processor.py
    └── test_stage6_api_flow.py
```

该目录树只包含 Git tracked files，不包含：

- `.venv`
- `__pycache__`
- pytest cache
- 本地数据库
- 编辑器临时文件
- 未跟踪本地文件

---

# 21. Stage History Summary

## Stage 0

开发环境建立与基础工具确认。

## Stage 1

FastAPI 基础应用与健康接口。

## Stage 2

Pydantic 岗位数据模型与模拟招聘页面。

## Stage 3

BaseJobCrawler 与 MockJobCrawler。

## Stage 4

岗位清洗、标准化与去重。

## Stage 5

SQLAlchemy、SQLite、Repository 与岗位持久化。

## Stage 6

FastAPI 岗位服务闭环：

```text
采集
→ 清洗
→ 去重
→ SQLite
→ HTTP 查询
```

## Stage 7

Tool-Calling Agent Runtime：

```text
User Goal
→ Model Decision
→ Tool Calling
→ Observation
→ Model Decision
→ FinalAnswer
```

并建立：

```text
Agent Contract
Agent State
Tool System
Model Abstraction
AgentOrchestrator
JobQueryPort
RepositoryJobQueryAdapter
```

---

# 22. Current Project Capability Summary

当前后端链路：

```text
Mock 招聘数据
↓
Crawler
↓
Pydantic Job Model
↓
Cleaning
↓
Normalization
↓
Deduplication
↓
SQLite Persistence
↓
Repository Query
↓
FastAPI
↓
HTTP Job API
```

当前 Agent Runtime：

```text
User Goal
↓
AgentOrchestrator
↓
ModelClient
↓
ToolCall
↓
ToolRegistry
↓
Tool
↓
JobQueryPort
↓
Repository Adapter
↓
Repository
↓
Observation
↓
ModelClient
↓
FinalAnswer
```

项目当前已经从“招聘岗位后端服务”推进到“拥有最小可测试 Tool-Calling Agent Runtime 的后端项目”。

---

# 23. Long-Term Development Rules

## 23.1 One Major Stage Per Chat

每个主要 Stage 使用独立 Chat。

如果一个 Stage 内部聊天过长：

```text
生成 Continuation Handoff
→ 新 Chat
→ State Recovery
→ Repo Reality Check
→ 继续开发
```

## 23.2 Repository Reality Wins

出现以下冲突时：

```text
聊天历史
Handoff
记忆
计划文档
Repository 实际状态
```

优先级最高的是 Repository Reality，包括：

```text
git status
git log
实际文件内容
pytest
```

## 23.3 File Modification Standard

修改项目文件时：

> 先提供涉及文件的完整、可直接复制代码，再说明修改了什么、为什么修改。

不要只给局部代码片段让开发者逐处查找替换。

## 23.4 Test Before Commit

重要代码修改后按范围逐步测试：

```text
Targeted Tests
↓
Subsystem Tests
↓
Full Regression
```

然后：

```text
git status
git add
git diff --cached --check
git commit
```

## 23.5 Code Review Is Read-Only

Codex Code Review 默认只读。

可以：

- 读取代码
- 读取 Git 状态
- 运行测试
- 报告问题

不允许自动：

- 修改代码
- git add
- commit
- push

## 23.6 Do Not Fix Non-Blocking Problems Without Benefit

例如：

```text
无影响的编辑器提示
已知第三方 warning
非阻塞 CRLF 提示
工具缺失但存在简单替代方案
```

如果不影响当前 Stage，不为了“看起来更干净”扩大开发范围。

## 23.7 PROJECT_STATE Update Rule

每完成一个主要 Stage：

```text
完成代码
↓
测试
↓
Code Review
↓
阶段文档
↓
PR
↓
Merge to main
↓
同步本地 main
↓
merge 后再次 pytest
↓
获取 git-tracked 源码树
↓
更新 PROJECT_STATE.md
```

PROJECT_STATE 必须记录：

- 当前完成 Stage
- 当前真实能力
- 当前架构
- 当前测试基线
- 当前已知问题
- 当前仍有效技术决策
- Stage merge identity
- 最新 Git-tracked source tree

不得提前记录尚未 merge 的版本为最终状态。

---

# 24. Current Acceptance State

Stage 7 最终验收：

```text
Stage 7 implementation       PASS
Agent architecture           PASS
Tool system                  PASS
Model abstraction            PASS
AgentOrchestrator            PASS
Tool failure observation     PASS
Unknown tool observation     PASS
max_steps                    PASS
Run isolation                PASS
Tool / Repository boundary   PASS
Codex final review           PASS
Stage 7 review               PASS
Development log              PASS
PR                            MERGED
main regression              PASS
```

最终测试：

```text
184 passed, 1 warning
```

Stage 7 merge identity：

```text
5c5f528
```

当前项目正式状态：

```text
Stage 0 ～ Stage 7 Complete
```

---

# 25. Next Action

Stage 7 已完成。

下一步：

```text
关闭 Stage 7 收尾
↓
独立规划 Stage 8
```

Stage 8 内容：

```text
UNKNOWN
```

在正式规划 Stage 8 前，不提前修改当前架构。
