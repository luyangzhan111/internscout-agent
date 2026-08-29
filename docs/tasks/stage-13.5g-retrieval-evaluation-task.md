# Stage 13.5G — Retrieval Evaluation / CI

## 1. Task Metadata

- Stage: `13.5G`
- Title: Retrieval Evaluation / CI
- Branch: `feat/stage13.5-rag`
- Baseline HEAD: `b05df82 fix: handle DeepSeek multiple tool calls sequentially`
- Task type: offline deterministic evaluation and blocking CI gate

This task adds a small, repository-specific evaluation for semantic job
retrieval and Agent retrieval-tool integration. It is not a generic RAG
benchmark and must not change production retrieval behavior.

## 2. Repository Reality

The existing Stage 12 evaluation structure is:

- `evals/contracts.py`
- `evals/dataset.py`
- `evals/runner.py`
- `evals/scorers.py`
- `evals/cases/agent_cases.jsonl`
- `evals/cases/agent_case.schema.json`
- `tests/evaluation/`

There is no `app/evals/` or `tests/evals/`.

The existing Agent dataset contains 9 cases:

- 2 `search_jobs`
- 2 `get_job_detail`
- 2 `match_jobs`
- 3 controlled-failure cases

The existing Agent metrics are:

- `execution_outcome`
- `tool_selection`
- `tool_sequence`
- `tool_arguments`
- `tool_results`
- `answer_facts`

Existing case scoring uses AND semantics. Existing run scoring aligns by
`case_id`, reports missing/unexpected IDs, and calculates pass rates.

The current Python CI gate is:

```text
python -m pytest -q
```

`tests/evaluation/test_evaluation_gate.py` is already collected by that
blocking gate.

## 3. Current Retrieval Boundary

The production path is:

```text
JobRead
  -> build_job_document()
  -> EmbeddingProvider
  -> VectorStore
  -> JobKnowledgeRetriever
  -> RetrieveJobKnowledgeTool
```

`RetrievalResult` contains `document` and `score`.

`JobDocument.id` is the authoritative retrieval identity. It comes from
`JobRead.id` and is also represented in
`JobDocument.metadata["job_id"]`.

`InMemoryVectorStore` uses cosine similarity, descending score order, and
insertion order for ties. Evaluation correctness must use returned job IDs,
not exact score values or a cosine threshold.

## 4. Scope and Non-Goals

### In scope

- six deterministic direct retrieval cases;
- retrieval-specific contracts, loader, runner, and scorers;
- a test-only controlled semantic embedding fixture;
- a blocking direct retrieval pytest gate;
- Agent retrieval-tool cases using `FakeModelClient`;
- reuse of the existing Stage 12 Agent runner/scorer where compatible;
- regression validation through the existing pytest command.

### Non-goals

- Generic RAG benchmarking;
- real embedding APIs, DeepSeek, OpenAI, Bailian, or real LLMs in CI;
- LLM-as-a-judge;
- MRR, Recall@K, BLEU, or ROUGE;
- sentence-transformers, torch, numpy, FAISS, Chroma, Milvus, or another
  external vector database;
- cosine-score thresholds;
- Memory, Multi-Agent runtime, parallel tool execution, or new API behavior;
- Docker, deployment, database schema, or production provider changes.

## 5. Controlled Semantic Embedding Fixture

The current `FakeEmbeddingProvider` derives vectors from `sha256(text)`.
It proves determinism but does not express semantic relatedness. Hash
stability must not be treated as semantic retrieval correctness.

Implement a test/evaluation-only `ControlledEmbeddingProvider` or equivalent
inside:

```text
tests/evaluation/
```

The fixture must:

- implement the existing `EmbeddingProvider` contract;
- use pure Python;
- be deterministic and network-free;
- read no secrets or environment configuration;
- use no numpy, torch, sentence-transformers, FAISS, or external vector DB;
- map text to a fixed concept-vector space using controlled aliases;
- derive vectors from text/concepts, never directly from expected job IDs.

Initial concept axes:

- `backend_api`
- `automated_testing`
- `data_crawling`
- `devops`
- `ai_rag_agent`
- `functional_testing`

Aliases must match actual fixture content. Examples include Python, FastAPI,
后端, 接口, 数据库, Pytest, 自动化测试, HTML, 数据采集, 数据清洗, Linux,
Docker, CI, 大模型, Agent, RAG, 工具调用, 功能测试, 接口验证, and 回归测试.

The implementation must not contain a rule such as `job id 5 -> AI vector`.
Fixed concept weights are allowed only when both query and document vectors
are derived from their text.

The fixture is a controlled semantic proxy for this repository, not evidence
of general embedding-model quality. Do not modify
`app/rag/embedding.py`. Evaluation modules under `evals/` must not import
the `tests` package.

## 6. Direct Retrieval Dataset

Direct retrieval evaluation uses independent explicit `JobRead` fixtures. It
must not depend on `internscout.db`, `SessionLocal`, FastAPI app state,
environment secrets, or auto-assigned database IDs.

Construct six fixtures with explicit IDs `1` through `6`, matching the
current `app/fixtures/sample_jobs.html` semantics:

| ID | Job |
| ---: | --- |
| 1 | Python后端实习生 |
| 2 | 自动化测试实习生 |
| 3 | 数据采集实习生 |
| 4 | DevOps实习生 |
| 5 | AI应用开发实习生 |
| 6 | 软件测试实习生 |

Add `evals/cases/retrieval_cases.jsonl` with exactly these initial cases:

| Case ID | Semantic intent | Expected ID | top_k |
| --- | --- | ---: | ---: |
| `retrieval_ai_rag` | 大模型 / Agent / RAG / 工具调用 | 5 | 3 |
| `retrieval_backend_api` | Python / FastAPI / 后端接口 / 数据库 | 1 | 3 |
| `retrieval_automated_testing` | Pytest / 接口自动化测试 | 2 | 3 |
| `retrieval_data_crawling` | 网页采集 / HTML解析 / 数据清洗 | 3 | 3 |
| `retrieval_devops` | Linux / Docker / CI / 部署 | 4 | 3 |
| `retrieval_functional_testing` | 功能测试 / 接口验证 / 回归测试 | 6 | 3 |

Every initial target must be Top-1 and present in the requested top-k. Do not
assert a complete fixed ordering for all other jobs unless a future case
explicitly adds that contract.

## 7. Retrieval Contracts and Loader

Direct retrieval evaluation must not force a retrieval result into the
Agent-specific `EvalCase`/`AgentResult` contract.

Add `evals/retrieval_contracts.py` with minimal contracts.

`RetrievalEvalCase` must contain:

- `schema_version`
- `case_id`
- `description`
- `query`
- `top_k`
- `expected_job_id`

`top_k` must be a strict positive integer and should remain within the
production tool range 1–20. `expected_job_id` must be a positive fixture ID.

`RetrievalEvaluationCaseResult` must represent:

- `case_id`;
- completed/failed state;
- `retrieved_job_ids`;
- error type/message when execution fails.

`RetrievalEvaluationScore` must represent:

- run `status`;
- case scores;
- `case_pass_rate`;
- `hit_at_k_rate`;
- `top_1_hit_rate`;
- `failed_case_ids`;
- missing/unexpected/alignment errors where needed.

Reuse the existing `MetricResult` only when it gives a clean contract. Do
not copy the complete Stage 12 Agent contract merely to share names.

Add:

```text
evals/retrieval_dataset.py
evals/cases/retrieval_case.schema.json
```

The loader must read UTF-8 JSONL, validate with Pydantic, preserve file order,
reject duplicate `case_id` values, include path/line context in useful
errors, and never read a database or environment configuration.

## 8. Direct Retrieval Runner

Add `evals/retrieval_runner.py`.

Its only responsibility is:

```text
RetrievalEvalCase
  -> retriever.search(query, top_k)
  -> JobDocument IDs
  -> RetrievalEvaluationCaseResult
```

The runner receives an already constructed `JobKnowledgeRetriever`. It must
not construct providers, read environment variables or SQLite, create
`RetrievalRuntime`, make network calls, or implicitly index fixtures.

Fixture composition belongs to the test layer:

```text
explicit JobRead fixtures
  -> ControlledEmbeddingProvider
  -> InMemoryVectorStore
  -> JobKnowledgeRetriever.index_jobs()
```

Retriever exceptions must become structured case failures so failed IDs and
errors remain visible to the scorer.

## 9. Retrieval Scorers

Add `evals/retrieval_scorers.py`.

Required case metrics:

```text
hit_at_k = expected_job_id in retrieved_job_ids[:top_k]
top_1_hit = retrieved_job_ids[0] == expected_job_id
```

Empty results must produce failed metrics, not an indexing exception. A case
passes only when both metrics pass.

Required run metrics:

- `case_pass_rate`
- `hit_at_k_rate`
- `top_1_hit_rate`
- `failed_case_ids`

Support empty results, wrong Top-1, target missing from top-k, missing cases,
unexpected cases, and duplicate actual results. Align by `case_id`, not
array position.

Do not add MRR, Recall@K, BLEU, ROUGE, LLM judging, cosine thresholds, or
score-value assertions.

## 10. Direct Retrieval CI Gate

Add `tests/evaluation/test_retrieval_evaluation_gate.py`.

The gate must exercise:

```text
explicit JobRead fixtures
  -> ControlledEmbeddingProvider
  -> InMemoryVectorStore
  -> production JobKnowledgeRetriever
  -> retrieval cases
  -> retrieval runner
  -> retrieval scorer
```

All six cases must pass. Failures must expose failed case IDs, failed metrics,
and missing/unexpected IDs when present.

The gate must require no API key, network, SQLite, DeepSeek, Bailian, or real
embedding service.

## 11. Agent Retrieval Evaluation

This is a separate second layer:

```text
semantic user request
  -> scripted FakeModelClient ToolCallResponse
  -> RetrieveJobKnowledgeTool
  -> ToolResult observation
  -> next ModelRequest
  -> FinalAnswerResponse
```

It verifies the Agent retrieval integration contract. It must not claim that
`FakeModelClient` proves autonomous real-LLM tool selection.

Add:

```text
evals/cases/agent_retrieval_cases.jsonl
tests/evaluation/test_agent_retrieval_gate.py
```

Add `retrieval` to `EvalCase.category` and
`evals/cases/agent_case.schema.json`. Keep the existing 9 Stage 12 cases
unchanged.

At least two cases are required:

1. AI/RAG request:
   - select `retrieve_job_knowledge`;
   - use exact query/top-k arguments;
   - return first `document.id == 5`;
   - satisfy final-answer facts.

2. Backend request:
   - select `retrieve_job_knowledge`;
   - use exact query/top-k arguments;
   - return first `document.id == 1`;
   - satisfy final-answer facts.

Use existing data-assertion paths such as
`items[0].document.id` where compatible with the serialized tool result.

## 12. Minimal Agent Runner Extension

The current `EvaluationRunner` has no retriever injection. A minimal
backward-compatible optional factory is allowed:

```text
Callable[[EvalCase], JobKnowledgeRetriever | None] | None
```

When absent, all Stage 12 behavior must remain unchanged. For retrieval cases,
the runner must pass the injected retriever through the existing seam:

```text
create_agent_orchestrator(..., job_retriever=retriever)
```

Do not modify production semantics in `create_agent_orchestrator`. Do not
modify `AgentOrchestrator`, `ToolRegistry`, or `BaseTool`.

The Agent gate must reuse `FakeModelClient`, `EvaluationRunner`,
`score_case`, and `score_run`. Do not create a second Agent scorer.

## 13. Expected File Plan

### New files

```text
evals/retrieval_contracts.py
evals/retrieval_dataset.py
evals/retrieval_runner.py
evals/retrieval_scorers.py

evals/cases/retrieval_cases.jsonl
evals/cases/retrieval_case.schema.json
evals/cases/agent_retrieval_cases.jsonl

tests/evaluation/retrieval_fixtures.py
tests/evaluation/test_retrieval_dataset.py
tests/evaluation/test_retrieval_scorers.py
tests/evaluation/test_retrieval_evaluation_gate.py
tests/evaluation/test_agent_retrieval_gate.py
```

### Modified files

```text
evals/contracts.py
evals/runner.py
evals/cases/agent_case.schema.json
```

If repository reality proves a listed file unnecessary, remove it rather than
creating an empty abstraction. Document any file-scope deviation in the
implementation closeout.

Do not modify `.github/workflows/ci.yml` unless real test-collection
evidence proves the existing pytest command cannot collect the new gates.

## 14. Protected Architecture

The following production files and boundaries are protected:

```text
app/agent/orchestrator.py
app/agent/providers/deepseek_client.py
app/agent/tools/registry.py
app/agent/tools/base.py

app/rag/embedding.py
app/rag/vector_store.py
app/rag/retriever.py
app/rag/runtime.py

production embedding provider
matching score
FastAPI contracts
database schema
Docker architecture
```

Evaluation must observe production behavior; it must not change production
semantics to make the evaluation pass.

## 15. CI Strategy

Do not add an independent GitHub Actions job. The existing
`python -m pytest -q` command must automatically collect both new gates under
`tests/evaluation/`.

The blocking path must remain offline, deterministic, secret-free,
network-free, and independent of local SQLite state. Real provider smoke
remains manual and non-blocking.

## 16. Execution Phases

### 13.5G-A — Contracts + Retrieval Dataset

**Goal**

Add retrieval-specific contracts and six direct cases without rewriting the
Stage 12 dataset.

**Allowed files**

```text
evals/retrieval_contracts.py
evals/retrieval_dataset.py
evals/contracts.py
evals/cases/retrieval_cases.jsonl
evals/cases/retrieval_case.schema.json
evals/cases/agent_retrieval_cases.jsonl
evals/cases/agent_case.schema.json
tests/evaluation/test_retrieval_dataset.py
```

**Implementation**

- Add strict Pydantic contracts and UTF-8 JSONL loading.
- Reject duplicate IDs and malformed/extra fields.
- Add six direct cases and at least two Agent retrieval cases.
- Add the `retrieval` Agent category only where required.

**Tests**

- schema/JSON validation;
- deterministic order;
- duplicate ID rejection;
- existing Stage 12 dataset tests.

**Acceptance criteria**

- six direct cases and two or more Agent cases load;
- all IDs are unique;
- existing 9-case dataset remains unchanged and valid.

**Non-goals / protected boundaries**

No embedding, database, runtime, API, or CI implementation.

### 13.5G-B — Controlled Semantic Fixture

**Goal**

Create a meaningful deterministic semantic proxy for evaluation only.

**Allowed files**

```text
tests/evaluation/retrieval_fixtures.py
tests/rag/test_embedding.py
tests/evaluation/test_retrieval_evaluation_gate.py
```

**Implementation**

- Build explicit `JobRead(id=1...6)` fixtures.
- Implement pure-Python concept/alias vectors.
- Derive vectors from text, not expected IDs.
- Index through `build_job_document()` and production
  `JobKnowledgeRetriever`.

**Tests**

- deterministic vectors;
- stable batch ordering;
- compatibility with actual JobDocument content;
- six expected relationships through the production retriever.

**Acceptance criteria**

- every target is Top-1 under the controlled fixture;
- no network, secret, database, or new ML dependency;
- `app/rag/embedding.py` is unchanged.

**Non-goals / protected boundaries**

Do not change `FakeEmbeddingProvider`, production embedding behavior, or
vector-store ranking.

### 13.5G-C — Retrieval Runner + Scorers

**Goal**

Execute retrieval cases against an injected retriever and score IDs.

**Allowed files**

```text
evals/retrieval_runner.py
evals/retrieval_scorers.py
evals/retrieval_contracts.py
tests/evaluation/test_retrieval_scorers.py
```

**Implementation**

- Implement `search(query, top_k)` execution.
- Record retrieved document IDs for correctness scoring.
- Implement Hit@K and Top-1.
- Align by case ID and report all alignment failures.

**Tests**

- pass cases;
- empty results;
- wrong Top-1;
- target outside top-k;
- missing/unexpected/duplicate results;
- run-level rates.

**Acceptance criteria**

- no score threshold or exact cosine assertion;
- failures expose IDs and metric reasons;
- run is PASS only when all cases and alignment checks pass.

**Non-goals / protected boundaries**

The runner must not instantiate providers, DB sessions, Runtime, or network
clients.

### 13.5G-D — Direct Retrieval CI Gate

**Goal**

Make the six-case direct retrieval evaluation a blocking pytest gate.

**Allowed files**

```text
tests/evaluation/test_retrieval_evaluation_gate.py
tests/evaluation/retrieval_fixtures.py
```

**Implementation**

- Compose fixtures, controlled provider, in-memory store, and retriever.
- Load, run, and score the six cases.
- Raise an informative assertion on failure.

**Tests**

```text
python -m pytest -q tests/evaluation
```

**Acceptance criteria**

- six cases pass;
- Hit@K rate is 1.0;
- Top-1 rate is 1.0;
- no API key, network, SQLite, DeepSeek, or Bailian dependency.

**Non-goals / protected boundaries**

No new GitHub Actions job and no production retrieval change.

### 13.5G-E — Agent Retrieval Evaluation Gate

**Goal**

Validate retrieval-tool integration using the Stage 12 Agent evaluation path.

**Allowed files**

```text
evals/runner.py
evals/contracts.py
evals/cases/agent_case.schema.json
evals/cases/agent_retrieval_cases.jsonl
tests/evaluation/test_agent_retrieval_gate.py
```

**Implementation**

- Add optional retriever factory injection with default `None`.
- Build the controlled retriever in test composition.
- Script retrieval ToolCallResponse followed by FinalAnswerResponse.
- Reuse `score_case` and `score_run`.
- Assert expected retrieval IDs through data assertions.

**Tests**

- tool selection and exact arguments;
- exact tool sequence;
- successful ToolResult;
- expected first document ID;
- ToolExecution in the next ModelRequest;
- final answer facts;
- existing Agent evaluation tests.

**Acceptance criteria**

- both Agent retrieval cases pass;
- the existing 9 cases remain unchanged and pass;
- no real LLM/provider call;
- no Agent runtime semantic change.

**Non-goals / protected boundaries**

Do not claim autonomous real-LLM tool-choice validation. Do not modify
`AgentOrchestrator`, `ToolRegistry`, `BaseTool`, or production composition
semantics.

### 13.5G-F — Regression + Final Review

**Goal**

Prove isolation, pytest collection, and no Stage 13.5F or earlier Agent
regression.

**Allowed files**

No additional implementation files are expected. Scope expansion requires
concrete test or collection evidence.

**Implementation**

Review the final diff for test-package imports from production-like modules,
network/secret access, local DB dependency, score-value assertions, protected
architecture changes, unnecessary workflow changes, and accidental rewriting
of the Stage 12 dataset.

**Tests**

```text
python -m pytest -q tests/evaluation
python -m pytest -q tests/rag tests/agent
python -m pytest -q
git diff --check
```

Known Windows temp-directory ACL failures must be classified separately from
product failures and rerun with an allowed repository-local basetemp when
needed.

**Acceptance criteria**

- `tests/evaluation`, `tests/rag`, and `tests/agent` pass;
- full pytest has no product regression;
- `git diff --check` passes;
- no API key, network, DB, or protected architecture dependency;
- `.github/workflows/ci.yml` remains unchanged unless justified by evidence.

**Non-goals / protected boundaries**

No real-provider smoke, deployment work, or production RAG expansion.

## 17. Final Acceptance

Stage 13.5G is complete only when:

- all 6 direct retrieval cases pass deterministically;
- every expected target is Top-1;
- Hit@K passes;
- Top-1 passes;
- Agent retrieval cases pass;
- the existing 9 Stage 12 Agent cases remain unchanged and pass;
- `tests/evaluation`, `tests/rag`, and `tests/agent` pass;
- full pytest has no product regression;
- `git diff --check` passes;
- no API key, network, or DB dependency exists;
- no protected production architecture is changed;
- no CI workflow change is made without clear evidence and justification.
