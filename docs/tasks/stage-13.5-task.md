# Stage 13.5 — Job Knowledge Retrieval Layer

## Goal

Introduce a semantic retrieval layer for job knowledge.

The current InternScout Agent supports:

- structured job query
- deterministic candidate-job matching
- tool calling
- agent evaluation

Stage 13.5 adds:

- job document processing
- embedding based retrieval
- vector search
- retrieval tool integration

The goal is to enable the Agent to search unstructured job knowledge from descriptions and requirements.

---

# Scope

## Included

- RAG architecture contracts
- Job document generation
- Embedding abstraction
- Vector store abstraction
- Semantic retrieval service
- Retrieval Agent Tool
- RAG evaluation cases


## Excluded

- LangChain integration
- Milvus deployment
- External vector database
- User document upload
- Long-term memory system


---

# Architecture


Current:

User

↓

Agent Runtime

↓

Tool Registry

↓

Structured Tools

↓

SQLite


Stage 13.5:

User

↓

Agent Runtime

↓

Tool Registry

↓

+----------------+
|                |
Structured Tools  Retrieval Tool
|                |
SQLite           Vector Store
                  |
             Job Knowledge


---

# Design Principles

## 1. Keep Agent Runtime unchanged

RAG should be integrated through tools.

Do not modify:

- AgentOrchestrator contract
- ModelClient contract
- ToolRegistry contract


unless required.


---

## 2. Keep Matching deterministic

RAG retrieval provides evidence.

It does not replace:

- CandidateMatcher
- JobMatchingService
- scoring logic


---

## 3. Provider independent

Embedding and vector storage must use abstractions.

Do not couple retrieval logic with:

- DeepSeek Provider
- OpenAI Provider


---

# New Module


app/rag/


Expected components:

app/rag/
contracts.py
document.py
embedding.py
vector_store.py
retriever.py
service.py


---

# Core Contracts


## Document

Represents searchable job knowledge.


Example:

JobDocument
id
content
metadata


---

## EmbeddingProvider


Responsible for converting text into vectors.


Interface:


embed(text)
embed_batch(texts)


---

## VectorStore


Responsible for vector persistence and search.


Interface:


add(documents)
search(query_vector, top_k)


---

## Retriever


Responsible for retrieval workflow.


Flow:


query

↓

embedding

↓

vector search

↓

documents


---

# Agent Integration

New tool:


RetrieveJobKnowledgeTool


Responsibility:

- accept natural language query
- call retrieval service
- return relevant jobs


The tool should not:

- calculate matching score
- modify database
- generate final answer


---

# Testing Requirements


Every component requires tests.


Required coverage:

- contract validation
- empty input handling
- document generation
- embedding behavior
- vector search
- retrieval ranking
- tool integration


---

# Acceptance Criteria


## Functionality

- Job descriptions can be transformed into searchable documents
- Semantic retrieval returns relevant jobs
- Agent can call retrieval tool
- Existing matching behavior remains unchanged


## Engineering

- RAG layer isolated under app/rag
- Existing Agent contracts remain stable
- All tests pass


## Regression

Before Stage 13.5:

pytest baseline:

570 passed


Target:

570 + new RAG tests