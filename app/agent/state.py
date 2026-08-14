from dataclasses import dataclass, field

from app.agent.contracts import ToolExecution


@dataclass
class AgentState:
    """Mutable runtime state for one agent execution."""

    user_message: str
    step_count: int = 0
    tool_executions: list[ToolExecution] = field(default_factory=list)
    final_answer: str | None = None