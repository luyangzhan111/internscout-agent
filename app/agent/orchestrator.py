from app.agent.contracts import (
    AgentResult,
    FinalAnswerResponse,
    ModelRequest,
    ToolCall,
    ToolCallResponse,
    ToolExecution,
    ToolResult,
)
from app.agent.exceptions import (
    AgentError,
    AgentMaxStepsExceeded,
)
from app.agent.model_client import ModelClient
from app.agent.state import AgentState
from app.agent.tools.registry import ToolRegistry


class AgentOrchestrator:
    """Coordinate model decisions, tool execution, and agent state."""

    def __init__(
        self,
        model_client: ModelClient,
        tool_registry: ToolRegistry,
        max_steps: int = 5,
    ) -> None:
        if max_steps < 1:
            raise ValueError(
                "max_steps must be greater than or equal to 1."
            )

        self._model_client = model_client
        self._tool_registry = tool_registry
        self._max_steps = max_steps

    def run(
        self,
        user_message: str,
    ) -> AgentResult:
        """Execute one bounded, stateless agent run."""

        normalized_message = self._normalize_user_message(
            user_message
        )

        state = AgentState(
            user_message=normalized_message
        )

        while True:
            if state.step_count >= self._max_steps:
                raise AgentMaxStepsExceeded(
                    (
                        "Agent exceeded the maximum "
                        f"step limit of {self._max_steps}."
                    )
                )

            request = self._build_model_request(
                state
            )

            response = self._model_client.generate(
                request
            )

            state.step_count += 1

            if isinstance(
                response,
                FinalAnswerResponse,
            ):
                state.final_answer = response.answer

                return self._build_result(
                    state
                )

            if isinstance(
                response,
                ToolCallResponse,
            ):
                execution = self._handle_tool_call(
                    response.tool_call
                )

                state.tool_executions.append(
                    execution
                )

                continue

            raise AgentError(
                "Unsupported model response."
            )

    @staticmethod
    def _normalize_user_message(
        user_message: str,
    ) -> str:
        """Trim surrounding whitespace and reject blank input."""

        normalized = user_message.strip()

        if not normalized:
            raise ValueError(
                "user_message cannot be blank."
            )

        return normalized

    def _build_model_request(
        self,
        state: AgentState,
    ) -> ModelRequest:
        """Build the model-facing snapshot for the next agent step."""

        return ModelRequest(
            user_message=state.user_message,
            tool_executions=state.tool_executions,
            tools=self._tool_registry.list_definitions(),
        )

    def _handle_tool_call(
        self,
        tool_call: ToolCall,
    ) -> ToolExecution:
        """
        Execute a registered tool or create a controlled observation
        when the model requests an unavailable tool.
        """

        try:
            tool = self._tool_registry.get(
                tool_call.tool_name
            )
        except KeyError:
            result = ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                error="Tool is not available.",
            )
        else:
            result = tool.execute(
                tool_call
            )

        return ToolExecution(
            call=tool_call,
            result=result,
        )

    @staticmethod
    def _build_result(
        state: AgentState,
    ) -> AgentResult:
        """Convert completed runtime state into the public result."""

        if state.final_answer is None:
            raise AgentError(
                "Agent finished without a final answer."
            )

        return AgentResult(
            answer=state.final_answer,
            tool_executions=state.tool_executions,
            steps=state.step_count,
        )