# Stage 12 Review — Agent Evaluation / CI

## Goal

Stage 12 focuses on improving InternScout Agent engineering reliability by adding deterministic Agent evaluation, reusable Agent composition, and automated CI verification.

The goal is to make the Agent system:

- measurable;
- regression-testable;
- maintainable;
- closer to a production AI application engineering workflow.

---

## Completed Work

## 1. Agent Composition Factory

Added:

app/agent/composition.py

Responsibilities:

- Centralize Agent object construction.
- Build Agent application object graph.
- Create JobMatchingService.
- Register Agent Tools.
- Create ToolRegistry.
- Create AgentOrchestrator.

Updated:

app/api/dependencies.py

Changes:

- Kept FastAPI dependency responsibilities.
- Kept Session lifecycle management.
- Kept DeepSeek configuration handling.
- Removed duplicated Agent construction logic.
- Reused Composition Factory.

Architecture boundary:

FastAPI Dependency Layer
    ↓
Agent Composition Factory
    ↓
Agent Runtime

---

## 2. Deterministic Agent Evaluation Framework

Added:

evals/

Implemented:

- Evaluation contracts.
- Dataset loader.
- Evaluation runner.
- Deterministic scorers.

Evaluation validates:

- Tool selection.
- Tool execution sequence.
- Tool arguments.
- Tool results.
- Answer grounding facts.

Evaluation runs offline with:

FakeModelClient

The evaluation framework does not modify:

- AgentOrchestrator.
- ModelClient.
- Tool implementations.
- Matching logic.
- FastAPI API contracts.

---

## 3. Evaluation Dataset

Added deterministic evaluation cases covering:

- search_jobs.
- get_job_detail.
- match_jobs.
- empty results.
- missing jobs.
- invalid tool arguments.
- controlled tool failures.
- unknown tools.

Dataset purpose:

Provide stable regression scenarios for Agent behavior verification.

---

## 4. GitHub Actions CI

Added:

.github/workflows/ci.yml

CI workflow:

- Uses Python 3.12.
- Installs dependencies from requirements.txt.
- Runs the complete pytest suite.

Command:

```bash
python -m pytest -q
CI does not require:
- DeepSeek API.
- Production database.
- External services.
- Local development environment.
Testing
Local Regression
Command:
python -m pytest -q
Result:
551 passed
GitHub Actions
Status:
PASS
CI successfully validates the project in a clean environment.
Architecture Decisions
Stage 12 keeps Evaluation separated from Agent Runtime.
Evaluation directly uses:
- AgentOrchestrator.
- AgentResult.
- ToolExecution trace.
Evaluation does not depend on:
- HTTP API layer.
- Provider SDK.
- Production infrastructure.
Design decisions:
- Deterministic offline evaluation is the default regression strategy.
- FakeModelClient is used for CI evaluation.
- Live Provider evaluation is separated from blocking CI.
- Evaluation failures should identify specific behavior regressions.
Risks Controlled
Stage 12 addresses several engineering risks:
Agent behavior regression
Controlled through:
- deterministic evaluation dataset;
- scorer validation;
- CI gate.
Production and evaluation composition drift
Controlled through:
- Agent Composition Factory.
Unstable model evaluation
Controlled through:
- offline FakeModelClient based evaluation.
CI dependency on external services
Controlled through:
- no live API calls;
- no production database usage.
Final Result
Stage 12 completed successfully.
New capabilities:
- Agent Composition Factory.
- Deterministic Agent Evaluation Framework.
- Evaluation Dataset.
- Evaluation Runner.
- Deterministic Scorer System.
- GitHub Actions CI.
- Offline Evaluation Gate.
Final validation:
python -m pytest -q

551 passed
Stage 12 successfully improves InternScout Agent from a functional Agent application into a measurable and maintainable AI application engineering project.

---

# Stage 12E — Basic Product Demo

## Goal

Stage 12E productizes the existing Agent matching capability as a minimal, runnable Streamlit demonstration. The Demo is an interaction and presentation layer; it does not introduce a new Agent Runtime, matching algorithm, or public deployment.

The default Demo data boundary is local SQLite data already available to the Backend. Demo data is not real-time recruiting website data. OPPO real-source ingestion remains a separate capability, and `POST /api/crawl` remains MockJobCrawler-specific.

## API Contract Extension

The existing `POST /api/agent/query` contract was extended without introducing a new recommendation endpoint.

- Request field `include_recommendations: bool` was added with default `false`.
- When enabled, the API projects the latest successful `match_jobs` result into `recommendations`.
- When no successful `match_jobs` result exists, the opt-in response contains an empty recommendation list.
- When disabled, the optional field is omitted and the legacy response shape remains valid.
- Internal ToolExecution trace is not exposed.

The projection is implemented at the HTTP boundary. Agent Runtime and Matching behavior remain unchanged.

## Demo Architecture

```text
User
  ↓
Streamlit UI
  ↓ HTTP
Demo HTTP Client
  ↓
FastAPI /api/agent/query
  ↓
Agent Runtime → match_jobs → Matching
  ↓
Repository → local SQLite
  ↓
Demo contracts → rendering layer → UI
```

The Demo does not directly access SQLite, create an Agent Runtime, create Tools, or execute matching logic.

## Actual Files

Added:

- `demo/app.py`
- `demo/client.py`
- `demo/contracts.py`
- `demo/rendering.py`
- `demo/__init__.py`
- `tests/demo/test_client.py`
- `tests/demo/test_contracts.py`
- `tests/demo/test_rendering.py`

Updated:

- `app/api/routes/agent.py`
- `app/schemas/agent.py`
- `tests/test_agent_api.py`
- `requirements.txt`
- `README.md`

## Tests and Verification

- Demo request, HTTP error translation, response contract, and rendering tests were added.
- Agent API tests cover disabled projection, successful projection, no `match_jobs`, and failed `match_jobs` cases.
- Final regression: `python -m pytest -q` → `567 passed`.
- GitHub Actions CI: PASS.
- Streamlit runtime smoke: PASS.
- Full chain verification: Streamlit → FastAPI → Agent Runtime → `match_jobs` → Matching → local SQLite → UI: PASS.

The Demo smoke verification used the local application data boundary. It does not establish that the Demo consumes live recruiting website data.

## Dependency and Runtime Resolution

- Added `streamlit==1.48.1`.
- Resolved the Streamlit dependency conflict by pinning `packaging==25.0`.
- An initial Streamlit package import/runtime issue was encountered during verification; the final pinned environment imported and ran successfully.
- Missing `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` configuration correctly produced HTTP 503 at the Backend boundary. No API key value was recorded.
- After the required provider configuration was available, the final Streamlit runtime verification succeeded.

## Limitations

- The Demo is local and is not deployed to the public internet.
- Default Demo data is local SQLite data, commonly prepared through the existing MockJobCrawler path.
- OPPO real-source ingestion exists separately and is not triggered by `POST /api/crawl`.
- The Agent remains stateless and supports sequential Tool Calling only.
- RAG, Memory, Vector DB, Multi-Agent, persistent conversation, and production deployment remain outside Stage 12E.

These are Stage 12E boundaries and non-goals, not defects.

## MUST FIX

Code-layer MUST FIX: 0.

## SHOULD FIX

Code-layer SHOULD FIX: 0.

## Final Disposition

Stage 12E implementation: COMPLETE

PR #13: MERGED

Merge identity:

- Short: `ae21931`
- Full: `ae2193130dd480dc06d3cb245e464ba5ba0336cc`
- Commit: `Merge pull request #13 from luyangzhan111/feat/stage-12e-product-demo`

Final regression: `567 passed`

Stage 12E is formally archived as a completed implementation and documentation milestone.
