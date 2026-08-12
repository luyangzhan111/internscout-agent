from typing import Any

from app.agent.tools.base import BaseTool


class ToolRegistry:
    """Allowlist of tools that an agent is permitted to use."""

    def __init__(self) -> None:
        self._tools: dict[
            str,
            BaseTool[Any],
        ] = {}

    def register(
        self,
        tool: BaseTool[Any],
    ) -> None:
        """Register one tool by its unique name."""

        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered."
            )

        self._tools[tool.name] = tool

    def get(
        self,
        name: str,
    ) -> BaseTool[Any]:
        """Return a registered tool by name."""

        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(
                f"Tool '{name}' is not registered."
            ) from exc

    def list_tools(
        self,
    ) -> list[BaseTool[Any]]:
        """Return registered tools in registration order."""

        return list(
            self._tools.values()
        )