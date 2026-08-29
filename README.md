# InternScout Agent

> An AI Agent application for internship discovery, job data processing, and candidate-job matching.
>
> Current development target / portfolio version: **v1.1.0**
>
> No `v1.1.0` Git tag or GitHub Release has been created.

## Project Overview

InternScout Agent 不是一个普通的爬虫脚本，而是一个把岗位数据 pipeline 作为基础能力、再由 Agent Runtime 完成查询、工具调用与候选人匹配的 AI Agent 应用。项目展示了从 internship crawling pipeline、数据清洗与标准化，到 FastAPI backend、Agent orchestration、tool calling、candidate-job matching、agent evaluation、Docker deployment 和 CI validation 的完整工程链路。

项目当前完成至 Stage 13.5G，正在进行 v1.1.0 closeout。Stage 11 完成确定性候选人 / 岗位匹配能力，Stage 12 完成 Agent Evaluation 与 CI validation，Stage 13 完成 Docker Compose 本地部署、Product Demo 与 release preparation，Stage 13.5 增加岗位知识语义检索层，并保留 OPPO Careers 数据源适配验证能力。

项目当前定位为可复现、可测试、可解释的本地产品原型与公开 portfolio 项目。默认 Demo 使用本地 SQLite 和 Mock 数据；OPPO Careers 数据源适配验证能力，不代表 Demo 默认读取实时招聘网站。

## Features

- **Internship crawling pipeline**：岗位采集、领域映射、处理、去重、持久化与查询的完整链路。
- **MockJobCrawler**：从本地 sample HTML 读取岗位，支持稳定、离线的开发和测试。
- **OPPO Careers real source**：通过 `OppoJobSourceClient` 与 `OppoJobCrawler` 接入 OPPO Careers 的岗位发现和详情数据。
- **Data cleaning and normalization**：规范化公司、城市和技能字段，并在写入前执行去重。
- **SQLite persistence**：通过 Repository 与 SQLAlchemy 将岗位持久化到 SQLite。
- **FastAPI backend**：提供健康检查、Mock 采集、岗位列表、岗位详情和 Agent 查询接口。
- **Agent orchestration**：provider-neutral、request-scoped 的顺序工具调用运行时。
- **Tool calling**：通过 `ToolRegistry` 暴露三个默认岗位工具，并在 retrieval ready 时增加可选的岗位知识检索工具。
- **Candidate-job matching**：确定性、可解释的匹配分数、已匹配技能、缺失技能、城市过滤和稳定排序。
- **Job knowledge retrieval**：将非结构化岗位描述转换为 `JobDocument`，通过 embedding 和向量搜索提供语义证据。
- **Provider-neutral retrieval abstractions**：`EmbeddingProvider`、`VectorStore`、`JobKnowledgeRetriever` 和可选的 `RetrievalRuntime`。
- **In-memory vector search**：使用 cosine similarity 和稳定 tie behavior 的 `InMemoryVectorStore`；它不是持久化 vector database。
- **Optional Agent retrieval tool**：retrieval ready 时注册 `retrieve_job_knowledge`，否则 Agent 保持默认三工具。
- **Production-compatible embeddings**：通过 OpenAI-compatible embedding provider 配置 Bailian-compatible endpoint。
- **Agent evaluation**：离线、确定性的 evaluation dataset、runner 和 scorers，用于验证工具选择、参数、结果和回答事实。
- **Retrieval evaluation**：6 个 direct retrieval cases、2 个 Agent retrieval cases，以及 Hit@K / Top-1 ranking gate。
- **DeepSeek Provider**：通过独立 Provider Adapter 对接 DeepSeek API，由 Agent Runtime 使用工具结果生成回答。
- **Docker deployment**：使用独立 Backend 与 Streamlit Demo 容器提供可复现的 Docker Compose 本地部署方式，并通过 named volume 持久化 SQLite；embedding provider 配置只传入 Backend。
- **CI validation**：GitHub Actions 执行 pytest、Docker Compose 配置校验和 Docker 镜像构建校验。

## Agent Layer

Agent Layer 位于 `app/agent/`，核心组件包括：

- `AgentOrchestrator`：驱动单次 Agent run，在模型响应与工具执行之间进行编排。
- `ToolRegistry`：注册并解析 Agent 可调用的工具。
- `SearchJobsTool`：按城市、公司、技能和分页条件查询岗位。
- `GetJobDetailTool`：按岗位 ID 获取单个岗位详情。
- `MatchJobsTool`：验证候选人匹配输入，并委托确定性匹配服务返回结构化结果。
- `RetrieveJobKnowledgeTool`：仅在 retriever 可用时注册，根据自然语言查询返回岗位知识检索结果。

默认 Agent tools 为 `search_jobs`、`get_job_detail`、`match_jobs`；retrieval runtime ready 时增加第四个 `retrieve_job_knowledge`。当前 Agent run 不保留跨请求会话状态，工具按顺序执行。

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

## Semantic Job Knowledge Retrieval

Stage 13.5 将两类能力保持为互补边界：

- **Structured deterministic matching**：structured fields → deterministic skill extraction → deterministic matching score。
- **Semantic job knowledge retrieval**：unstructured job descriptions → `JobDocument` → `EmbeddingProvider` → `VectorStore` → `JobKnowledgeRetriever` → `retrieve_job_knowledge`。

Retrieval adds semantic evidence. It does not replace deterministic candidate-job matching, scoring, city filtering, or ranking logic.

The production adapter uses an OpenAI-compatible embeddings API and can be configured for a Bailian-compatible endpoint. The CI semantic fixture is controlled and repository-specific; it is not a general embedding-quality benchmark.

## Streamlit Demo

项目提供一个轻量的 Streamlit Product Demo，用于展示现有 Agent 能力和完整的请求链路。

- 用户输入候选人技能和意向城市。
- Demo 通过 FastAPI 调用 Agent，不直接访问 Agent Runtime、数据库或 Matching Service。
- 页面展示推荐岗位、匹配分数、已匹配技能、缺失技能和 Agent 推荐解释。
- Demo 在 local Python development mode 下通过 `http://127.0.0.1:8000` 调用单独运行的 Backend；在 Docker Compose local mode 下通过 Compose 网络中的 `http://backend:8000` 调用 Backend。
- 两种模式都使用本地 SQLite / MockJobCrawler 数据；这些 Demo 数据不是实时招聘网站数据。
- Demo 当前没有独立 retrieval UI；岗位知识检索通过 Agent tool 使用。
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

Retrieval branch:

```text
Job Database
    |
    +--------------------------+
    |                          |
    v                          v
Structured Query          JobDocument
    |                          |
    v                          v
Deterministic          EmbeddingProvider
Matching Score               |
                               v
                          VectorStore
                               |
                               v
                     JobKnowledgeRetriever
                               |
                               v
                    retrieve_job_knowledge
                               |
                               v
                       AgentOrchestrator
```

`RetrievalRuntime` is optional and process-local. FastAPI startup constructs it without embedding all jobs. On an Agent request, a dirty or unready runtime collects the current job snapshot and rebuilds lazily. Successful crawl ingestion calls `mark_dirty()`; it does not embed during crawl. Rebuild uses build-then-swap: a successful new index replaces the current retriever, while a failed refresh keeps the old retriever dirty. A failed initial rebuild leaves the Agent with the default three tools.

DeepSeek uses the Responses API with `reasoning={"effort": "none"}` for tool compatibility. If the provider returns multiple function calls, InternScout projects the provider-order first call, executes one tool, and lets the next model turn replan. The runtime remains sequential; it does not execute tools in parallel.

## REST API

- `GET /`：服务入口。
- `GET /api/health`：服务与数据库健康检查。
- `POST /api/crawl`：执行 `MockJobCrawler` 采集。
- `GET /api/jobs`：筛选并分页查询岗位。
- `GET /api/jobs/{job_id}`：获取岗位详情。
- `POST /api/agent/query`：触发一次独立的 Agent run。

岗位知识检索通过 Agent tool 提供，没有新增独立 retrieval HTTP endpoint。

`POST /api/crawl` 当前仅用于 Mock 采集。真实 OPPO 数据链路通过显式组合调用，尚未暴露为公共 HTTP 采集入口。OPPO source 使用招聘网站观察到的内部接口，其 schema 可能发生变化。

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
- OpenAI-compatible Embeddings API

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

使用真实 DeepSeek Provider 前，需要将 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_MODEL` 注入当前进程。要启用 semantic retrieval，还需要 `INTERNSCOUT_EMBEDDING_API_KEY` 和 `INTERNSCOUT_EMBEDDING_BASE_URL`；`INTERNSCOUT_EMBEDDING_MODEL` 默认是 `text-embedding-v4`，`INTERNSCOUT_EMBEDDING_DIMENSIONS` 默认是 `1024`。直接运行 Python 时不会自动加载 `.env` 文件；Docker Compose 会读取项目根目录的 `.env`。

Embedding configuration is optional for the application. If the embedding API key or base URL is missing or invalid, FastAPI still starts and the Agent exposes `search_jobs`、`get_job_detail`、`match_jobs` 三个默认工具。

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
- **Tool Calling**：通过 ToolRegistry 连接默认岗位查询、岗位详情和匹配能力，并按需连接 retrieval tool。
- **Deterministic Matching**：提供稳定、可测试、可解释的匹配分数和技能分析。
- **Semantic Job Retrieval**：提供 provider-neutral embedding/vector abstractions、JobDocument pipeline 和 semantic job knowledge retrieval。
- **Retrieval Lifecycle**：使用 process-local、lazy、build-then-swap 的 RetrievalRuntime 管理索引刷新。
- **Retrieval Evaluation**：使用受控 fixture 验证 deterministic Hit@K / Top-1 ranking，不把它当作真实 embedding benchmark。
- **Evaluation Framework**：使用离线、确定性的评估场景验证 Agent 行为。
- **CI**：通过 GitHub Actions 自动执行 pytest 回归、`docker compose config` 配置校验和 Docker 镜像构建校验；阻塞 CI 不依赖实时 DeepSeek 调用。
- **Product Demo**：使用 Streamlit 展示 User → FastAPI → Agent Runtime 的实际产品链路。

Product Demo 当前支持单独 Python 进程和 Docker Compose 两种本地运行方式；Docker Compose 会将 DeepSeek 和 embedding provider 配置传给 Backend，不会传给 Demo。项目未部署到公网或生产环境。

## Evaluation and Testing

Stage 13.5G closeout 的 automated regression evidence：

- **710 passed**
- `tests/evaluation`: **95 passed**
- `tests/agent`: **139 passed**
- `tests/rag`: **58 passed**

运行测试：

```powershell
python -m pytest tests -q -p no:cacheprovider --basetemp <fresh external directory>
```

Stage 12 deterministic Agent evaluation 使用 9 个 cases 和 `execution_outcome`、`tool_selection`、`tool_sequence`、`tool_arguments`、`tool_results`、`answer_facts` metrics。Stage 13.5 direct retrieval evaluation 使用 6 个 cases，通过 `ControlledEmbeddingProvider` 和 production `JobKnowledgeRetriever` 验证 Hit@K 与 Top-1；Agent retrieval integration evaluation 使用 2 个 `FakeModelClient` scripted cases 通过真实 Agent loop 验证 tool integration。

这些 blocking CI gates 保持 offline、deterministic、secret-free、network-free，不使用 LLM judge、MRR 或 real embedding benchmark。GitHub Actions 还会独立执行 Docker Compose 配置和镜像构建校验。

## Current Boundaries

- SQLite 是当前唯一数据库，没有数据库迁移系统。
- `POST /api/crawl` 仍是 Mock-specific，不会触发真实 OPPO crawler。
- OPPO 接入依赖网站内部接口，外部 schema 变化可能要求更新 source adapter。
- Agent 每次请求独立运行，不提供持久会话。
- Tool Calling 当前仅支持顺序执行。
- `InMemoryVectorStore` 是 process-local index，不是持久化 external vector database。
- Retrieval rebuild 是 lazy 的；embedding config 缺失时 retrieval optional disabled。
- `ControlledEmbeddingProvider` 只用于受控 semantic regression，不保证真实 embedding 的通用质量。
- 当前没有 retry、partial-success policy、真实 source HTTP trigger 或分布式采集。
- Product Demo 默认消费 local SQLite / MockJobCrawler 数据，不代表实时招聘网站数据；Demo 可通过 Python 或 Docker Compose 在本地运行，但未部署到公网或生产环境。
