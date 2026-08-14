class AgentError(RuntimeError):
    """Base exception for Agent Layer execution failures."""


class AgentMaxStepsExceeded(AgentError):
    """Raised when an agent run exhausts its model-step budget."""