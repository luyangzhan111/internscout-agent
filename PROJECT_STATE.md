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
- OpenAI Python SDK（作为 DeepSeek OpenAI-compatible API 客户端）
- DeepSeek Responses API
- Git、GitHub、Codex、VS Code

开发环境：Windows、PowerShell、Python Virtual Environment（.venv）。不使用 requests。

# 3. Current Version Identity

## Stage 10 Merge Identity

Short: 9c8b2ba

Full: 9c8b2bac6bdcb417e62ef0051d8c6a43ee38da5c

Corresponding merge: Merge pull request #10 from luyangzhan111/feat/stage-10-oppo-source-integration

Merge commit message: Stage 10: integrate OPPO real recruitment source

## Snapshot Basis

Branch: main

Stage 10 merge commit: 9c8b2ba

Working tree before PROJECT_STATE update: clean

Post-merge full regression: 350 passed, 0 warnings

Targeted OPPO regression: 131 passed

The later PROJECT_STATE documentation commit does not replace the Stage 10 feature merge identity. Stage 9 merge identity 30062fc is historical, not current. Stage 8 identity 796db56 is historical.

# 4. Current Stage

## 已完成阶段

Stage 0 ～ Stage 10

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

## Next Stage

Stage 11

Specific Goal: UNKNOWN

Stage 11 必须从 repository reality 开始正式 Planning；本快照不猜测 Stage 11 roadmap，也不开始 Stage 11 规划。

# 5. Implemented Backend Capabilities

## FastAPI and job data

当前 HTTP API：GET /、GET /api/health、POST /api/crawl、GET /api/jobs、GET /api/jobs/{job_id}、POST /api/agent/query。

POST /api/agent/query 表示每个 request 触发一次独立、无持久会话的 Agent run。公共 response 只包含 answer、steps、tool_execution_count；它不是 persistent chat，也不暴露内部 ToolExecution trace。

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

Agent Layer 位于 app/agent/，提供 provider-neutral Tool-Calling Runtime。AgentState 仅存在于单次 run；BaseTool、ToolRegistry、JobQueryPort 与 RepositoryJobQueryAdapter 保持既有边界。当前 Job Tools 为 SearchJobsTool 与 GetJobDetailTool，仅支持 Sequential Tool Calling。

# 7. Application Composition and HTTP Boundary

FastAPI composition root：app/api/dependencies.py。Provider construction 是 lazy 的。环境变量为 DEEPSEEK_API_KEY、DEEPSEEK_MODEL；不记录或暴露 API key value。

# 8. Real LLM Provider Layer

文件：app/agent/providers/deepseek_client.py；Class：DeepSeekModelClient。AgentOrchestrator → ModelClient → DeepSeekModelClient → DeepSeek Responses API。Provider-specific code 不进入 Agent Runtime、Tool System、Database 或 FastAPI route。DeepSeekModelClient 是 stateless；当前不实现 Retry、reasoning continuity 或 provider conversation persistence。

# 9. Current Architecture

Mock route path：POST /api/crawl → MockJobCrawler → ingest_jobs。

Real-source integration path：explicit composition → httpx.Client → OppoJobSourceClient → OppoJobCrawler → ingest_jobs。

Shared downstream：Repository → SQLite → Jobs API / Agent Tools。

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

- Source client: 117 passed
- Crawler: 13 passed
- Ingestion: 1 passed
- Combined Stage 10 OPPO: 131 passed
- Full project: 350 passed
- Warnings: 0
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
PROJECT_STATE.md
README.md
app/__init__.py
app/agent/__init__.py
app/agent/contracts.py
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
app/workflows/__init__.py
app/workflows/job_ingestion.py
docs/codex-workflow.md
docs/development-log.md
docs/stage-reviews/stage-01-review.md through stage-10-review.md
docs/tasks/stage-08-task.md
docs/tasks/stage-09-task.md
docs/tasks/stage-10-task.md
requirements.txt
tests/agent/__init__.py
tests/agent/fakes/__init__.py
tests/agent/fakes/fake_model_client.py
tests/agent/providers/__init__.py
tests/agent/providers/test_deepseek_client.py
tests/agent/test_agent_exceptions.py
tests/agent/test_base_tool.py
tests/agent/test_contracts.py
tests/agent/test_job_tools.py
tests/agent/test_model_client.py
tests/agent/test_orchestrator.py
tests/agent/test_state.py
tests/agent/test_tool_registry.py
tests/database/test_job_query_adapter.py
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

Current Stage documentation：docs/tasks/stage-10-task.md、docs/stage-reviews/stage-10-review.md、docs/development-log.md、docs/codex-workflow.md。

长期工作方式：Architecture-First + Codex-Driven Implementation + Human Verification。

Routine：Luna。High reasoning 用于 complex architecture、difficult debugging 和 Stage Final Read-Only Review。

Codex Git restrictions remain unchanged：默认禁止 git add、git commit、git push、PR、merge 与 branch deletion。事实优先级为 Repository Reality > Task docs > Chat history。

标准流：formal Planning from repository reality → feature branch → implementation → tests → Final Read-Only Review → Stage Review → Development Log → PR → merge → main regression → PROJECT_STATE → branch cleanup。

Next Stage 为 Stage 11，Specific Goal 为 UNKNOWN；必须先正式 Planning，不得从本快照推断或承诺未来功能。
