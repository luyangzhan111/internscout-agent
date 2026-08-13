from abc import ABC, abstractmethod

from app.agent.contracts import (
    ModelRequest,
    ModelResponse,
)


class ModelClient(ABC):
    """Provider-neutral interface used by the agent to request a decision."""

    @abstractmethod
    def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        """Generate the model's next agent decision."""