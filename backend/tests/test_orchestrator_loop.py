import asyncio
from types import SimpleNamespace

import pytest
from google.genai import types

from app.orchestrator.loop import OrchestratorError, run_tool_loop
from app.tools.base import Tool
from app.tools.fake import check_availability_tool


def model_says(*parts: types.Part) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=list(parts)))]
    )


def call(name: str, **args) -> types.Part:
    return types.Part(function_call=types.FunctionCall(id=f"id-{name}", name=name, args=args))


class FakeClient:
    """Stands in for genai.Client: returns scripted responses and records each request."""

    def __init__(self, *responses: types.GenerateContentResponse):
        self.responses = list(responses)
        self.requests: list[list[types.Content]] = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, *, model, contents, config):
        self.requests.append(list(contents))
        return self.responses.pop(0)


def run(client, tools, max_steps=8):
    return asyncio.run(
        run_tool_loop(
            client,
            model="test-model",
            system_instruction="sys",
            contents=[types.Content(role="user", parts=[types.Part(text="table for 4 at 19:00?")])],
            tools=tools,
            max_steps=max_steps,
        )
    )


def test_model_tool_result_model():
    client = FakeClient(
        model_says(call("check_availability", restaurant="Dishoom", party_size=4, time="19:00")),
        model_says(types.Part(text="19:00 is full; 20:30 is free.")),
    )
    result = run(client, [check_availability_tool])

    assert result.text == "19:00 is full; 20:30 is free."
    assert [c.name for c in result.tool_calls] == ["check_availability"]
    assert result.tool_calls[0].result == {"available": False, "alternatives": ["17:30", "20:30"]}
    # Second request carries the model's call and our function response back to Gemini.
    second = client.requests[1]
    assert second[-2].role == "model"
    response = second[-1].parts[0].function_response
    assert (response.id, response.name) == ("id-check_availability", "check_availability")
    assert response.response["available"] is False


def test_tool_errors_are_returned_to_model():
    client = FakeClient(
        model_says(call("check_availability", restaurant="X"), call("nope")),
        model_says(types.Part(text="Sorry.")),
    )
    result = run(client, [check_availability_tool])

    assert "TypeError" in result.tool_calls[0].result["error"]
    assert result.tool_calls[1].result == {"error": "Unknown tool: nope"}
    assert result.text == "Sorry."


def test_ends_turn_tool_pauses_loop():
    async def place_call(phone: str) -> dict:
        return {"status": "dialing"}

    place_call_tool = Tool("place_call", "Call someone.", {"type": "object"}, place_call, ends_turn=True)
    client = FakeClient(model_says(call("place_call", phone="+440000")))
    result = run(client, [place_call_tool])

    assert result.paused_on == "place_call"
    assert result.text == ""
    assert result.history[-1].parts[0].function_response.response == {"status": "dialing"}


def test_max_steps():
    client = FakeClient(*[model_says(call("nope")) for _ in range(2)])
    with pytest.raises(OrchestratorError):
        run(client, [], max_steps=2)


def test_failed_ends_turn_tool_does_not_pause():
    async def place_call(contact_id: str) -> dict:
        return {"error": "Unknown contact_id"}

    place_call_tool = Tool("place_call", "Call someone.", {"type": "object"}, place_call, ends_turn=True)
    client = FakeClient(model_says(call("place_call", contact_id="x")), model_says(types.Part(text="Couldn't call.")))
    result = run(client, [place_call_tool])

    assert result.paused_on is None
    assert result.text == "Couldn't call."
