from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from google.genai import types

Handler = Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class Tool:
    """A function Gemini can call. `parameters` is a JSON schema for the handler's kwargs."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Handler
    # Stop the loop after this tool runs (e.g. place_call: the loop resumes when the call finishes).
    ends_turn: bool = False

    def declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            name=self.name,
            description=self.description,
            parameters_json_schema=self.parameters,
        )
