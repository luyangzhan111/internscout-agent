# Stage 12E Task — Basic Product Demo

## 1. Background

InternScout Agent has completed the core AI application engineering pipeline:

- Recruitment data ingestion.
- Data cleaning and normalization.
- Database persistence.
- FastAPI backend.
- Agent Runtime.
- Tool Calling.
- Candidate / Job Matching.
- Agent Evaluation Framework.
- GitHub Actions CI.

Current system capabilities are mainly demonstrated through:

- API endpoints.
- Automated tests.
- Evaluation framework.

However, the project currently lacks a lightweight interactive demo layer that allows external users or interviewers to quickly understand:

- What the Agent does.
- How users interact with the system.
- What recommendation results look like.

Stage 12E introduces a minimal product demonstration layer.

The goal is not to build a complete frontend product, but to provide a clear and runnable AI application demo.

---

# 2. Goals

## Goal 1 — Provide Interactive Demo Experience

Create a lightweight user interface where users can:

Input:

- Candidate skills.
- Preferred city.

Receive:

- Recommended jobs.
- Matching score.
- Matched skills.
- Missing skills.
- Agent explanation.

Example:

Input:

Skills:
Python, RAG
City:
Shenzhen

Output:

Recommended Job:
AI Product Intern
Match Score:
50
Matched Skills:
RAG
Missing Skills:
LLM
Reason:
...

---

## Goal 2 — Demonstrate Agent Application Architecture

The demo should clearly demonstrate the existing architecture:

User
↓
Demo UI
↓
FastAPI Backend
↓
Agent Runtime
↓
Tool Calling
↓
Matching Service
↓
Database

The demo layer should only provide interaction and visualization.

It must not duplicate Agent logic.

---

## Goal 3 — Improve Portfolio Presentation

The completed demo should improve:

- GitHub repository readability.
- Resume project presentation.
- Interview demonstration experience.

The project should allow a reviewer to understand the system within minutes.

---

# 3. Scope

## 3.1 Streamlit Demo Layer

Add:

demo/

Suggested structure:

demo/
├── app.py
└── README.md

Responsibilities:

- Provide user input interface.
- Send requests to backend API.
- Render Agent results.

The UI should remain simple.

No complex frontend framework is required.

---

## 3.2 Backend Integration

The demo should communicate with the existing FastAPI backend.

Preferred architecture:

Streamlit
↓
HTTP Request
↓
FastAPI API
↓
Agent Runtime

The demo should reuse existing API contracts whenever possible.

Do not bypass:

- API layer.
- Agent Runtime.
- Tool system.
- Matching service.

---

## 3.3 Result Presentation

The demo should display:

Required:

- Job title.
- Company.
- City.
- Matching score.
- Matched skills.
- Missing skills.
- Recommendation explanation.

Optional:

- Agent execution trace.
- Tool usage information.

Optional features must not complicate the core demo.

---

## 3.4 Documentation Update

Update README with:

- Demo introduction.
- Screenshot.
- Startup instructions.
- Example usage.

Goal:

A new visitor can understand how to run the demo quickly.

---

# 4. Non-goals

The following are explicitly excluded from Stage 12E.

## 4.1 No React / Vue Frontend

Reason:

The project target is:

- AI Application Engineer.
- Agent Engineer.

Frontend engineering is not the main objective.

---

## 4.2 No User Authentication

Do not implement:

- Login.
- Registration.
- User management.
- Permission system.

---

## 4.3 No New Agent Capability

Do not add:

- Multi-Agent.
- Memory system.
- Planning Agent.
- Autonomous workflow expansion.

---

## 4.4 No RAG Implementation

RAG remains a future enhancement stage.

Do not introduce:

- Vector database.
- Embedding pipeline.
- Document retrieval system.

---

## 4.5 No Deployment

Do not implement:

- Docker.
- Cloud deployment.
- Production hosting.

Deployment belongs to later stages.

---

# 5. Architecture Constraints

## Additional Architecture Decision

Stage 12E will reuse the existing Agent API whenever possible.

A new recommendation endpoint will not be introduced in the first implementation phase.

The Demo layer should consume structured response data exposed by the existing backend contract.

The purpose is to demonstrate existing Agent capabilities rather than redesign API architecture.

## 5.1 Preserve Agent Runtime

Do not modify:

app/agent/orchestrator.py
app/agent/model_client.py
app/agent/tools/*

The Agent Runtime architecture is considered stable.

---

## 5.2 Preserve Matching Logic

Do not modify:

app/matching/*

Matching behavior has already been validated.

---

## 5.3 Demo Must Not Duplicate Business Logic

The demo layer must not directly:

- Query database.
- Execute matching.
- Create tools.
- Create Agent runtime.

Incorrect:

Streamlit
↓
Database
↓
Matching Service

Correct:

Streamlit
↓
FastAPI
↓
Agent Runtime

---

# 6. Task Breakdown

## Stage 12E-1 — Demo Architecture Design

Objectives:

- Define demo directory structure.
- Confirm API integration method.
- Define displayed data format.

Deliverables:

- Architecture decision.
- Implementation plan.

---

## Stage 12E-2 — Streamlit Demo Implementation

Objectives:

Implement:

- User input components.
- Backend API request.
- Response parsing.
- Result rendering.

Acceptance:

User can complete:

Input → Request → Result display.

---

## Stage 12E-3 — Demo Testing

Add tests covering:

- Request formatting.
- Response parsing.
- Empty result handling.
- Backend unavailable handling.

The demo should fail gracefully.

---

## Stage 12E-4 — Documentation Integration

Update:

README.md

Add:

- Demo screenshot.
- Running instructions.
- Example workflow.

---

# 7. Testing Strategy

Testing should follow existing project standards.

## Unit Testing

Test:

- Demo request construction.
- Response parsing.
- Error handling.

---

## Integration Testing

Verify:

Demo
↓
FastAPI
↓
Agent API
↓
Agent Runtime

works correctly.

---

## Regression Testing

Before merge:

Run:

```bash
python -m pytest -q
Expected:
All existing tests remain passing.
Current baseline:
551 passed

# 8. Acceptance Criteria

Stage 12E is complete when:

---

## Functional

- [ ] Streamlit demo can start successfully.

Example:

```bash
streamlit run demo/app.py
- User can input skills.
- User can input preferred city.
- Demo can request backend API.
- Demo displays recommendation results.
- Demo displays matching explanation.
Architecture
- Demo does not bypass FastAPI.
- Agent Runtime remains unchanged.
- Matching logic remains unchanged.
- No duplicate business logic exists.
Engineering
- Tests are added.
- Existing regression suite passes.
- Documentation is updated.
9. Risks
Risk 1 — Demo Layer Becomes Too Large
Problem:
UI work may consume excessive development time.
Solution:
Keep Streamlit implementation minimal.
The demo should focus on:
- Input.
- API communication.
- Result visualization.
Do not build a full frontend application.
Risk 2 — Architecture Leakage
Problem:
Demo directly calling internal modules.
Example:
Streamlit

↓

AgentOrchestrator

↓

Database
This bypasses the backend architecture.
Solution:
Only communicate through FastAPI API.
Correct:
Streamlit

↓

FastAPI

↓

Agent Runtime
Risk 3 — Duplicate Business Logic
Problem:
Demo reimplements:
- Matching logic.
- Tool execution.
- Agent workflow.
Solution:
Reuse existing backend capabilities.
The demo should only:
- Collect user input.
- Send requests.
- Display responses.
Risk 4 — Scope Expansion
Problem:
Adding unrelated features during implementation.
Avoid:
- Authentication.
- RAG.
- Deployment.
- Multi-Agent.
- Complex frontend framework.
Stage 12E should remain a lightweight product demo layer.
10. Final Expected Result
After Stage 12E:
InternScout Agent becomes:
                 User

                  |

                  v

            Streamlit Demo

                  |

                  v

            FastAPI Backend

                  |

                  v

          Agent Runtime

                  |

        +---------+---------+

        |                   |

        v                   v

   Tool Calling       Matching Engine

                  |

                  v

             Job Database
The project will demonstrate:
- AI Application Architecture.
- Agent Engineering.
- Tool Calling.
- Evaluation.
- CI.
- Interactive Demo Experience.
Stage 12E Final Boundary
Stage 12E focuses on:
Productizing existing Agent capabilities without expanding system complexity.

The goal is not to create a large frontend application.
The goal is to make InternScout Agent:
- understandable,
- runnable,
- demonstrable,
- portfolio-ready.

