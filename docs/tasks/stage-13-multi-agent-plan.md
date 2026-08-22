# Stage 13 Multi-Agent Development Plan

## 1. Purpose

Stage 13 introduces a simulated team-development workflow for InternScout Agent.

The goal is not only to complete Docker and deployment-related engineering work, but also to practice a development model closer to a real engineering team:

- Multiple independent implementation tasks.
- Independent Git branches.
- Independent Codex contexts.
- Pull Request based integration.
- CI validation.
- Final integration review.

Stage 13 therefore has two parallel objectives:

1. Improve project reproducibility and deployment readiness.
2. Practice multi-agent engineering collaboration.

---

## 2. Stage 13 Main Goal

Stage 13 focuses on:

> Deployment & Reproducibility

The final target is that a new developer can clone the repository, configure required environment variables, and start the complete application with a reproducible workflow.

Target experience:

```text
git clone

↓

configure .env

↓

docker compose up

↓

FastAPI Backend

+

Streamlit Demo

↓

InternScout Agent available locally
```

The target architecture is:
```text
                 User
                  |
                  v
           Streamlit Demo
              :8501
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
        Matching / Database
                  |
                  v
             SQLite

                  |
                  v

             DeepSeek API
```

## 3. Development Model

Stage 13 will use a multi-agent simulated team workflow.
The main repository remains the integration workspace:
`D:\AI-Project\internscout-agent`
The main repository should normally remain on:
`main`
Independent implementation agents work in separate Git worktrees.
Each worktree has:

- its own directory;
- its own feature branch;
- its own Codex conversation;
- its own file ownership boundary.
General model:
```text
                         main
                          |
          +---------------+---------------+
          |               |               |
          v               v               v
      Agent A           Agent B         Agent C
      Docker            Config          CI + Docs

          \               |               /
           \              |              /
            +-------------+-------------+
                          |
                          v
                   Integration Review
                          |
                          v
                         main
```

## 4. Team Roles

Stage 13 uses three implementation agents and one final review role.

### Agent A — Containerization Engineer

#### Mission

Containerize the FastAPI backend and Streamlit demo and define the Docker Compose topology.

#### Primary responsibilities

Agent A owns:

- `Dockerfile.backend`
- `Dockerfile.demo`
- `docker-compose.yml`
- `.dockerignore`

Possible additional Docker-specific files may be added only if clearly necessary.

#### Expected work

Agent A should:

- inspect current FastAPI startup requirements;
- inspect current Streamlit startup requirements;
- build reproducible Python 3.12 images;
- expose required ports;
- define backend/demo service networking;
- ensure Streamlit calls the backend through Docker service discovery;
- define SQLite persistence strategy;
- define health checks where appropriate;
- keep image design minimal.
#### Architecture constraints

Agent A must not:

- modify Agent Runtime behavior;
- modify Matching logic;
- modify Tool behavior;
- add PostgreSQL, Redis, Kubernetes, or unrelated infrastructure;
- embed real API keys into images;
- duplicate application logic.
#### Acceptance criteria

Agent A is complete when:

- backend image builds successfully;
- demo image builds successfully;
- Docker Compose defines both services;
- backend and demo can communicate through the Compose network;
- no real secret is committed;
- Docker files pass review.
### Agent B — Configuration & Environment Engineer

#### Mission

Define reproducible configuration and environment-variable handling for local and container execution.

#### Primary responsibilities

Agent B owns:

- `.env.example`

and configuration-related documentation or minimal configuration code only when necessary.

#### Expected work

Agent B should identify and document required configuration such as:

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`
- `INTERNSCOUT_API_BASE_URL`
- `INTERNSCOUT_API_TIMEOUT_SECONDS`

Agent B should ensure the repository clearly distinguishes:

developer-local configuration

vs

container configuration

vs

secret values

#### Configuration principles

Real secrets must never appear in:

- source code;
- README examples;
- Dockerfiles;
- docker-compose.yml;
- committed .env files.
Only safe placeholders should appear in:

`.env.example`

#### Architecture constraints

Agent B must not:

- redesign the Provider layer;
- add a new settings framework without strong justification;
- introduce unrelated configuration libraries;
- change Agent Runtime behavior.
#### Acceptance criteria

Agent B is complete when:

- .env.example exists;
- required variables are documented;
- secret handling is clear;
- local and Compose configuration expectations are consistent;
- no secrets are committed.
### Agent C — CI & Deployment Documentation Engineer

#### Mission

Extend engineering validation for containerized execution and document the deployment workflow.

#### Primary responsibilities

Agent C owns:

- `.github/workflows/ci.yml`
- `README.md`
- `docs/deployment.md`

or an equivalent deployment documentation path approved during implementation.

#### CI responsibilities

Existing CI must continue to run:

```text
python -m pytest -q
```

Agent C may add container validation such as:

```text
docker build
```

or:

```text
docker compose config
```

provided the CI remains:

- deterministic;
- offline with respect to DeepSeek;
- free of real secrets;
- reasonably fast.
#### Documentation responsibilities

Deployment documentation should explain:

1. Clone repository.
2. Create environment configuration.
3. Start services.
4. Access FastAPI.
5. Access Streamlit Demo.
6. Stop containers.
7. Understand local SQLite persistence.
#### Architecture constraints

Agent C must not:

- change application behavior;
- modify Agent Runtime;
- redesign Dockerfiles owned by Agent A;
- introduce deployment platforms such as Kubernetes without approval.
#### Acceptance criteria

Agent C is complete when:

- CI still passes;
- Docker validation is appropriately represented in CI;
- deployment instructions are reproducible;
- documentation matches actual Docker commands;
- no secrets appear in documentation.
## 5. Integration / Review Role
After implementation agents complete their tasks, a separate Review Agent or senior-review pass will evaluate the integrated Stage 13 result.

The Review Agent should not immediately rewrite implementation.

Its first responsibility is:

inspect, identify integration risks, and report findings.

### Integration Review Scope

The review should verify consistency across:

- `Dockerfiles`
- `docker-compose.yml`
- `.env.example`
- `CI`
- `README`
- `deployment docs`
- `application configuration`

The Review Agent must specifically check:
#### Networking
Does Streamlit use the correct Backend address inside Compose?
Example:
`http://backend:8000`
instead of:
`http://localhost:8000`
inside the Streamlit container.
#### Environment
Are:
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`
passed only to the Backend service where required?
Does the Demo avoid receiving secrets unnecessarily?
#### Ports
Expected external ports:
- FastAPI: `8000`

- Streamlit: `8501`
#### Database persistence
SQLite behavior must be explicit.
The review should determine:
- where the SQLite file lives inside the container;
- whether a Docker volume is used;
- what happens when containers are recreated.
#### Security

Verify:
- no real API key;
- no .env committed;
- no unnecessary secret exposure;
- .dockerignore excludes sensitive/local files.
#### Reproducibility

A clean user should be able to follow documented steps without relying on:
- the developer's .venv;
- Windows-only paths;
- hidden shell configuration;
- manually installed Python packages outside Docker.
## 6. Git Branch Design

Each implementation agent receives an independent branch.

Recommended branches:

- `feat/stage13-docker`
- `feat/stage13-config`
- `feat/stage13-ci-docs`

The integration repository remains:

`main`

Feature branches must start from the same Stage 13 baseline commit.

## 7. Git Worktree Design

Recommended local layout:

- `D:\AI-Project\internscout-agent`
- `D:\AI-Project\internscout-stage13-docker`
- `D:\AI-Project\internscout-stage13-config`
- `D:\AI-Project\internscout-stage13-ci-docs`
Mapping:

|  |  |
| --- | --- |
| `internscout-agent` | → `main`<br>
→ integration / manager workspace |
| `internscout-stage13-docker` | → `feat/stage13-docker`<br>
→ Agent A |
| `internscout-stage13-config` | → `feat/stage13-config`<br>
→ Agent B |
| `internscout-stage13-ci-docs` | → `feat/stage13-ci-docs`<br>
→ Agent C |

Agents must not switch branches inside another agent's worktree.

## 8. File Ownership Rules

To reduce merge conflicts, each agent has a primary ownership boundary.

| Area | Owner |
| --- | --- |
| Dockerfiles | Agent A |
| docker-compose.yml | Agent A |
| .dockerignore | Agent A |
| .env.example | Agent B |
| configuration contract | Agent B |
| GitHub Actions | Agent C |
| deployment docs | Agent C |
| README deployment section | Agent C |

If an agent believes another agent's owned file must change:

1. Do not silently modify it.
2. Report the required dependency.
3. Let the integration process resolve the change.
## 9. Dependency Relationships

The tasks are not fully independent.

The expected dependency graph is:
```text
Agent B
Configuration contract
      |
      v
Agent A
Docker / Compose
      |
      v
Agent C
CI + Deployment Docs
```

However, Agents may perform analysis in parallel.

Implementation should respect the following dependency rules:

`Agent B → Agent A`
Agent A needs to know:
- required Backend environment variables;
- Demo Backend URL variable;
- secret boundaries.
`Agent A → Agent C`
Agent C needs to know:
- actual image names;
- actual Compose service names;
- actual startup commands;
- actual ports.
Because of these dependencies, Stage 13 is:

> partially parallel

not:
> completely independent parallel development.

## 10. Recommended Execution Order

### Phase 0 — Planning

Complete:

- `stage-13-task.md`
- `stage-13-multi-agent-plan.md`

Freeze:
- goals;
- boundaries;
- branch names;
- ownership.

### Phase 1 — Worktree Setup

Create all worktrees from the same baseline.
Verify each worktree:

```text
git status
git branch --show-current
```

### Phase 2 — Parallel Architecture Analysis

Each Codex agent first performs read-only analysis.

No agent writes code immediately.

Outputs:

#### Agent A:

Containerization Design Report

#### Agent B:

Configuration Design Report

#### Agent C:

CI and Deployment Documentation Design Report

The project lead reviews the three reports.

### Phase 3 — Implementation
After architecture approval:

- Agent A → Docker implementation
- Agent B → configuration implementation
- Agent C → CI/docs implementation
Each agent:
- modifies only approved files;
- runs relevant tests/checks;
- commits independently;
- pushes its branch;
- opens a Pull Request.
## 11. PR Strategy

Recommended PRs:

### PR A:

Stage 13 Docker & Compose

### PR B:

Stage 13 Configuration

### PR C:

Stage 13 CI & Deployment Docs
Each PR should clearly include:
- scope;
- files;
- validation;
- non-goals;
- dependencies on other Stage 13 PRs.
## 12. Merge Order

Recommended merge order:
1. Configuration
2. Docker / Compose
3. CI / Documentation
Reason:
```text
configuration contract
        ↓
container configuration
        ↓
CI and documentation
```

After each merge:
```text
main
 ↓
sync remaining branches
 ↓
resolve integration differences
```
Do not assume all PRs created from the same baseline can be merged without revalidation.
## 13. Conflict Policy

Merge conflicts are not CI failures.
If two branches change the same lines:
`Git merge conflict`
must be manually resolved before CI can evaluate the integrated result.
CI validates:
`the merged code`
CI does not decide:
`which conflicting implementation should win`
The integration owner is responsible for conflict resolution.
## 14. Testing Strategy
Stage 13 must preserve the current application regression suite.
Current baseline:

```text
python -m pytest -q
```

567 passed
The authoritative Stage 13 final baseline may increase as tests are added.
### Application Regression

Before final merge:

```text
python -m pytest -q
```

must pass.

### Docker Validation

Expected checks include:

```text
docker compose config
```

and successful image builds.

Final runtime validation should include:

```text
docker compose up
```

followed by:

`GET /api/health`

and Streamlit Demo access.

### Manual Product Verification

Final Stage 13 smoke path:
```text
Browser
 ↓
Streamlit container
 ↓
FastAPI container
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
This requires valid Provider configuration and should not become a secret-dependent blocking CI test.
## 15. CI Strategy

PR CI should remain:

- offline
- deterministic
- secret-free

Blocking CI must not require:

`DEEPSEEK_API_KEY`

Possible Stage 13 CI validation:
```text
pytest
+
docker build
+
docker compose config
```

Live DeepSeek runtime verification remains manual.
## 16. Security Rules

The following must never be committed:

- real API keys
- `.env`
- credentials
- tokens
- local secret files

The repository should contain:

`.env.example`

only.
Docker configuration should pass secrets through environment variables.
## 17. Stage 13 Non-goals

Stage 13 explicitly does not include:
- Kubernetes.
- Terraform.
- Helm.
- PostgreSQL migration.
- Redis.
- Microservice decomposition.
- Cloud production deployment.
- RAG.
- Memory.
- Multi-Agent runtime architecture.
- Agent feature expansion.
The multi-agent concept in Stage 13 refers only to:
development workflow simulation

not:
InternScout Agent runtime architecture.

## 18. Learning Objectives

Stage 13 should teach:
### Git / Team Collaboration
- independent branches;
- worktrees;
- pull requests;
- ownership boundaries;
- merge dependencies;
- conflict resolution.
### Docker
- images;
- containers;
- Dockerfiles;
- Docker Compose;
- service networking;
- environment injection;
- volumes.
### CI
- clean-environment validation;
- container build checks;
- regression gates.
### Engineering Management
- task decomposition;
- parallel work;
- integration sequencing;
- technical review.
## 19. Success Criteria
Stage 13 multi-agent workflow is successful when:
- Three implementation worktrees are created.
- Each agent has a clear branch and ownership boundary.
- Each agent completes architecture analysis before implementation.
- Independent implementation commits are created.
- Pull Requests are reviewed independently.
- Integration order is respected.
- Full regression remains passing.
- Docker images build successfully.
- Docker Compose configuration validates.
- Full application starts through Docker Compose.
- Streamlit can reach FastAPI inside the Compose network.
- FastAPI can access persistent SQLite data.
- No secret is committed.
- Deployment documentation matches actual runtime behavior.
- Final integration review reports no blocking issue.
## 20. Final Expected Workflow

The Stage 13 development process should look like:
```text
                         Project Lead
                              |
                              v
                       Stage 13 Planning
                              |
                              v
                   Multi-Agent Task Contract
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
       Agent A             Agent B             Agent C
       Docker              Config              CI + Docs
          |                   |                   |
          v                   v                   v
       Branch A            Branch B            Branch C
          |                   |                   |
          v                   v                   v
        PR A                PR B                PR C
          \                   |                   /
           \                  |                  /
            +-----------------+-----------------+
                              |
                              v
                    Integration / Review Agent
                              |
                              v
                         Final Regression
                              |
                              v
                             main
```

Stage 13 is the first InternScout Agent stage to intentionally simulate a small engineering team's parallel development workflow.
