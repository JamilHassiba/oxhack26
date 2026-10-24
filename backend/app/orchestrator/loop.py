"""Gemini orchestration loop. Owner: Alex.

Runs model -> tool call -> result -> model until Gemini answers in text.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

from app.tools.base import Tool

log = logging.getLogger(__name__)


class OrchestratorError(RuntimeError):
    pass


@dataclass
class ToolCallRecord:
    name: str
    args: dict[str, Any]
    result: dict[str, Any]


@dataclass
class LoopResult:
    text: str
    history: list[types.Content]
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    # Name of the ends_turn tool that paused the loop, if any. Resume by appending to `history`.
    paused_on: str | None = None


async def run_tool_loop(
    client: genai.Client,
    *,
    model: str,
    system_instruction: str,
    contents: list[types.Content],
    tools: list[Tool],
    max_steps: int = 8,
    temperature: float = 0.2,
) -> LoopResult:
    by_name = {t.name: t for t in tools}
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        tools=[types.Tool(function_declarations=[t.declaration() for t in tools])] if tools else None,
        # We run tools ourselves so every call can be logged and can pause the loop.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    history = list(contents)
    records: list[ToolCallRecord] = []

    for _ in range(max_steps):
        response = await client.aio.models.generate_content(model=model, contents=history, config=config)
        if not response.candidates or response.candidates[0].content is None:
            raise OrchestratorError(f"Gemini returned no content: {response.prompt_feedback}")
        # Append the model turn as-is so thought signatures are sent back on the next request.
        history.append(response.candidates[0].content)

        function_calls = response.function_calls or []
        if not function_calls:
            return LoopResult(text=response.text or "", history=history, tool_calls=records)

        parts: list[types.Part] = []
        paused_on = None
        for call in function_calls:
            args = dict(call.args or {})
            tool = by_name.get(call.name)
            result = await _execute(tool, call.name, args)
            log.info("tool %s(%s) -> %s", call.name, args, result)
            records.append(ToolCallRecord(name=call.name, args=args, result=result))
            parts.append(
                types.Part(function_response=types.FunctionResponse(id=call.id, name=call.name, response=result))
            )
            # A failed call (e.g. unknown contact) doesn't pause: Gemini sees the error and can retry.
            if tool is not None and tool.ends_turn and "error" not in result:
                paused_on = tool.name
        history.append(types.Content(role="user", parts=parts))

        if paused_on:
            return LoopResult(text="", history=history, tool_calls=records, paused_on=paused_on)

    raise OrchestratorError(f"Tool loop did not finish within {max_steps} steps")


async def _execute(tool: Tool | None, name: str, args: dict[str, Any]) -> dict[str, Any]:
    # Errors go back to the model as tool results so it can retry or explain, instead of crashing the task.
    if tool is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return await tool.handler(**args)
    except Exception as e:
        log.exception("tool %s failed", name)
        return {"error": f"{type(e).__name__}: {e}"}
