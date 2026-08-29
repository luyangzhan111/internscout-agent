# InternScout Agent — Current Project Snapshot

> 本文件是 InternScout Agent 当前状态的唯一项目快照（Current Project Snapshot）。它只保留当前仍然有效的项目身份、能力、架构、provider、Agent tools、retrieval、evaluation、deployment、testing、限制、下一阶段与长期工程约束；它不是 development log、changelog、debug transcript、commit history、tutorial 或 interview review document。

## 1. Project Identity and Release Status

InternScout Agent 是一个面向软件工程、AI 与 Agent 实习岗位的信息采集、处理、存储、查询与智能分析的 AI Agent / AI application portfolio project。

核心闭环：

```text
job ingestion
→ normalization
→ persistence
→ structured query
→ deterministic candidate-job matching
→ semantic job knowledge retrieval
→ Agent tool orchestration
→ FastAPI
→ Streamlit Demo
→ deterministic evaluation / CI
→ local Docker Compose
```

- Previous released baseline: `v1.0.0`（tag 已存在并保持冻结）。
- Current portfolio / product version: `v1.1.0`。
- Current release line: `main` / `v1.1.0`。
- PR #14 已 merge into `main`；PR merge commit 为 `16313c1`，merged feature head 为 `bfc3fd5`，merge tree 与 reviewed feature tree 一致。
- FastAPI application metadata version 仍为 `0.1.0`；本次 snapshot 更新不修改 production code。

## 2. Current Stage Status

- Stage 0–13: complete。
- Stage 13.5: complete / release-ready。
- PR #14: merged into `main`。
- Release validation: complete。

## 3. Current Capabilities

### Job ingestion

- `BaseJobCrawler`、`MockJobCrawler` 与本地 sample fixture。
- OPPO explicit real-source adapter：`OppoJobSourceClient` / `OppoJobCrawler`。
- cleaning、normalization、deduplication 与 SQLite persistence。
- 默认 `POST /api/crawl` 使用 `MockJobCrawler`；OPPO adapter 需要显式组合调用。

### Query and API

- FastAPI health、crawl、job list/filter/pagination、job detail 与 Agent query。
- 当前 HTTP endpoints：`GET /`、`GET /api/health`、`POST /api/crawl`、`GET /api/jobs`、`GET /api/jobs/{job_id}`、`POST /api/agent/query`。
- `/api/agent/query` 每次请求触发一个独立的 request-scoped Agent run，不提供持久会话。

### Candidate matching

- `CandidateProfile`、`JobSkillExtractor`、`CandidateMatcher` 与 `JobMatchingService`。
- deterministic skill extraction、deterministic scoring、match reasons、city filtering 与 stable ranking。
- `MatchJobsTool` 委托 matching service；deterministic matching score 不由 LLM 拥有或替代。

### Agent runtime

- provider-neutral `AgentOrchestrator`、`ToolRegistry`、显式 tool contracts 与 sequential tool execution。
- `DeepSeekModelClient` 作为真实 provider adapter。
- `FakeModelClient` 用于 deterministic、offline tests/evaluations。

### Semantic job retrieval

- `JobDocument`、`EmbeddingProvider`、`FakeEmbeddingProvider` 与 `OpenAICompatibleEmbeddingProvider`。
- `VectorStore`、`InMemoryVectorStore`、`JobKnowledgeRetriever` 与 `RetrievalRuntime`。
- `RetrieveJobKnowledgeTool` 将岗位知识检索接入 Agent。
- Semantic retrieval 为非结构化岗位描述增加 evidence/retrieval，和 deterministic matching score 互补，不替代 deterministic matching。

### Evaluation

- Stage 12 Agent evaluation。
- Stage 13.5 direct retrieval evaluation。
- Stage 13.5 Agent retrieval integration evaluation。

### Deployment

- FastAPI Backend。
- Streamlit Product Demo。
- Docker Compose local topology。
- Backend `backend_data:/data` named volume 持久化 SQLite。

## 4. Architecture

项目保持分层：

```text
Streamlit Demo → FastAPI → Agent Runtime → Tools + Matching → Database
```

岗位 ingestion 的共享下游为：

```text
Crawler → cleaning / normalization / deduplication → SQLite
                                                        ↓
                                      Jobs API / Agent tools / retrieval snapshot
```

Deterministic matching 与 semantic retrieval 是互补的两层能力。项目的 retrieval 是 semantic job knowledge retrieval，不是 generic PDF RAG。

### Retrieval architecture

```text
JobRead
→ build_job_document()
→ EmbeddingProvider
→ VectorStore
→ JobKnowledgeRetriever
→ RetrieveJobKnowledgeTool
→ AgentOrchestrator
```

`JobDocument` searchable content 包含：`title`、`company`、`city`、`skills`、`description`。当前 metadata 仅包含 `job_id`、`company`、`city`；不把 `salary`、`published_at`、`source` 或 `source_url` 当作 searchable content 或 metadata。

`InMemoryVectorStore` 是 process-local in-memory store，使用 cosine similarity，按 score descending 排序；相同分数保持 deterministic insertion-order tie behavior。它不是 persistent vector DB、external vector database 或 distributed index。

### Agent tool registry

Default / no retriever 时固定为 3 个工具：

1. `search_jobs`
2. `get_job_detail`
3. `match_jobs`

Retrieval ready 时在上述工具之后增加：

4. `retrieve_job_knowledge`

因此 Agent 不固定拥有 4 tools；retrieval 不可用时保留三工具 fallback。运行时仍为 sequential tool execution，不实现 parallel tool execution 或 Multi-Agent runtime。

## 5. Retrieval Runtime and Provider Configuration

### RetrievalRuntime semantics

- Initial state：`dirty=True`，没有 retriever。
- `mark_dirty()`：只标记当前 index stale，不执行 embedding 或 rebuild。
- `rebuild()`：创建新的 vector store 与 retriever；完整构建成功后才 build-then-swap 当前 retriever。
- Refresh failure：保留旧 retriever，`dirty` 保持 `True`。
- First rebuild failure：没有可用 retriever；Agent 仍可使用默认三工具。
- FastAPI startup 只构造 optional runtime/provider，不 eager embedding 或 indexing 全部岗位。
- Agent request 遇到 dirty / not-ready runtime 时，通过完整 job snapshot 惰性 rebuild。
- 成功 crawl ingestion 之后调用 `mark_dirty()`；crawl 本身不做 embedding。

### Embedding provider

Production abstraction 为 `OpenAICompatibleEmbeddingProvider`，当前目标兼容 Alibaba Cloud Bailian / Model Studio 的 OpenAI-compatible embeddings endpoint（Bailian-compatible endpoint）。

配置接口：

- `INTERNSCOUT_EMBEDDING_API_KEY`
- `INTERNSCOUT_EMBEDDING_BASE_URL`
- optional `INTERNSCOUT_EMBEDDING_MODEL`，default `text-embedding-v4`
- optional `INTERNSCOUT_EMBEDDING_DIMENSIONS`，default `1024`

缺少 API key 或 base URL 时 retrieval disabled，FastAPI 与默认 Agent tools 仍可工作。当前 CI 不对真实 Bailian embedding quality 做 benchmark。

### DeepSeek provider decision

- Real LLM provider：DeepSeek。
- API：DeepSeek Responses API。
- Request reasoning：`{"effort": "none"}`。
- Provider 返回多个 function calls 时采用 provider-order first-call projection，执行一个 selected call，再由下一轮 model turn replans。
- Agent runtime 保持 sequential；不执行 parallel tool runtime，也不引入 multi-agent。

## 6. Evaluation and CI

### Stage 12 Agent Evaluation

使用 9 个 deterministic cases，metrics 为：

- `execution_outcome`
- `tool_selection`
- `tool_sequence`
- `tool_arguments`
- `tool_results`
- `answer_facts`

### Stage 13.5 Direct Retrieval Evaluation

使用 6 个 cases，采用 `ControlledEmbeddingProvider` 与 production `JobKnowledgeRetriever`，metrics 仅为：

- Hit@K
- Top-1

### Stage 13.5 Agent Retrieval Evaluation

使用 2 个 cases，通过 `FakeModelClient` scripted `ToolCall`、真实 Agent loop 与 production retrieval tool path 验证 Agent/retrieval integration。

`ControlledEmbeddingProvider` 是 evaluation-only deterministic semantic fixture，用于证明 controlled semantic retrieval pipeline 与 ranking regression；它不证明 Bailian general embedding quality。

Blocking CI evaluation 保持 offline、deterministic、secret-free、network-free，不使用真实 embedding provider call、DeepSeek API key、LLM judge、MRR 或 real embedding benchmark。

GitHub Actions 当前使用 Python 3.12，至少执行：

- `python -m pytest -q`
- `docker compose config --quiet`
- `docker compose build`

Retrieval evaluation gates 通过 normal pytest collection 进入现有 CI gate；没有独立 real-provider CI。

## 7. Deployment and Demo State

Docker Compose 当前真实状态：

- Backend：host port `8000`。
- Streamlit Demo：host port `8501`。
- SQLite URL：`sqlite:////data/internscout.db`。
- volume：`backend_data:/data`。
- Demo backend URL：`http://backend:8000`。
- DeepSeek env 与 embedding env 只传给 Backend。
- Embedding Compose defaults：model `text-embedding-v4`、dimensions `1024`。
- 缺少 embedding API key/base URL 时 retrieval disabled，FastAPI 仍可工作。

这代表 local Docker Compose reproducibility，不代表 public production deployment。

默认数据与 Demo：

- 默认 `POST /api/crawl` 使用 `MockJobCrawler` 与本地 sample fixture，sample fixture 为 6 jobs，不是 live recruitment feed。
- OPPO real-source adapter 已存在，但不是默认 `/api/crawl` 来源。
- Streamlit Demo 仅通过 HTTP client 调用 FastAPI；不直接访问 SQLite、Agent internals 或 provider secrets。
- 当前没有 dedicated retrieval UI；retrieval 通过 Agent tool 提供。

## 8. Security and Data Boundaries

- Provider secrets 通过 environment variables 注入。
- `.env` 被忽略，不提交真实密钥或 secret value。
- `DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL` 与 embedding credentials 均为 Backend-only configuration。
- Demo 不接收 provider key。
- 当前 SQLite persistence 使用本地数据库与 Compose named volume；默认 fixture 数据不代表实时招聘数据。

## 9. Current Test Baseline

Verified Stage 13.5 product regression baseline（reviewed feature / pre-merge full regression）：

- `tests/evaluation`: 95 passed。
- `tests/agent`: 139 passed。
- `tests/rag`: 58 passed。
- `tests/test_agent_api.py`: 22 passed。
- Full suite: `710 passed in 16.64s`，0 failed，0 errors。

Post-merge `main` validation：

- PR #14 GitHub Actions: SUCCESS。
- Merge tree 与 reviewed feature head `bfc3fd5` 一致。
- `tests/evaluation`: 95 passed。
- `tests/agent` + `tests/rag`: 197 passed。
- `git diff --check`: PASS。
- `docker compose config --quiet`: PASS。
- Full local rerun collected 710 tests：618 passed，0 failed，92 errors；errors 来自 Windows temporary-directory / SQLite ACL，分类为 CLASS D local environment issue，不是 product regression。
- Local `docker compose build` 未取得新的成功 evidence；Docker Desktop Linux engine / buildx local access failure 分类为 CLASS D local environment issue，不是 product blocker。

当前稳定 product baseline 是 reviewed Stage 13.5 full regression 的 `710 passed`；不能把 post-merge 本机 environment-limited rerun 表述为 `710 passed`。旧的 `570 passed` 不再作为 current baseline。

## 10. Known Limitations and Explicit Non-goals

- `InMemoryVectorStore` 仅为 process-local index。
- 没有 persistent external vector DB、distributed index 或其他持久向量数据库。
- Retrieval rebuild 在 Agent dependency path 上惰性执行。
- Embedding configuration 是 optional；缺少配置时 retrieval disabled。
- 没有 persistent conversation memory。
- 没有 Multi-Agent runtime 或 parallel tool execution。
- 默认 crawler 使用本地 fixture；没有 live recruitment feed。
- `/api/crawl` 不触发 OPPO real-source crawler；没有 public real-source HTTP trigger。
- OPPO 依赖 observed website/internal endpoints，source schema 可能变化。
- 当前没有 public production deployment。
- `ControlledEmbeddingProvider` 的 controlled semantic CI 不等于真实 provider benchmark，不提供 general embedding quality guarantee。
- SQLite 仍是当前数据库，暂无迁移系统；没有 scheduler、retry 或 partial-success policy。

Semantic job retrieval 已实现，不应再把 RAG 或 retrieval 列为不存在的能力。

## 11. Repository Inventory

以下只列当前 snapshot 相关的真实 tracked paths，不列 `__pycache__`、pytest temporary directories、database files 或 secrets：

- `app/rag/`
  - `contracts.py`
  - `document.py`
  - `embedding.py`
  - `retriever.py`
  - `runtime.py`
  - `vector_store.py`
- `evals/`
  - `retrieval_contracts.py`
  - `retrieval_dataset.py`
  - `retrieval_runner.py`
  - `retrieval_scorers.py`
  - `cases/retrieval_cases.jsonl`
  - `cases/retrieval_case.schema.json`
- `tests/rag/`
  - `test_contracts.py`
  - `test_document.py`
  - `test_embedding.py`
  - `test_openai_embedding.py`
  - `test_retriever.py`
  - `test_runtime.py`
  - `test_vector_store.py`
- `tests/evaluation/`
  - `retrieval_fixtures.py`
  - `test_agent_retrieval_gate.py`
  - `test_retrieval_dataset.py`
  - `test_retrieval_evaluation_gate.py`
  - `test_retrieval_fixtures.py`
  - `test_retrieval_runner.py`
  - `test_retrieval_scorers.py`
- Agent retrieval integration：
  - `app/agent/tools/retrieval_tool.py`
  - `app/agent/composition.py`
  - `app/api/dependencies.py`
  - `app/main.py`
- `docs/tasks/stage-13.5-task.md`
- `docs/tasks/stage-13.5g-retrieval-evaluation-task.md`
- `docs/deployment.md`
- `docker-compose.yml`
- `.github/workflows/ci.yml`

Current documentation state：

- README Stage 13.5 updated。
- `docs/deployment.md` Stage 13.5 updated。
- `PROJECT_STATE.md` is the current snapshot。
- `docs/stage-reviews/stage-13.5-review.md` exists and is complete。
- `docs/development-log.md` has the Stage 13.5 milestone appended。

## 12. Long-term Engineering Constraints

- Deterministic business logic stays outside the LLM。
- Agent orchestrates tools; it does not own the database or business rules。
- `ModelClient` abstraction isolates real providers。
- Tool contracts remain explicit and provider-neutral。
- Real providers remain optional where possible; offline tests stay deterministic。
- Retrieval supplements deterministic matching and does not replace its score。
- Provider secrets stay Backend-only。
- CI uses deterministic offline tests and validation gates。
- Preserve backward compatibility, especially the retrieval-disabled three-tool path。
- Avoid framework inflation without a demonstrated requirement。
