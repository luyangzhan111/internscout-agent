# InternScout Agent

> An AI Agent application for internship discovery, job data processing, and candidate-job matching.
>
> Release target: **v1.0.0**

## Project Overview

InternScout Agent 不是一个普通的爬虫脚本，而是一个把岗位数据 pipeline 作为基础能力、再由 Agent Runtime 完成查询、工具调用与候选人匹配的 AI Agent 应用。项目展示了从 internship crawling pipeline、数据清洗与标准化，到 FastAPI backend、Agent orchestration、tool calling、candidate-job matching、agent evaluation、Docker deployment 和 CI validation 的完整工程链路。

项目当前完成至 Stage 13。此前 Stage 11 已完成确定性候选人 / 岗位匹配能力，Stage 12 进一步完成了 Agent Evaluation、CI validation 和 Product Demo 能力，Stage 13 增加了环境配置、Docker Compose 本地运行方式、Product Demo、CI validation 和 release preparation。完成 OPPO Careers 数据源适配验证。

项目当前定位为可复现、可测试、可解释的本地产品原型与公开 portfolio 项目。默认 Demo 使用本地 SQLite 和 Mock 数据；OPPO Careers 数据源适配验证能力，不代表 Demo 默认读取实时招聘网站。

## Features

- **Internship crawling pipeline**：岗位采集、领域映射、处理、去重、持久化与查询的完整链路。
- **MockJobCrawler**：从本地 sample HTML 读取岗位，支持稳定、离线的开发和测试。
- **OPPO Careers real source**：通过 `OppoJobSourceClient` 与 `OppoJobCrawler` 接入 OPPO Careers 的岗位发现和详情数据。
- **Data cleaning and normalization**：规范化公司、城市和技能字段，并在写入前执行去重。
- **SQLite persistence**：通过 Repository 与 SQLAlchemy 将岗位持久化到 SQLite。
- **FastAPI backend**：提供健康检查、Mock 采集、岗位列表、岗位详情和 Agent 查询接口。
- **Agent orchestration**：provider-neutral、request-scoped 的顺序工具调用运行时。
- **Tool calling**：通过 `ToolRegistry` 暴露岗位搜索、岗位详情和候选人匹配工具。
- **Candidate-job matching**：确定性、可解释的匹配分数、已匹配技能、缺失技能、城市过滤和稳定排序。
- **Agent evaluation**：离线、确定性的 evaluation dataset、runner 和 scorers，用于验证工具选择、参数、结果和回答事实。
- **DeepSeek Provider**：通过独立 Provider Adapter 对接 DeepSeek API，由 Agent Runtime 使用工具结果生成回答。
- **Docker deployment**：使用独立 Backend 与 Streamlit Demo 容器提供可复现的 Docker Compose 本地部署方式，并通过 named volume 持久化 SQLite。
- **CI validation**：GitHub Actions 执行 pytest、Docker Compose 配置校验和 Docker 镜像构建校验。

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
- Demo 在 local Python development mode 下通过 `http://127.0.0.1:8000` 调用单独运行的 Backend；在 Docker Compose local mode 下通过 Compose 网络中的 `http://backend:8000` 调用 Backend。
- 两种模式都使用本地 SQLite / MockJobCrawler 数据；这些 Demo 数据不是实时招聘网站数据。
- OPPO real-source ingestion capability 是独立的数据采集能力，不等同于 Demo 默认数据来源。
- 项目提供本地 Docker Compose 运行方式，但没有 public production deployment。

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

使用真实 DeepSeek Provider 前，需要将 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_MODEL` 注入当前进程。直接运行 Python 时不会自动加载 `.env` 文件；Docker Compose 会读取项目根目录的 `.env`。

## Quick Start (Docker Compose)

Docker Compose 提供 Backend 与 Streamlit Demo 的本地容器运行方式。需要安装 Docker Engine 与 Docker Compose plugin，并准备一个不包含真实密钥的 `.env` 配置文件：

```powershell
Copy-Item .env.example .env
```

编辑 `.env` 后，可先校验 Compose 配置，再构建并启动服务：

```powershell
docker compose config --quiet
docker compose up --build
```

容器启动后，在另一个终端初始化本地 Demo 岗位数据：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/crawl
```

访问地址：

- FastAPI Backend：`http://127.0.0.1:8000`
- Streamlit Demo：`http://127.0.0.1:8501`

Backend 启动时会自动创建缺失的 SQLite 表。Compose 使用 `backend_data` named volume 保存 `/data/internscout.db`，因此普通 `docker compose down` 不会删除数据库数据；`docker compose down -v` 会删除该 volume。

完整的环境变量、启动、停止、数据初始化和故障排查说明见 [`docs/deployment.md`](docs/deployment.md)。

## Project Highlights

- **Agent Runtime**：provider-neutral、request-scoped 的顺序工具调用运行时。
- **Tool Calling**：通过 ToolRegistry 连接岗位查询、岗位详情和匹配能力。
- **Deterministic Matching**：提供稳定、可测试、可解释的匹配分数和技能分析。
- **Evaluation Framework**：使用离线、确定性的评估场景验证 Agent 行为。
- **CI**：通过 GitHub Actions 自动执行 pytest 回归、`docker compose config` 配置校验和 Docker 镜像构建校验；阻塞 CI 不依赖实时 DeepSeek 调用。
- **Product Demo**：使用 Streamlit 展示 User → FastAPI → Agent Runtime 的实际产品链路。

Product Demo 当前支持单独 Python 进程和 Docker Compose 两种本地运行方式，未部署到公网或生产环境。

## Testing

当前 Stage 13 完整回归基线：

- **570 passed**

运行测试：

```powershell
python -m pytest -q
```

测试保持离线，不依赖真实 OPPO 或 DeepSeek 网络请求。GitHub Actions 还会独立执行 Docker Compose 配置和镜像构建校验。

历史回归基线：

- **503 passed**
- **0 warnings**

## Current Boundaries

- SQLite 是当前唯一数据库，没有数据库迁移系统。
- `POST /api/crawl` 仍是 Mock-specific，不会触发真实 OPPO crawler。
- OPPO 接入依赖网站内部接口，外部 schema 变化可能要求更新 source adapter。
- Agent 每次请求独立运行，不提供持久会话。
- Tool Calling 当前仅支持顺序执行。
- 当前没有 retry、partial-success policy、真实 source HTTP trigger 或分布式采集。
- Product Demo 默认消费 local SQLite / MockJobCrawler 数据，不代表实时招聘网站数据；Demo 可通过 Python 或 Docker Compose 在本地运行，但未部署到公网或生产环境。
