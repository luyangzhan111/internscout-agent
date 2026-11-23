"""Exercise the no-key quickstart through the backend and UI data contracts."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.database import create_database_engine, create_session_factory
from app.database import session as database_session
from app.main import app
from demo.data_client import ImportRun, build_manual_import_payload, safe_http_url
from demo.recommendation_client import (
    AgentRecommendationResponse,
    build_recommendation_candidate,
)


def test_no_key_quickstart_from_empty_database(tmp_path, monkeypatch):
    for name in (
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "INTERNSCOUT_EMBEDDING_API_KEY",
        "INTERNSCOUT_EMBEDDING_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    def reject_external_request(self, request):
        pytest.fail(f"Quickstart attempted an outbound request: {request.method} {request.url}")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", reject_external_request)

    engine = create_database_engine(f"sqlite:///{(tmp_path / 'quickstart.db').as_posix()}")
    monkeypatch.setattr(app.state, "database_engine", engine, raising=False)
    monkeypatch.setattr(database_session, "SessionLocal", create_session_factory(engine))
    monkeypatch.setattr(app.state, "retrieval_runtime", None, raising=False)

    source_url = "https://jobs.fixture.test/job/python-intern"
    description = "负责使用 Python 开发后端服务。\n本科及以上学历；至少实习3个月。"
    payload = build_manual_import_payload(
        title="Python 后端开发实习生",
        company="测试公司",
        city="深圳",
        description=description,
        source_url=source_url,
    )
    candidate = build_recommendation_candidate(
        skills_text="Python",
        target_directions=["backend"],
        degree="master",
        internship_months="4",
        city_mode="selected",
        cities_text="深圳",
    )

    try:
        with TestClient(app) as client:
            assert client.get("/api/health").raise_for_status().json()["database"] == "ok"
            assert client.get("/api/jobs").raise_for_status().json()["total"] == 0

            imported = client.post("/api/imports/manual", json=payload).raise_for_status()
            run = ImportRun.model_validate(imported.json())
            assert run.status == "succeeded"
            assert run.created_count == 1

            response = client.post("/api/agent/recommend", json={
                "candidate": candidate,
                "limit": 5,
                "explain_with_model": False,
            }).raise_for_status()
            result = AgentRecommendationResponse.model_validate(response.json())
            assert result.explanation_status == "disabled"
            assert result.counts.returned == 1
            card = result.recommendations[0]
            assert [card.job.id] == run.job_ids
            assert card.job.status == "unknown"
            assert safe_http_url(card.job.source_url) == source_url
            assert card.matched_skills == ["Python"]

            duration = next(
                check for check in card.eligibility.checks if check.dimension == "internship_duration"
            )
            assert duration.status == "met"
            assert any(
                quote.field == "description"
                and quote.text == description[quote.start:quote.end]
                and "至少实习3个月" in quote.text
                for quote in duration.evidence
            )
    finally:
        engine.dispose()
