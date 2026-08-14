from app.agent.contracts import (
    ModelRequest,
    ModelResponse,
)
from app.agent.model_client import ModelClient


class FakeModelClient(ModelClient):
    """Deterministic model client used by agent tests."""

    def __init__(
        self,
        responses: list[ModelResponse],
    ) -> None:
        self._responses = [
            response.model_copy(
                deep=True
            )
            for response
            in responses
        ]
        self._next_response_index = 0
        self.requests: list[ModelRequest] = []

    def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        self.requests.append(
            request.model_copy(
                deep=True
            )
        )

        if (
            self._next_response_index
            >= len(self._responses)
        ):
            raise RuntimeError(
                "Fake model has no remaining responses."
            )

        response = self._responses[
            self._next_response_index
        ]

        self._next_response_index += 1

        return response.model_copy(
            deep=True
        )