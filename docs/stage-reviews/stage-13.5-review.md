# Stage 13.5 Review — Semantic Job Knowledge Retrieval

## Purpose

Stage 13.5 builds on the v1.0.0 / Stage 13 deployment baseline. Before this
stage, InternScout Agent already had two important capabilities:

- structured job queries; and
- deterministic candidate-job matching.

Stage 13.5 adds a semantic Job Knowledge Retrieval Layer for unstructured job
descriptions and semantic evidence. It is repository-specific job retrieval,
not generic PDF RAG.

The central rule is:

~~~text
Retrieval supplements deterministic matching.
Retrieval does not replace deterministic scoring.
~~~

Retrieval finds relevant evidence in natural-language job knowledge. Matching
remains responsible for business decisions such as skill overlap, missing
skills, score calculation, and reason generation.

## Architecture Overview

The existing application layering remains intact:

~~~text
Streamlit Demo
    ↓ HTTP
FastAPI
    ↓
Agent Runtime
    ├── Structured Tools → Job Query / Matching → Database
    └── retrieve_job_knowledge → Job Knowledge Retrieval Layer
                                  ├── JobDocument
                                  ├── EmbeddingProvider
                                  ├── VectorStore
                                  └── JobKnowledgeRetriever
~~~

The retrieval path is:

~~~text
JobRead
  → build_job_document()
  → EmbeddingProvider
  → VectorStore
  → JobKnowledgeRetriever
  → RetrieveJobKnowledgeTool
~~~

The retrieval tool returns evidence. It does not calculate matching scores,
modify the database, or generate the final Agent answer.

## What Was Built

### 1. JobDocument

JobRead is converted into a searchable JobDocument.

Searchable content contains:

- title;
- company;
- city;
- skills; and
- description.

Metadata contains:

- job_id;
- company; and
- city.

This keeps the searchable text focused on job meaning while preserving stable
identity and useful display/filter metadata separately.

The current semantic content does not include salary, published_at, source, or
source_url. Those fields may be useful for filtering, display, or provenance,
but they are not part of the current searchable text contract.

### 2. EmbeddingProvider

EmbeddingProvider is a provider-neutral abstraction with single-text and batch
embedding operations.

The repository contains:

- FakeEmbeddingProvider for deterministic, network-free unit tests; and
- OpenAICompatibleEmbeddingProvider for application integration.

The production integration uses an OpenAI-compatible endpoint. Its defaults
target the Bailian-compatible text-embedding-v4 model with 1024 dimensions.
The embedding provider is deliberately not hard-coded into the retriever.

This boundary gives the project provider replaceability, deterministic tests,
no embedding API dependency in CI, and a clearer separation between retrieval
orchestration and provider configuration. The current tests do not benchmark
real embedding quality.

### 3. VectorStore

VectorStore abstracts document storage and similarity search.

The current implementation is InMemoryVectorStore:

- process-local;
- non-persistent;
- dependency-light; and
- ranked by cosine similarity in descending order.

This is an intentional YAGNI decision for sample/local portfolio scale. The
project does not yet need persistence, distribution, or the operational
complexity of FAISS, Chroma, Milvus, or an external vector database. The
abstraction leaves room for a later implementation without coupling the
retriever to one storage product.

The trade-off is explicit: the index is lost with the process, a rebuild is
required, and this is not a persistent large-scale retrieval architecture.

### 4. JobKnowledgeRetriever

JobKnowledgeRetriever exposes the two core operations:

- index_jobs() transforms jobs, embeds their document content, and stores the
  resulting documents and vectors;
- search() embeds a natural-language query and returns ranked RetrievalResult
  values containing a document and similarity score.

The authoritative retrieval identity is the JobDocument.id, derived from
JobRead.id. Evaluation therefore checks returned job IDs and rank rather than
exact floating-point score values.

### 5. RetrievalRuntime

RetrievalRuntime owns the application-level retrieval lifecycle.

Its state is intentionally small:

- dirty: the active index may be stale;
- ready: a complete current retriever is available; and
- current_retriever: the active indexed retriever, when one exists.

The lifecycle is:

~~~text
startup
  → construct optional runtime

Agent request with dirty / unready runtime
  → collect the current job snapshot
  → rebuild lazily
  → provide the retriever to the Agent composition

successful crawl ingestion
  → mark_dirty()
  → defer embedding until a later retrieval request
~~~

The system does not re-embed every job during every Agent request, and a crawl
does not immediately perform an embedding rebuild.

### 6. Agent Integration

create_agent_orchestrator() accepts an optional job_retriever. When one is
available, the composition root registers retrieve_job_knowledge after the
three structured tools:

1. search_jobs;
2. get_job_detail;
3. match_jobs; and
4. retrieve_job_knowledge.

When no retriever is supplied, the existing three-tool path remains intact.
This keeps retrieval integrated through the tool boundary without changing the
core Agent Runtime contract.

### 7. FastAPI Integration

FastAPI constructs an optional application-scoped retrieval runtime at
startup. Missing or invalid embedding credentials disable retrieval without
preventing FastAPI or the structured Agent tools from starting.

The request dependency obtains a current database snapshot through the existing
JobQueryPort / repository adapter, rebuilds lazily when necessary, and passes
the resulting retriever into Agent composition. A successful crawl calls
mark_dirty() only after ingestion; it does not perform an immediate embedding
operation.

This makes retrieval an enhancement rather than a hard dependency of the
application.

### 8. Retrieval Evaluation

Stage 13.5G added a controlled, offline evaluation path:

- six direct retrieval cases;
- two Agent retrieval integration cases;
- Hit@K and Top-1 metrics; and
- blocking pytest collection through the existing python -m pytest -q gate.

The direct gate composes explicit JobRead fixtures, a controlled embedding
provider, the production JobKnowledgeRetriever, the retrieval runner, and the
retrieval scorer. The Agent gate reuses the existing Agent evaluation runner
and scorer.

## Why Matching Was Not Replaced

Candidate matching is business logic. It needs stable, explainable behavior
for:

- skills overlap;
- missing skills;
- deterministic score calculation; and
- reason generation.

Semantic retrieval is useful for a different question: which job documents
contain evidence that is semantically related to this natural-language query?

The division is therefore:

~~~text
retrieval  → find semantic evidence
matching   → make a deterministic decision / calculate a score
~~~

Replacing matching with similarity would make business decisions depend on
embedding behavior, weaken explainability, and blur the existing contract.
Keeping the two layers separate is both an engineering boundary and an
important interview design point.

## Design Review: JobDocument

The current searchable content is intentionally composed from title, company,
city, skills, and description because these fields describe what a role is,
where it is, and what work or capabilities it involves.

Metadata has a different responsibility. job_id preserves identity for
retrieval results and downstream assertions; company and city support result
context. A field can be useful to the product without being useful as semantic
input. Salary, publication date, source, and source URL are therefore outside
the current semantic content contract rather than being silently mixed into
the embedding text.

## Cosine Similarity

Cosine similarity compares vector direction rather than absolute vector
length:

~~~text
cos(a, b) = (a · b) / (||a|| ||b||)
~~~

The current vector store sorts scores from highest to lowest, so the most
semantically similar document is returned first. Zero vectors are treated as
unrelated. Evaluation checks rank and returned IDs, not a hand-picked score
threshold.

## RetrievalRuntime and Build-Then-Swap

Re-embedding the complete job collection on every Agent query would add
avoidable latency and provider cost. The runtime therefore keeps the current
retriever and refreshes it only when the index is dirty or has not been built.

The important rebuild rule is build-then-swap:

~~~text
build a new vector store and retriever separately
  → index the complete snapshot
  → replace the active retriever only after success
~~~

An unsafe alternative would mutate the active index during a rebuild. If an
embedding request or indexing step failed halfway through, the currently
usable index could be corrupted or partially refreshed.

With build-then-swap:

- a successful build replaces the current reference;
- a refresh failure leaves the existing retriever usable and keeps dirty true;
  and
- a first-build failure leaves no old retriever, so the request falls back to
  the three structured Agent tools.

This is an availability and consistency trade-off implemented within one
process. It is not a distributed transaction.

## Optional Retrieval

If the embedding API key or base URL is missing, retrieval is disabled and the
FastAPI application still starts. The Agent receives three tools. When a
retriever is ready, it receives four tools including retrieve_job_knowledge.

This behavior protects the core structured query and matching product path
from optional provider configuration. It also makes local development and
offline tests simpler. The trade-off is that semantic retrieval is unavailable
until its configuration is supplied and valid.

## DeepSeek Multiple Function Calls: Compatibility Lesson

The DeepSeek Responses API can return multiple function-call items in one
response. The existing Agent Runtime contract is one tool per model turn with
sequential execution.

The Stage 13.5 compatibility layer projects the first function call in
provider order:

~~~text
provider response
  → select function_calls[0]
  → execute one tool
  → send ToolExecution result on the next request
  → let the model re-plan
~~~

This preserves the existing sequential runtime semantics while accepting the
provider response shape. It is a focused MVP compatibility boundary, not a
reason to redesign the orchestrator around multiple simultaneous tools.

## Evaluation Design

### Why the Evaluation Is Offline

Real embedding APIs are unsuitable for a blocking CI gate because they add:

- network dependence;
- API cost;
- credentials and secret management;
- nondeterministic provider behavior; and
- model/provider drift.

The blocking path therefore uses a deterministic semantic proxy. Real provider
smoke remains manual and non-blocking.

### ControlledEmbeddingProvider

ControlledEmbeddingProvider is a test-only fixture under tests/evaluation/.
It maps text concepts to a fixed six-axis vector space:

- backend/API;
- automated testing;
- data crawling;
- DevOps;
- AI/RAG/Agent; and
- functional testing.

It detects controlled aliases in the input text and derives the vector from
those concepts. It never receives or looks up an expected job ID. It is not a
fake expected-ID lookup; it is a deterministic semantic proxy for this small
repository corpus.

Its limitation is equally important: passing this fixture proves the
retrieval pipeline and ranking regression for the controlled concepts. It does
not prove general real-embedding quality.

### The ci / City Fixture Bug

An early fixture alias used ordinary substring matching for ci. That alias
also matched the City: label emitted by build_job_document(), which could add
the DevOps dimension to every document.

The fix was deliberately scoped to fixture quality:

- ASCII aliases use token / word-boundary matching;
- Chinese aliases continue to use substring matching.

This is a useful testing lesson: a deterministic fixture can still contain a
semantic bug. The fixture itself must be validated against the actual document
format rather than assuming that only production code can be wrong.

### Retrieval Metrics

Hit@K asks whether the expected job appears in the first K results. Top-1 asks
whether the expected job is ranked first.

The six direct cases require both metrics to pass. This is enough for the
current portfolio-scale deterministic regression target. The scorer also
reports failed case IDs and alignment problems such as missing, unexpected, or
duplicate case results.

The current evaluation intentionally does not add MRR, an LLM judge, or a
larger benchmark suite. Those would increase surface area without improving
the current regression question.

### Agent Retrieval Evaluation

The two Agent retrieval cases validate a deeper contract than direct ranking:

~~~text
FakeModelClient
  → ToolCall
  → AgentOrchestrator
  → RetrieveJobKnowledgeTool
  → ToolExecution
  → next ModelRequest
  → FinalAnswer
~~~

This proves that the retrieval tool is composed, called, observed, and carried
into the next sequential model request. It does not prove that a real DeepSeek
model will autonomously choose the retrieval tool in every situation.

### Evaluation Layers

The current evaluation is layered:

1. Stage 12 deterministic Agent evaluation: 9 cases;
2. Stage 13.5 direct retrieval evaluation: 6 cases; and
3. Stage 13.5 Agent retrieval integration evaluation: 2 cases.

Blocking CI remains offline, deterministic, secret-free, network-free, and
independent of local SQLite state.

## Test Isolation Lesson

Legacy Agent API tests were once affected by host-level
INTERNSCOUT_EMBEDDING_* variables. The same test could otherwise see either
three or four tools, and could attempt to construct a real embedding provider.

The shared test fixture now clears the four embedding configuration variables
before entering the TestClient lifespan. The legacy test therefore remains
explicitly retrieval-disabled, while retrieval-enabled behavior is tested by
the dedicated retrieval gate.

The general lesson is that tests must control optional runtime configuration at
the lifecycle boundary. Windows temporary-directory ACL warnings are separate
environment noise and are not the core retrieval lesson.

## Verified Evidence

The current Stage 13.5G closeout baseline records:

~~~text
tests/evaluation: 95 passed
tests/agent:       139 passed
tests/rag:          58 passed
full suite:        710 passed in 16.64s
~~~

The full-suite evidence used a fresh external pytest basetemp to avoid known
Windows temporary-directory ACL failures. The 710-pass result is the current
Stage 13.5G baseline; the older Stage 13 baseline of 570 passes is historical
context.

## Docker Configuration Lesson

Stage 13.5H-B retained a small but important configuration rule. Compose
initially passed empty MODEL / DIMENSIONS values, which could override the
application provider defaults. The corrected Compose defaults are:

~~~text
INTERNSCOUT_EMBEDDING_MODEL=text-embedding-v4
INTERNSCOUT_EMBEDDING_DIMENSIONS=1024
~~~

Deployment configuration must preserve the same default semantics as
application configuration. The Docker result is a local Docker Compose
topology; it is not a public deployment claim.

## Important Architecture Decisions

| Decision | Why |
| --- | --- |
| Retrieval supplements matching | Semantic evidence and deterministic business scoring answer different questions. |
| EmbeddingProvider abstraction | Enables provider replacement, deterministic tests, and a clear API boundary. |
| VectorStore abstraction | Keeps retrieval independent of storage technology. |
| In-memory first | Fits sample/local scale and avoids premature persistence, distribution, and dependency complexity. |
| Lazy rebuild | Avoids embedding the complete job collection on every Agent query. |
| Build-then-swap | Keeps the last complete retriever usable if a refresh fails. |
| Optional retrieval | Missing embedding configuration must not disable the core FastAPI and structured-tool path. |
| Sequential first-call projection | Preserves the existing one-tool-per-turn runtime contract while handling DeepSeek multi-call responses. |
| Offline deterministic retrieval evaluation | Keeps blocking CI reproducible, secret-free, and network-free. |

## Interview Review Questions

### 1. Why does retrieval not replace matching?

Answer points: retrieval finds semantic evidence; matching applies deterministic
business rules. Replacing matching would make score and reason generation depend
on embedding behavior and reduce explainability.

### 2. What is an embedding?

Answer points: an embedding maps text into a numeric vector space. Texts with
related meaning should have similar vector directions, which enables semantic
search beyond exact keyword matching.

### 3. What is cosine similarity?

Answer points: it compares the direction of two vectors using their dot product
divided by both magnitudes. The current store ranks larger cosine similarity
first and treats zero vectors as unrelated.

### 4. Why use a VectorStore abstraction?

Answer points: retrieval should depend on add/search behavior, not on one
storage product. It allows the current in-memory implementation to be replaced
later without rewriting document or retriever orchestration.

### 5. Why not use Milvus now?

Answer points: the current corpus is sample/local portfolio scale and does not
need persistence or distribution. Avoiding an external service reduces
dependency, Docker, and operational complexity while preserving a migration
seam.

### 6. What problem does build-then-swap solve?

Answer points: it prevents a failed rebuild from partially mutating the active
index. The new retriever becomes active only after complete indexing succeeds;
otherwise the old retriever remains available and dirty.

### 7. What is the lazy rebuild trade-off?

Answer points: it reduces crawl-time work and repeated embedding cost, but the
first retrieval after a change pays rebuild latency. A failed first build means
retrieval is unavailable for that request while structured tools still work.

### 8. How does the system avoid a permanently stale index after crawling?

Answer points: successful ingestion calls mark_dirty(). The next retrieval
request sees the dirty state, collects a fresh job snapshot, and rebuilds
before providing the retriever.

### 9. What happens if the embedding API is unavailable?

Answer points: provider construction or rebuild can fail. Retrieval remains
optional; a previous complete index can remain usable, while a first-build
failure falls back to the three structured Agent tools.

### 10. Why does CI not use the real embedding service?

Answer points: real calls require network access and credentials, cost money,
and can drift with provider/model changes. The controlled fixture makes the
semantic path deterministic; real-provider smoke is manual and non-blocking.

### 11. What is the difference between Hit@K and Top-1?

Answer points: Hit@K passes when the expected job is anywhere in the first K
results. Top-1 passes only when it is first. The current case passes only when
both pass.

### 12. What are the limitations of ControlledEmbeddingProvider?

Answer points: it uses a small fixed concept vocabulary and hand-controlled
aliases. It validates repository-specific pipeline behavior, not the quality or
generalization of a real embedding model.

### 13. Why does DeepSeek multi-call handling not execute all calls at once?

Answer points: the existing Agent Runtime contract is sequential, one tool per
model turn. Projecting the first provider-order call preserves that contract;
the next turn receives the result and lets the model re-plan.

### 14. How could the project migrate to a persistent vector store?

Answer points: implement the existing VectorStore contract, define document and
embedding persistence, and choose an operational refresh strategy. The
retriever and Agent tool should remain unchanged if the contract is preserved.

### 15. How would retrieval scale to a much larger job corpus?

Answer points: use persistent storage and incremental indexing, batch provider
requests, add observability and retry policies, and evaluate on a larger real
corpus. The current in-memory rebuild model is intentionally not that design.

## Safe Portfolio / Project Explanation Points

Safe statements include:

- implemented semantic job retrieval for unstructured job descriptions;
- introduced provider-neutral embedding and vector-store abstractions;
- added a process-local, lazy, build-then-swap retrieval runtime;
- integrated retrieval through an Agent tool;
- added deterministic Hit@K / Top-1 CI evaluation;
- added a DeepSeek tool-calling compatibility layer that preserves sequential
  runtime behavior; and
- provided a local Docker Compose topology.

Do not describe the project as having a production-scale persistent vector
store, distributed RAG, public deployment, parallel multi-Agent execution, or a
live recruitment feed. Do not describe the controlled fixture as a real
embedding benchmark.

## Limitations and Optional Future Improvements

Current limitations:

- InMemoryVectorStore is process-local and non-persistent;
- a current index must be rebuilt after process restart or a dirty mark;
- the embedding provider is optional and may be unavailable;
- no persistent memory layer is implemented;
- Agent tool calling remains sequential;
- the default crawl path remains the Mock crawler;
- there is no public deployment; and
- the controlled evaluation is not a real-embedding quality benchmark.

Optional future improvements, not commitments for the next stage:

- add a persistent vector-store implementation;
- evaluate a larger real job corpus;
- expand retrieval quality metrics when a concrete product question requires
  them; and
- consider public deployment after the operational requirements are defined.

## Final Review Disposition

Stage 13.5 implementation and Stage 13.5G evaluation are complete. Stage 13.5H
closeout is in progress, with this review documenting the architecture,
trade-offs, lessons, and claim boundaries. The v1.1.0 closeout is not yet a
release claim.

