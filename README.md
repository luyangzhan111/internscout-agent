# InternScout Agent

InternScout Agent 是一个基于 Agent Runtime 的智能实习岗位采集与匹配系统，用于演示从岗位数据采集、清洗、持久化和查询，到确定性候选人匹配与大模型工具调用的完整工程链路。

项目当前完成至 Stage 12。此前 Stage 11 已完成确定性候选人 / 岗位匹配能力，Stage 12 进一步完成了 Agent Evaluation、CI 和 Product Demo 能力。它以可测试、可解释和边界清晰为目标，保留 Mock 数据链路，并接入 OPPO Careers 作为首个经过验证的真实招聘数据源。

## 核心能力

- **Job data pipeline**：岗位采集、领域映射、清洗、去重、持久化与查询的完整链路。
- **MockJobCrawler**：从本地 sample HTML 读取岗位，支持稳定、离线的开发和测试。
- **OPPO Careers real source**：通过 `OppoJobSourceClient` 与 `OppoJobCrawler` 接入 OPPO Careers 的岗位发现和详情数据。
- **Cleaning**：规范化岗位字段、城市和技能数据，并在写入前执行去重。
- **SQLite persistence**：通过 Repository 与 SQLAlchemy 将岗位持久化到 SQLite。
- **REST API**：提供健康检查、Mock 采集、岗位列表、岗位详情和 Agent 查询接口。
- **Agent Runtime**：provider-neutral、request-scoped 的顺序工具调用运行时。
- **DeepSeek Provider**：通过独立 Provider Adapter 对接 DeepSeek API，由 Agent Runtime 使用工具结果生成回答。

## Agent Layer

Agent Layer 位于 `app/agent/`，核心组件包括：

- `AgentOrchestrator`：驱动单次 Agent run，在模型响应与工具执行之间进行编排。
- `ToolRegistry`：注册并解析 Agent 可调用的工具。
- `SearchJobsTool`：按城市、公司、技能和分页条件查询岗位。
- `GetJobDetailTool`：按岗位 ID 获取单个岗位详情。
- `MatchJobsTool`：验证候选人匹配输入，并委托确定性匹配服务返回结构化结果。

当前 Agent run 不保留跨请求会话状态，工具按顺序执行。

## Candidate Matching

Stage 11 加入了确定性、可测试的候选人 / 岗位匹配能力：

- `CandidateProfile`：验证并规范化候选人技能与意向城市。
- `JobSkillExtractor`：从岗位 structured skills、title 和 description 中提取确定性技能证据。
- `CandidateMatcher`：计算 matched skills、missing skills、匹配分数与解释原因。
- `JobMatchingService`：读取候选岗位，执行城市过滤、匹配、稳定排序和结果截断。
- **deterministic matching**：相同输入和岗位数据产生一致结果。
- **explainable score**：分数由可测试的应用逻辑计算，不由模型生成。
- **missing skill analysis**：明确返回已匹配技能与缺失技能。
- **city filtering**：按规范化后的候选人意向城市筛选符合条件的岗位。

`MatchJobsTool` 只负责 Agent Tool 边界与服务委托；技能提取、评分和排序逻辑保留在 matching layer。

## Streamlit Demo

项目提供一个轻量的 Streamlit Product Demo，用于展示现有 Agent 能力和完整的请求链路。

- 用户输入候选人技能和意向城市。
- Demo 通过 FastAPI 调用 Agent，不直接访问 Agent Runtime、数据库或 Matching Service。
- 页面展示推荐岗位、匹配分数、已匹配技能、缺失技能和 Agent 推荐解释。
- Demo 默认使用本地 Backend 与 local SQLite 中已有的岗位数据；这些 Demo 数据不是实时招聘网站数据。
- OPPO real-source ingestion capability 是独立的数据采集能力，不等同于 Demo 默认数据来源。

## Architecture

Product Demo flow:

```text
User
 |
Streamlit Demo
 |
FastAPI
 |
Agent Runtime
 |
Tools
 |
Matching
 |
Database
```

```text
Local sample HTML                         OPPO Careers
        |                                      |
        v                                      v
 MockJobCrawler                    OppoJobSourceClient
        |                                      |
        |                               OppoJobCrawler
        |                                      |
        +---------------> JobCreate <----------+
                               |
                               v
                  Cleaning + Deduplication
                               |
                               v
                    Repository / SQLAlchemy
                               |
                               v
                            SQLite
                               |
              +----------------+----------------+
              |                                 |
              v                                 v
         REST Jobs API                      JobQueryPort
                                                |
                         +----------------------+------------------+
                         |                      |                  |
                         v                      v                  v
                  SearchJobsTool       GetJobDetailTool   MatchJobsTool
                                                                  |
                                                                  v
                                                       JobMatchingService
                                                        /               \
                                                       v                 v
                                               JobSkillExtractor  CandidateMatcher
                         \                      |                  /
                          +---------------------+-----------------+
                                                |
                                                v
                                         ToolRegistry
                                                |
                                                v
                                        AgentOrchestrator
                                                |
                                                v
                                      DeepSeek Provider Adapter
                                                |
                                                v
                                           DeepSeek API
```

## REST API

- `GET /`：服务入口。
- `GET /api/health`：服务与数据库健康检查。
- `POST /api/crawl`：执行 `MockJobCrawler` 采集。
- `GET /api/jobs`：筛选并分页查询岗位。
- `GET /api/jobs/{job_id}`：获取岗位详情。
- `POST /api/agent/query`：触发一次独立的 Agent run。

`POST /api/crawl` 当前仅用于 Mock 采集。真实 OPPO 数据链路通过显式组合调用，尚未暴露为公共 HTTP 采集入口。OPPO source 使用招聘网站的 observed internal endpoints，其 schema 可能发生变化。

准备本地 Demo 数据时，先启动 FastAPI，再调用 `POST /api/crawl`。该 endpoint 使用 `MockJobCrawler` 采集本地 sample HTML 并写入 SQLite，不会抓取实时招聘网站数据：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/crawl
```

## Tech Stack

- Python 3.12
- FastAPI
- SQLAlchemy 2.x
- SQLite
- Pydantic
- pytest
- httpx
- Streamlit
- DeepSeek API

## Local Development

创建并激活 Python 虚拟环境，然后安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

启动 FastAPI 服务：

```powershell
python -m uvicorn app.main:app --reload
```

启动 Streamlit Demo：

```powershell
streamlit run demo/app.py
```

使用真实 DeepSeek Provider 前，需要配置 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_MODEL`。不要把 API key 写入代码或提交到仓库。

## Project Highlights

- **Agent Runtime**：provider-neutral、request-scoped 的顺序工具调用运行时。
- **Tool Calling**：通过 ToolRegistry 连接岗位查询、岗位详情和匹配能力。
- **Deterministic Matching**：提供稳定、可测试、可解释的匹配分数和技能分析。
- **Evaluation Framework**：使用离线、确定性的评估场景验证 Agent 行为。
- **CI**：通过 GitHub Actions 自动执行完整测试回归。
- **Product Demo**：使用 Streamlit 展示 User → FastAPI → Agent Runtime 的实际产品链路。

Product Demo 当前提供本地运行方式，未部署到公网。

## Testing

Stage 11 merge 后完整回归基线：

- **503 passed**
- **0 warnings**

Stage 12 当前完整回归基线：

- **567 passed**

运行测试：

```powershell
python -m pytest
```

自动化测试保持离线，不依赖真实 OPPO 或 DeepSeek 网络请求。

## Current Boundaries

- SQLite 是当前唯一数据库，没有数据库迁移系统。
- `POST /api/crawl` 仍是 Mock-specific，不会触发真实 OPPO crawler。
- OPPO 接入依赖网站内部接口，外部 schema 变化可能要求更新 source adapter。
- Agent 每次请求独立运行，不提供持久会话。
- Tool Calling 当前仅支持顺序执行。
- 当前没有 retry、partial-success policy、真实 source HTTP trigger 或分布式采集。
- Product Demo 默认消费 local SQLite / MockJobCrawler 数据，不代表实时招聘网站数据；Demo 未部署到公网。
