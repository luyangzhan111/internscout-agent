import json
import os
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


class DeepSeekModelClient(ModelClient):
    """Adapt the provider-neutral model contract to DeepSeek Responses."""

    def __init__(
        self,
        model: str,
        client: Any | None = None,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model cannot be blank")

        self.model = model
        if client is not None:
            self._client = client
        else:
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                raise ValueError(
                    "DEEPSEEK_API_KEY is required when no client is injected."
                )
            self._client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com",
            )

    def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        response = self._client.responses.create(
            model=self.model,
            input=self._map_input(request),
            tools=[self._map_tool(tool) for tool in request.tools],
            reasoning={"effort": "none"},
        )
        return self._map_response(response)

    @staticmethod
    def _map_input(request: ModelRequest) -> str | list[dict[str, Any]]:
        if not request.tool_executions:
            return request.user_message

        input_items: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": request.user_message,
            }
        ]

        for execution in request.tool_executions:
            input_items.append(
                {
                    "type": "function_call",
                    "call_id": execution.call.call_id,
                    "name": execution.call.tool_name,
                    "arguments": DeepSeekModelClient._serialize_json(
                        execution.call.arguments,
                        "Tool call arguments",
                    ),
                }
            )

            result = execution.result
            observation: dict[str, Any] = {
                "success": result.success,
                "tool_name": result.tool_name,
            }
            if result.success:
                observation["data"] = result.data
            else:
                observation["error"] = result.error

            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": result.call_id,
                    "output": DeepSeekModelClient._serialize_json(
                        observation,
                        "Tool result observation",
                    ),
                }
            )

        return input_items

    @staticmethod
    def _serialize_json(value: Any, label: str) -> str:
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{label} must be JSON serializable.") from exc

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
                "DeepSeek response contains multiple function calls; "
                "parallel tool calling is not supported."
            )

        if function_calls:
            output_items = getattr(response, "output", []) or []
            message_items = [
                item
                for item in output_items
                if getattr(item, "type", None) == "message"
            ]
            message_phases = {
                getattr(item, "phase", None)
                for item in message_items
            }
            if message_items and "final_answer" in message_phases:
                raise ValueError(
                    "DeepSeek response cannot contain both a function call and a "
                    "final answer."
                )

            if message_items and message_phases != {"commentary"}:
                raise ValueError(
                    "DeepSeek response contains a function call with an "
                    "unsupported message phase."
                )

            if not message_items:
                answer = getattr(response, "output_text", None)
                if isinstance(answer, str) and answer.strip():
                    raise ValueError(
                        "DeepSeek response cannot contain both a function call and "
                        "a final answer."
                    )

            call = function_calls[0]
            arguments = json.loads(call.arguments)
            if not isinstance(arguments, dict):
                raise ValueError(
                    "DeepSeek function call arguments must be a JSON object."
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
                "DeepSeek response did not contain a final answer or function call."
            )

        return FinalAnswerResponse(answer=answer)
