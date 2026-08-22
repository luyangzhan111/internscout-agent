# Stage 13 Task — Deployment & Reproducibility

## 1. Background

InternScout Agent has completed the core AI application engineering workflow through Stage 12E.

Current capabilities include:

- Recruitment data ingestion.
- Data cleaning and normalization.
- SQLite persistence.
- FastAPI backend.
- Agent Runtime.
- Tool Calling.
- DeepSeek provider integration.
- Deterministic candidate/job matching.
- Agent Evaluation framework.
- GitHub Actions CI.
- Streamlit Product Demo.

The current application can run locally through separate development processes:

```text
FastAPI:
python -m uvicorn app.main:app --reload

Streamlit:
python -m streamlit run demo/app.py
```

However, the current runtime still depends on developer-local environment setup.

A new developer must understand:

- Python installation;
- virtual environment setup;
- dependency installation;
- environment variables;
- Backend startup;
- Streamlit startup;
- SQLite location.

Stage 13 addresses this problem.

The objective is to make InternScout Agent reproducible and easier to run in a clean environment.

---

# 2. Stage Goal

Stage 13 focuses on:

> Deployment & Reproducibility

The target developer experience is:

```text
git clone

↓

configure .env

↓

docker compose up

↓

FastAPI Backend + Streamlit Demo

↓

InternScout Agent available locally
```

The final target architecture is:

```text
                 User
                  |
                  v
           Streamlit Demo
              :8501
                  |
                  v
          Docker Network
                  |
                  v
         FastAPI Backend
              :8000
                  |
                  v
          Agent Runtime
                  |
                  v
              Tools
                  |
                  v
        Matching / Repository
                  |
                  v
             SQLite
                  |
                  v
             DeepSeek API
```

---

# 3. Current Baseline

Stage 13 starts from the Stage 12E completed repository state.

Current authoritative regression baseline:

```bash
python -m pytest -q
```

Result:

```text
567 passed
```

Stage 13 must not regress existing application behavior.

---

# 4. Development Model

Stage 13 uses a simulated multi-agent engineering workflow.

The detailed collaboration rules are defined in:

```text
docs/tasks/stage-13-multi-agent-plan.md
```

Three implementation roles will be used:

```text
Agent A — Containerization Engineer
Agent B — Configuration & Environment Engineer
Agent C — CI & Deployment Documentation Engineer
```

A separate Integration / Review role validates the final combined result.

Each implementation agent works in:

- an independent Git branch;
- an independent Git worktree;
- an independent Codex context.

The main repository remains the integration workspace.

---

# 5. Goals

## Goal 1 — Reproducible Runtime

A new developer should not need the maintainer's local `.venv` or hidden shell configuration.

The project must define a reproducible Docker-based startup process.

---

## Goal 2 — Containerize Backend

FastAPI must run inside a Docker container.

The container should:

- use Python 3.12;
- install project dependencies;
- start the existing FastAPI application;
- expose port 8000;
- preserve existing Agent behavior.

---

## Goal 3 — Containerize Streamlit Demo

Streamlit must run inside a separate Docker container.

The container should:

- start the existing Demo;
- expose port 8501;
- communicate with FastAPI through Docker networking;
- not contain DeepSeek secrets unless technically required.

---

## Goal 4 — Docker Compose Orchestration

The full local application should start through:

```bash
docker compose up
```

Docker Compose should manage:

- Backend service.
- Demo service.
- Networking.
- Environment configuration.
- SQLite persistence where appropriate.

---

## Goal 5 — Configuration Contract

The project must document required environment variables.

Expected configuration includes at least:

```text
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
INTERNSCOUT_API_BASE_URL
INTERNSCOUT_API_TIMEOUT_SECONDS
```

Repository reality must determine whether additional database-related configuration is required.

No real secret may be committed.

---

## Goal 6 — CI Container Validation

Existing GitHub Actions regression testing must remain operational.

Stage 13 should add lightweight container validation where appropriate.

Examples:

```text
docker compose config
docker build
```

Blocking CI must remain:

- deterministic;
- offline;
- secret-free.

---

## Goal 7 — Deployment Documentation

A new developer should be able to follow repository documentation to:

1. Clone the project.
2. Configure environment variables.
3. Build/start containers.
4. Open FastAPI.
5. Open Streamlit.
6. Stop the application.
7. Understand SQLite persistence behavior.

---

# 6. Scope

Stage 13 may add or modify infrastructure/configuration files such as:

```text
Dockerfile.backend
Dockerfile.demo
docker-compose.yml
.dockerignore
.env.example
.gitignore
.github/workflows/ci.yml
docs/deployment.md
README.md
```

Minimal application configuration changes are allowed only when repository reality proves they are necessary for container execution.

Such changes must:

- remain configuration-only;
- preserve application behavior;
- receive architecture review before implementation.

---

# 7. Non-goals

Stage 13 explicitly does not include:

- Kubernetes.
- Terraform.
- Helm.
- Cloud production deployment.
- PostgreSQL migration.
- Redis.
- Microservice decomposition.
- RAG.
- Memory.
- Multi-Agent runtime architecture.
- Parallel Tool Calling.
- New Agent features.
- New recruitment sources.

The multi-agent concept in Stage 13 refers only to:

> development workflow simulation

and not to InternScout Agent runtime behavior.

---

# 8. Architecture Constraints

## 8.1 Preserve Agent Runtime

Do not redesign:

```text
app/agent/orchestrator.py
app/agent/model_client.py
app/agent/tools/
```

unless an independently reviewed blocking container issue requires a minimal configuration-only change.

---

## 8.2 Preserve Matching

Do not modify matching behavior:

```text
app/matching/
```

Dockerization must not change:

- score;
- ranking;
- matched skills;
- missing skills;
- deterministic behavior.

---

## 8.3 Preserve Public API Behavior

Existing FastAPI API contracts must remain compatible.

Stage 13 is infrastructure work, not an API redesign stage.

---

## 8.4 Demo Must Continue Through HTTP

The Streamlit Demo must continue to communicate through:

```text
Streamlit
↓
FastAPI HTTP API
↓
Agent Runtime
```

It must not directly import or execute:

- AgentOrchestrator;
- Matching Service;
- SQLAlchemy Session.

---

# 9. Interface Freeze Gate

Parallel architecture analysis is allowed.

Parallel implementation does not begin until the project lead freezes the cross-agent interface contract.

The following values must be agreed before implementation:

## Service Names

Example:

```text
backend
demo
```

Final names are determined during architecture review.

---

## Ports

Expected external ports:

```text
FastAPI: 8000
Streamlit: 8501
```

---

## Backend URL Inside Compose

Streamlit must not assume:

```text
localhost:8000
```

inside its own container.

It should use Docker service discovery, for example:

```text
http://backend:8000
```

through the existing Demo environment configuration boundary.

---

## Environment Variables

The team must agree on:

- variable names;
- which service receives each variable;
- defaults;
- secret/non-secret classification.

---

## SQLite Persistence

The team must determine:

- current SQLite path;
- container SQLite path;
- volume/mount strategy;
- container recreation behavior.

No agent may independently invent a conflicting database path convention.

---

# 10. Agent Responsibilities

## Stage 13A — Configuration & Environment Contract

Owner:

```text
Agent B
```

Primary files:

```text
.env.example
.gitignore (only if required for secret safety)
```

Possible minimal configuration-related application changes require explicit approval.

Responsibilities:

- identify required environment variables;
- document safe placeholders;
- confirm secret boundaries;
- verify `.env` cannot be accidentally committed;
- define local vs Compose configuration expectations;
- investigate SQLite path configuration requirements.

Deliverable:

```text
Stage 13 Configuration Design Report
```

then implementation after approval.

---

# 11. Stage 13B — Docker & Compose

Owner:

```text
Agent A
```

Primary files:

```text
Dockerfile.backend
Dockerfile.demo
docker-compose.yml
.dockerignore
```

Responsibilities:

- Backend image.
- Streamlit image.
- Compose network.
- Service discovery.
- Environment injection.
- SQLite volume strategy.
- Health checks where justified.

Agent A must consume the frozen configuration contract.

Agent A must not independently redesign application configuration.

Deliverable:

```text
Stage 13 Containerization Design Report
```

then implementation after approval.

---

# 12. Stage 13C — CI & Deployment Documentation

Owner:

```text
Agent C
```

Primary files:

```text
.github/workflows/ci.yml
README.md
docs/deployment.md
```

Responsibilities:

- preserve existing pytest CI;
- add appropriate Docker validation;
- document actual Docker commands;
- document runtime configuration;
- document SQLite behavior;
- document startup/shutdown workflow.

Agent C may perform architecture analysis in parallel.

However, final implementation and documentation validation must use the merged/frozen Configuration and Docker reality.

Deliverable:

```text
Stage 13 CI and Deployment Documentation Design Report
```

then implementation after approval.

---

# 13. Git / Worktree Strategy

The integration repository remains:

```text
D:\AI-Project\internscout-agent
```

and should remain on:

```text
main
```

Implementation worktrees:

```text
D:\AI-Project\internscout-stage13-config
D:\AI-Project\internscout-stage13-docker
D:\AI-Project\internscout-stage13-ci-docs
```

Branches:

```text
feat/stage13-config
feat/stage13-docker
feat/stage13-ci-docs
```

All branches must originate from the same frozen Stage 13 planning baseline.

---

# 14. Recommended Execution Sequence

## Phase 0 — Planning

Complete and commit:

```text
docs/tasks/stage-13-task.md
docs/tasks/stage-13-multi-agent-plan.md
```

Only after these documents are committed to `main` is the Stage 13 baseline frozen.

---

## Phase 1 — Worktree Setup

Create three worktrees from the frozen baseline.

Verify each:

```bash
git status
git branch --show-current
```

---

## Phase 2 — Parallel Read-only Analysis

Run three Codex architecture analyses in parallel.

No implementation yet.

Outputs:

```text
Agent A:
Containerization Design Report

Agent B:
Configuration Design Report

Agent C:
CI and Deployment Documentation Design Report
```

---

## Phase 3 — Interface Freeze Review

Project lead reviews all three reports.

Freeze:

- service names;
- environment variables;
- SQLite persistence;
- ports;
- Compose networking;
- CI expectations.

Only then can implementation begin.

---

## Phase 4 — Implementation

Recommended dependency-aware implementation order:

```text
Agent B
Configuration
    ↓
Agent A
Docker / Compose
    ↓
Agent C
CI / Documentation
```

Coding may overlap where interfaces are already frozen.

---

## Phase 5 — Pull Requests

Expected PRs:

```text
PR 1 — Stage 13 Configuration
PR 2 — Stage 13 Docker & Compose
PR 3 — Stage 13 CI & Deployment Docs
```

---

## Phase 6 — Integration Review

Run a separate senior review after all Stage 13 changes are integrated.

The Review Agent should first operate in read-only mode.

It should check:

- networking;
- configuration;
- SQLite persistence;
- secrets;
- Docker build;
- Compose validation;
- CI;
- documentation;
- runtime behavior.

---

# 15. Merge Order

Recommended merge order:

```text
1. Configuration
2. Docker / Compose
3. CI / Deployment Documentation
```

After every merge:

1. Update main.
2. Synchronize remaining feature branches/worktrees.
3. Re-run relevant validation.
4. Resolve conflicts before continuing.

CI does not resolve merge conflicts.

---

# 16. Testing Strategy

## Existing Regression

The complete existing regression suite must remain passing:

```bash
python -m pytest -q
```

Starting baseline:

```text
567 passed
```

---

## Docker Static Validation

Expected:

```bash
docker compose config
```

must pass.

---

## Docker Build Validation

Backend and Demo images must build successfully.

---

## Container Runtime Validation

Final Stage 13 validation must include:

```bash
docker compose up
```

Then verify:

```text
GET /api/health
```

and:

```text
http://localhost:8501
```

---

## Product Smoke Test

With valid Provider configuration:

```text
Browser
↓
Streamlit Container
↓
FastAPI Container
↓
Agent Runtime
↓
DeepSeek
↓
Matching
↓
SQLite
↓
Recommendation UI
```

must work.

This live Provider test is manual and must not become blocking CI.

---

# 17. CI Strategy

Blocking CI should remain:

- offline;
- deterministic;
- secret-free.

Required existing gate:

```bash
python -m pytest -q
```

Possible Stage 13 additions:

```text
docker compose config
docker build / docker compose build
```

CI must not require:

```text
DEEPSEEK_API_KEY
```

---

# 18. Security Requirements

Never commit:

```text
.env
real API keys
tokens
credentials
local secret files
```

Repository-safe configuration:

```text
.env.example
```

If `.gitignore` does not already protect `.env`, Agent B owns the minimal correction.

`.dockerignore` must prevent local secrets and unnecessary development files from entering Docker build contexts.

The Demo service should not receive Provider secrets unless repository reality proves they are required.

---

# 19. SQLite Persistence Requirements

SQLite remains the Stage 13 database.

Stage 13 must explicitly define:

- database file location;
- container path;
- persistence strategy;
- Docker volume or bind-mount behavior;
- behavior after container recreation.

If repository reality shows the current SQLite path cannot be safely/container-reproducibly managed:

1. Agent B documents the problem.
2. A minimal configuration change is proposed.
3. Project lead reviews it.
4. Agent A consumes the approved path contract.

Agent A must not independently modify database application logic.

---

# 20. Documentation Requirements

Stage 13 documentation must explain:

- prerequisites;
- `.env` setup;
- Docker build/start;
- Docker stop;
- Backend URL;
- Streamlit URL;
- SQLite persistence;
- Demo data expectations;
- DeepSeek configuration;
- CI behavior.

Documentation must match repository reality.

Do not document commands that were not actually validated.

---

# 21. Risks

## Risk 1 — Parallel Agents Use Different Assumptions

Mitigation:

Interface Freeze Gate before implementation.

---

## Risk 2 — Docker Networking Uses localhost Incorrectly

Mitigation:

Streamlit must use Docker service discovery through configured Backend URL.

---

## Risk 3 — Secrets Enter Git or Docker Image

Mitigation:

- `.env.example`;
- `.gitignore`;
- `.dockerignore`;
- review secret propagation.

---

## Risk 4 — SQLite Data Disappears

Mitigation:

Explicit persistence strategy and runtime verification.

---

## Risk 5 — CI Becomes Slow or Secret-dependent

Mitigation:

Keep blocking CI offline and minimal.

---

## Risk 6 — Documentation Drifts From Implementation

Mitigation:

Agent C finalizes documentation only after Configuration and Docker interfaces are frozen/integrated.

---

# 22. Acceptance Criteria

Stage 13 is complete when:

## Reproducibility

- [ ] A clean environment can build the application.
- [ ] No developer `.venv` is required inside Docker.
- [ ] Required configuration is documented.

## Docker

- [ ] Backend image builds.
- [ ] Demo image builds.
- [ ] `docker compose config` passes.
- [ ] `docker compose up` starts the full application.

## Networking

- [ ] Streamlit reaches FastAPI through Compose networking.
- [ ] Browser can access Streamlit on port 8501.
- [ ] Backend health endpoint works on port 8000.

## Configuration

- [ ] `.env.example` exists.
- [ ] Real secrets are not committed.
- [ ] Provider secrets are scoped appropriately.

## Database

- [ ] SQLite behavior is documented.
- [ ] Required persistence survives expected container recreation.

## Testing

- [ ] Full Python regression passes.
- [ ] Docker validation passes.
- [ ] Manual live smoke test passes.

## CI

- [ ] Existing pytest CI remains passing.
- [ ] Approved Docker validation runs in CI.

## Collaboration

- [ ] Three independent worktrees are used.
- [ ] Three architecture reports are reviewed.
- [ ] Interface contract is frozen before implementation.
- [ ] Independent PRs are produced.
- [ ] Merge order is respected.
- [ ] Final integration review reports no blocking issue.

---

# 23. Final Definition of Done

Stage 13 is formally complete only when:

```text
Planning                  PASS
Multi-Agent Workflow      PASS
Configuration             PASS
Docker Backend            PASS
Docker Demo               PASS
Docker Compose            PASS
SQLite Persistence        PASS
CI                        PASS
Documentation             PASS
Full Regression           PASS
Runtime Smoke             PASS
Integration Review        PASS
PR / Merge                PASS
Stage Archive             PASS
```

Stage 13 must improve deployment reproducibility without changing InternScout Agent's existing Agent, Matching, or product behavior.