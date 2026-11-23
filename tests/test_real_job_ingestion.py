"""Acceptance checks for real imports, partial refreshes, and library reads."""

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.api.dependencies import _get_request_retriever
from app.api.routes.imports import get_oppo_batch_fetcher
from app.crawlers.contracts import CrawlBatch, CrawlFailure
from app.database import create_database_engine, create_session_factory, get_session, init_database
from app.database.job_query_adapter import RepositoryJobQueryAdapter
from app.database.repository import get_dataset_revision, list_jobs, upsert_job
from app.main import app
from app.rag.embedding import FakeEmbeddingProvider
from app.rag.runtime import RetrievalRuntime
from app.schemas.job import JobCreate
from app.workflows.real_job_ingestion import import_job_batch


def job(**overrides: object) -> JobCreate:
    values = dict(
        title="Python 后端实习生", company="示例公司", city="深圳",
        description="开发 Python 接口", source="oppo", source_job_id="role-1",
        source_url="https://career.oppo.com/official/oppo/recruitment/post/1",
        skills=["Python"], status="active",
    )
    values.update(overrides)
    return JobCreate(**values)


def manual_payload(**overrides: object) -> dict:
    values = dict(
        title="后端开发实习生", company="示例公司", city="深圳市",
        description="负责 API 开发，熟悉 Python。", source_url="https://example.com/jobs/1",
        skills=["python"],
    )
    values.update(overrides)
    return values


@pytest.fixture
def sessions(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'real-import.db').as_posix()}")
    init_database(engine)
    factory = create_session_factory(engine)
    yield engine, factory
    engine.dispose()


@pytest.fixture
def api_client(sessions, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    engine, factory = sessions
    previous_engine = getattr(app.state, "database_engine", None)
    previous_overrides = dict(app.dependency_overrides)
    app.state.database_engine = engine

    def test_session():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    for name in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "INTERNSCOUT_EMBEDDING_API_KEY", "INTERNSCOUT_EMBEDDING_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        if previous_engine is None:
            del app.state.database_engine
        else:
            app.state.database_engine = previous_engine


def test_manual_import_update_and_history_work_without_model(api_client: TestClient) -> None:
    first = api_client.post("/api/imports/manual", json={"jobs": [manual_payload()]})
    assert first.status_code == 200
    assert first.json()["created_count"] == 1
    first_id = first.json()["job_ids"][0]

    repeated = api_client.post("/api/imports/manual", json={"jobs": [manual_payload()]})
    assert repeated.json()["unchanged_count"] == 1
    changed = api_client.post("/api/imports/manual", json={"jobs": [manual_payload(description="新的岗位描述", status="closed")]})
    assert changed.json()["updated_count"] == 1
    assert changed.json()["job_ids"] == [first_id]

    result = api_client.get("/api/jobs", params={"source": "manual", "status": "closed"}).json()
    assert result["total"] == 1
    assert result["items"][0]["description"] == "新的岗位描述"
    assert result["items"][0]["last_checked_at"]
    assert api_client.get("/api/jobs", params={"status": "active"}).json()["total"] == 0
    assert api_client.get("/api/imports").json()[0]["id"] == changed.json()["id"]
    assert api_client.get(f"/api/imports/{first.json()['id']}").json()["created_count"] == 1
    assert api_client.get("/api/imports/99999").status_code == 404


@pytest.mark.parametrize("invalid", [
    {"source_url": "javascript:alert(1)"},
    {"source_url": "https://user:secret@example.com/job"},
    {"source": "oppo"},
    {"source_job_id": "x" * 201},
    {"description": "   "},
])
def test_invalid_manual_batch_is_rejected_before_any_write(api_client: TestClient, invalid: dict) -> None:
    response = api_client.post("/api/imports/manual", json={"jobs": [manual_payload(), manual_payload(**invalid)]})
    assert response.status_code == 422
    assert api_client.get("/api/jobs").json()["total"] == 0
    assert api_client.get("/api/imports").json() == []


def test_oppo_partial_refresh_keeps_success_and_reports_failure(api_client: TestClient) -> None:
    requests = []

    def fetch(request):
        requests.append(request)
        return CrawlBatch(jobs=[job()], failures=[CrawlFailure("2", "详情暂时不可用")], complete=False)

    app.dependency_overrides[get_oppo_batch_fetcher] = lambda: fetch
    response = api_client.post("/api/imports/oppo", json={"keyword": "Python", "max_pages": 1, "max_jobs": 3})
    assert response.status_code == 200
    data = response.json()
    assert (data["status"], data["created_count"], data["failed_count"], data["complete"]) == ("partial", 1, 1, False)
    assert requests[0].max_jobs == 3
    assert api_client.get("/api/jobs", params={"source": "oppo"}).json()["total"] == 1

    def fail(request):
        raise RuntimeError("secret upstream response should never reach clients")

    app.dependency_overrides[get_oppo_batch_fetcher] = lambda: fail
    failed = api_client.post("/api/imports/oppo", json={})
    assert failed.json()["status"] == "failed"
    assert "secret upstream" not in failed.text
    assert api_client.get("/api/jobs").json()["items"][0]["status"] == "active"


@pytest.mark.parametrize("payload", [{"max_jobs": 101}, {"max_pages": 0}, {"max_jobs": True}, {"url": "https://example.com"}])
def test_source_limits_cannot_be_bypassed(api_client: TestClient, payload: dict) -> None:
    def unexpected_call(request):
        pytest.fail("Invalid input must not contact the source")

    app.dependency_overrides[get_oppo_batch_fetcher] = lambda: unexpected_call
    assert api_client.post("/api/imports/oppo", json=payload).status_code == 422


def test_failed_item_does_not_rollback_other_items_or_close_missing_jobs(sessions, monkeypatch: pytest.MonkeyPatch) -> None:
    _, factory = sessions
    with factory() as session:
        existing = upsert_job(session, job(source_job_id="missing")).job
        real_upsert = upsert_job

        def sometimes_fail(session: Session, value: JobCreate):
            if value.source_job_id == "bad":
                raise ValueError("bad item")
            return real_upsert(session, value)

        monkeypatch.setattr("app.workflows.real_job_ingestion.upsert_job", sometimes_fail)
        run = import_job_batch(session, source="oppo", fetch=lambda: CrawlBatch(
            jobs=[job(source_job_id="new-1"), job(source_job_id="bad"), job(source_job_id="new-2")],
            failures=[], complete=True,
        ))
        assert (run.status, run.created_count, run.failed_count, run.complete) == ("partial", 2, 1, False)
        assert len(list_jobs(session)) == 3
        session.refresh(existing)
        assert existing.status == "active"


def test_external_update_refreshes_index_and_closed_jobs_leave_recommendations(sessions) -> None:
    _, factory = sessions
    runtime = RetrievalRuntime(embedding_provider=FakeEmbeddingProvider())
    with factory() as writer:
        saved = upsert_job(writer, job()).job
        saved_id = saved.id

    with factory() as reader:
        query = RepositoryJobQueryAdapter(reader)
        first = _get_request_retriever(runtime, query, get_dataset_revision(reader))
        assert first is not None

    with factory() as writer:
        upsert_job(writer, job())
    with factory() as reader:
        second = _get_request_retriever(runtime, RepositoryJobQueryAdapter(reader), get_dataset_revision(reader))
        assert second is first

    with factory() as writer:
        upsert_job(writer, job(status="closed"))
    with factory() as reader:
        query = RepositoryJobQueryAdapter(reader)
        assert query.search_jobs()[1] == 0
        assert query.get_job_by_id(saved_id).status == "closed"
        third = _get_request_retriever(runtime, query, get_dataset_revision(reader))
        assert third is not first
        assert third.search("Python", top_k=5) == []


def test_changed_dataset_never_falls_back_to_stale_semantic_evidence(sessions, monkeypatch: pytest.MonkeyPatch) -> None:
    _, factory = sessions
    runtime = RetrievalRuntime(embedding_provider=FakeEmbeddingProvider())
    with factory() as session:
        upsert_job(session, job())
        query = RepositoryJobQueryAdapter(session)
        original = _get_request_retriever(runtime, query, get_dataset_revision(session))
        assert original is not None
        upsert_job(session, job(status="closed"))

        def fail_rebuild(*args, **kwargs):
            raise RuntimeError("embedding unavailable")

        monkeypatch.setattr(runtime, "rebuild", fail_rebuild)
        assert _get_request_retriever(runtime, query, get_dataset_revision(session)) is None
        assert query.search_jobs()[1] == 0


def test_bounded_success_is_partial_without_inventing_failed_jobs(sessions) -> None:
    _, factory = sessions
    with factory() as session:
        run = import_job_batch(session, source="oppo", fetch=lambda: CrawlBatch(
            jobs=[job()], failures=[], complete=False, warnings=["已达到数量上限"],
        ))
        assert (run.status, run.created_count, run.failed_count) == ("partial", 1, 0)
        assert run.errors == []
        assert run.warnings == ["已达到数量上限"]
