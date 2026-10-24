"""Phase 0 spike: run the Gemini tool loop once against the real API with the fake tool.

    cd backend
    .venv/Scripts/python -m scripts.gemini_hello "Can I get a table for 4 at Dishoom at 19:00?"
    .venv/Scripts/python -m scripts.gemini_hello --list-models
"""

import argparse
import asyncio

from google.genai import types

from app.config import get_settings
from app.orchestrator.loop import run_tool_loop
from app.services.gemini import get_client
from app.tools.fake import check_availability_tool

SYSTEM = (
    "You are Maya, a concierge agent. Use the check_availability tool before answering any booking "
    "question. If the time is unavailable, check the alternatives and recommend one. Be brief."
)


async def main(prompt: str) -> None:
    settings = get_settings()
    result = await run_tool_loop(
        get_client(),
        model=settings.gemini_model,
        system_instruction=SYSTEM,
        contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
        tools=[check_availability_tool],
    )
    print(f"model: {settings.gemini_model}")
    for i, call in enumerate(result.tool_calls, 1):
        print(f"[{i}] {call.name}({call.args}) -> {call.result}")
    print(f"\nanswer: {result.text}")


def list_models() -> None:
    for m in get_client().models.list():
        if "generateContent" in (m.supported_actions or []):
            print(m.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="?", default="Can I get a table for 4 at Dishoom at 19:00 tonight?")
    parser.add_argument("--list-models", action="store_true")
    args = parser.parse_args()
    if args.list_models:
        list_models()
    else:
        asyncio.run(main(args.prompt))
