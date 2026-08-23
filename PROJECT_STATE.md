# InternScout Agent — Project State

> 本文件是 InternScout Agent 当前状态的唯一项目快照（Project Snapshot）。它记录仍然有效的项目能力、架构、技术决策、测试状态、限制、下一阶段与长期开发规范；它不是开发日志、完整 Debug 历史或 Stage Review。

---

# 1. Project Overview

InternScout Agent 是一个面向软件工程、AI 与 Agent 实习岗位的信息采集、处理、存储、查询与智能分析练习型软件工程项目。

当前已具备：

- 岗位数据模型、MockJobCrawler / sample HTML、数据清洗、去重与 SQLite 持久化
- 第一个已验证的真实招聘数据源：OPPO Careers
- OPPO Careers → OppoJobSourceClient → OppoJobCrawler → JobCreate → existing processing / persistence → Jobs API / Agent
- Repository 查询、REST API、筛选、分页与 HTTP 服务闭环
- provider-neutral Agent Contract、Tool System、Tool-Calling Agent Runtime 与 AgentOrchestrator
- Tool / Repository 的 Port / Adapter 解耦
- DeepSeek 真实 LLM Provider Adapter 与真实 Provider / Agent 验证
- CandidateProfile、JobSkillExtractor、CandidateMatcher 与 JobMatchingService
- MatchJobsTool 与 deterministic and explainable job matching
- Agent evaluation layer、offline evaluation runner 与 application composition factory
- Stage 12E Streamlit Product Demo、Demo HTTP client、Demo-side contracts 与 rendering layer
- `.env.example`、`INTERNSCOUT_DATABASE_URL` 与本地 / Compose 环境配置边界
- FastAPI Backend 与 Streamlit Demo 的 Docker images、Docker Compose topology 与 SQLite named volume persistence
- GitHub Actions 中的 pytest、Docker Compose 配置校验与 Docker image build 校验
- 自动化测试、Git / GitHub / Pull Request Workflow 与 Codex Review

项目当前不声称具备 multi-source orchestration、production scheduler、real-source HTTP trigger 或 distributed crawling。

# 2. Core Technology Stack

- Python 3.12
- FastAPI
- Pydantic
- BeautifulSoup
- SQLAlchemy 2.x
- SQLite
- httpx（OPPO real-source HTTP boundary）
- pytest
- Streamlit 1.48.1
- OpenAI Python SDK（作为 DeepSeek OpenAI-compatible API 客户端）
- DeepSeek Responses API
- Git、GitHub、Codex、VS Code

开发环境：Windows、PowerShell、Python Virtual Environment（.venv）。不使用 requests。

# 3. Current Version Identity

## Stage 11 Merge Identity

Short: e3b9b6c

Full: e3b9b6c0f33bd785103466c025b2b8072097eec5

Corresponding merge: Merge pull request #11 from luyangzhan111/feat/stage-11-candidate-job-matching

Merge commit message: feat: complete Stage 11 deterministic candidate job matching

## Snapshot Basis

Branch: main

Stage 12 merge commit: d77bbc3

Stage 12 merge commit full hash: d77bbc391613c886bffdd04ce522e4937451e117

Working tree before PROJECT_STATE update: clean

Post-merge full regression: 567 passed

Stage 11 merge identity e3b9b6c remains historical. Stage 10 merge identity 9c8b2ba is historical, not current. Stage 9 merge identity 30062fc is historical. Stage 8 identity 796db56 is historical.

Stage 10 historical regression facts remain: combined OPPO regression 131 passed；post-merge main regression 350 passed, 0 warnings。

## Stage 12 Merge Identity

Short: d77bbc3

Full: d77bbc391613c886bffdd04ce522e4937451e117

Corresponding merge: Merge pull request #12 from luyangzhan111/feat/stage-12-agent-evaluation-ci-demo

Merge commit message: feat: implement agent evaluation framework and GitHub Actions CI

## Stage 12E Merge Identity

Short: ae21931

Full: ae2193130dd480dc06d3cb245e464ba5ba0336cc

Corresponding merge: Merge pull request #13 from luyangzhan111/feat/stage-12e-product-demo

Merge commit message: feat: add Streamlit product demo for agent matching

## Stage 13 Integrated Identity

Integrated baseline branch: `main`

Configuration commit: `4403314` — `feat: support configurable database url`

Docker merge commit: `41b871a` — `Merge branch 'feat/stage13-docker'`

CI merge commit: `30614b0` — `Merge branch 'feat/stage13-ci'`

Documentation closeout branch: `feat/stage13-docs`

# 4. Current Stage

## 已完成阶段

Stage 0 ～ Stage 13

## Stage 10 状态

Implementation: COMPLETE
Real Source Integration: PASS
Real OPPO Discovery / Detail: PASS
Real Ingestion: PASS
Jobs API Verification: PASS
Real DeepSeek Agent E2E: PASS
Final Review: PASS
MUST FIX: 0
SHOULD FIX: 0
Post-merge main regression: PASS

## Stage 11 状态

Implementation: COMPLETE
Deterministic Candidate / Job Matching: PASS
Agent MatchJobsTool Integration: PASS
Real Stage 11G Verification: PASS
Final Review: PASS
Post-merge main regression: PASS
MUST FIX: 0
SHOULD FIX: 0

Regression:
503 passed, 0 warnings

## Stage 12A-D 状态

Implementation: COMPLETE
Evaluation Layer: PASS
Composition Factory: PASS
GitHub Actions CI: PASS
Post-merge main regression: PASS

Historical regression before Stage 12E:
`python -m pytest -q` => 551 passed

## Stage 12E 状态

Implementation: COMPLETE
Optional Agent recommendation projection: PASS
Streamlit Product Demo: PASS
Demo HTTP client / contracts / rendering: PASS
Dependency resolution (`streamlit==1.48.1`, `packaging==25.0`): PASS
Streamlit runtime smoke: PASS
Streamlit → FastAPI → Agent Runtime → match_jobs → Matching → local SQLite → UI: PASS
GitHub Actions CI: PASS
PR #13 merge: PASS
MUST FIX: 0
SHOULD FIX: 0

Authoritative regression before Stage 13 documentation closeout:
`python -m pytest -q` => 567 passed

## Stage 13 状态

Implementation: COMPLETE for the integrated configuration, Docker, Compose, and CI changes

Environment configuration: PASS — `.env.example` and `INTERNSCOUT_DATABASE_URL` support are present

Docker capability: PASS — separate Backend and Demo Dockerfiles, Compose services, service networking, and SQLite named volume are present

Docker Compose configuration: PASS — `docker compose config --quiet`

Docker image build: NOT LOCALLY VERIFIED IN THIS DOCUMENTATION CLOSEOUT

CI capability: PRESENT — GitHub Actions defines pytest and Docker validation jobs; an execution result is not recorded here

Public or production deployment: NOT CLAIMED

Documentation closeout: COMPLETE IN WORKING TREE on `feat/stage13-docs`

Stage 13 implementation branches and their integrated commits are recorded above. The documentation branch has not been committed or merged by this task.

## Next Stage

Specific Goal: UNKNOWN

Stage 13 已完成配置、Docker、Compose、CI 与本地部署文档工作；下一阶段尚未定义。

# 5. Implemented Backend Capabilities

## Stage 11 candidate / job matching

Stage 11 matching components：CandidateProfile、JobSkillExtractor、CandidateMatcher、JobMatchingService、MatchJobsTool。

组件职责与边界：

- CandidateProfile：验证并确定性规范化 request-scoped candidate skills 与 preferred cities。
- JobSkillExtractor：从岗位 structured skills、title 与 description 中提取确定性技能证据。
- CandidateMatcher：纯确定性计算 matched skills、missing skills、match score 与 reason。
- JobMatchingService：通过 JobQueryPort 获取候选岗位，执行 city eligibility、matching、stable ranking 与 top_k 截断。
- MatchJobsTool：作为只读 Agent Tool 验证输入并委托 JobMatchingService，不在 Tool 或 LLM 中复制 scoring 与 ranking logic。

当前能力：

- deterministic skill extraction
- explainable matching score
- matched/missing skill analysis
- city filtering
- deterministic ranking

## Stage 12 evaluation and composition

- `app/agent/composition.py` 提供 `create_agent_orchestrator`，集中构造 request-scoped Agent Runtime object graph。
- `evals/` 提供 evaluation contracts、dataset loading、offline runner 与 deterministic scorers。
- Evaluation runner 通过注入的 ModelClientFactory 与 JobQueryFactory 执行离线 evaluation cases。

## Stage 12E product demo

- `demo/app.py` 提供 Streamlit UI，收集候选人技能与意向城市并渲染推荐结果。
- `demo/client.py` 仅通过 HTTP 调用现有 `POST /api/agent/query`。
- `demo/contracts.py` 校验 Demo-side response contract；`demo/rendering.py` 负责展示转换。
- Demo 默认消费 local SQLite 中已有岗位数据；Demo 数据不是实时招聘网站数据。
- OPPO real-source ingestion capability 独立存在，不等同于默认 Demo 数据来源。

## FastAPI and job data

当前 HTTP API：GET /、GET /api/health、POST /api/crawl、GET /api/jobs、GET /api/jobs/{job_id}、POST /api/agent/query。

POST /api/agent/query 表示每个 request 触发一次独立、无持久会话的 Agent run。请求可通过 `include_recommendations=true` opt in 结构化 `match_jobs` 推荐投影；默认仍只返回 answer、steps、tool_execution_count。它不是 persistent chat，也不暴露内部 ToolExecution trace。

岗位服务支持健康与数据库检查、模拟岗位采集、岗位列表与详情查询、城市 / 公司 / 技能筛选、组合筛选与分页。岗位核心数据由 Pydantic 验证，数据库内部 identity_key 不向 API 或 Agent Tool 暴露。

## Crawling, cleaning and persistence

项目同时包含 MockJobCrawler 和 OppoJobCrawler。POST /api/crawl 仍为 mock-specific，仅执行 MockJobCrawler；HTTP clients 当前不能通过该端点触发真实 OPPO crawler。

真实 OPPO 路径：OPPO Careers → OppoJobSourceClient → OppoJobCrawler → JobCreate → process_jobs → Cleaning + Deduplication → ingest_jobs → Repository → SQLite。

MockJobCrawler 仍从 app/fixtures/sample_jobs.html 读取模拟招聘页面。当前 identity key 仍为 normalized company + title + city；Cleaning、Deduplication、Repository 与 SQLite 边界保持既有行为。

## Real source layer

app/crawlers/oppo_source_client.py symbols：OppoJobSourceClient、OppoPositionSummary、OppoPositionPage、OppoPositionDetail。

app/crawlers/oppo_crawler.py symbol：OppoJobCrawler。

架构：caller-owned synchronous httpx.Client → OppoJobSourceClient → typed OPPO source data → OppoJobCrawler → JobCreate。

Source Client 负责 HTTP、timeout、status handling、JSON envelope validation、pagination validation 与 detail validation；它不感知 persistence、API 或 Agent。Crawler 负责 source query policy、finite pagination、detail ordering 与 JobCreate mapping；它不拥有 HTTP implementation。

# 6. Agent Layer

Agent Layer 位于 app/agent/，提供 provider-neutral Tool-Calling Runtime。AgentState 仅存在于单次 run；BaseTool、ToolRegistry、JobQueryPort 与 RepositoryJobQueryAdapter 保持既有边界。

当前 Job Tools：

- SearchJobsTool
- GetJobDetailTool
- MatchJobsTool

当前仅支持 Sequential Tool Calling。

# 7. Application Composition and HTTP Boundary

FastAPI composition root：app/api/dependencies.py。Agent application composition factory：app/agent/composition.py。Provider construction 是 lazy 的。环境变量为 DEEPSEEK_API_KEY、DEEPSEEK_MODEL；不记录或暴露 API key value。

# 8. Real LLM Provider Layer

文件：app/agent/providers/deepseek_client.py；Class：DeepSeekModelClient。AgentOrchestrator → ModelClient → DeepSeekModelClient → DeepSeek Responses API。Provider-specific code 不进入 Agent Runtime、Tool System、Database 或 FastAPI route。DeepSeekModelClient 是 stateless；当前不实现 Retry、reasoning continuity 或 provider conversation persistence。

# 9. Current Architecture

Mock route path：POST /api/crawl → MockJobCrawler → ingest_jobs。

Real-source integration path：explicit composition → httpx.Client → OppoJobSourceClient → OppoJobCrawler → ingest_jobs。

Shared downstream：Repository → SQLite → Jobs API / Agent Tools。

Stage 11 matching path：

CandidateProfile
↓
JobMatchingService
↓
JobQueryPort
↓
Repository
↓
MatchJobsTool
↓
AgentOrchestrator
↓
DeepSeek explanation

真实 OPPO 已集成，但 /api/crawl 仍为 mock-specific；既有 HTTP / Agent paths 保持不变。

# 10. Frozen Architecture Decisions

Stage 7–9 decisions retained：AgentOrchestrator remains provider-neutral；AgentState is per-run；ModelClient、BaseTool、ToolRegistry、JobQueryPort 与 RepositoryJobQueryAdapter 保持既有边界；DeepSeek isolated behind ModelClient and stateless；no parallel tool execution；real provider verification 与 pytest 分离；/api/agent/query 是一次 stateless Agent run。

Stage 10 decisions：

- External source HTTP/schema knowledge stays in OppoJobSourceClient。
- OppoJobCrawler maps typed source data to existing JobCreate。
- Real-source integration reuses process_jobs / ingest_jobs / Repository。
- Source mapping and domain cleaning remain separate。
- OppoJobCrawler preserves raw city；Cleaner owns normalization。
- Automated source tests remain network-free；real external verification is separate from pytest。
- Caller owns httpx.Client lifecycle。
- No retry or partial-success policy in Stage 10。
- /api/crawl remains mock-specific。
- No database identity redesign。
- No cross-page exact metadata equality assumption。

Stage 12 decisions：

- Agent Runtime object graph construction is centralized in `create_agent_orchestrator`。
- Evaluation runs use injected offline ModelClient and JobQuery factories。
- GitHub Actions runs the full `python -m pytest -q` suite on push and pull requests targeting `main`。

Stage 12E decisions：

- Reuse the existing `POST /api/agent/query`; do not introduce a new recommendation endpoint。
- Recommendation projection is opt-in through `include_recommendations` and does not alter Agent Runtime or matching logic。
- Streamlit communicates only with FastAPI through the Demo HTTP client。
- Demo presentation owns validation and rendering only; it does not query SQLite or execute matching directly。
- Default Demo data is local SQLite / MockJobCrawler data, not real-time recruiting website data。
- OPPO real-source ingestion remains a separate capability；`POST /api/crawl` remains MockJobCrawler-specific。

Stage 13 decisions：

- `INTERNSCOUT_DATABASE_URL` is the supported database URL override; the direct local default remains `sqlite:///./internscout.db`。
- Compose uses `sqlite:////data/internscout.db` in the Backend container and persists `/data` through the `backend_data` named volume。
- Compose contains two services: `backend` and `demo`；the Demo reaches the Backend through `http://backend:8000` and does not receive DeepSeek secrets。
- Stage 13 adds local container reproducibility and validation；it does not claim public or production deployment。

# 11. OPPO Source Contract and Defensive Rules

以下是 observed website/internal JSON endpoints，不是 officially supported public developer API：

Discovery endpoint: POST https://career.oppo.com/ats-candidate-api/open-api/position/queryPositionList

Detail endpoint: GET https://career.oppo.com/ats-candidate-api/open-api/position/queryPosition

Human source URL: https://career.oppo.com/official/oppo/recruitment/post/{position_id}?recruitType={recruit_type}

source_url 存储 human recruitment page。

- Success code 仅接受 0 或 "0"。
- Discovery total 接受 non-negative int 或 canonical non-negative ASCII decimal string；string total normalizes to int。
- pageNum、pageSize、pages 保持 strict int-only。
- Source Reality > Fixture Assumptions。

分页数据完整性规则：当 pages > 0 时，maximum_representable_total = (pages - 1) * returned_page_size + len(raw_positions)。若 total > maximum_representable_total 则拒绝。该规则防止 metadata 导致 silent truncation；不强制 cross-page total equality、cross-page pages equality、full pages 或 accumulated crawler count。

# 12. Automated Testing, Review, and Real Verification

Current authoritative baseline：

- Stage 13 recorded regression baseline: `python -m pytest -q` => 570 passed
- Documentation-closeout rerun: environment-blocked after 486 passed and 84 `tmp_path` setup errors caused by Windows `WinError 5` permissions
- Docker Compose configuration: `docker compose config --quiet` => PASS
- Docker image build: NOT LOCALLY VERIFIED IN THIS DOCUMENTATION CLOSEOUT
- Stage 12E post-merge main regression: PASS
- Stage 12E GitHub Actions CI: PASS
- Stage 12E Streamlit runtime smoke: PASS
- Stage 12E full Demo chain through local SQLite to UI: PASS
- Final Stage 11 Review: PASS；MUST FIX = 0；SHOULD FIX = 0
- Real Stage 11G Verification: PASS

Stage 10 historical baseline：

- Source client: 117 passed
- Crawler: 13 passed
- Ingestion: 1 passed
- Combined Stage 10 OPPO: 131 passed
- Full project: 350 passed, 0 warnings
- Post-merge main regression: 350 passed, 0 warnings
- Final Stage 10 Review: MUST FIX = 0；SHOULD FIX = 0

Real Stage 10 verification：

- Real OPPO discovery/detail: PASS
- Position: 2061649545671430146 / AI产品实习生 / 东莞市 / 2026-06-01 / OFFEN-RECRUITMENT
- Real ingestion: PASS；Persisted city: 东莞
- GET /api/jobs: 200；GET /api/jobs/1: 200
- Provider: DeepSeek；Model: deepseek-v4-flash
- POST /api/agent/query: 200；steps: 2；tool_execution_count: 1；Tool: search_jobs
- Persisted OPPO data consumed: YES

真实验证不记录或暴露 API key 内容。

# 13. Current Limitations

- Demo 默认使用 local SQLite 中已有岗位数据，不表示实时招聘网站数据。
- OPPO real-source ingestion capability 与默认 Demo 数据来源不同；OPPO 仍不是 `/api/crawl` 的触发来源。
- Demo 可通过分别运行的 Python 进程或 Docker Compose 在本地运行；未部署到公网或生产环境。
- Mock HTML remains supported, but OPPO is the first real source。
- OPPO 使用 observed website/internal JSON endpoints，source schema may change。
- No production HTTP trigger for real OPPO crawling；/api/crawl remains MockJobCrawler-specific。
- No retry、partial success、scheduler 或 multi-source orchestration。
- Existing identity key remains normalized company + title + city；distinct OPPO position IDs with identical normalized identity may collapse。
- SQLite remains the database；no Alembic migration。
- No Memory / RAG / Vector DB / Streaming / Parallel Tool Calling / Multi-Agent / Persistent Conversation / reasoning continuity / token-cost accounting。

# 14. Repository Tree

以下为当前真实 tracked files（由 git ls-files 确认）：

.gitattributes
.gitignore
.github/workflows/ci.yml
PROJECT_STATE.md
README.md
app/__init__.py
app/agent/__init__.py
app/agent/contracts.py
app/agent/composition.py
app/agent/exceptions.py
app/agent/model_client.py
app/agent/orchestrator.py
app/agent/providers/__init__.py
app/agent/providers/deepseek_client.py
app/agent/state.py
app/agent/tools/__init__.py
app/agent/tools/base.py
app/agent/tools/job_query.py
app/agent/tools/job_tools.py
app/agent/tools/matching_tool.py
app/agent/tools/registry.py
app/api/__init__.py
app/api/dependencies.py
app/api/routes/__init__.py
app/api/routes/agent.py
app/api/routes/crawl.py
app/api/routes/health.py
app/api/routes/jobs.py
app/crawlers/__init__.py
app/crawlers/base.py
app/crawlers/mock_crawler.py
app/crawlers/oppo_crawler.py
app/crawlers/oppo_source_client.py
app/database/__init__.py
app/database/job_query_adapter.py
app/database/models.py
app/database/repository.py
app/database/session.py
app/fixtures/sample_jobs.html
app/main.py
app/matching/__init__.py
app/matching/contracts.py
app/matching/matcher.py
app/matching/service.py
app/matching/skill_extractor.py
app/schemas/__init__.py
app/schemas/agent.py
app/schemas/crawl_response.py
app/schemas/health_response.py
app/schemas/job.py
app/schemas/job_response.py
app/services/__init__.py
app/services/cleaner.py
app/services/deduplicator.py
app/services/processor.py
app/services/skill_vocabulary.py
app/workflows/__init__.py
app/workflows/job_ingestion.py
demo/__init__.py
demo/app.py
demo/client.py
demo/contracts.py
demo/rendering.py
docs/codex-workflow.md
docs/development-log.md
docs/stage-reviews/stage-01-review.md through stage-12-review.md
docs/tasks/stage-08-task.md
docs/tasks/stage-09-task.md
docs/tasks/stage-10-task.md
docs/tasks/stage-11-task.md
docs/tasks/stage-12-task.md
docs/tasks/stage-12e-task.md
requirements.txt
evals/__init__.py
evals/contracts.py
evals/dataset.py
evals/runner.py
evals/scorers.py
evals/cases/agent_case.schema.json
evals/cases/agent_cases.jsonl
tests/agent/__init__.py
tests/agent/fakes/__init__.py
tests/agent/fakes/fake_model_client.py
tests/agent/providers/__init__.py
tests/agent/providers/test_deepseek_client.py
tests/agent/test_agent_exceptions.py
tests/agent/test_base_tool.py
tests/agent/test_composition.py
tests/agent/test_contracts.py
tests/agent/test_job_tools.py
tests/agent/test_matching_tool.py
tests/agent/test_model_client.py
tests/agent/test_orchestrator.py
tests/agent/test_state.py
tests/agent/test_tool_registry.py
tests/database/test_job_query_adapter.py
tests/demo/test_client.py
tests/demo/test_contracts.py
tests/demo/test_rendering.py
tests/evaluation/__init__.py
tests/evaluation/test_contracts.py
tests/evaluation/test_dataset.py
tests/evaluation/test_evaluation_gate.py
tests/evaluation/test_runner.py
tests/evaluation/test_scorers.py
tests/matching/__init__.py
tests/matching/test_contracts.py
tests/matching/test_matcher.py
tests/matching/test_service.py
tests/matching/test_skill_extractor.py
tests/test_agent_api.py
tests/test_cleaner.py
tests/test_crawl_api.py
tests/test_database.py
tests/test_database_session.py
tests/test_deduplicator.py
tests/test_health.py
tests/test_job_api.py
tests/test_job_detail_api.py
tests/test_job_ingestion.py
tests/test_job_query_repository.py
tests/test_job_repository.py
tests/test_job_response_schema.py
tests/test_job_schema.py
tests/test_mock_crawler.py
tests/test_oppo_crawler.py
tests/test_oppo_ingestion.py
tests/test_oppo_source_client.py
tests/test_processor.py
tests/test_stage6_api_flow.py

.venv、pytest temp directories、.pytest_cache、database temporary files 与 secrets 不属于 tree。

# 15. Current Documentation and Development Workflow

Current Stage documentation：docs/tasks/stage-12-task.md、docs/tasks/stage-12e-task.md、docs/tasks/stage-13-task.md、docs/tasks/stage-13-multi-agent-plan.md、docs/stage-reviews/stage-12-review.md、docs/stage-reviews/stage-11-review.md、docs/deployment.md、docs/development-log.md、docs/codex-workflow.md。

长期工作方式：Architecture-First + Codex-Driven Implementation + Human Verification。

Routine：Luna。High reasoning 用于 complex architecture、difficult debugging 和 Stage Final Read-Only Review。

Codex Git restrictions remain unchanged：默认禁止 git add、git commit、git push、PR、merge 与 branch deletion。事实优先级为 Repository Reality > Task docs > Chat history。

标准流：formal Planning from repository reality → feature branch → implementation → tests → Final Read-Only Review → Stage Review → Development Log → PR → merge → main regression → PROJECT_STATE → branch cleanup。

Stage 13 documentation closeout is present in the working tree; no subsequent stage or goal has been defined。
