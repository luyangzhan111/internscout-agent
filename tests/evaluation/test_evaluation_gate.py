"""End-to-end offline regression gate for the formal evaluation dataset."""

from datetime import date, datetime

from app.agent.contracts import (
    FinalAnswerResponse,
    ModelResponse,
    ToolCall,
    ToolCallResponse,
)
from app.agent.tools.job_query import JobQueryPort
from app.schemas.job_response import JobRead
from evals.contracts import EvalCase
from evals.dataset import load_eval_cases
from evals.runner import EvaluationRunner
from evals.scorers import score_run
from tests.agent.fakes.fake_model_client import FakeModelClient


def _make_job(
    *,
    skills: list[str],
    city: str = "深圳",
) -> JobRead:
    return JobRead(
        id=1,
        title="Python 后端实习生",
        company="Offline Fixture Co.",
        city=city,
        salary="面议",
        description="负责后端实习项目开发。",
        skills=skills,
        source="offline-fixture",
        source_url="https://example.invalid/jobs/1",
        published_at=date(2024, 1, 1),
        created_at=datetime(2024, 1, 1, 0, 0, 0),
    )


class EvaluationGateJobQuery(JobQueryPort):
    """Case-scoped in-memory query port used by the formal gate."""

    def __init__(self, case_id: str) -> None:
        self._case_id = case_id

    def search_jobs(
        self,
        *,
        city: str | None = None,
        company: str | None = None,
        skill: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[JobRead], int]:
        del company, page

        if self._case_id == "search_jobs_empty_result":
            return [], 0

        if self._case_id == "match_jobs_partial_skill_evidence":
            return [
                _make_job(
                    skills=["Python", "FastAPI", "SQL"],
                )
            ], 1

        if self._case_id in {
            "match_jobs_python_shenzhen",
            "search_jobs_by_city_and_skill",
        }:
            if city is not None and city != "深圳":
                return [], 0
            if skill is not None and skill != "Python":
                return [], 0
            return [_make_job(skills=["Python"])], 1

        return [], 0

    def get_job_by_id(self, job_id: int) -> JobRead | None:
        if (
            self._case_id == "get_job_detail_existing_job"
            and job_id == 1
        ):
            return _make_job(skills=["Python"])
        return None


_FINAL_ANSWERS = {
    "search_jobs_by_city_and_skill": "已找到深圳 Python 实习岗位。",
    "search_jobs_empty_result": "没有找到匹配的岗位。",
    "get_job_detail_existing_job": "岗位 1 详细信息如下。",
    "get_job_detail_missing_job": "岗位 999999 不存在。",
    "match_jobs_python_shenzhen": "匹配到深圳的 Python 岗位。",
    "match_jobs_partial_skill_evidence": "Python 技能可以匹配这些岗位。",
    "search_jobs_invalid_page": "参数无效，无法执行查询。",
    "match_jobs_invalid_top_k": "参数无效，无法执行匹配。",
    "unknown_tool_observation": "工具不可用，无法执行。",
}


def _model_client_factory(case: EvalCase) -> FakeModelClient:
    expected_call = case.expected.tool_calls[0]
    tool_call = ToolCall(
        call_id=f"gate-{case.case_id}",
        tool_name=expected_call.tool_name,
        arguments=expected_call.arguments,
    )
    responses: list[ModelResponse] = [
        ToolCallResponse(tool_call=tool_call),
        FinalAnswerResponse(answer=_FINAL_ANSWERS[case.case_id]),
    ]
    return FakeModelClient(responses=responses)


def test_formal_dataset_runner_scorer_gate_passes() -> None:
    cases = load_eval_cases()
    assert len(cases) == 9

    runner = EvaluationRunner(
        model_client_factory=_model_client_factory,
        job_query_factory=lambda case: EvaluationGateJobQuery(case.case_id),
    )
    run = runner.run()
    score = score_run(cases, run)

    if not score.passed:
        failures = [
            {
                "case_id": case_score.case_id,
                "failure_reasons": case_score.failure_reasons,
            }
            for case_score in score.case_scores
            if not case_score.passed
        ]
        raise AssertionError(
            "Deterministic evaluation gate failed: "
            f"failed_case_ids={score.failed_case_ids}, "
            f"missing_case_ids={score.missing_case_ids}, "
            f"unexpected_case_ids={score.unexpected_case_ids}, "
            f"failures={failures}"
        )

    assert score.total_cases == 9
    assert score.passed_cases == 9
    assert score.failed_cases == 0
    assert score.case_pass_rate == 1
    assert score.failed_case_ids == []
