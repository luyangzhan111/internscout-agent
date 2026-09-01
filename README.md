# InternScout Agent

> An AI Agent application for internship discovery, job data processing, explainable candidate-job matching, and semantic job knowledge retrieval.

[![CI](https://github.com/luyangzhan111/internscout-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/luyangzhan111/internscout-agent/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/luyangzhan111/internscout-agent)](https://github.com/luyangzhan111/internscout-agent/releases/tag/v1.1.0)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Agent%20Backend-green)
![Tests](https://img.shields.io/badge/tests-710%20passed-brightgreen)

**Current portfolio release: `v1.1.0`**

InternScout Agent 是一个面向招聘岗位发现与候选人匹配场景构建的 AI Agent 应用。

它不是单纯的 LLM API Demo，也不是只有数据采集功能的招聘爬虫。项目从真实岗位数据 pipeline 出发，将 **岗位采集、数据清洗、数据库、FastAPI、Agent Tool Calling、确定性岗位匹配、Semantic Retrieval、Evaluation、CI、Streamlit Demo 和 Docker Compose** 组合成一套完整、可测试、可复现的 AI 应用工程链路。

项目的核心设计原则之一是：

> **Semantic Retrieval 负责提供非结构化语义证据，Deterministic Matching 负责结构化、稳定、可解释的最终匹配逻辑。两者互补，而不是互相替代。**

---

## Highlights

| Area | Implementation |
| --- | --- |
| **Agent Runtime** | `AgentOrchestrator` + `ToolRegistry`，模型驱动工具选择与顺序执行 |
| **Tool Calling** | 岗位搜索、岗位详情、候选人匹配，以及按需启用的语义检索工具 |
| **Real Job Source** | OPPO Careers 招聘源 Adapter |
| **Candidate Matching** | 确定性技能提取、匹配评分、缺失技能分析、城市过滤、稳定排序 |
| **Semantic Retrieval** | `JobDocument` + `EmbeddingProvider` + `VectorStore` + cosine similarity |
| **Retrieval Runtime** | lazy indexing + dirty tracking + build-then-swap |
| **LLM Provider** | DeepSeek Responses API Adapter |
| **Evaluation** | Deterministic Agent Evaluation + Retrieval Evaluation |
| **Backend** | FastAPI + SQLAlchemy + SQLite |
| **Product Demo** | Streamlit |
| **Deployment** | Docker Compose local deployment |
| **Quality** | GitHub Actions CI + **710 passed** release regression |

---

## What It Does

InternScout Agent 支持从岗位数据进入系统，到 Agent 为候选人查询和分析岗位的完整流程。

### 1. Job Data Pipeline

项目实现岗位数据的：

```text
Collection
    ↓
Parsing
    ↓
Cleaning
    ↓
Normalization
    ↓
Deduplication
    ↓
Persistence
    ↓
Query
```

目前支持两类数据来源：

- `MockJobCrawler`：读取本地 sample HTML，用于稳定、离线、可复现的开发和测试。
- OPPO Careers Adapter：通过 `OppoJobSourceClient` 与 `OppoJobCrawler` 验证真实招聘源采集链路。

经过清洗与标准化后的岗位数据通过 SQLAlchemy 持久化到 SQLite，并由 FastAPI 与 Agent Tool 层进一步消费。

---

### 2. Agent Tool Calling

Agent Layer 位于 `app/agent/`。

核心运行时由以下组件组成：

```text
DeepSeek Provider
       ↑
       |
AgentOrchestrator
       |
       v
 ToolRegistry
       |
       +-----------------------+
       |           |           |
       v           v           v
 search_jobs  get_job_detail  match_jobs
                              
                + optional
                    |
                    v
        retrieve_job_knowledge
```

默认 Agent Tools：

- `search_jobs`
- `get_job_detail`
- `match_jobs`

当 Semantic Retrieval Runtime 可用时，会额外注册：

- `retrieve_job_knowledge`

Agent 每次请求独立运行。

当前 Tool Calling Runtime 保持**顺序执行**，不执行 Multi-Agent 或 parallel tool runtime。

---

## Candidate-Job Matching

岗位匹配采用确定性应用逻辑，而不是让 LLM 直接生成一个不可验证的匹配分数。

核心组件包括：

### `CandidateProfile`

负责候选人技能与意向城市输入的验证和标准化。

### `JobSkillExtractor`

根据岗位中的：

- structured skills
- title
- description

提取确定性的技能证据，并执行技能 alias normalization 与去重。

### `CandidateMatcher`

根据候选人技能与岗位技能证据计算：

- matched skills
- missing skills
- match score
- match reasons

### `JobMatchingService`

负责：

```text
Candidate
    ↓
City Filtering
    ↓
Skill Evidence Extraction
    ↓
Deterministic Matching
    ↓
Stable Ranking
    ↓
Top Results
```

这一设计保证：

- 相同输入得到稳定结果；
- 匹配分数可以测试；
- 推荐原因可以解释；
- 缺失技能可以明确展示；
- LLM 不负责最终匹配评分。

---

## Semantic Job Knowledge Retrieval

为了处理岗位 description 等非结构化信息，项目在确定性匹配之外增加了一条独立的 Semantic Retrieval 路径。

```text
Job Database
     |
     v
 JobDocument
     |
     v
EmbeddingProvider
     |
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

核心抽象包括：

- `JobDocument`
- `EmbeddingProvider`
- `VectorStore`
- `JobKnowledgeRetriever`
- `RetrievalRuntime`

当前默认向量实现为：

```text
InMemoryVectorStore
        +
Cosine Similarity
```

项目同时提供 OpenAI-compatible embedding provider adapter，可配置兼容 endpoint。

### Matching vs Retrieval

这两个能力被刻意保持为两条不同路径：

```text
Structured Job Data
        |
        v
Deterministic Skill Evidence
        |
        v
Candidate Matching
        |
        v
Explainable Match Score
```

与：

```text
Unstructured Job Description
        |
        v
Embedding
        |
        v
Vector Search
        |
        v
Semantic Evidence
```

因此：

**Retrieval adds semantic evidence. It does not replace deterministic candidate-job matching.**

Semantic similarity 不直接决定候选人与岗位的最终匹配分数。

---

## Retrieval Runtime Design

Semantic Retrieval 使用 process-local `RetrievalRuntime` 管理索引生命周期。

它没有在 FastAPI 启动时立即 embedding 全部岗位，而采用 lazy rebuild：

```text
Application Startup
       |
       v
RetrievalRuntime
   unready / dirty
       |
       | first retrieval request
       v
Collect Job Snapshot
       |
       v
Build New Index
       |
       v
Successful?
   /        \
 yes        no
  |          |
  v          v
Swap      Keep Old
Index     Retriever
```

岗位数据发生变化后，只调用：

```text
mark_dirty()
```

而不是在 crawl / ingestion 路径中立即执行 embedding。

刷新采用 **build-then-swap**：

- 新索引成功构建后才替换当前 retriever；
- refresh 失败时保留旧 retriever；
- 初始构建失败时，Agent 仍可继续使用默认三个非 Retrieval Tools。

这样可以将核心 Agent 能力与可选 Semantic Retrieval 能力解耦。

---

## System Architecture

```text
                         ┌───────────────────┐
                         │   Streamlit Demo  │
                         └─────────┬─────────┘
                                   │
                                   v
                         ┌───────────────────┐
                         │      FastAPI      │
                         └─────────┬─────────┘
                                   │
                                   v
                        ┌─────────────────────┐
                        │ AgentOrchestrator   │
                        └─────────┬───────────┘
                                  │
                                  v
                           ┌──────────────┐
                           │ ToolRegistry │
                           └──────┬───────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
              v                   v                   v
       Search / Detail      MatchJobsTool     Retrieval Tool
              │                   │                   │
              │                   v                   v
              │          JobMatchingService   JobKnowledgeRetriever
              │                   │                   │
              │          ┌────────┴────────┐          v
              │          │                 │     VectorStore
              │          v                 v          │
              │   JobSkillExtractor  CandidateMatcher│
              │                                      v
              │                              EmbeddingProvider
              │
              └───────────────────┬───────────────────┘
                                  │
                                  v
                        ┌─────────────────────┐
                        │ Job Query / Storage │
                        └─────────┬───────────┘
                                  │
                                  v
                         SQLAlchemy / SQLite
                                  ▲
                                  │
             ┌────────────────────┴────────────────────┐
             │                                         │
             v                                         v
      MockJobCrawler                            OPPO Careers
                                             Source Adapter
```

---

## End-to-End Data Flow

```text
Local Sample HTML                      OPPO Careers
       |                                    |
       v                                    v
MockJobCrawler                     OppoJobSourceClient
       |                                    |
       |                              OppoJobCrawler
       |                                    |
       +--------------> JobCreate <---------+
                            |
                            v
                 Cleaning + Normalization
                            |
                            v
                      Deduplication
                            |
                            v
                 Repository / SQLAlchemy
                            |
                            v
                         SQLite
                            |
              +-------------+-------------+
              |                           |
              v                           v
        REST Jobs API                Agent Tools
                                          |
                                          v
                                  AgentOrchestrator
                                          |
                                          v
                                   DeepSeek Provider
```

---

## Product Demo

项目提供 Streamlit Product Demo，用于展示实际的：

```text
User
 ↓
Streamlit
 ↓
FastAPI
 ↓
Agent Runtime
 ↓
Tools
 ↓
Matching / Retrieval
 ↓
Job Data
```

Demo 支持用户输入：

- candidate skills
- preferred city

并展示：

- 推荐岗位
- match score
- matched skills
- missing skills
- Agent recommendation / explanation

Demo 不直接访问数据库、Matching Service 或 Agent Runtime，而始终通过 FastAPI 与后端交互。

当前 Product Demo 使用本地 SQLite / MockJobCrawler 数据，不代表实时招聘网站内容。

项目目前提供本地运行与 Docker Compose 部署方式，**没有 public production deployment**。

---

## Evaluation & Testing

InternScout Agent 不仅验证“程序能否运行”，还针对 Agent 与 Retrieval 行为建立了 deterministic evaluation。

### Release Regression

`v1.1.0` release regression：

```text
710 passed
```

其中包括：

```text
tests/evaluation    95 passed
tests/agent        139 passed
tests/rag           58 passed
```

---

### Agent Evaluation

Agent Evaluation 使用离线、确定性的 evaluation dataset、runner 和 scorers。

当前覆盖 **9 个 deterministic Agent cases**，包括：

- tool selection
- tool sequence
- tool arguments
- tool results
- execution outcome
- answer facts
- empty results
- invalid arguments
- missing job
- unknown tool

Evaluation 不依赖实时 LLM judge。

---

### Retrieval Evaluation

Semantic Retrieval Evaluation 包括：

- **6 个 direct retrieval cases**
- **2 个 Agent retrieval integration cases**

Direct evaluation 验证：

- Hit@K
- Top-1 ranking

Agent integration evaluation 则通过真实 Agent loop 验证：

```text
Agent
 ↓
retrieve_job_knowledge
 ↓
Retriever
 ↓
Tool Result
 ↓
Agent Response
```

CI 中使用的 semantic fixture 是受控、repository-specific 的 deterministic regression fixture。

它用于验证系统行为稳定性，**不代表真实 embedding model 的通用质量 benchmark**。

---

## CI

GitHub Actions 持续验证：

```text
pytest regression
        +
docker compose config validation
        +
Docker image build validation
```

Blocking CI 保持：

- offline
- deterministic
- secret-free
- network-free

因此 CI 不依赖实时 DeepSeek API 或真实 Embedding API。

---

## Tech Stack

### Backend

- Python 3.12
- FastAPI
- SQLAlchemy 2.x
- SQLite
- Pydantic
- httpx

### Agent / AI

- AgentOrchestrator
- ToolRegistry
- DeepSeek Responses API
- Tool Calling
- EmbeddingProvider abstraction
- VectorStore abstraction
- Cosine Similarity
- Semantic Retrieval

### Quality

- pytest
- Deterministic Agent Evaluation
- Retrieval Evaluation
- GitHub Actions CI

### Product & Deployment

- Streamlit
- Docker
- Docker Compose

---

## REST API

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/` | Service entry |
| `GET` | `/api/health` | Service and database health |
| `POST` | `/api/crawl` | Run local MockJobCrawler ingestion |
| `GET` | `/api/jobs` | Filter and paginate jobs |
| `GET` | `/api/jobs/{job_id}` | Get job detail |
| `POST` | `/api/agent/query` | Execute one Agent run |

Semantic Job Knowledge Retrieval 当前作为 Agent Tool 提供，没有额外暴露独立 Retrieval HTTP endpoint。

`POST /api/crawl` 当前只执行 Mock 数据采集。

OPPO real-source ingestion 通过独立 source adapter / composition 使用，目前没有暴露公共 HTTP trigger。

---

## Quick Start

### Option 1 — Docker Compose

Clone repository:

```bash
git clone https://github.com/luyangzhan111/internscout-agent.git
cd internscout-agent
```

创建环境变量文件：

```powershell
Copy-Item .env.example .env
```

根据需要填写 DeepSeek / Embedding 配置。

校验 Docker Compose：

```bash
docker compose config --quiet
```

启动：

```bash
docker compose up --build
```

启动后初始化本地 Demo 数据：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/crawl
```

访问：

```text
FastAPI Backend
http://127.0.0.1:8000

Streamlit Demo
http://127.0.0.1:8501
```

完整部署说明：

[`docs/deployment.md`](docs/deployment.md)

---

### Option 2 — Local Python

创建虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动 FastAPI：

```powershell
python -m uvicorn app.main:app --reload
```

初始化本地岗位数据：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/crawl
```

启动 Streamlit：

```powershell
streamlit run demo/app.py
```

---

## Provider Configuration

使用真实 DeepSeek Provider 时需要配置：

```text
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
```

启用 Semantic Retrieval 时还需要：

```text
INTERNSCOUT_EMBEDDING_API_KEY
INTERNSCOUT_EMBEDDING_BASE_URL
```

默认配置：

```text
INTERNSCOUT_EMBEDDING_MODEL=text-embedding-v4
INTERNSCOUT_EMBEDDING_DIMENSIONS=1024
```

Embedding configuration 是可选能力。

如果 Embedding Provider 没有配置或不可用：

- FastAPI 仍然可以启动；
- Agent 仍然提供默认三个 Tools：
  - `search_jobs`
  - `get_job_detail`
  - `match_jobs`

只有 Retrieval Runtime ready 时才加入：

```text
retrieve_job_knowledge
```

---

## Project Structure

```text
internscout-agent/
│
├── app/
│   ├── agent/              # Agent runtime, tools, providers
│   ├── database/           # SQLAlchemy, repositories, query adapters
│   ├── matching/           # Candidate-job deterministic matching
│   ├── rag/                # Semantic retrieval and vector abstractions
│   ├── routers/            # FastAPI endpoints
│   └── ...
│
├── demo/                   # Streamlit product demo
├── evals/                  # Agent / Retrieval evaluation datasets
├── tests/                  # Automated test suites
├── docs/                   # Deployment and project documentation
├── .github/workflows/      # GitHub Actions CI
│
├── Dockerfile.backend
├── Dockerfile.demo
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Key Engineering Decisions

### Why not let the LLM calculate match scores?

LLM-generated scores are difficult to reproduce and test.

InternScout therefore keeps:

```text
Match Score = Deterministic Application Logic
```

while the model focuses on orchestration and natural-language interaction.

---

### Why doesn't Retrieval replace Matching?

Semantic similarity and candidate-job suitability are different problems.

Retrieval answers:

> “Which job descriptions are semantically relevant to this query?”

Matching answers:

> “Based on known candidate skills and structured job evidence, how well does this candidate match this job?”

Keeping them separate improves:

- explainability
- testability
- stability
- architectural clarity

---

### Why abstract EmbeddingProvider and VectorStore?

The retrieval domain should not depend directly on one embedding vendor or one vector database.

Therefore the application depends on:

```text
EmbeddingProvider
VectorStore
```

rather than concrete infrastructure.

Current implementation uses an in-memory vector store, while the abstraction leaves room for replacing infrastructure without rewriting the retrieval domain.

---

### Why lazy build-then-swap?

Embedding every job during application startup or ingestion would tightly couple retrieval availability to the core application path.

The Runtime instead:

```text
mark_dirty()
    ↓
lazy rebuild
    ↓
build new retriever
    ↓
successful?
    ↓
swap
```

A failed refresh therefore does not automatically destroy the previously working retrieval state.

---

## Current Scope & Boundaries

InternScout Agent `v1.1.0` intentionally remains a portfolio-scale AI application.

Current boundaries:

- SQLite is the only application database.
- No database migration system.
- `POST /api/crawl` currently triggers Mock ingestion only.
- OPPO integration depends on observed recruitment-site interfaces and may require adapter changes if external schemas change.
- Agent runs are request-scoped and do not provide persistent conversation memory.
- Tool execution is sequential.
- No Multi-Agent runtime.
- No parallel Agent execution.
- `InMemoryVectorStore` is process-local.
- No persistent external vector database.
- Retrieval indexing is lazy.
- Retrieval remains optional when embedding configuration is unavailable.
- Controlled Retrieval Evaluation is not a real embedding-quality benchmark.
- Product Demo uses local / Mock job data by default.
- No public production deployment.

These boundaries are intentional for the current portfolio release and are not presented as production-scale capabilities.

---

## Release

Latest portfolio release:

### [`v1.1.0`](https://github.com/luyangzhan111/internscout-agent/releases/tag/v1.1.0)

Release verification includes:

```text
Full regression             710 passed
Agent evaluation              9 cases
Direct retrieval              6 cases
Agent retrieval integration   2 cases
GitHub Actions CI             PASS
Docker Compose validation     PASS
```

---

## Project Status

**InternScout Agent v1.1.0 is feature-complete for the current portfolio scope.**

The current focus is maintaining a stable, reproducible release rather than continuously expanding feature scope.