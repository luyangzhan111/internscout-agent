# Stage 11 — Deterministic Candidate / Job Matching & Agent Intelligence

## 1. Goal

Stage 11 adds the first explicit candidate-to-job intelligence layer to InternScout Agent.

The goal is to implement a **deterministic, testable Candidate / Job Matching v1** that can:

- accept an explicit candidate skill profile;
- optionally accept preferred work cities;
- derive deterministic skill evidence from stored jobs;
- calculate skill-based candidate/job match results;
- expose matched skills and missing skills;
- rank jobs deterministically;
- expose this capability through a new Agent Tool;
- allow the existing DeepSeek Agent to explain the structured matching result.

The intended high-level path is:

```text
CandidateProfile
        |
        v
JobMatchingService
        |
        +--------------------------+
        |                          |
        v                          v
JobQueryPort                CandidateMatcher
        |                          ^
        v                          |
RepositoryJobQueryAdapter   JobSkillExtractor
        |                          ^
        v                          |
Repository                     JobRead
        |
        v
SQLite

                |
                v

MatchJobsTool
        |
        v
ToolRegistry
        |
        v
AgentOrchestrator
        |
        v
ModelClient
        |
        v
DeepSeekModelClient
        |
        v
DeepSeek
```

Stage 11 is a **domain/service/tool integration stage**.

It is not an Agent Runtime redesign, recommendation-learning system, resume platform, RAG system, or database migration stage.

The core architectural principle is:

```text
LLM decides intent.

Deterministic application code owns:
- skill extraction;
- normalization;
- scoring;
- filtering;
- ranking.

LLM may explain the result,
but it must not own the score.
```

---

## 2. Repository Baseline

Stage 11 Planning was approved from the following repository reality:

| Check | Verified value |
| --- | --- |
| Branch | `main` |
| HEAD | `30f3d97cef99fa32f67739569938029ca7c4f461` |
| Stage 10 feature merge identity | `9c8b2bac6bdcb417e62ef0051d8c6a43ee38da5c` |
| Stage 10 PROJECT_STATE snapshot | `30f3d97` |
| Stage 10 status | CLOSEOUT COMPLETE |
| Full regression baseline | `350 passed, 0 warnings` |
| Stage 10 OPPO targeted baseline | `131 passed` |
| Next Stage before Planning | Stage 11 |
| Specific Goal before Planning | `UNKNOWN` |

The final Stage 11 test count must come from actual execution after implementation.

`350 passed, 0 warnings` is the authoritative **pre-Stage 11 regression baseline**, not a predicted final count.

Current relevant architecture already provides:

- `JobCreate`;
- `JobRead`;
- SQLite persistence;
- Repository;
- `JobQueryPort`;
- `RepositoryJobQueryAdapter`;
- `SearchJobsTool`;
- `GetJobDetailTool`;
- `ToolRegistry`;
- provider-neutral `AgentOrchestrator`;
- provider-neutral `ModelClient`;
- `DeepSeekModelClient`;
- stateless `/api/agent/query`.

Stage 11 must reuse those boundaries where possible instead of redesigning them.

---

## 3. Problem Statement

Before Stage 11, InternScout Agent can:

```text
collect jobs
-> persist jobs
-> query jobs
-> let the Agent search/read jobs
-> generate an answer
```

But it does not have a deterministic application-level answer to:

```text
How well does this candidate match this job?

Which candidate skills match?

Which job skills are missing?

Which stored jobs are strongest for this candidate?
```

That missing layer is the primary Stage 11 capability gap.

### 3.1 Real OPPO data constraint

A critical current repository fact is that `OppoJobCrawler` maps OPPO jobs with:

```python
skills=[]
```

Therefore Stage 11 must **not** implement matching using only:

```text
candidate.skills
INTERSECT
job.skills
```

Such an implementation could appear correct on mock fixtures while producing meaningless results for real persisted OPPO data.

Stage 11 must introduce deterministic job-skill extraction that can combine:

```text
existing structured job.skills
+
job.title
+
job.description
```

into a normalized set of matching skill evidence.

Stage 11 must not solve this problem by asking an LLM to infer skills.

---

## 4. Frozen Stage 11 Scope

Stage 11 is limited to the following capabilities:

```text
CandidateProfile
+
Deterministic Skill Vocabulary / Normalization
+
JobSkillExtractor
+
CandidateMatcher
+
JobMatchingService
+
MatchJobsTool
+
Agent integration
+
offline automated tests
+
real persisted-job / DeepSeek E2E verification
```

No persistent candidate account is required.

No matching result persistence is required.

No database schema change is required.

---

## 5. Candidate Profile Contract

Stage 11 introduces a request-scoped candidate value object.

Recommended model:

```text
CandidateProfile
```

Minimum supported fields:

```python
skills: list[str]
preferred_cities: list[str]
```

The profile represents explicit candidate input for a single matching operation.

It is not a persisted user account.

### 5.1 Candidate skill requirements

Candidate skills must:

- be explicit strings supplied to the matching operation;
- reject invalid element types;
- reject or remove blank values according to the frozen validation implementation;
- normalize whitespace;
- normalize supported aliases to canonical skill names;
- deduplicate case-insensitively while preserving deterministic output.

Existing project skill normalization rules should be reused or extracted into an appropriate shared boundary rather than creating conflicting normalization logic.

Examples of existing canonical names include:

```text
Python
FastAPI
SQL
Git
pytest
HTTP
HTML
Beautiful Soup
Docker
Linux
Shell
Postman
LLM
RAG
```

Stage 11 may extend the deterministic vocabulary when justified by real project/job data, but additions must be explicit and test-covered.

### 5.2 Preferred city requirements

`preferred_cities`:

- may be empty;
- must contain valid nonblank strings when supplied;
- must use the existing city-normalization behavior;
- must be deduplicated deterministically.

Known existing normalization examples include:

```text
北京市 -> 北京
上海市 -> 上海
深圳市 -> 深圳
广州市 -> 广州
东莞市 -> 东莞
```

Preferred cities are a **filter / eligibility constraint**, not part of the skill score.

---

## 6. Job Skill Evidence Contract

Stage 11 introduces a deterministic representation of skills detected for one job.

Recommended model:

```text
JobSkillEvidence
```

It should contain enough information to make matching explainable.

Minimum conceptual fields:

```text
skills
```

The implementation may additionally preserve evidence source information if it remains narrow and useful, for example whether a skill came from:

```text
structured job.skills
title
description
```

Such evidence metadata is optional unless required by implementation or tests.

The architecture must not expand into a broad NLP annotation framework.

---

## 7. Deterministic `JobSkillExtractor`

Recommended responsibility:

```text
JobRead
    |
    v
JobSkillExtractor
    |
    v
JobSkillEvidence
```

The extractor must derive a canonical skill set from:

```text
job.skills
+
job.title
+
job.description
```

### 7.1 Required behavior

The extractor must:

- always produce the same result for the same job;
- never call DeepSeek or another LLM;
- never call an external network;
- use an explicit deterministic skill vocabulary / alias mechanism;
- preserve canonical skill names;
- deduplicate detected skills;
- avoid substring rules that obviously create false positives;
- work when `job.skills == []`;
- combine structured and text-derived evidence without duplicates.

### 7.2 Structured skills

Existing `job.skills` remain valid evidence.

They must be normalized using the same canonical skill rules as candidate skills.

### 7.3 Text extraction

The extractor may inspect:

```text
job.title
job.description
```

using deterministic lexical / alias matching.

Example:

```text
熟悉 Python，了解大模型应用开发，
有 FastAPI 项目经验优先。
```

may deterministically yield:

```text
Python
LLM
FastAPI
```

only when those concepts are covered by the explicit vocabulary/rules.

The extractor must not perform open-ended semantic inference.

For example, Stage 11 must not automatically infer:

```text
“backend development”
-> FastAPI

“AI experience”
-> LLM

“data”
-> SQL
```

unless an explicit reviewed rule exists.

### 7.4 Unknown skill evidence

If no supported skills are detected:

```text
detected_job_skills = []
```

The system must not invent requirements.

This state must remain distinguishable from a strong or weak skill match.

---

## 8. `JobMatchResult`

Stage 11 introduces a structured matching result.

Recommended model:

```text
JobMatchResult
```

The result must expose, at minimum:

```text
job
match_score
matched_skills
missing_skills
detected_job_skills
reason
```

The exact internal model structure may use a job summary instead of duplicating every `JobRead` field, provided the result contains enough stable identity/context for the Agent and tests.

### 8.1 Match score meaning

`match_score` has one frozen meaning:

> Percentage of detected job skills that are present in the candidate's normalized skill set.

For a job with:

```text
Python
FastAPI
SQL
Docker
```

and candidate:

```text
Python
FastAPI
Git
```

the result is:

```text
matched_skills:
Python
FastAPI

missing_skills:
SQL
Docker

match_score:
50
```

Conceptually:

```text
match_score =
    matched_job_skill_count
    /
    detected_job_skill_count
    * 100
```

The implementation must define an explicit deterministic rounding / numeric representation policy and cover it with tests.

### 8.2 Score constraints

`match_score` must:

```text
0 <= match_score <= 100
```

Location, salary, company prestige, publication date, LLM opinion, title similarity, or other hidden factors must not change this score in Stage 11.

This keeps the meaning of the value explainable.

---

## 9. Zero-Evidence Matching Policy

When:

```text
detected_job_skills == []
```

Stage 11 must not:

- ask DeepSeek to guess requirements;
- assign an arbitrary neutral score such as `50`;
- interpret no evidence as full compatibility.

The frozen v1 behavior is:

```text
match_score = 0
matched_skills = []
missing_skills = []
```

The result must include a deterministic reason indicating insufficient skill evidence.

Example semantic meaning:

```text
Insufficient structured skill evidence for matching.
```

The exact user-facing wording may differ, but tests should verify the stable behavior rather than depend unnecessarily on prose.

---

## 10. `CandidateMatcher`

Recommended responsibility:

```text
CandidateProfile
+
JobSkillEvidence
        |
        v
CandidateMatcher
        |
        v
JobMatchResult
```

The matcher must be deterministic and independent from:

- SQLAlchemy;
- FastAPI;
- DeepSeek;
- Agent Runtime;
- network access.

### 10.1 Required calculations

The matcher owns:

```text
matched_skills
missing_skills
match_score
deterministic reason state
```

Definitions:

```text
matched_skills =
detected_job_skills INTERSECT candidate.skills
```

```text
missing_skills =
detected_job_skills MINUS candidate.skills
```

Comparisons must use canonicalized identity rather than unsafe raw string equality.

### 10.2 Pure-business-rule preference

Where practical, matcher logic should behave as a pure application/domain calculation.

It must be independently unit-testable without:

```text
database
HTTP
Agent
LLM
```

---

## 11. Location Filtering

Preferred city behavior is frozen separately from skill scoring.

When:

```text
preferred_cities == []
```

the matching operation may consider jobs from any city.

When one or more preferred cities are supplied, only jobs whose normalized city is included in the candidate's normalized preferred cities are eligible.

For example:

```text
candidate preferred city:
东莞市

stored normalized job city:
东莞
```

must match after normalization.

Location must not contribute bonus or penalty points to `match_score`.

Stage 11 must not introduce hidden rules such as:

```text
+10 same city
-20 different city
```

---

## 12. Deterministic Ranking

Matching results must use stable ordering.

Recommended frozen order:

```text
1. match_score DESC
2. matched_skills count DESC
3. job.id ASC
```

This guarantees deterministic tie-breaking.

The implementation must not allow the LLM to reorder jobs before the structured tool result is created.

If repository reality requires a minor adjustment to the final stable tie-breaker, it must remain explicit and test-covered.

---

## 13. `JobMatchingService`

Recommended responsibility:

```text
CandidateProfile
        |
        v
JobMatchingService
        |
        +----> JobQueryPort
        |
        +----> JobSkillExtractor
        |
        +----> CandidateMatcher
        |
        v
ranked JobMatchResult list
```

The application service coordinates matching across stored jobs.

It must not directly depend on SQLAlchemy.

### 13.1 Database access

Database reads must continue through:

```text
JobQueryPort
        |
        v
RepositoryJobQueryAdapter
        |
        v
Repository
        |
        v
SQLAlchemy / SQLite
```

Do not let matching services or Agent Tools import SQLAlchemy sessions or repository internals.

### 13.2 Pagination / candidate job collection

The existing `JobQueryPort.search_jobs()` is paginated.

Stage 11 must implement a finite and deterministic strategy for retrieving the candidate set used for matching.

The implementation must not silently inspect only the first page and then claim that it ranked all stored eligible jobs.

Acceptable approaches include safely walking available pages through the existing port or a narrowly reviewed extension to the read port if existing repository reality proves that necessary.

Any change to `JobQueryPort` must be minimal, backward-compatible where practical, and justified by the matching use case.

Do not bypass the port by accessing Repository or SQLAlchemy directly.

### 13.3 `top_k`

The matching service supports a bounded number of returned recommendations.

Recommended input:

```text
top_k
```

It must:

- be an integer;
- reject boolean values if necessary under Python/Pydantic behavior;
- have a lower bound of `1`;
- have a conservative upper bound;
- return at most `top_k` ranked matches.

A suitable maximum should be chosen during implementation and frozen in tests.

Do not return an unbounded result set through the Agent Tool.

---

## 14. `MatchJobsTool`

Stage 11 adds one new read-only Agent Tool:

```text
match_jobs
```

Recommended class:

```text
MatchJobsTool
```

The tool should follow the existing `BaseTool` / Pydantic argument-validation pattern used by current job tools.

Minimum conceptual arguments:

```text
skills
preferred_cities
top_k
```

Example:

```json
{
  "skills": [
    "Python",
    "FastAPI",
    "LLM"
  ],
  "preferred_cities": [
    "深圳",
    "东莞"
  ],
  "top_k": 5
}
```

### 14.1 Tool responsibilities

`MatchJobsTool` must:

- validate arguments;
- construct or validate `CandidateProfile`;
- delegate business logic to `JobMatchingService`;
- return structured, JSON-serializable match results.

It must not:

- implement scoring itself;
- directly access SQLAlchemy;
- call DeepSeek;
- rewrite Agent Runtime behavior.

### 14.2 Tool result

The structured result must give the model enough evidence to explain recommendations, including:

```text
job identity/context
match_score
matched_skills
missing_skills
detected_job_skills
reason
```

The model must not need to reconstruct the score.

---

## 15. Agent Composition

The existing composition root remains:

```text
app/api/dependencies.py
```

Stage 11 may extend this composition to construct:

```text
RepositoryJobQueryAdapter
JobSkillExtractor
CandidateMatcher
JobMatchingService
MatchJobsTool
```

and register the new tool in the existing `ToolRegistry`.

Existing tools remain available:

```text
search_jobs
get_job_detail
```

The expected registry becomes conceptually:

```text
SearchJobsTool
GetJobDetailTool
MatchJobsTool
```

The exact construction may be adjusted to avoid unnecessary duplication while preserving current dependency boundaries.

---

## 16. Frozen Agent Boundaries

The following architectural contracts must remain unchanged unless repository reality proves a blocking defect that is separately reviewed.

### Agent Runtime

- `AgentOrchestrator` remains provider-neutral.
- `AgentState` remains per-run.
- Tool execution remains sequential.
- No parallel tool execution is added.
- No persistent conversation state is added.
- No Agent memory is added.

### Provider

- `ModelClient` remains the provider boundary.
- `DeepSeekModelClient` remains isolated behind `ModelClient`.
- DeepSeek remains stateless at the application adapter boundary.
- Stage 11 does not redesign provider request/response contracts unless absolutely necessary for a verified blocking issue.

### Tool / Database boundary

The existing pattern remains:

```text
Tool
-> application/domain service
-> JobQueryPort
-> RepositoryJobQueryAdapter
-> Repository
-> SQLAlchemy
-> SQLite
```

Agent Tools must not directly depend on SQLAlchemy.

---

## 17. LLM Responsibility Boundary

Stage 11 explicitly forbids LLM-owned scoring.

The following architecture is forbidden:

```text
Candidate
+
Job
        |
        v
DeepSeek
        |
        v
"match score = 87"
```

The LLM must not determine:

- `match_score`;
- `matched_skills`;
- `missing_skills`;
- ranking order;
- city eligibility.

Those values must already exist in the tool result.

The valid flow is:

```text
Candidate input
        |
        v
deterministic application logic
        |
        v
structured matching result
        |
        v
DeepSeek
        |
        v
natural-language explanation
```

DeepSeek may:

- understand the user's request;
- choose the matching tool;
- provide candidate skills/tool arguments based on explicit user input;
- explain returned matches;
- describe missing skills;
- suggest learning priorities based on the structured result.

DeepSeek must not invent unsupported scores or claim that an unreturned skill was part of deterministic matching evidence.

---

## 18. Database Decision

Stage 11 introduces **no database migration**.

Do not add:

```text
candidate_profiles table
job_matches table
skill_embeddings table
candidate_job_scores table
```

Do not redesign:

```text
JobModel
identity_key
Repository uniqueness
SQLite schema
```

No Alembic work belongs in Stage 11.

Matching results are computed on demand:

```text
CandidateProfile
x
Current persisted jobs
->
JobMatchResult
```

They are not persisted.

---

## 19. Skill Vocabulary Boundary

Stage 11 needs an explicit deterministic vocabulary.

The implementation should reuse current canonicalization behavior rather than maintain two inconsistent skill systems.

Possible design choices include:

```text
existing cleaner skill aliases
```

or a narrowly extracted shared skill-normalization module consumed by both the cleaner and matching layer.

The final choice must minimize unrelated refactoring.

### 19.1 Requirements

The skill vocabulary must:

- use explicit canonical display values;
- support case-insensitive alias identity;
- have tests for supported aliases;
- prevent accidental duplicate canonical skills;
- remain deterministic.

### 19.2 Scope control

Stage 11 does not require a comprehensive technology ontology.

Only skills justified by:

- current fixtures;
- real OPPO job text;
- target project/job use cases;

need to be supported.

Do not build:

```text
skill knowledge graph
taxonomy database
embedding vocabulary
semantic ontology service
```

---

## 20. Failure and Validation Policy

Stage 11 remains defensive and fail-fast for invalid internal/application inputs.

Examples that must be rejected or handled explicitly include:

- invalid candidate profile type;
- invalid skills list element;
- blank candidate skill where prohibited;
- invalid preferred city element;
- invalid `top_k`;
- malformed tool arguments;
- inconsistent internal match data;
- impossible score values.

The exact Pydantic models should enforce the majority of boundary validation.

Normal business states are not failures.

For example:

```text
no jobs
```

should produce an empty matching result.

Likewise:

```text
job with no detectable skill evidence
```

is a valid zero-evidence matching state, not an exception.

---

## 21. File Touch Set

The exact final paths should follow current repository organization and may be refined during implementation.

### 21.1 Expected new production files

A reasonable Stage 11 layout is:

```text
app/matching/__init__.py
app/matching/contracts.py
app/matching/skill_extractor.py
app/matching/matcher.py
app/matching/service.py
```

Equivalent narrow placement under existing `services` / `schemas` is acceptable if repository style strongly favors it.

The implementation must not create excessive micro-files merely to match this suggestion.

Expected Agent addition:

```text
app/agent/tools/matching_tools.py
```

or another narrow location consistent with current Agent Tool organization.

### 21.2 Expected modified production files

Potential modifications include:

```text
app/api/dependencies.py
app/services/cleaner.py
app/agent/tools/__init__.py
app/matching/__init__.py
```

Only modify package `__init__.py` files if useful under current package style.

`app/services/cleaner.py` should only change if skill normalization must be cleanly shared without duplication.

A minimal `JobQueryPort` / adapter extension may be allowed only if pagination requirements cannot be implemented correctly through the existing contract.

### 21.3 Expected tests

Recommended new tests:

```text
tests/matching/test_contracts.py
tests/matching/test_skill_extractor.py
tests/matching/test_matcher.py
tests/matching/test_service.py
tests/agent/test_matching_tool.py
```

Existing Agent/API tests may be extended where appropriate.

Exact paths may follow repository test naming conventions.

### 21.4 Frozen files by default

Unless a verified blocker requires otherwise, Stage 11 must not modify:

```text
app/agent/orchestrator.py
app/agent/model_client.py
app/agent/providers/deepseek_client.py

app/database/models.py
app/database/session.py

app/crawlers/oppo_source_client.py
app/crawlers/oppo_crawler.py

app/workflows/job_ingestion.py

requirements.txt
```

Stage 11 requires no new third-party dependency.

---

## 22. Automated Test Rules

Normal Stage 11 automated tests must:

- require no Internet;
- require no real OPPO request;
- require no real DeepSeek request;
- require no API key;
- be deterministic;
- be repeatable;
- use temporary database state where integration persistence is required.

Real DeepSeek verification remains separate from pytest.

Real OPPO network retrieval is not required for Stage 11 automated tests because Stage 10 already owns source integration.

Stage 11 real verification may use persisted real OPPO-shaped or previously ingested real OPPO data according to the final verification procedure.

---

## 23. Required Test Matrix

### 23.1 Candidate profile

Cover:

- valid skills;
- skill whitespace normalization;
- skill aliases;
- duplicate skills;
- case-insensitive duplicate identity;
- invalid elements;
- empty or blank handling;
- preferred city normalization;
- preferred city deduplication;
- empty preferred cities.

### 23.2 Skill extractor

Cover:

- structured `job.skills`;
- title-only detection;
- description-only detection;
- combined structured/title/description evidence;
- alias detection;
- canonical output;
- duplicate evidence removal;
- case variation;
- no supported skill evidence;
- real OPPO-style `skills=[]`;
- deterministic repeated extraction;
- common false-positive boundaries where relevant.

### 23.3 Matcher

Cover:

- full match;
- partial match;
- zero match;
- zero job-skill evidence;
- correct `matched_skills`;
- correct `missing_skills`;
- score boundaries;
- deterministic score representation;
- normalization identity behavior;
- repeated invocation produces identical result.

### 23.4 Location

Cover:

- empty city preference accepts all cities;
- matching normalized city;
- nonmatching city excluded;
- alias form such as `东莞市` matching stored `东莞`;
- city filter does not alter skill score.

### 23.5 Ranking

Cover:

- higher score first;
- same score uses larger matched-skill count;
- final stable tie-break by job ID;
- stable repeated ordering;
- `top_k`;
- `top_k` validation;
- fewer matches than `top_k`.

### 23.6 Matching service

Cover:

- no jobs;
- one job;
- multiple jobs;
- repository/port pagination beyond first page;
- preferred-city filtering;
- ranking;
- top-k truncation;
- zero-evidence jobs;
- service depends on `JobQueryPort`, not SQLAlchemy internals.

A specific regression test must prove that matching is not silently limited to only the first page of repository results.

### 23.7 Agent Tool

Cover:

- correct tool name;
- correct description;
- tool schema;
- valid arguments;
- extra arguments rejected;
- invalid skills;
- invalid cities;
- invalid `top_k`;
- successful delegation to matching service;
- JSON-serializable structured result;
- no direct SQLAlchemy behavior.

### 23.8 Agent integration

Using fake model behavior, cover a flow such as:

```text
user message
-> model requests match_jobs
-> tool returns structured matches
-> model returns final answer
```

Verify:

- sequential Tool execution remains correct;
- correct Tool is executed;
- Tool result reaches the next ModelRequest;
- `AgentResult` behavior remains unchanged;
- existing search/detail tool behavior is not regressed.

### 23.9 HTTP regression

Existing:

```text
POST /api/agent/query
```

must remain compatible.

No new public HTTP matching endpoint is required by Stage 11.

If matching is exposed only through the Agent Tool, no standalone `/api/match` endpoint should be added merely for symmetry.

---

## 24. Real Stage 11 Verification

After automated implementation and review pass, perform a separate real E2E verification.

Target flow:

```text
real persisted OPPO job
        |
        v
SQLite
        |
        v
JobQueryPort
        |
        v
JobSkillExtractor
        |
        v
CandidateMatcher
        |
        v
MatchJobsTool
        |
        v
AgentOrchestrator
        |
        v
DeepSeek
        |
        v
final candidate/job recommendation
```

The real verification must confirm:

- at least one persisted OPPO job is consumed;
- real OPPO `skills=[]` does not prevent deterministic text skill extraction when supported vocabulary exists;
- if no supported skill evidence exists, the system reports the deterministic insufficient-evidence state rather than hallucinating requirements;
- DeepSeek calls `match_jobs`;
- the Agent receives the structured match result;
- the final response uses the deterministic match score;
- the final response does not silently substitute an LLM-generated score.

Record:

```text
Provider
Model
HTTP status
Agent steps
tool_execution_count
tool name
candidate profile
selected job identity
detected_job_skills
matched_skills
missing_skills
match_score
```

Do not record or expose API key values.

---

## 25. Stage 11 Non-Goals

The following are explicitly out of Stage 11 scope:

### Candidate / resume platform

```text
Resume PDF parsing
Resume upload
OCR
Candidate account
Candidate profile persistence
Education matching
GPA matching
Years-of-experience matching
Salary expectation matching
```

### Semantic retrieval

```text
Embeddings
Vector database
Semantic search
RAG
Knowledge base
Resume embedding
Job embedding
```

### LLM-owned intelligence

```text
LLM scoring
LLM skill extraction
LLM ranking
LLM-generated hidden match factors
```

### Agent expansion

```text
Memory
Persistent conversation
Parallel Tool Calling
Multi-Agent
MCP integration
reasoning continuity
Streaming
```

### Crawling / infrastructure

```text
Production OPPO HTTP crawl trigger
Scheduler
Retry framework
Partial crawler success
Multi-source orchestration
Distributed crawling
```

### Persistence / database

```text
Candidate tables
Match tables
Embedding tables
Alembic
Database identity redesign
```

### Portfolio closeout

The following remain later-stage concerns:

```text
GitHub Actions / CI
full Agent evaluation framework
Docker
deployment
production hosting
portfolio README redesign
architecture diagram packaging
demo packaging
```

Those belong primarily to Stage 12 / Stage 13 unless a small prerequisite is independently reviewed.

---

## 26. Frozen Architecture Summary

Stage 11 target architecture:

```text
CandidateProfile
        |
        v
JobMatchingService
        |
        +------------------------------+
        |                              |
        v                              v
JobQueryPort                    CandidateMatcher
        |                              ^
        v                              |
RepositoryJobQueryAdapter       JobSkillEvidence
        |                              ^
        v                              |
Repository                     JobSkillExtractor
        |                              ^
        v                              |
SQLAlchemy / SQLite                JobRead
```

Agent path:

```text
User
 |
 v
POST /api/agent/query
 |
 v
AgentOrchestrator
 |
 v
DeepSeekModelClient
 |
 v
DeepSeek
 |
 | requests
 v
match_jobs
 |
 v
MatchJobsTool
 |
 v
JobMatchingService
 |
 v
deterministic ranked JobMatchResult
 |
 v
DeepSeek explanation
 |
 v
AgentResult
```

The architecture must preserve:

```text
AgentOrchestrator
!=
matching business logic
```

and:

```text
DeepSeek
!=
scoring engine
```

---

## 27. Acceptance Criteria

Stage 11 implementation is complete only when all of the following are satisfied.

### Domain / contracts

- `CandidateProfile` exists and is validated.
- Candidate skill normalization is deterministic.
- Preferred city normalization is deterministic.
- Matching output uses a structured validated contract.
- Invalid inputs fail clearly.

### Skill extraction

- Real-job-compatible deterministic extraction exists.
- `job.skills` is supported.
- title/description extraction is supported.
- OPPO-style `skills=[]` is handled.
- no LLM is used.
- no network is used.
- zero evidence is explicit.

### Matching

- matched skills are correct.
- missing skills are correct.
- score is deterministic.
- score stays in `0..100`.
- zero-evidence behavior is frozen and tested.
- location does not contaminate skill score.

### Ranking

- ranking is deterministic.
- tie-breaking is deterministic.
- `top_k` is bounded and validated.
- matching does not silently stop at database page 1.

### Architecture

- matching business logic is independent of SQLAlchemy.
- Agent Tool does not directly query SQLAlchemy.
- database access remains behind `JobQueryPort`.
- `AgentOrchestrator` remains provider-neutral.
- `ModelClient` boundary remains intact.
- DeepSeek adapter remains provider-specific and isolated.
- sequential Tool Calling remains unchanged.

### Database

- no migration.
- no candidate persistence.
- no match persistence.
- no identity-key redesign.

### Agent

- `match_jobs` is registered.
- fake-model integration proves the Agent can invoke it.
- structured tool result reaches the model.
- DeepSeek is not responsible for scoring.

### Tests

- all Stage 11 unit tests pass.
- all Stage 11 integration tests pass.
- all existing tests pass.
- authoritative pre-stage `350 passed, 0 warnings` baseline is not regressed.
- final full-project test count is recorded from actual execution.
- final warning count is recorded from actual execution.

### Real verification

- persisted OPPO data is consumed.
- real DeepSeek Agent E2E succeeds.
- `match_jobs` is invoked.
- deterministic match evidence is visible.
- score is produced by application logic.
- final Agent recommendation is based on the structured tool result.

### Review

Final Codex Read-Only Review must report:

```text
MUST FIX = 0
```

Any `SHOULD FIX` findings must either:

- be resolved before closeout; or
- be explicitly reviewed and documented as accepted limitations.

---

## 28. Stage 11 Sub-stages

### Stage 11A — Matching Contracts & Skill Vocabulary

Goal:

```text
Freeze the deterministic domain contracts and canonical skill boundary.
```

Expected work:

- `CandidateProfile`;
- `JobSkillEvidence`;
- `JobMatchResult`;
- candidate normalization;
- shared or reused skill normalization;
- domain/contract tests.

Acceptance:

- no Agent changes;
- no database changes;
- no LLM use;
- contract tests pass.

---

### Stage 11B — Deterministic Job Skill Extraction

Goal:

```text
Extract canonical skill evidence from stored jobs.
```

Inputs:

```text
job.skills
job.title
job.description
```

Expected work:

- deterministic vocabulary matching;
- structured skill support;
- text skill extraction;
- duplicate removal;
- OPPO `skills=[]` support;
- zero-evidence state;
- extractor tests.

Acceptance:

- same job always produces same evidence;
- no network;
- no LLM;
- OPPO-style job text can be tested.

---

### Stage 11C — Candidate Matcher

Goal:

```text
Calculate explainable deterministic skill compatibility.
```

Expected work:

- matched skills;
- missing skills;
- match score;
- zero-evidence behavior;
- deterministic reason state;
- matcher unit tests.

Acceptance:

- no database;
- no Agent;
- no LLM;
- pure deterministic calculation.

---

### Stage 11D — Job Matching Application Service

Goal:

```text
Match one candidate against persisted eligible jobs and rank results.
```

Expected work:

- `JobMatchingService`;
- `JobQueryPort` integration;
- finite complete pagination behavior;
- location filtering;
- deterministic ranking;
- `top_k`;
- temporary database / fake-port tests.

Acceptance:

- no direct SQLAlchemy dependency from matching service;
- jobs beyond first page are not silently ignored;
- output ranking is stable.

---

### Stage 11E — `MatchJobsTool`

Goal:

```text
Expose matching as a provider-neutral read-only Agent capability.
```

Expected work:

- tool arguments;
- strict Pydantic validation;
- `MatchJobsTool`;
- service delegation;
- structured result serialization;
- tool tests.

Acceptance:

- no scoring logic inside Tool;
- no SQLAlchemy inside Tool;
- no DeepSeek inside Tool.

---

### Stage 11F — Agent Integration

Goal:

```text
Allow the existing Agent Runtime to execute match_jobs.
```

Expected work:

- composition-root registration;
- fake-model Tool-Calling flow;
- `/api/agent/query` regression;
- existing tools regression.

Acceptance:

```text
model
-> match_jobs
-> tool result
-> model
-> final answer
```

works using the unchanged sequential Agent loop.

---

### Stage 11G — Real Matching E2E

Goal:

```text
Verify the complete real persisted OPPO + deterministic matching + DeepSeek Agent flow.
```

Expected flow:

```text
Persisted OPPO Job
-> Skill Extraction
-> Candidate Matching
-> match_jobs
-> DeepSeek
-> Final Recommendation
```

Acceptance:

- real persisted OPPO job used;
- real DeepSeek used outside pytest;
- Tool call confirmed;
- deterministic score confirmed;
- result is explainable;
- no API secret exposed.

---

### Stage 11H — Final Review & Closeout

Required sequence:

```text
targeted tests
->
full pytest
->
Final Codex Read-Only Review
->
resolve findings
->
full regression
->
docs/stage-reviews/stage-11-review.md
->
docs/development-log.md
->
PR
->
merge
->
post-merge main regression
->
PROJECT_STATE.md
->
branch cleanup
```

Closeout is not complete until:

```text
MUST FIX = 0
```

and the final actual regression baseline is recorded.

---

## 29. Development Workflow

Continue the existing workflow:

```text
Architecture-First
+
Codex-Driven Implementation
+
Human Verification
```

Codex model policy:

```text
Routine implementation / analysis:
Luna

Complex architecture:
Sol High

Difficult debugging:
Sol High

Stage Final Read-Only Review:
Sol High
```

Before every Codex task, verify the selected model.

Codex must not perform Git lifecycle operations by default.

Forbidden unless explicitly changed by the human workflow:

```text
git add
git commit
git push
create PR
merge PR
delete branch
```

Git lifecycle remains human-controlled.

---

## 30. Stage 11 Start Rule

Implementation must not begin until this task specification passes Human Review.

After Human Review approval:

1. verify `main`;
2. verify `HEAD`;
3. verify `origin/main`;
4. verify clean working tree;
5. verify pre-Stage 11 full regression if required;
6. create the Stage 11 feature branch;
7. begin Stage 11A only.

Recommended branch name:

```text
feat/stage-11-candidate-job-matching
```

Do not begin Stage 11B–11H before the preceding sub-stage meets its acceptance criteria.

---

## 31. Final Stage 11 Definition

Stage 11 succeeds when InternScout Agent moves from:

```text
job retrieval Agent
```

to:

```text
candidate-aware job matching Agent
```

while preserving a clear engineering boundary:

```text
LLM:
intent + explanation

Application code:
evidence + matching + scoring + ranking
```

The value of Stage 11 is not the sophistication of the scoring algorithm.

The value is that matching becomes:

```text
deterministic
testable
explainable
real-data-compatible
Agent-usable
```

without introducing unnecessary RAG, embeddings, persistence, or Agent complexity.