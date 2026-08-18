# Stage 10 — Real Recruitment Source Integration & Source Abstraction

## 1. Goal

Integrate OPPO Careers as InternScout Agent's first real recruitment source while preserving the Stage 3–9 ingestion, persistence, API, and Agent architecture.

The completed data path is:

```text
OPPO Careers
-> OPPO discovery JSON endpoint
-> positionId
-> OPPO detail JSON endpoint
-> OppoJobSourceClient
-> OppoJobCrawler
-> JobCreate
-> existing process_jobs
-> existing cleaning / deduplication
-> existing ingest_jobs
-> existing Repository
-> SQLite
-> existing Jobs API
-> existing Agent Tools
-> existing DeepSeek Agent
```

Stage 10 is a source-integration and crawler-boundary engineering stage. It is not an Agent Runtime redesign.

## 2. Repository Baseline

The following repository reality was verified before this task specification was created:

| Check | Verified value |
| --- | --- |
| Branch | `feat/stage-10-oppo-source-integration` |
| HEAD | `21d33b0` |
| Working tree | clean |
| Authoritative pre-Stage 10 regression baseline | `219 passed, 0 warnings` |

The regression baseline is the recorded Stage 9 full-project baseline. It is not a predicted Stage 10 final count. The authoritative final test count must come from actual execution after implementation.

Repository contracts relevant to this task were also verified:

- `BaseJobCrawler.fetch_jobs()` returns `list[JobCreate]`.
- `ingest_jobs()` accepts the existing `JobCrawlerProtocol`, then calls the existing `process_jobs()` and repository path.
- `JobCreate.published_at` uses `datetime.date | None`.
- The existing cleaner maps `东莞市` to `东莞`.
- The existing identity rule is based on normalized company, title, and city.
- `requirements.txt` already contains `httpx==0.28.1`; Stage 10 requires no new dependency.
- `POST /api/crawl` is currently mock-specific.

## 3. Verified External Source Facts

### 3.1 Selected source

The first real source is **OPPO Careers**.

ByteDance was evaluated first and rejected for the initial Stage 10 integration. Its detail JSON was accessible with plain `httpx`, but its discovery flow was not reproducible with ordinary unsigned `httpx` within the permitted scope. Stage 10 must not implement ByteDance or investigate or reverse-engineer ByteDance `_signature` behavior.

### 3.2 OPPO discovery endpoint

Verified website endpoint:

```http
POST https://career.oppo.com/ats-candidate-api/open-api/position/queryPositionList
```

Observed JSON request fields:

- `pageNum`
- `pageSize`
- `publishName`
- `workCityCodeList`
- `jobTypeList`
- `recruitTypeList`
- `shareId`

Observed response shape:

```text
code
msg
data.pageNum
data.pageSize
data.pages
data.total
data.list
```

Plain synchronous `httpx` access was manually verified without login, cookies, authorization, token, signature, Selenium, Playwright, or other browser automation.

A verified internship result contained:

| Field | Value |
| --- | --- |
| `positionId` | `2061649545671430146` |
| `publishName` | `AI产品实习生` |
| `workCityName` | `东莞市` |
| `recruitTypeName` | `日常实习生招聘` |
| recruitment code | `OFFEN-RECRUITMENT` |

`OFFEN-RECRUITMENT` is the verified code corresponding to `日常实习生招聘` in this result. Stage 10 defaults to this internship recruitment type. It must not default `publishName` or another keyword to `AI`; the default query covers the full daily-internship scope unless the caller supplies a keyword.

### 3.3 OPPO detail endpoint

Verified endpoint:

```http
GET https://career.oppo.com/ats-candidate-api/open-api/position/queryPosition?positionId={position_id}
```

Plain synchronous `httpx` access was manually verified under the same no-authentication, no-cookie, and no-signature conditions. A successful response used `code = 0` and `msg = success`.

Useful observed detail fields are:

- `positionId`
- `publishName`
- `publishDate`
- `recruitType`
- `recruitTypeName`
- `workCityName`
- `jobDuty`
- `workRequire`
- `jobType`
- `educationRequire`

A verified `publishDate` sample was `2026-06-01`. This ISO `YYYY-MM-DD` value is compatible with the current `JobCreate.published_at` date contract after validation.

### 3.4 Human-readable source URL

The verified official OPPO job-detail browser URL pattern is:

```text
https://career.oppo.com/official/oppo/recruitment/post/{position_id}?recruitType={recruit_type}
```

The canonical `JobCreate.source_url` must use the actual `positionId` and `recruitType` returned by OPPO detail data. It must not use an internal JSON endpoint.

The discovery and detail JSON endpoints are internal endpoints used by the public recruitment website. Stage 10 documentation and code must not describe them as an officially supported OPPO public developer API.

## 4. Frozen Architecture

```text
BaseJobCrawler
        ^
        |
OppoJobCrawler
        |
        v
OppoJobSourceClient
        |
        v
injected synchronous httpx.Client
        |
        v
OPPO JSON endpoints
```

The source boundary is intentionally narrow. Stage 10 must not introduce a universal recruitment provider interface, generic provider factory, broad source abstraction, or large external Pydantic schema hierarchy.

## 5. `OppoJobSourceClient`

Recommended location and class:

```text
app/crawlers/oppo_source_client.py
OppoJobSourceClient
```

### 5.1 Responsibilities

`OppoJobSourceClient` must:

- own the OPPO discovery and detail endpoint URLs;
- accept a constructor-injected synchronous `httpx.Client`;
- perform the discovery `POST` and detail `GET`;
- own a narrow source timeout policy;
- call `raise_for_status()`;
- decode JSON;
- validate the response envelope;
- require `code == 0`;
- validate the source response shape and required values;
- return the minimum lightweight typed source objects needed by the crawler.

Suitable frozen dataclasses include:

- `OppoPositionPage`
- `OppoPositionSummary`
- `OppoPositionDetail`

The exact fields should be limited to pagination, detail lookup, mapping, and validation needs.

### 5.2 Forbidden knowledge

`OppoJobSourceClient` must not know about:

- `JobCreate`;
- SQLAlchemy or `Session`;
- Repository or SQLite;
- FastAPI;
- Agent Runtime or Agent Tools;
- DeepSeek.

### 5.3 HTTP client lifecycle and timeout

The lifecycle is frozen as constructor-injected synchronous `httpx.Client`. Production and manual composition own that lifecycle, for example:

```python
with httpx.Client(...) as http_client:
    source_client = OppoJobSourceClient(http_client)
    crawler = OppoJobCrawler(source_client)
    ingest_jobs(crawler, session)
```

Implementation must not use module-level `httpx.get()` or `httpx.post()`, and must not silently create an unmanaged long-lived client.

Use a narrow module-level default such as:

```python
DEFAULT_TIMEOUT_SECONDS = 10.0
```

A constructor-level override may be supported if useful. Do not add application-wide environment or configuration infrastructure for this timeout.

### 5.4 Source validation contract

Validation must cover, at minimum:

- a JSON object response envelope;
- present and valid `code`, with success only when `code == 0`;
- present and correctly shaped `data`;
- discovery pagination fields with usable types and ranges;
- a discovery `list` that is a list;
- nonblank `positionId` values;
- required detail fields with valid types;
- nonblank mapping-critical detail values, including `positionId`, `publishName`, `recruitType`, `workCityName`, `jobDuty`, and `workRequire`;
- a `publishDate` value compatible with the current `date` contract.

Pagination metadata must define a finite, forward-progressing page range. Impossible, contradictory, or otherwise unsafe metadata must fail clearly rather than cause silent truncation or an unbounded loop.

### 5.5 Error behavior

- Propagate `httpx` transport failures.
- Propagate HTTP status failures produced by `raise_for_status()`.
- Raise contextual `ValueError` for malformed JSON, an invalid envelope, nonzero source code, or malformed source data.
- Perform one HTTP attempt per requested operation.
- Do not retry and do not use exponential backoff.
- Do not create a broad custom source exception taxonomy.

## 6. `OppoJobCrawler`

Recommended location and class:

```text
app/crawlers/oppo_crawler.py
OppoJobCrawler
```

`OppoJobCrawler` must inherit `BaseJobCrawler` and satisfy the existing contract:

```python
def fetch_jobs(self) -> list[JobCreate]:
    ...
```

### 6.1 Responsibilities

The crawler must:

- request OPPO discovery pages through `OppoJobSourceClient`;
- own the discovery pagination loop;
- obtain position IDs from discovery results;
- fetch each position detail through `OppoJobSourceClient` sequentially;
- map typed OPPO detail data into the existing `JobCreate` unchanged;
- return `list[JobCreate]` only after all requested detail records have been fetched and validated.

The crawler must not know about `Session`, Repository, SQLite, FastAPI, Agent Runtime, Agent Tools, or DeepSeek.

### 6.2 Source defaults and optional filters

- The default recruitment type is `OFFEN-RECRUITMENT`.
- The default page size is `20`.
- The default keyword is absent; it must not be `AI`.
- City, job type, keyword, and other filters are used only when supplied by the caller or clearly required by the narrow implementation.
- Do not create an application-wide configuration framework for source filters.

## 7. Pagination

Pagination ownership is frozen:

- `OppoJobSourceClient` validates and returns exactly one discovery page per call.
- `OppoJobCrawler` owns the page loop.

Required flow:

```text
request page 1 with page_size=20
-> inspect the validated pages value
-> sequentially request pages 2 through pages
-> sequentially fetch details for discovered position IDs
```

The crawler must not request an arbitrarily large `pageSize` to avoid pagination. Malformed page metadata must raise an error rather than silently truncate results or loop indefinitely. An otherwise valid empty discovery result returns `[]`.

## 8. OPPO-to-`JobCreate` Mapping

The existing `JobCreate` schema remains unchanged.

| OPPO source value | `JobCreate` field |
| --- | --- |
| `publishName` | `title` |
| constant `OPPO` | `company` |
| `workCityName` | `city` |
| `None` | `salary` |
| combined duties and requirements text | `description` |
| `[]` | `skills` |
| constant `oppo` | `source` |
| official browser URL constructed from `positionId` and `recruitType` | `source_url` |
| validated `publishDate` | `published_at` |

Description format:

```text
岗位职责：
{jobDuty}

任职要求：
{workRequire}
```

Both `jobDuty` and `workRequire` must be nonblank before mapping. `publishDate` must be validated against the current date contract. Any resulting `JobCreate` validation failure propagates and fails the crawl.

Stage 10 must not add LLM-based skill extraction.

## 9. Failure Policy

Stage 10 is fail-fast.

The following all fail the operation:

- transport failure;
- HTTP non-2xx response;
- invalid JSON;
- OPPO `code != 0`;
- missing or malformed `data`;
- malformed discovery page or pagination metadata;
- malformed discovery list;
- missing or blank position ID;
- malformed detail data;
- missing or blank required detail field;
- invalid publication date;
- `JobCreate` validation failure.

If any detail fetch fails, `fetch_jobs()` fails immediately and makes no later detail calls. It must not silently skip the failed job or return partial results.

No retry, partial-success semantics, structured crawler warning collection, or crawler observability framework belongs in Stage 10. Because `fetch_jobs()` completes before `ingest_jobs()` begins persistence, a detail failure occurs before this ingestion invocation persists any returned jobs.

## 10. Frozen Existing Boundaries

The following files and contracts remain unchanged unless repository reality proves a genuinely blocking issue and a later review explicitly changes scope:

### Crawler and schema contracts

- `app/crawlers/base.py`
- `app/crawlers/mock_crawler.py`
- `BaseJobCrawler`
- `app/schemas/job.py`
- `JobCreate`

### Processing and ingestion

- `app/services/cleaner.py`
- `app/services/deduplicator.py`
- `app/services/processor.py`
- `process_jobs`
- `app/workflows/job_ingestion.py`
- `app/workflows/__init__.py`
- `JobCrawlerProtocol`
- `ingest_jobs`

### Persistence

- `app/database/models.py`
- `app/database/repository.py`
- database schema and uniqueness behavior
- Repository behavior

### API and Agent

- `app/api/routes/crawl.py`
- `app/api/dependencies.py`
- `app/main.py`
- existing Jobs API read paths
- `app/agent/**`
- Agent Runtime
- Agent Tools

### Dependencies

- `requirements.txt`

No new dependency is required.

## 11. FastAPI and Application Integration Decision

Minimal Stage 10 does not replace or redesign `POST /api/crawl`. That endpoint remains unchanged and mock-specific.

Initial OPPO ingestion uses explicit manual composition:

```text
httpx.Client
-> OppoJobSourceClient
-> OppoJobCrawler
-> ingest_jobs(session)
```

After persistence, OPPO jobs become visible naturally through the existing interfaces:

- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/agent/query`

No source-specific changes are required in those APIs, Agent Tools, or Agent Runtime. A real OPPO crawl HTTP endpoint may be considered only by a later reviewed Stage 10 subtask that explicitly changes this scope.

## 12. File Touch Set

### 12.1 New files

Expected production files:

- `app/crawlers/oppo_source_client.py`
- `app/crawlers/oppo_crawler.py`

Expected automated test files:

- `tests/test_oppo_source_client.py`
- `tests/test_oppo_crawler.py`
- `tests/test_oppo_ingestion.py`

This Stage 10C task-contract phase adds only:

- `docs/tasks/stage-10-task.md`

### 12.2 Potentially modified file

- `app/crawlers/__init__.py`, only if exporting the new symbols is consistent with current package style and useful.

Do not modify it solely for symmetry.

### 12.3 Frozen and untouched files

All files listed in Section 10 remain untouched during the minimal implementation. In particular, do not modify production processing, persistence, API, or Agent code; do not modify existing tests merely to accommodate the new source; and do not modify `requirements.txt`.

Stage review, project snapshot, and closeout documentation belong to the separately reviewed 10H phase and are not implementation-boundary changes.

## 13. Automated Test Rules

- `pytest` must never call a real OPPO network endpoint.
- Source-client tests must use `httpx.MockTransport` with an injected `httpx.Client`.
- Crawler tests must use a fake injected OPPO source client.
- Ingestion tests must use fake, real-source-shaped OPPO data and temporary SQLite.
- Real-network smoke testing must be explicitly separated from `pytest`.
- Normal automated test execution must not depend on Internet availability.

## 14. Required Test Matrix

### 14.1 Source client

Tests must cover:

- correct discovery `POST` endpoint;
- correct detail `GET` endpoint;
- correct discovery JSON payload and detail query parameter behavior;
- default and explicitly supplied filter representation;
- valid discovery response parsing;
- valid detail response parsing;
- HTTP transport failure propagation;
- HTTP non-2xx propagation;
- invalid JSON converted to contextual `ValueError`;
- `code != 0` converted to contextual `ValueError`;
- missing or malformed envelope `data`;
- malformed page metadata;
- malformed discovery list;
- missing or blank `positionId`;
- missing, blank, or malformed required detail fields;
- invalid publication date behavior;
- one HTTP attempt only, with no retry.

All endpoint and request assertions must be made against `httpx.MockTransport`; none may contact OPPO.

### 14.2 Crawler

Tests must cover:

- inheritance from or conformance to `BaseJobCrawler` through `fetch_jobs()`;
- default `OFFEN-RECRUITMENT` behavior;
- no default `AI` keyword;
- optional keyword and filter behavior if implemented;
- default `page_size=20` behavior;
- one-page discovery;
- multi-page discovery;
- sequential discovery page requests;
- an empty valid discovery result returning `[]`;
- sequential position-detail fetches;
- exact OPPO-to-`JobCreate` mapping;
- `salary is None`;
- `skills == []`;
- `source == "oppo"`;
- `company == "OPPO"`;
- exact description combination;
- canonical human-readable `source_url` construction;
- publication date parsing and mapping;
- detail failure stopping `fetch_jobs()`;
- no later detail calls after a fail-fast detail error;
- malformed pagination failing clearly.

Crawler tests use a fake source client and do not exercise HTTP.

### 14.3 Ingestion integration

Using fake, network-free, OPPO-shaped source data, test this existing path:

```text
OppoJobCrawler
-> ingest_jobs
-> process_jobs
-> cleaner
-> deduplication
-> repository
-> temporary SQLite
```

Verify at minimum:

- a real-source-shaped job persists;
- `东莞市` is normalized to `东莞` by the existing cleaner;
- the mapped description persists;
- `salary=None` persists;
- `skills=[]` persists;
- `source="oppo"` persists;
- the canonical OPPO `source_url` persists;
- the publication date persists;
- re-ingestion remains idempotent under the current identity rule.

The integration test must prove reuse of the existing pipeline without modifying it.

### 14.4 API integration

No new OPPO route tests are required for the minimal implementation because `/api/crawl` remains mock-specific. The existing API regression suite must continue to pass.

### 14.5 Agent regression

No Agent source-specific test redesign is required. The existing full suite must demonstrate that the OPPO integration does not regress Agent behavior.

## 15. Manual Real OPPO Smoke

Real OPPO network access occurs only as an explicit manual smoke after all automated tests pass. It must never be placed in `pytest`.

The smoke must demonstrate:

```text
OPPO discovery
-> OPPO detail
-> JobCreate
-> ingest_jobs
-> persisted OPPO record
```

Then verify the persisted record through the existing Jobs API. Finally, perform an explicit Agent query showing that the existing Agent can consume the persisted OPPO job without Agent Runtime or Agent Tool changes.

Record enough evidence to identify the exercised position, successful persistence, Jobs API read, and Agent result while avoiding the creation of a permanent automated dependency on the external website.

## 16. Implementation Phases

### 10C — Task specification and test matrix

- Freeze this implementation contract.
- Confirm repository baseline and boundary assumptions.
- Make no production or test changes.

### 10D — OPPO source HTTP boundary

- Add the lightweight typed OPPO source structures.
- Implement `OppoJobSourceClient` with injected synchronous `httpx.Client`.
- Add network-free `httpx.MockTransport` tests for requests, parsing, validation, errors, and no-retry behavior.

### 10E — OPPO crawler boundary

- Implement `OppoJobCrawler` under `BaseJobCrawler`.
- Implement defaults, pagination, sequential detail fetch, mapping, and fail-fast behavior.
- Add fake-client crawler tests.

### 10F — Existing ingestion integration

- Add the fake-source OPPO integration test with temporary SQLite.
- Prove cleaning, deduplication, persistence, and idempotency through the unchanged ingestion pipeline.

### 10G — Regression and explicit real-source verification

- Run targeted and full automated regression suites.
- Run `git diff --check`.
- Only after automated success, run the explicit real OPPO smoke.
- Verify the persisted job through the existing Jobs API and Agent flow.

### 10H — Review and closeout

- Complete final Codex review.
- Resolve all `MUST FIX` findings.
- Record the actual final test count and warning count from execution.
- Complete Stage review, project snapshot, development record, and PR closeout under a separately reviewed documentation scope.

Each phase depends on the preceding phase; real-network verification must not precede the automated boundary and integration tests.

## 17. Acceptance Criteria

Stage 10 is accepted only when all of the following are true:

1. `OppoJobSourceClient` exists behind an injected synchronous `httpx.Client`.
2. OPPO discovery and detail response boundaries are validated.
3. No automated test accesses the real OPPO website.
4. `OppoJobCrawler` satisfies the existing `BaseJobCrawler` contract.
5. Real pagination is implemented with crawler ownership and a default page size of `20`.
6. OPPO detail data maps exactly into the existing `JobCreate`.
7. The default real-source scope is OPPO daily internship recruitment using `OFFEN-RECRUITMENT`, without a default `AI` keyword.
8. The existing cleaning, deduplication, ingestion, and repository path remains unchanged.
9. OPPO-shaped fake data passes an ingestion integration test using temporary SQLite.
10. `/api/crawl` remains unchanged and mock-specific.
11. Existing Jobs API and Agent architecture require no source-specific change.
12. The full `pytest` regression passes with no new warnings.
13. The explicit manual OPPO smoke succeeds after automated tests pass.
14. A real OPPO job is persisted and read through the existing Jobs API.
15. The existing Agent flow consumes the persisted OPPO job.
16. `git diff --check` passes.
17. Final Codex review reports no `MUST FIX` items before Stage 10 closeout.

No final passed-test number is specified here. Closeout must report the count produced by actual execution.

## 18. Known Limitations

- The existing business identity key uses normalized company, title, and city. Distinct OPPO `positionId` values with the same normalized `OPPO` company, title, and city may collapse into one record.
- The existing schema does not use the external position ID as database identity.
- Source availability and undocumented internal website response shapes may change outside this repository's control.
- Minimal Stage 10 has no real-source API trigger, scheduler, retry, partial-success behavior, or multi-source orchestration.

These are recorded limitations, not authorization to redesign the database, repository, API, or source architecture during Stage 10.

## 19. Non-Goals

The following are explicitly outside Stage 10:

- ByteDance integration;
- multiple recruitment sites;
- universal source abstraction;
- generic provider factory;
- retry;
- exponential backoff;
- partial-success crawler behavior;
- crawler observability framework;
- browser automation;
- Selenium;
- Playwright;
- CAPTCHA bypass;
- signature reverse engineering;
- LLM skill extraction;
- Memory;
- RAG;
- Vector DB;
- Streaming;
- Multi-Agent;
- Parallel Tool Calling;
- persistent conversation;
- database redesign;
- Repository redesign;
- FastAPI global redesign;
- Agent Runtime redesign;
- Agent Tool redesign;
- a new real-crawl API endpoint;
- production scheduler;
- distributed crawler.

## 20. Stage Closeout Requirements

Before Stage 10 closeout:

- run all targeted OPPO source-client, crawler, and ingestion tests;
- run the full `pytest` suite and record the actual pass and warning counts;
- confirm no automated test made a real OPPO request;
- run the explicit real OPPO smoke only after automated tests pass;
- preserve evidence of successful discovery, detail mapping, persistence, Jobs API retrieval, and Agent consumption;
- run `git diff --check`;
- review the complete file touch set against this contract;
- confirm all frozen files and boundaries remained unchanged;
- confirm `/api/crawl` remains mock-specific;
- complete final Codex review with no remaining `MUST FIX` findings;
- record known limitations without expanding implementation scope;
- complete the separately reviewed Stage 10 review, project snapshot, development log, and PR closeout documentation.

Any proposed departure from the frozen architecture, failure policy, API decision, or file boundaries requires explicit review before implementation.
