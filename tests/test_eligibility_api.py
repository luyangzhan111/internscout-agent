"""Integration acceptance: current JD, exact evidence, bounded read-only checks."""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.database import create_database_engine, create_session_factory, get_session
from app.database.repository import get_dataset_revision
from app.main import app


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'eligibility.db').as_posix()}")
    factory = create_session_factory(engine)
    previous_engine = getattr(app.state, "database_engine", None)
    previous_overrides = dict(app.dependency_overrides)
    app.state.database_engine = engine

    def sessions():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    for name in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "INTERNSCOUT_EMBEDDING_API_KEY", "INTERNSCOUT_EMBEDDING_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        if previous_engine is None:
            del app.state.database_engine
        else:
            app.state.database_engine = previous_engine
        engine.dispose()


def import_job(client, **changes):
    job = {
        "title": "软件开发实习生", "company": "测试公司", "city": "北京、深圳",
        "description": "面向2027届毕业生。\n本科及以上学历。\n工作经验不限。\n至少实习6个月。",
        "source_url": "https://example.com/jobs/eligibility", "status": "active",
    }
    job.update(changes)
    result = client.post("/api/imports/manual", json={"jobs": [job]})
    assert result.status_code == 200, result.text
    return result.json()["job_ids"][0]


PROFILE = {
    "graduation_year": 2027, "degree": "bachelor", "degree_status": "completed",
    "work_experience_months": 0, "acceptable_cities": ["深圳市"], "internship_months": 6,
}


def evaluate(client, ids, profile=None):
    return client.post("/api/eligibility/evaluate", json={"job_ids": ids, "profile": PROFILE if profile is None else profile})


def assert_exact_evidence(result):
    for check in result["checks"]:
        for evidence in check["evidence"]:
            assert result["job"][evidence["field"]][evidence["start"]:evidence["end"]] == evidence["text"]


def test_five_conditions_read_only_without_model(api):
    client, factory = api
    job_id = import_job(client)
    jobs_before = client.get("/api/jobs").json()
    runs_before = client.get("/api/imports").json()
    with factory() as session:
        revision = get_dataset_revision(session)
    response = evaluate(client, [job_id])
    assert response.status_code == 200, response.text
    result = response.json()["items"][0]
    assert result["overall"] == "met"
    assert {item["dimension"] for item in result["checks"]} == {"graduation_year", "degree", "experience", "city", "internship_duration"}
    assert all(check["status"] == "met" and check["evidence"] for check in result["checks"])
    assert all(check["unknown_reason"] is None and check["next_step"] == "" for check in result["checks"])
    assert_exact_evidence(result)
    assert response.json()["assessed_at"].endswith(("Z", "+00:00"))
    assert client.get("/api/jobs").json() == jobs_before
    assert client.get("/api/imports").json() == runs_before
    with factory() as session:
        assert get_dataset_revision(session) == revision


def test_update_recomputes_decision_and_quotes(api):
    client, _ = api
    job_id = import_job(client)
    before = evaluate(client, [job_id]).json()["items"][0]
    assert import_job(client, description="仅限2026届毕业生。\n硕士及以上学历。\n至少2年工作经验。\n至少实习9个月。") == job_id
    after = evaluate(client, [job_id]).json()["items"][0]
    assert after["overall"] == "not_met"
    assert after["source_fingerprint"] != before["source_fingerprint"]
    assert {check["dimension"] for check in after["checks"] if check["status"] == "not_met"} == {"graduation_year", "degree", "experience", "internship_duration"}
    assert_exact_evidence(after)
    assert all("2027" not in evidence["text"] for check in after["checks"] for evidence in check["evidence"])
    assert all(check["unknown_reason"] is None and check["next_step"] == ""
               for check in after["checks"] if check["status"] != "unknown")


def test_unknown_missing_candidate_and_closed_status(api):
    client, _ = api
    job_id = import_job(client, description="负责开发和协作。")
    result = evaluate(client, [job_id], {}).json()["items"][0]
    assert result["overall"] == "unknown"
    assert all(check["status"] == "unknown" for check in result["checks"])
    assert import_job(client, status="closed") == job_id
    closed = evaluate(client, [job_id]).json()["items"][0]
    assert closed["overall"] == "not_met"
    assert closed["blocking_reasons"]


@pytest.mark.parametrize("description,city,profile,dimension,category,action", [
    ("负责开发与协作。", "深圳", {}, "degree", "source_unspecified", "招聘方"),
    ("硕士优先。", "深圳", {}, "degree", "source_unspecified", "招聘方"),
    ("本科及以上学历。", "深圳", {}, "degree", "candidate_missing", "补充"),
    ("本科在读。", "深圳", {"degree": "bachelor"}, "degree", "candidate_missing", "在读还是已取得"),
    ("本科及以上学历。", "深圳", {"degree": "bachelor", "degree_status": "enrolled"},
     "degree", "interpretation_uncertain", "招聘方"),
    ("实习最多6个月。", "深圳", {"internship_months": 12},
     "internship_duration", "interpretation_uncertain", "缩短"),
    ("工作地点北京。", "深圳", {}, "city", "requirements_conflict", "招聘方"),
])
def test_unknown_cause_and_next_step_are_serialized_without_changing_decisions(
    api, description, city, profile, dimension, category, action,
):
    client, _ = api
    job_id = import_job(client, description=description, city=city)
    response = evaluate(client, [job_id], profile)
    assert response.status_code == 200, response.text
    result = response.json()["items"][0]
    item = next(check for check in result["checks"] if check["dimension"] == dimension)
    assert item["status"] == result["overall"] == "unknown"
    assert item["unknown_reason"] == category
    assert action in item["next_step"]
    assert result["rules_version"] == "stage23-rules-v1"
    assert_exact_evidence(result)


def test_missing_ids_reject_entire_request_and_order_is_preserved(api):
    client, _ = api
    first = import_job(client)
    second = import_job(client, source_url="https://example.com/jobs/second", title="算法实习生")
    result = evaluate(client, [second, first]).json()
    assert [item["job"]["id"] for item in result["items"]] == [second, first]
    missing = evaluate(client, [first, 999999])
    assert missing.status_code == 404
    assert "999999" in missing.json()["detail"]
    assert "items" not in missing.json()


@pytest.mark.parametrize("profile", [
    {"graduation_year": True}, {"graduation_year": "2027"}, {"graduation_year": 1900},
    {"degree": "phd"}, {"degree_status": "maybe"}, {"work_experience_months": -1},
    {"work_experience_months": 0.5}, {"internship_months": 121},
    {"acceptable_cities": [1]}, {"acceptable_cities": ["  "]},
    {"acceptable_cities": ["x"] * 21}, {"resume": "unexpected personal data"},
])
def test_invalid_profile(api, profile):
    client, _ = api
    assert evaluate(client, [1], profile).status_code == 422


@pytest.mark.parametrize("ids", [[], [0], [-1], [True], ["1"], [1, 1], list(range(1, 52))])
def test_invalid_job_selection(api, ids):
    client, _ = api
    assert evaluate(client, ids).status_code == 422
