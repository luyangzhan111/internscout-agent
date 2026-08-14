from app.agent.exceptions import (
    AgentError,
    AgentMaxStepsExceeded,
)


def test_agent_max_steps_exceeded_is_agent_error() -> None:
    error = AgentMaxStepsExceeded(
        "step budget exhausted"
    )

    assert isinstance(
        error,
        AgentError,
    )
    assert str(error) == (
        "step budget exhausted"
    )