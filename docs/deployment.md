# InternScout Agent Deployment Runbook

## 1. Scope and non-goals

This runbook documents reproducible local execution for InternScout Agent:

```text
Streamlit Demo → FastAPI Backend → Agent Runtime → Tools / Matching / Optional Retrieval → SQLite
```

It covers direct Python development and Docker Compose local execution.

It does not describe public production deployment, cloud hosting, Kubernetes, Memory, a Multi-Agent runtime, parallel tool execution, persistent conversation, or real-time recruitment data. Retrieval is supported as an optional local capability when the Backend receives embedding configuration. The Stage 13 “multi-agent” wording refers to the development workflow only.

## 2. Prerequisites

For direct Python development:

- Python 3.12
- A virtual environment
- Dependencies from `requirements.txt`

For Docker Compose execution:

- Docker Engine or Docker Desktop
- Docker Compose plugin

The Docker path does not require the maintainer’s virtual environment or manually installed Python packages.

## 3. Environment configuration

Copy the safe template and edit the resulting `.env` file for Compose:

```powershell
Copy-Item .env.example .env
```

Required Backend variables for Agent queries:

```text
DEEPSEEK_API_KEY=your-real-key
DEEPSEEK_MODEL=your-model-name
```

Required Backend variables to enable semantic retrieval:

```text
INTERNSCOUT_EMBEDDING_API_KEY=your-embedding-key
INTERNSCOUT_EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

Optional embedding settings:

```text
INTERNSCOUT_EMBEDDING_MODEL=text-embedding-v4
INTERNSCOUT_EMBEDDING_DIMENSIONS=1024
```

Never commit `.env` or a real API key.

The supported configuration variables are:

| Variable | Purpose | Default or Compose value |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | Backend provider authentication | No default; required for Agent queries |
| `DEEPSEEK_MODEL` | Backend provider model | No default; required for Agent queries |
| `INTERNSCOUT_EMBEDDING_API_KEY` | Backend embedding provider authentication | No default; required to enable retrieval |
| `INTERNSCOUT_EMBEDDING_BASE_URL` | OpenAI-compatible embedding endpoint | No default; required to enable retrieval |
| `INTERNSCOUT_EMBEDDING_MODEL` | Embedding model name | `text-embedding-v4` |
| `INTERNSCOUT_EMBEDDING_DIMENSIONS` | Expected embedding vector size | `1024` |
| `INTERNSCOUT_DATABASE_URL` | SQLite URL for direct local Backend execution | `sqlite:///./internscout.db` |
| `INTERNSCOUT_API_BASE_URL` | Backend URL used by the Demo | Local: `http://127.0.0.1:8000`; Compose: `http://backend:8000` |
| `INTERNSCOUT_API_TIMEOUT_SECONDS` | Demo HTTP timeout | `60` |

Direct Python processes read environment variables but do not automatically load `.env`. Docker Compose reads `.env` for Compose interpolation. The current Compose file explicitly passes DeepSeek and embedding configuration to the Backend, sets the container database URL to `sqlite:////data/internscout.db`, and sets the container Demo URL to `http://backend:8000`. Provider secrets are not passed to the Demo.

## 4. Local Python development

Create the environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For a local Agent query, inject the provider variables into the current process environment. Then start the Backend:

```powershell
python -m uvicorn app.main:app --reload
```

In a second terminal, start the Demo:

```powershell
streamlit run demo/app.py
```

The local Demo calls `http://127.0.0.1:8000` by default. This mode runs the two processes separately and uses the local SQLite default unless `INTERNSCOUT_DATABASE_URL` is overridden. Retrieval is optional; set the two required embedding variables to enable it.

## 5. Docker Compose startup

From the repository root:

```powershell
docker compose config --quiet
docker compose up --build
```

Compose starts two services:

- `backend`: FastAPI on container port `8000`
- `demo`: Streamlit on container port `8501`

The Demo uses Docker service discovery and calls `http://backend:8000` inside the Compose network. It does not receive DeepSeek or embedding provider secrets.

## 6. Service URLs

With the default port mappings:

- Backend root: <http://127.0.0.1:8000>
- Backend health: <http://127.0.0.1:8000/api/health>
- FastAPI documentation: <http://127.0.0.1:8000/docs>
- Streamlit Demo: <http://127.0.0.1:8501>

The Demo depends on the Backend health check before Compose starts the Demo service.

## 7. Database initialization

FastAPI initializes missing database tables during application startup. No separate schema initialization command is required for the current SQLite design.

In Compose:

- Database URL: `sqlite:////data/internscout.db`
- Container directory: `/data`
- Named volume: `backend_data`

This creates the database schema on first startup, but it does not automatically insert job rows. The project does not currently use Alembic or another database migration system.

## 8. Loading Mock data

After the Backend is healthy, load the local sample jobs through the existing Mock-only endpoint:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/crawl
```

This populates local SQLite data from `MockJobCrawler`. It does not fetch live recruitment data and does not trigger the OPPO real-source crawler.

## 9. Provider configuration and retrieval lifecycle

`DEEPSEEK_API_KEY` and `DEEPSEEK_MODEL` are Backend configuration. They are required when using `POST /api/agent/query` or the Streamlit Agent Demo.

`INTERNSCOUT_EMBEDDING_API_KEY` and `INTERNSCOUT_EMBEDDING_BASE_URL` are also Backend-only configuration. They are required to enable semantic retrieval. The model and dimensions variables are optional and default to `text-embedding-v4` and `1024`.

If either required embedding variable is missing or invalid, the Backend still starts and exposes health/data endpoints. Retrieval is disabled and the Agent falls back to `search_jobs`, `get_job_detail`, and `match_jobs`. Embedding configuration is not required for FastAPI startup.

FastAPI constructs an optional `RetrievalRuntime` at startup without embedding all jobs. On an Agent request, a dirty or unready runtime collects the current database snapshot and rebuilds lazily. Successful `/api/crawl` ingestion only calls `mark_dirty()`; it does not perform embedding during crawl. A successful rebuild swaps in the new retriever. A failed refresh keeps the old retriever and leaves the runtime dirty; a failed initial rebuild leaves retrieval unavailable for that request.

Retrieval is exposed through the Agent tool `retrieve_job_knowledge`; the Streamlit Demo has no separate retrieval UI.

DeepSeek uses the Responses API with reasoning disabled for tool compatibility. If multiple function calls are returned, InternScout projects the provider-order first call, executes one tool, and lets the next model turn replan. Tool execution remains sequential.

Blocking CI does not require a DeepSeek key and must not call the live provider.

## 10. Shutdown and volume persistence

Stop the Compose services with:

```powershell
docker compose down
```

The named `backend_data` volume is preserved by ordinary `down`, so the SQLite file remains available after containers are recreated.

The following command removes the named volume and its persisted SQLite data:

```powershell
docker compose down -v
```

Use `down -v` only when intentionally resetting local data.

## 11. CI validation

GitHub Actions runs on pushes and pull requests targeting `main`.

The workflow contains:

1. A Python 3.12 job that installs `requirements.txt` and runs `python -m pytest -q`.
2. A Docker validation job that runs `docker compose config --quiet` and `docker compose build`.

The workflow validates the test suite, Compose syntax, and image build definitions. It does not run a public deployment, require production infrastructure, or perform a live DeepSeek request.

## 12. Troubleshooting

### Backend health check fails

Inspect Backend logs:

```powershell
docker compose logs backend
```

Check that port `8000` is available and that the Backend container reaches its startup health check.

### Demo cannot reach the Backend

Inside Compose, the Demo URL must be `http://backend:8000`, not `http://127.0.0.1:8000` or `http://localhost:8000`.

### Agent query returns provider unavailable

Check `DEEPSEEK_API_KEY` and `DEEPSEEK_MODEL` in `.env`, then recreate the Backend container:

```powershell
docker compose up --build
```

### No jobs appear in the Demo

A fresh SQLite volume has tables but no jobs. Call `POST /api/crawl` and retry the Demo request.

### Docker build cannot connect to the engine

Confirm that Docker Engine or Docker Desktop is running. A local engine availability failure is an environment issue and is separate from Compose file validation.

## 13. Known limitations

- SQLite is the only supported database and has no migration system.
- `/api/crawl` remains MockJobCrawler-specific.
- The default Demo data is local SQLite/Mock data, not real-time recruitment data.
- Agent runs are request-scoped and do not preserve cross-request conversation state.
- Tool calling remains sequential.
- `InMemoryVectorStore` is a process-local index and is not a persistent external vector database.
- Retrieval rebuild is lazy and retrieval remains optional when embedding configuration is absent.
- The controlled CI embedding fixture is not a general real-embedding quality benchmark.
- No public production deployment is provided.
