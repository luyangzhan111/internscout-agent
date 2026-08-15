import json
from typing import Any

from openai import OpenAI

from app.agent.contracts import (
    FinalAnswerResponse,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolCallResponse,
)
from app.agent.model_client import ModelClient


class OpenAIModelClient(ModelClient):
    """Adapt the provider-neutral model contract to OpenAI Responses."""

    def __init__(
        self,
        model: str,
        client: Any | None = None,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model cannot be blank")

        self.model = model
        self._client = client if client is not None else OpenAI()

    def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        if request.tool_executions:
            raise ValueError(
                "OpenAIModelClient does not yet support tool execution history."
            )

        response = self._client.responses.create(
            model=self.model,
            input=request.user_message,
            tools=[self._map_tool(tool) for tool in request.tools],
            parallel_tool_calls=False,
        )
        return self._map_response(response)

    @staticmethod
    def _map_tool(tool: Any) -> dict[str, Any]:
        return {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }

    @staticmethod
    def _map_response(response: Any) -> ModelResponse:
        function_calls = [
            item
            for item in getattr(response, "output", [])
            if getattr(item, "type", None) == "function_call"
        ]

        if len(function_calls) > 1:
            raise ValueError(
                "OpenAI response contains multiple function calls; "
                "parallel tool calling is not supported."
            )

        if function_calls:
            answer = getattr(response, "output_text", None)
            if isinstance(answer, str) and answer.strip():
                raise ValueError(
                    "OpenAI response cannot contain both a function call and a "
                    "final answer."
                )

            call = function_calls[0]
            arguments = json.loads(call.arguments)
            if not isinstance(arguments, dict):
                raise ValueError(
                    "OpenAI function call arguments must be a JSON object."
                )

            return ToolCallResponse(
                tool_call=ToolCall(
                    call_id=call.call_id,
                    tool_name=call.name,
                    arguments=arguments,
                )
            )

        answer = getattr(response, "output_text", None)
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError(
                "OpenAI response did not contain a final answer or function call."
            )

        return FinalAnswerResponse(answer=answer)
