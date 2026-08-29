"""Blocking offline gate for the formal direct retrieval evaluation."""

from app.rag.retriever import JobKnowledgeRetriever
from evals.retrieval_contracts import RetrievalEvaluationScore
from evals.retrieval_dataset import load_retrieval_cases
from evals.retrieval_runner import RetrievalEvaluationRunner
from evals.retrieval_scorers import score_retrieval_run
from tests.evaluation.retrieval_fixtures import build_controlled_retriever


_EXPECTED_CASE_IDS = (
    "retrieval_ai_rag",
    "retrieval_backend_api",
    "retrieval_automated_testing",
    "retrieval_data_crawling",
    "retrieval_devops",
    "retrieval_functional_testing",
)


def _diagnostic_message(score: RetrievalEvaluationScore) -> str:
    """Render case and alignment details when the blocking gate fails."""

    failed_case_scores = [
        {
            "case_id": case_score.case_id,
            "failed_metrics": [
                {
                    "name": metric.name,
                    "reason": metric.reason,
                }
                for metric in case_score.metrics
                if not metric.passed
            ],
        }
        for case_score in score.case_scores
        if not case_score.passed
    ]
    return (
        "Direct retrieval evaluation gate failed: "
        f"failed_case_ids={score.failed_case_ids}, "
        f"missing_case_ids={score.missing_case_ids}, "
        f"unexpected_case_ids={score.unexpected_case_ids}, "
        f"alignment_errors={score.alignment_errors}, "
        f"failed_metrics={failed_case_scores}"
    )


def test_formal_direct_retrieval_evaluation_gate_passes() -> None:
    """Run the authoritative six-case path through production retrieval."""

    cases = load_retrieval_cases()
    assert [case.case_id for case in cases] == list(_EXPECTED_CASE_IDS)
    assert len(cases) == 6

    retriever = build_controlled_retriever()
    assert isinstance(retriever, JobKnowledgeRetriever)

    runner = RetrievalEvaluationRunner(retriever)
    run = runner.run(cases)
    score = score_retrieval_run(cases, run)

    if score.status != "PASS":
        raise AssertionError(_diagnostic_message(score))

    assert len(run.case_results) == 6
    assert run.completed_count == 6
    assert run.failed_count == 0
    assert score.total_cases == 6
    assert score.passed_cases == 6
    assert score.failed_cases == 0
    assert score.case_pass_rate == 1.0
    assert score.hit_at_k_rate == 1.0
    assert score.top_1_hit_rate == 1.0
    assert score.failed_case_ids == []
    assert score.missing_case_ids == []
    assert score.unexpected_case_ids == []
    assert score.alignment_errors == []
